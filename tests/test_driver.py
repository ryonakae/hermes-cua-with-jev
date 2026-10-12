import asyncio
from types import SimpleNamespace
import pytest

from hermes_cua_with_jev.driver import Driver, DriverError


class Session:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def call_tool(self, name, args):
        self.calls.append((name,args))
        return self.result


def driver_for(result):
    session = Session(result)
    schemas = {'click': {'type':'object', 'properties':{'pid':{'type':'integer'}, 'session':{'type':'string'}}, 'required':['pid'], 'additionalProperties':False}}
    return Driver(session, schemas, 'public-label'), session


def test_driver_injects_only_supported_session_and_keeps_payload_local():
    driver, session = driver_for(SimpleNamespace(isError=False, structuredContent={'effect':'confirmed'}))
    assert asyncio.run(driver.call('click', {'pid':10})) == {'effect':'confirmed'}
    assert session.calls == [('click', {'pid':10, 'session':'public-label'})]


@pytest.mark.parametrize('payload', [{'status':'refused','code':'approval_required'}, {'refusal':{'code':'denied'}}, {'error':{'code':'stale'}}])
def test_structured_refusal_is_not_success(payload):
    driver, _ = driver_for(SimpleNamespace(isError=False, structuredContent=payload))
    with pytest.raises(DriverError):
        asyncio.run(driver.call('click', {'pid':10}))


def test_driver_refuses_unadvertised_argument_before_call():
    driver, session = driver_for(SimpleNamespace(isError=False, structuredContent={}))
    with pytest.raises(DriverError, match='schema_mismatch'):
        asyncio.run(driver.call('click', {'pid':10, 'bypass':True}))
    assert session.calls == []
