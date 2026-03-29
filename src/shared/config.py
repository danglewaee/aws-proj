import os


def findings_table_name():
    return os.environ["LEAK_FINDINGS_TABLE"]


def evidence_bucket_name():
    return os.environ["EVIDENCE_BUCKET"]


def status_index_name():
    return os.environ.get("STATUS_INDEX_NAME", "status-receivedAt-index")


def github_webhook_secret():
    return os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def github_token():
    return os.environ.get("GITHUB_TOKEN", "")
