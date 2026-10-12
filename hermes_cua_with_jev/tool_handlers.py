import json


def handle(args, **kwargs):
    from .models import Request
    from pydantic import ValidationError
    try:
        request = Request.model_validate(args)
    except ValidationError:
        return json.dumps({"status": "blocked", "reason": "invalid_request"})
    from .process import invoke
    return json.dumps(invoke(request, **kwargs), ensure_ascii=False)
