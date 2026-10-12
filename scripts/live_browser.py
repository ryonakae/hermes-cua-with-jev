"""Opt-in isolated browser fixture, never an existing logged-in profile."""
import asyncio
import json
import logging
import shutil
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

from hermes_cua_with_jev.driver import connect, DriverError
from hermes_cua_with_jev.jev import Jev
from hermes_cua_with_jev.models import Request
from hermes_cua_with_jev.runner import execute
from hermes_cua_with_jev.runtime import DesktopLease


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


async def main():
    key = sys.stdin.read()
    server = ThreadingHTTPServer(('127.0.0.1',0), partial(Handler,directory=str(Path(__file__).resolve().parents[1]/'tests/fixtures')))
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with DesktopLease(Path.home()/'.cache/hermes-cua-with-jev') as lease:
            lease.require_settled()
            async with connect(shutil.which('cua-driver')) as driver:
                prepared = await driver.call('browser_prepare', {'allow_launch':True,'profile':{'mode':'isolated_new'}})
                pid = prepared['prepared_pid']
                windows = []
                for _ in range(20):
                    found = (await driver.call('list_windows', {'pid':pid})).get('windows', [])
                    windows = [w for w in found if w.get('is_on_screen') and w.get('title') == 'about:blank']
                    if len(windows) == 1:
                        break
                    await asyncio.sleep(.2)
                if len(windows) != 1:
                    print(json.dumps({'status':'blocked','reason':'fixture_window_ambiguous','window_count':len(windows), 'prepared_fields':list(prepared), 'owned_window_details':[{k:w.get(k) for k in ('window_id','title','bounds','is_on_screen')} for w in windows], 'ownership':prepared.get('endpoint_ownership')}))
                    return 1
                window_id = windows[0]['window_id']
                bound = await driver.call('get_browser_state', {'pid':pid,'window_id':window_id})
                tab = bound['tabs'][0]['tab_id']
                url = f'http://127.0.0.1:{server.server_port}/browser.html'
                await driver.call('browser_navigate', {'target_id':bound['target_id'],'tab_id':tab,'url':url})
                request = Request.model_validate({'action':'run','target':{'kind':'browser','pid':pid,'window_id':window_id,'tab_url':url},
                    'goal':'Click Complete so Status becomes Done.', 'controls':[{'role':'button','label':'Complete','operation':'click'}],
                    'expect':[{'role':'textbox','label':'Status','value_equals':'Done'}], 'max_steps':3})
                async with AsyncTypeSafeClient(api_key=key,base_url='https://api.typesafe.ai',model='jev-latest',retry=RetryPolicy(max_retries=0)) as client:
                    result = await execute(request,driver,Jev(client),lease.before_mutation,lease.after_mutation)
                print(json.dumps(result))
                return 0 if result['status'] == 'completed' else 1
    except DriverError as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)}))
        return 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    raise SystemExit(asyncio.run(main()))
