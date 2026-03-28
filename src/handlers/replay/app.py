import json
from datetime import datetime, timezone

from shared.config import raw_payload_bucket_name, webhook_events_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import not_found, json_response
from shared.storage import s3_client


def lambda_handler(event, context):
    event_id = (event.get("pathParameters") or {}).get("eventId")
    if not event_id:
        return not_found("Event id was not provided.")

    body = json.loads(event.get("body") or "{}")
    replay_reason = body.get("reason", "manual replay requested")
    replayed_at = datetime.now(timezone.utc).isoformat()

    table = table_resource(webhook_events_table_name())
    response = table.get_item(Key={"eventId": event_id})
    item = response.get("Item")
    if not item:
        return not_found(f"Event {event_id} was not found.")

    payload_key = item.get("payloadS3Key")
    if payload_key:
        payload_response = s3_client.get_object(
            Bucket=raw_payload_bucket_name(),
            Key=payload_key,
        )
        original_payload = payload_response["Body"].read()
        replay_key = f"replays/{item['source']}/{replayed_at}/{event_id}.json"
        s3_client.put_object(
            Bucket=raw_payload_bucket_name(),
            Key=replay_key,
            Body=original_payload,
            ContentType="application/json",
            Metadata={"replay-reason": replay_reason},
        )

    replay_count = int(item.get("replayCount", 0)) + 1
    table.update_item(
        Key={"eventId": event_id},
        UpdateExpression=(
            "SET #status = :status, replayCount = :replay_count, replayedAt = :replayed_at, "
            "lastProcessedAt = :replayed_at, lastReplayReason = :reason"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "REPLAYED",
            ":replay_count": replay_count,
            ":replayed_at": replayed_at,
            ":reason": replay_reason,
        },
    )

    updated = table.get_item(Key={"eventId": event_id}).get("Item", {})
    return json_response(
        200,
        {
            "message": "Replay recorded.",
            "event": deserialize_item(updated),
        },
    )
