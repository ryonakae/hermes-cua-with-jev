"""Public MCP adapter; no Hermes internal CUA imports."""
import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from jsonschema import validate, ValidationError
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class DriverError(Exception):
    """A safe local reason, never a raw server message or request body."""


class Driver:
    def __init__(self, session, schemas, label):
        self.session = session
        self.schemas = schemas
        self.label = label

    async def call(self, name, args):
        schema = self.schemas.get(name)
        if schema is None:
            raise DriverError('unsupported_tool')
        payload = dict(args)
        if 'session' in schema.get('properties', {}):
            payload['session'] = self.label
        try:
            validate(payload, schema)
        except ValidationError:
            raise DriverError('schema_mismatch') from None
        response = await self.session.call_tool(name, payload)
        if response.isError:
            raise DriverError('driver_error')
        data = response.structuredContent
        if data is None:
            for part in getattr(response, 'content', []):
                if getattr(part, 'type', None) == 'text':
                    try:
                        data = json.loads(part.text)
                    except (ValueError, TypeError):
                        continue
                    break
        if not isinstance(data, dict):
            raise DriverError('invalid_driver_response')
        if data.get('status') in {'refused', 'error', 'denied'} or data.get('refusal') or data.get('error') or data.get('success') is False:
            raise DriverError('driver_refused')
        return data


@asynccontextmanager
async def connect(binary, socket=None):
    # No provider secrets or ambient driver permission overrides cross this boundary.
    env = {k: os.environ[k] for k in ('HOME', 'PATH', 'USER', 'LANG', 'DISPLAY',
           'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS') if k in os.environ}
    args = ['mcp']
    if socket:
        args += ['--socket', socket]
    with open(os.devnull, 'w') as errlog:
        async with stdio_client(StdioServerParameters(command=binary, args=args, env=env), errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                driver = Driver(session, {t.name:t.inputSchema for t in tools}, 'jev-' + uuid4().hex)
                try:
                    yield driver
                finally:
                    schema = driver.schemas.get('end_session', {})
                    if 'session' in schema.get('properties', {}):
                        try:
                            import asyncio
                            await asyncio.wait_for(driver.call('end_session', {}), timeout=3)
                        except Exception:
                            pass  # Cleanup must not replace the original action outcome.
