import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml


HERMES_AGENT_ROOT = Path("/Users/ryo.nakae/.hermes/hermes-agent")
if str(HERMES_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(HERMES_AGENT_ROOT))

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "hermes-cua-with-jev"
TOOL_NAME = "cua_jev"
TOOLSET_NAME = "cua_with_jev"


@pytest.fixture(autouse=True)
def isolated_hermes_runtime(monkeypatch):
    scratch = Path("/Users/ryo.nakae/.hermes/cache/scratch")
    root = scratch / f"test-loader-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    bundled = root / "empty-bundled-plugins"
    bundled.mkdir()
    launch_home = root / "launch-home"
    launch_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(launch_home))
    monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(bundled))
    monkeypatch.delenv("HERMES_ENABLE_PROJECT_PLUGINS", raising=False)

    from hermes_cli import plugins as plugins_mod

    plugins_mod._reset_plugin_managers_for_tests()
    try:
        yield root
    finally:
        plugins_mod._reset_plugin_managers_for_tests()
        shutil.rmtree(root, ignore_errors=True)


def _make_profile(root: Path, name: str) -> Path:
    home = root / f"profile-{name}"
    plugin = home / "plugins" / PLUGIN_NAME
    plugin.mkdir(parents=True)

    shutil.copy2(PLUGIN_ROOT / "__init__.py", plugin / "__init__.py")
    shutil.copy2(PLUGIN_ROOT / "plugin.yaml", plugin / "plugin.yaml")
    shutil.copytree(PLUGIN_ROOT / "hermes_cua_with_jev", plugin / "hermes_cua_with_jev")
    shutil.copytree(PLUGIN_ROOT / "skills", plugin / "skills")

    # process.invoke only checks this path before Popen; Popen is mocked below.
    fake_python = plugin / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("mock plugin runtime\n", encoding="utf-8")

    (home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": [PLUGIN_NAME]}}), encoding="utf-8"
    )
    (plugin / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": f"jev-model-{name}",
                "driver_binary": f"mock-driver-{name}",
                "driver_socket": f"/scratch/{name}.sock",
            }
        ),
        encoding="utf-8",
    )
    (home / ".env").write_text(
        f"TYPESAFE_API_KEY=mock-typesafe-key-{name}\n", encoding="utf-8"
    )
    return home


def _load_profile(home: Path):
    from gateway.run import _profile_runtime_scope
    from hermes_cli import plugins as plugins_mod

    with _profile_runtime_scope(home):
        manager = plugins_mod.get_plugin_manager()
        manager.discover_and_load()
    return manager


def _tool_names(definitions):
    return {item["function"]["name"] for item in definitions}


def test_real_loader_discovers_plugin_and_filters_enabled_disabled_toolset(isolated_hermes_runtime):
    home = _make_profile(isolated_hermes_runtime, "loader")
    manager = _load_profile(home)

    loaded = manager._plugins[PLUGIN_NAME]
    assert loaded.manifest.source == "user"
    assert loaded.enabled is True
    assert loaded.error is None
    assert loaded.tools_registered == [TOOL_NAME]

    from hermes_constants import hermes_home_key
    from model_tools import get_tool_definitions
    from tools.registry import registry

    scope = hermes_home_key(home)
    entry = registry.get_entry(TOOL_NAME, scope=scope)
    assert entry is not None
    assert entry.toolset == TOOLSET_NAME
    assert callable(entry.handler)

    from gateway.run import _profile_runtime_scope
    from toolsets import resolve_toolset

    with _profile_runtime_scope(home):
        assert resolve_toolset(TOOLSET_NAME) == [TOOL_NAME]
        enabled = get_tool_definitions(
            enabled_toolsets=[TOOLSET_NAME],
            quiet_mode=True,
            skip_tool_search_assembly=True,
        )
        disabled = get_tool_definitions(
            enabled_toolsets=[TOOLSET_NAME],
            disabled_toolsets=[TOOLSET_NAME],
            quiet_mode=True,
            skip_tool_search_assembly=True,
        )

    assert TOOL_NAME in _tool_names(enabled)
    assert TOOL_NAME not in _tool_names(disabled)


def test_profile_runtime_config_and_api_key_round_trip_a_b_a(
    isolated_hermes_runtime, monkeypatch
):
    home_a = _make_profile(isolated_hermes_runtime, "a")
    home_b = _make_profile(isolated_hermes_runtime, "b")

    manager_a = _load_profile(home_a)
    manager_b = _load_profile(home_b)
    module_a = manager_a._plugins[PLUGIN_NAME].module
    module_b = manager_b._plugins[PLUGIN_NAME].module
    assert module_a.__name__ != module_b.__name__

    calls = []

    class FakeProcess:
        returncode = 0

        def __init__(self, argv, cwd, env):
            self.argv = argv
            self.cwd = cwd
            self.env = env

        def communicate(self, input=None, timeout=None):
            calls.append(
                {
                    "payload": json.loads(input),
                    "timeout": timeout,
                    "argv": self.argv,
                    "cwd": self.cwd,
                    "env": self.env,
                }
            )
            return json.dumps({"status": "observed"}), ""

        def terminate(self):
            pass

        def kill(self):
            pass

    def fake_popen(*args, **kwargs):
        return FakeProcess(args[0], kwargs["cwd"], kwargs["env"])

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    request = {
        "action": "run",
        "target": {"kind": "native", "pid": 101, "window_id": 7},
        "goal": "mock bounded run",
        "controls": [{"role": "AXButton", "label": "Go", "operation": "click"}],
        "expect": [{"role": "AXStaticText", "label": "Done"}],
        "timeout_seconds": 1,
    }

    from gateway.run import _profile_runtime_scope
    from hermes_cli import plugins as plugins_mod
    from tools.registry import registry

    results = []
    for home, manager in ((home_a, manager_a), (home_b, manager_b), (home_a, manager_a)):
        with _profile_runtime_scope(home):
            assert plugins_mod.get_plugin_manager() is manager
            manager.discover_and_load()
            result = json.loads(
                registry.dispatch(TOOL_NAME, request, scope=manager.scope_key)
            )
            results.append(result)

    assert [result["status"] for result in results] == ["observed", "observed", "observed"]
    assert len(calls) == 3

    payloads = [call["payload"] for call in calls]
    assert [payload["settings"]["model"] for payload in payloads] == [
        "jev-model-a",
        "jev-model-b",
        "jev-model-a",
    ]
    assert [payload["settings"]["driver_binary"] for payload in payloads] == [
        "mock-driver-a",
        "mock-driver-b",
        "mock-driver-a",
    ]
    assert [payload["api_key"] for payload in payloads] == [
        "mock-typesafe-key-a",
        "mock-typesafe-key-b",
        "mock-typesafe-key-a",
    ]
    assert [payload["runtime_dir"] for payload in payloads] == [
        str(home_a / "runtime/cua-with-jev"),
        str(home_b / "runtime/cua-with-jev"),
        str(home_a / "runtime/cua-with-jev"),
    ]
    assert [call["env"]["HERMES_HOME"] for call in calls] == [
        str(home_a),
        str(home_b),
        str(home_a),
    ]

    # The child receives an explicit profile home but never an ambient API key.
    assert all("TYPESAFE_API_KEY" not in call.get("env", {}) for call in calls)
    assert all("TYPESAFE_API_KEY" not in payload for payload in payloads)
