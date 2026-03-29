import os


def findings_table_name():
    return os.environ["LEAK_FINDINGS_TABLE"]


def deliveries_table_name():
    return os.environ["DELIVERIES_TABLE"]


def evidence_bucket_name():
    return os.environ["EVIDENCE_BUCKET"]


def scan_queue_url():
    return os.environ["SCAN_QUEUE_URL"]


def status_index_name():
    return os.environ.get("STATUS_INDEX_NAME", "status-receivedAt-index")


def github_webhook_secret():
    return os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def github_token():
    return os.environ.get("GITHUB_TOKEN", "")


def alert_topic_arn():
    return os.environ.get("ALERT_TOPIC_ARN", "")


def auto_disable_mode():
    return os.environ.get("AUTO_DISABLE_MODE", "OFF").strip().upper() or "OFF"


def auto_disable_enabled():
    return auto_disable_mode() != "OFF"


def delivery_ttl_days():
    return int(os.environ.get("DELIVERY_TTL_DAYS", "14"))


def disable_allowlist_users():
    raw_value = os.environ.get("DISABLE_ALLOWLIST_USERS", "")
    if not raw_value.strip():
        return set()
    return {part.strip() for part in raw_value.split(",") if part.strip()}
