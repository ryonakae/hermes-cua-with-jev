import importlib.util
import json
from pathlib import Path


def test_plugin_registers_one_tool_and_readonly_skill():
    from hermes_cua_with_jev.plugin import register

    class Context:
        def __init__(self):
            self.tools = []
            self.skills = []

        def register_tool(self, **kw):
            self.tools.append(kw)

        def register_skill(self, **kw):
            self.skills.append(kw)

    ctx = Context()
    register(ctx)
    assert [t['name'] for t in ctx.tools] == ['cua_jev']
    assert ctx.tools[0]['toolset'] == 'cua_with_jev'
    assert ctx.skills[0]['path'].is_file()
    assert set(ctx.tools[0]['schema']['parameters']['properties']['action']['enum']) == {'discover', 'inspect', 'run', 'step'}


def test_entrypoint_loads_as_plugin_package():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('jev_plugin_test', root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert callable(module.register)
