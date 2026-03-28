import os


def webhook_events_table_name():
    return os.environ["WEBHOOK_EVENTS_TABLE"]


def raw_payload_bucket_name():
    return os.environ["RAW_PAYLOAD_BUCKET"]


def status_index_name():
    return os.environ.get("STATUS_INDEX_NAME", "status-receivedAt-index")
