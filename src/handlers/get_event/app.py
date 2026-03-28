import json

from shared.config import raw_payload_bucket_name, webhook_events_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import not_found, json_response
from shared.storage import s3_client


def lambda_handler(event, context):
    event_id = (event.get("pathParameters") or {}).get("eventId")
    if not event_id:
        return not_found("Event id was not provided.")

    table = table_resource(webhook_events_table_name())
    response = table.get_item(Key={"eventId": event_id})
    item = response.get("Item")
    if not item:
        return not_found(f"Event {event_id} was not found.")

    event_summary = deserialize_item(item)
    payload_key = event_summary.get("payloadS3Key")

    payload_body = None
    if payload_key:
        payload_response = s3_client.get_object(
            Bucket=raw_payload_bucket_name(),
            Key=payload_key,
        )
        payload_body = payload_response["Body"].read().decode("utf-8")

    try:
        parsed_payload = json.loads(payload_body) if payload_body else None
    except json.JSONDecodeError:
        parsed_payload = {"rawPayload": payload_body}

    return json_response(
        200,
        {
            "event": event_summary,
            "payload": parsed_payload,
        },
    )
