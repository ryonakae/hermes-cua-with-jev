import asyncio

from hermes_cua_with_jev.models import Request


def native_request(**changes):
    args = dict(action='run', target=dict(kind='native', pid=10, window_id=20),
                goal='Change the title', controls=[dict(role='AXTextField', label='Title', operation='type', input_key='title')],
                inputs={'title':'New title'}, expect=[dict(role='AXTextField', label='Title', value_equals='New title')])
    args.update(changes)
    return Request.model_validate(args)


class Driver:
    def __init__(self):
        self.calls = []
        self.value = 'Old title'
        self.stale = False
        self.noop = False

    async def call(self, name, args):
        self.calls.append((name,args))
        if name == 'verify_state':
            return {'status': 'satisfied' if self.value == 'New title' else 'unsatisfied'}
        if name == 'get_window_state':
            return {'snapshot_id':'s12345678','elements':[{'element_token':'opaque-current-token','role':'AXTextField','label':'Title','value':self.value}]}
        if name == 'type_text':
            if self.stale:
                from hermes_cua_with_jev.driver import DriverError
                raise DriverError('stale')
            if not self.noop:
                self.value = args['text']
            return {'effect':'unverifiable'}
        raise AssertionError(name)


class Chooser:
    def __init__(self, selected='c0'):
        self.selected = selected
        self.usage = {'input_tokens': 20, 'output_tokens': 1}
        self.calls = []

    async def choose(self, goal, observation, candidates):
        self.calls.append((goal,observation,candidates))
        return self.selected


def test_run_uses_bound_token_and_independent_verification():
    from hermes_cua_with_jev.runner import execute
    driver, chooser = Driver(), Chooser()
    result = asyncio.run(execute(native_request(), driver, chooser))
    assert result['status'] == 'completed'
    assert result['steps'] == 1
    mutations = [args for name,args in driver.calls if name == 'type_text']
    assert mutations == [{'pid':10,'window_id':20,'element_token':'opaque-current-token','text':'New title','delivery_mode':'background'}]
    assert driver.calls[-1][0] == 'verify_state'
    assert 'Old title' not in str(result)
    assert len(chooser.calls) == 1


def test_unknown_candidate_cannot_mutate():
    from hermes_cua_with_jev.runner import execute
    driver = Driver()
    result = asyncio.run(execute(native_request(), driver, Chooser('invented-id')))
    assert result['status'] == 'need_help'
    assert result['reason'] == 'invalid_candidate'
    assert not any(name == 'type_text' for name,_ in driver.calls)


def test_unverified_input_is_not_replayed():
    from hermes_cua_with_jev.runner import execute
    driver = Driver()
    driver.noop = True
    result = asyncio.run(execute(native_request(), driver, Chooser()))
    assert result['status'] == 'need_help'
    assert result['reason'] == 'effect_unverified'
    assert sum(name == 'type_text' for name,_ in driver.calls) == 1


def test_only_allowed_candidates_and_bounded_observation_reach_jev():
    from hermes_cua_with_jev.runner import execute
    chooser = Chooser()
    asyncio.run(execute(native_request(), Driver(), chooser))
    _, observation, candidates = chooser.calls[0]
    assert 'opaque-current-token' not in str(observation)
    assert 'args' not in candidates[0]
    assert candidates[0]['input'] == 'New title'


def test_stale_action_stops_without_replay():
    from hermes_cua_with_jev.runner import execute
    driver = Driver()
    driver.stale = True
    result = asyncio.run(execute(native_request(), driver, Chooser()))
    assert result['status'] == 'blocked'
    assert result['reason'] == 'stale'
    assert sum(name == 'type_text' for name,_ in driver.calls) == 1


def test_step_uses_same_surface_without_jev():
    from hermes_cua_with_jev.runner import execute
    result = asyncio.run(execute(native_request(action='step'), Driver(), None))
    assert result['status'] == 'completed'


def test_browser_uses_fresh_refs_and_exact_tab():
    from hermes_cua_with_jev.runner import execute
    class Browser:
        def __init__(self):
            self.value = 'Old title'
            self.calls = []
        async def call(self, name, args):
            self.calls.append((name,args))
            if name == 'get_browser_state' and 'pid' in args:
                return {'target_id':'target', 'tabs':[{'tab_id':'tab','url':'http://localhost/form'}]}
            if name == 'get_browser_state':
                return {'target_id':'target','tab_id':'tab','refs':[{'ref':'p1:1','role':'textbox','name':'Title','value':self.value}]}
            if name == 'browser_type':
                assert args == {'target_id':'target','tab_id':'tab','ref':'p1:1','text':'New title','replace':True}
                self.value = args['text']
                return {'effect':'unverifiable'}
            raise AssertionError(name)
    driver = Browser()
    req = native_request(target=dict(kind='browser',pid=10,window_id=20,tab_url='http://localhost/form'),
                         controls=[dict(role='textbox',label='Title',operation='type',input_key='title')],
                         expect=[dict(role='textbox',label='Title',value_equals='New title')])
    result = asyncio.run(execute(req,driver,Chooser()))
    assert result['status'] == 'completed'
    assert driver.calls[-1][0] == 'get_browser_state'
