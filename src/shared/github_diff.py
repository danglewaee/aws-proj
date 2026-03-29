import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shared.config import github_token


def build_compare_api_url(payload):
    repository = payload.get("repository") or {}
    full_name = repository.get("full_name")
    before = payload.get("before")
    after = payload.get("after")
    if not full_name or not before or not after:
        return None
    return f"https://api.github.com/repos/{full_name}/compare/{before}...{after}"


def fetch_compare_diff(payload):
    inline_diff = payload.get("inlineDiff")
    if inline_diff:
        return inline_diff

    compare_api_url = build_compare_api_url(payload)
    token = github_token()
    if not compare_api_url or not token:
        return ""

    request = Request(compare_api_url)
    request.add_header("Accept", "application/vnd.github.v3.diff")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("User-Agent", "LeakGuardPrototype")

    try:
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError):
        return ""


def summarize_compare_window(payload):
    repository = payload.get("repository") or {}
    return {
        "repoFullName": repository.get("full_name", "unknown"),
        "branch": (payload.get("ref") or "").replace("refs/heads/", ""),
        "before": payload.get("before"),
        "after": payload.get("after"),
        "compareUrl": payload.get("compare"),
    }


def raw_payload_bytes(payload):
    return json.dumps(payload).encode("utf-8")
