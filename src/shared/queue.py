import json

import boto3

from shared.config import scan_queue_url


_sqs_client = boto3.client("sqs")


def enqueue_scan_job(message):
    _sqs_client.send_message(
        QueueUrl=scan_queue_url(),
        MessageBody=json.dumps(message),
    )
