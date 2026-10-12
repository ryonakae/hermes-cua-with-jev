from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Target(Strict):
    kind: Literal["native", "browser"]
    pid: int = Field(gt=0)
    window_id: int = Field(ge=0)
    tab_url: str | None = None

    @model_validator(mode="after")
    def exact_browser(self):
        if self.kind == "browser" and not self.tab_url:
            raise ValueError("browser target requires an exact tab_url")
        return self


class Control(Strict):
    role: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=500)
    operation: Literal["click", "type"]
    input_key: str | None = None

    @model_validator(mode="after")
    def typed_input(self):
        if self.operation == "type" and not self.input_key:
            raise ValueError("type requires input_key")
        if self.operation == "click" and self.input_key is not None:
            raise ValueError("click cannot use input_key")
        return self


class Expectation(Strict):
    role: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=500)
    value_equals: str | None = Field(default=None, max_length=4000)


class Request(Strict):
    action: Literal["discover", "inspect", "run", "step"]
    target: Target | None = None
    goal: str = Field(default="", max_length=4000)
    controls: list[Control] = Field(default_factory=list, max_length=60)
    inputs: dict[str, str] = Field(default_factory=dict)
    expect: list[Expectation] = Field(default_factory=list, max_length=8)
    max_steps: int = Field(default=12, ge=1, le=50)
    timeout_seconds: int = Field(default=60, ge=1, le=300)

    @model_validator(mode="after")
    def operation_contract(self):
        if self.action != "discover" and self.target is None:
            raise ValueError("target required")
        if self.action in {"run", "step"}:
            if not self.expect or not self.controls:
                raise ValueError("controls and independently checked expect are required")
            if self.action == "run" and not self.goal:
                raise ValueError("run requires goal")
            if self.action == "step" and len(self.controls) != 1:
                raise ValueError("step requires exactly one control")
        if len(self.inputs) > 20 or any(len(k)>120 or len(v)>4000 for k,v in self.inputs.items()):
            raise ValueError("input budget exceeded")
        if any(c.operation == "type" and c.input_key not in self.inputs for c in self.controls):
            raise ValueError("missing input_key")
        return self
