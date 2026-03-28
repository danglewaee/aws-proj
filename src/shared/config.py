import os


def spend_cases_table_name():
    return os.environ["SPEND_CASES_TABLE"]


def alert_archive_bucket_name():
    return os.environ["ALERT_ARCHIVE_BUCKET"]


def status_index_name():
    return os.environ.get("STATUS_INDEX_NAME", "status-receivedAt-index")
