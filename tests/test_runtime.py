import asyncio
from pathlib import Path
import pytest


def test_host_lock_blocks_second_controller_and_releases(tmp_path):
    from hermes_cua_with_jev.runtime import DesktopLease, Busy
    with DesktopLease(tmp_path):
        with pytest.raises(Busy):
            with DesktopLease(tmp_path):
                pass
    with DesktopLease(tmp_path):
        pass


def test_uncertain_mutation_survives_process_lease(tmp_path):
    from hermes_cua_with_jev.runtime import DesktopLease, Uncertain
    with DesktopLease(tmp_path) as lease:
        lease.before_mutation()
    with DesktopLease(tmp_path) as lease:
        with pytest.raises(Uncertain):
            lease.require_settled()
        lease.after_mutation()
        lease.require_settled()


def test_worker_inspect_uses_profile_receipt_and_no_api_key(tmp_path):
    from hermes_cua_with_jev.worker import run_request
    from hermes_cua_with_jev.models import Request
    from contextlib import asynccontextmanager
    class Driver:
        async def call(self,name,args):
            assert name == 'get_window_state'
            return {'elements':[{'role':'AXButton','label':'Save','element_token':'not-returned'}]}
    @asynccontextmanager
    async def connection(*_):
        yield Driver()
    req = Request.model_validate({'action':'inspect','target':{'kind':'native','pid':10,'window_id':20}})
    result = asyncio.run(run_request(req, {'driver_binary':'test','driver_socket':None,'model':'jev-latest'},
                                    tmp_path/'profile', tmp_path/'host', '', connector=connection))
    assert result['status'] == 'observed'
    assert 'not-returned' not in str(result)
    receipt = Path(result['receipt'])
    assert receipt.is_relative_to(tmp_path/'profile')
    assert 'Save' not in receipt.read_text()
