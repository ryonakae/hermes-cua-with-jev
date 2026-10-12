"""One isolated SDK/MCP runtime per public tool request; stdin carries the secret."""
import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from uuid import uuid4

from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy
from .driver import connect
from .jev import Jev
from .models import Request
from .runtime import DesktopLease, Busy, Uncertain
from .runner import execute


async def run_request(request, settings, runtime_dir, host_dir, api_key, connector=connect):
    result = None
    try:
        with DesktopLease(host_dir) as lease:
            if request.action in {'run','step'}:
                lease.require_settled()
            if request.action == 'run' and not api_key:
                return {'status':'blocked','reason':'missing_typesafe_api_key'}
            async with asyncio.timeout(request.timeout_seconds + 10):
                async with connector(settings['driver_binary'], settings.get('driver_socket')) as driver:
                    if request.action == 'run':
                        async with AsyncTypeSafeClient(api_key=api_key, base_url='https://api.typesafe.ai',
                                model=settings['model'], timeout=10, retry=RetryPolicy(max_retries=0)) as client:
                            result = await execute(request, driver, Jev(client), lease.before_mutation, lease.after_mutation)
                    else:
                        result = await execute(request, driver, None, lease.before_mutation, lease.after_mutation)
    except Busy:
        result = {'status':'blocked','reason':'desktop_busy'}
    except Uncertain:
        result = {'status':'blocked','reason':'previous_action_uncertain'}
    except (TimeoutError, asyncio.CancelledError):
        result = {'status':'interrupted','reason':'worker_deadline_or_cancel','mutation_may_have_occurred':True}
    except Exception:
        result = {'status':'blocked','reason':'connection_or_sdk_error','mutation_may_have_occurred':True}
    # No UI content, input values, tokens, or exceptions go into the receipt.
    safe = {k:v for k,v in result.items() if k not in {'elements','windows','receipt'}}
    runtime = Path(runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt = runtime / (uuid4().hex + '.json')
    fd = os.open(receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(safe, output)
    result['receipt'] = str(receipt)
    return result


async def main(payload):
    task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    return await run_request(Request.model_validate(payload['request']), payload['settings'],
                             payload['runtime_dir'], payload['host_dir'], payload.get('api_key',''))


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    try:
        payload = json.load(sys.stdin)
        result = asyncio.run(main(payload))
    except BaseException:
        result = {'status':'blocked','reason':'worker_failure','mutation_may_have_occurred':True}
    print(json.dumps(result, ensure_ascii=False))
