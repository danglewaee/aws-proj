from shared.config import operator_action_token
from shared.http import unauthorized


def _headers(event):
    return {(key or "").lower(): value for key, value in (event.get("headers") or {}).items()}


def require_operator_auth(event):
    headers = _headers(event)
    configured_token = operator_action_token().strip()
    presented_token = (headers.get("x-operator-token") or "").strip()
    operator_id = (headers.get("x-operator-id") or "").strip()

    if configured_token and presented_token != configured_token:
        return None, unauthorized("Operator token was missing or invalid.")

    if operator_id:
        return operator_id, None

    if configured_token:
        return "authenticated-operator", None

    return "console-operator", None
