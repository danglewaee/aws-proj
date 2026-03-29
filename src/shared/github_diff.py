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


def _compare_api_request(compare_api_url, token):
    request = Request(compare_api_url)
    request.add_header("Accept", "application/vnd.github.v3.diff")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("User-Agent", "LeakGuardPrototype")
    with urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8")


def fetch_compare_diff(payload):
    inline_diff = payload.get("inlineDiff")

    compare_api_url = build_compare_api_url(payload)
    token = github_token()

    if compare_api_url and token:
        try:
            return {
                "diffText": _compare_api_request(compare_api_url, token),
                "source": "GITHUB_COMPARE_API",
                "error": "",
            }
        except (HTTPError, URLError) as exc:
            if inline_diff:
                return {
                    "diffText": inline_diff,
                    "source": "INLINE_DIFF_FALLBACK",
                    "error": str(exc)[:240],
                }
            return {
                "diffText": "",
                "source": "GITHUB_COMPARE_API_ERROR",
                "error": str(exc)[:240],
            }

    if inline_diff:
        return {
            "diffText": inline_diff,
            "source": "INLINE_DIFF",
            "error": "" if not compare_api_url else "GitHub token not configured. Used inline diff fallback.",
        }

    if compare_api_url and not token:
        return {
            "diffText": "",
            "source": "COMPARE_API_UNCONFIGURED",
            "error": "GitHub compare URL exists but GITHUB_TOKEN is not configured.",
        }

    return {
        "diffText": "",
        "source": "NO_DIFF_SOURCE",
        "error": "No compare URL or inline diff available in payload.",
    }


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
