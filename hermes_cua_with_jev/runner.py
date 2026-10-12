"""Goal loop over public Driver observations and locally grounded candidates."""
import asyncio
import time

from .driver import DriverError


def protected(row):
    role = str(row.get('role', '')).lower()
    kind = str(row.get('type', row.get('input_type', ''))).lower()
    return 'secure' in role or 'password' in role or kind == 'password' or row.get('protected') is True


def project(rows):
    return [{k: str(row.get(k, ''))[:200] for k in ('role', 'label', 'value')}
            for row in rows[:40] if not protected(row)]


def matches(rows, selector):
    return [r for r in rows if r.get('role') == selector.role and r.get('label') == selector.label and not protected(r)]


class Surface:
    def __init__(self, target, driver):
        self.target = target
        self.driver = driver
        self.native = {'pid': target.pid, 'window_id': target.window_id}
        self.browser = None

    async def bind(self):
        if self.target.kind == 'browser':
            bound = await self.driver.call('get_browser_state', self.native)
            tabs = [t for t in bound.get('tabs', []) if t.get('url') == self.target.tab_url]
            if len(tabs) != 1 or not bound.get('target_id') or not tabs[0].get('tab_id'):
                raise DriverError('ambiguous_browser_target')
            self.browser = {'target_id': bound['target_id'], 'tab_id': tabs[0]['tab_id']}

    async def observe(self):
        if self.browser is not None:
            data = await self.driver.call('get_browser_state', {**self.browser, 'snapshot_format':'semantic_v2'})
            if any(data.get(k) != v for k,v in self.browser.items()):
                raise DriverError('browser_target_mismatch')
            return [{**r, 'label': r.get('name', ''), 'handle': r.get('ref')} for r in data.get('refs', [])]
        data = await self.driver.call('get_window_state', {**self.native, 'include_screenshot':False, 'max_elements':200})
        if data.get('degraded_reason'):
            raise DriverError('degraded_native_target')
        return [{**r, 'handle':r.get('element_token')} for r in data.get('elements', [])]

    async def satisfied(self, rows, expected):
        if not expected:
            return False
        for want in expected:
            found = matches(rows, want)
            if len(found) != 1 or (want.value_equals is not None and found[0].get('value') != want.value_equals):
                return False
        if self.browser is not None:
            return True
        predicates = []
        for want in expected:
            e = {'selector':{'role':want.role, 'label_contains':want.label}, 'exists':True}
            if want.value_equals is not None:
                e['value_equals'] = want.value_equals
            predicates.append({'element': e})
        state = await self.driver.call('verify_state', {**self.native, 'expect':predicates,
            'include_screenshot':False, 'timeout_ms':0, 'stable_samples':1})
        return state.get('status') == 'satisfied'

    def candidates(self, rows, request):
        candidates = []
        for control in request.controls:
            found = matches(rows, control)
            if len(found) != 1:
                continue
            row = found[0]
            if not row.get('handle') or row.get('enabled') is False or row.get('in_web_content') is True:
                continue
            text = request.inputs.get(control.input_key) if control.input_key else None
            if control.operation == 'type' and row.get('value') == text:
                continue
            if self.browser is not None:
                args = {**self.browser, 'ref': row['handle']}
                tool = {'click':'browser_click', 'type':'browser_type'}[control.operation]
                if control.operation == 'type':
                    args.update(text=text, replace=True)
                else:
                    args['input_route'] = 'dom_event'
            else:
                args = {**self.native, 'element_token':row['handle'], 'delivery_mode':'background'}
                tool = {'click':'click', 'type':'type_text'}[control.operation]
                if control.operation == 'type':
                    args['text'] = text
            candidates.append({'id':f'c{len(candidates)}','operation':control.operation,
                'role':control.role,'label':control.label,'input':text,'tool':tool,'args':args})
        return candidates


async def execute(request, driver, chooser, before_mutation=None, after_mutation=None):
    started = time.monotonic()
    steps = 0
    attempts = 0

    def result(status, reason=None, **extra):
        data = {'status':status, 'steps':steps, 'attempted_steps':attempts,
                'mutation_may_have_occurred': attempts > 0,
                'elapsed_seconds':round(time.monotonic()-started, 3), **extra}
        if reason:
            data['reason'] = reason
        if chooser is not None:
            data['jev_usage'] = dict(chooser.usage)
            data['jev_model'] = getattr(chooser, 'model', None)
        return data

    async def run():
        nonlocal steps, attempts
        if request.action == 'discover':
            raw = await driver.call('list_windows', {})
            windows = raw.get('windows', [])
            return result('observed', windows=[{k:r.get(k) for k in ('pid','window_id','app_name')} for r in windows[:100]],
                          truncated=len(windows)>100)
        surface = Surface(request.target, driver)
        await surface.bind()
        rows = await surface.observe()
        if request.action == 'inspect':
            return result('observed', elements=project(rows), truncated=len(rows)>40)
        for _ in range(1 if request.action == 'step' else request.max_steps):
            if await surface.satisfied(rows, request.expect):
                return result('completed')
            # Native verification can replace the window snapshot, even on an unknown result.
            if surface.browser is None:
                rows = await surface.observe()
            candidates = surface.candidates(rows, request)
            if not candidates:
                return result('need_help', 'no_allowed_candidate')
            permitted = {(c.role,c.label) for c in request.controls} | {(e.role,e.label) for e in request.expect}
            observation = project([r for r in rows if (r.get('role'),r.get('label')) in permitted])
            options = [{k:v for k,v in c.items() if k not in {'args','tool'}} for c in candidates]
            choice = candidates[0]['id'] if request.action == 'step' else await chooser.choose(request.goal, observation, options)
            if choice == 'stop':
                return result('need_help', 'jev_abstained')
            candidate = next((c for c in candidates if c['id'] == choice), None)
            if candidate is None:
                return result('need_help', 'invalid_candidate')
            if before_mutation:
                before_mutation()
            attempts += 1
            await driver.call(candidate['tool'], candidate['args'])
            steps += 1
            after = await surface.observe()
            if await surface.satisfied(after, request.expect):
                if after_mutation:
                    after_mutation()
                return result('completed')
            # Compare the selected control, not unrelated clocks/spinners, before continuing.
            changed = [(r.get('role'),r.get('label'),r.get('value')) for r in after if (r.get('role'),r.get('label')) in permitted]
            previous = [(r.get('role'),r.get('label'),r.get('value')) for r in rows if (r.get('role'),r.get('label')) in permitted]
            if changed == previous:
                return result('need_help', 'effect_unverified')
            if after_mutation:
                after_mutation()
            rows = after
            if request.action == 'step':
                return result('step_done')
        return result('need_help', 'step_limit')

    try:
        async with asyncio.timeout(request.timeout_seconds):
            return await run()
    except TimeoutError:
        return result('timeout', 'time_limit')
    except asyncio.CancelledError:
        return result('interrupted', 'cancelled')
    except DriverError as exc:
        return result('blocked', str(exc))
    except Exception:
        return result('blocked', 'execution_error')
