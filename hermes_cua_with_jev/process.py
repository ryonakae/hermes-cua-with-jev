"""Hermes boundary: scope secrets here; isolate third-party SDK dependencies."""
import json
import os
import subprocess
from pathlib import Path

from .config import load_settings


def invoke(request, **kwargs):
    from hermes_constants import get_hermes_home
    from agent.secret_scope import get_secret
    home = Path(get_hermes_home())
    root = Path(__file__).resolve().parents[1]
    python = root / '.venv/bin/python'
    if not python.is_file():
        return {'status':'blocked','reason':'plugin_venv_missing'}
    try:
        settings = load_settings(home)
        key = get_secret('TYPESAFE_API_KEY') if request.action == 'run' else ''
    except Exception:
        return {'status':'blocked','reason':'configuration_or_secret_scope_error'}
    if request.action == 'run' and not key:
        return {'status':'blocked','reason':'missing_typesafe_api_key'}
    payload = {'request':request.model_dump(), 'settings':settings.model_dump(), 'api_key':key,
               'runtime_dir':str(home / 'runtime/cua-with-jev'),
               'host_dir':str(Path.home() / '.cache/hermes-cua-with-jev')}
    env = {k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','LANG','TMPDIR','DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'}}
    env['HERMES_HOME'] = str(home)
    child = subprocess.Popen([str(python), '-m', 'hermes_cua_with_jev.worker'], cwd=root,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, env=env)
    try:
        stdout, _ = child.communicate(json.dumps(payload), timeout=request.timeout_seconds + 15)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        child.terminate()
        try:
            stdout, _ = child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
        return {'status':'interrupted','reason':'worker_terminated','mutation_may_have_occurred':True}
    try:
        if child.returncode != 0 or len(stdout) > 32000:
            raise ValueError
        result = json.loads(stdout)
        if not isinstance(result, dict) or result.get('status') not in {'completed','observed','step_done','need_help','blocked','timeout','interrupted'}:
            raise ValueError
        return result
    except (ValueError, TypeError):
        return {'status':'blocked','reason':'invalid_worker_result','mutation_may_have_occurred':True}
