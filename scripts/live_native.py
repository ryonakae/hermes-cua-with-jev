"""Explicit, opt-in native fixture smoke. API key is read from stdin."""
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

from hermes_cua_with_jev.driver import connect
from hermes_cua_with_jev.models import Request
from hermes_cua_with_jev.worker import run_request


async def main():
    key = sys.stdin.read()
    fixture = subprocess.Popen([sys.argv[1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        binary = shutil.which('cua-driver')
        async with connect(binary) as driver:
            for _ in range(20):
                windows = [w for w in (await driver.call('list_windows', {'pid':fixture.pid})).get('windows', []) if w.get('title') == 'Hermes Jev Test Fixture']
                if windows:
                    break
                await asyncio.sleep(.2)
            if not windows:
                raise RuntimeError('fixture_window_missing')
            window_id = windows[0]['window_id']
            state = await driver.call('get_window_state', {'pid':fixture.pid, 'window_id':window_id, 'include_screenshot':False})
            print(json.dumps({'fixture_elements':[{k:r.get(k) for k in ['role','label','value','in_web_content']} for r in state.get('elements', [])]}))
        request = Request.model_validate({'action':'run','target':{'kind':'native','pid':fixture.pid,'window_id':window_id},
            'goal':'Click Complete so Status becomes Done.',
            'controls':[{'role':'AXButton','label':'Complete','operation':'click'}],
            'expect':[{'role':'AXTextField','label':'Status','value_equals':'Done'}], 'max_steps':3})
        result = await run_request(request, {'driver_binary':binary,'driver_socket':None,'model':'jev-latest'},
            Path(sys.argv[2]), Path.home()/'.cache/hermes-cua-with-jev', key)
        print(json.dumps(result))
        return 0 if result['status'] == 'completed' else 1
    finally:
        fixture.terminate()
        fixture.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
