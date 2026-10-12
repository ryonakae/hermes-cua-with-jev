from pathlib import Path

from .models import Request


def register(ctx):
    from .tool_handlers import handle

    ctx.register_tool(
        name="cua_jev", toolset="cua_with_jev",
        schema={"name": "cua_jev", "description": (
            "Run bounded browser/native GUI work using Jev; discover windows, inspect one exact target, "
            "run a goal, or recover with one explicitly selected action. Read skill "
            "hermes-cua-with-jev:usage first. Only pass controls and inputs authorized by the user. "
            "Never pass credentials. Do not run another GUI controller concurrently."
        ), "parameters": Request.model_json_schema()},
        handler=handle,
    )
    ctx.register_skill(name="usage", path=Path(__file__).resolve().parents[1] / "skills/usage/SKILL.md",
                       description="Use the unified Jev CUA tool safely and interpret incomplete results.")
