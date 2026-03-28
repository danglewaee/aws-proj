import base64
import json
import uuid
from datetime import datetime, timezone

from shared.config import raw_payload_bucket_name, webhook_events_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import bad_request, json_response
from shared.storage import s3_client


def _read_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def lambda_handler(event, context):
    source = (event.get("pathParameters") or {}).get("source")
    if not source:
        return bad_request("Missing webhook source path parameter.")

    raw_body = _read_body(event)
    if not raw_body:
        return bad_request("Webhook body must not be empty.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return bad_request("Webhook body must be valid JSON.")

    event_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc).isoformat()
    event_type = payload.get("type", "unknown")
    correlation_id = (
        payload.get("correlationId")
        or (event.get("headers") or {}).get("x-correlation-id")
        or event_id
    )
    status = "FAILED" if payload.get("simulateFailure") else "PROCESSED"
    payload_key = f"raw/{source}/{received_at}/{event_id}.json"

    s3_client.put_object(
        Bucket=raw_payload_bucket_name(),
        Key=payload_key,
        Body=raw_body.encode("utf-8"),
        ContentType="application/json",
    )

    table = table_resource(webhook_events_table_name())
    item = {
        "eventId": event_id,
        "source": source,
        "eventType": event_type,
        "status": status,
        "receivedAt": received_at,
        "lastProcessedAt": received_at,
        "correlationId": correlation_id,
        "payloadS3Key": payload_key,
        "replayCount": 0,
        "lastReplayReason": None,
        "lastErrorCode": "SIMULATED_FAILURE" if status == "FAILED" else None,
        "lastErrorMessage": "Failure requested by payload flag." if status == "FAILED" else None,
    }
    table.put_item(Item=item)

    return json_response(
        202,
        {
            "message": "Webhook accepted.",
            "event": deserialize_item(item),
        },
    )
