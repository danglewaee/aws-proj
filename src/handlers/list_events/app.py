from boto3.dynamodb.conditions import Key

from shared.config import status_index_name, webhook_events_table_name
from shared.dynamo import deserialize_items, table_resource
from shared.http import json_response


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    status = params.get("status")
    source = params.get("source")
    event_type = params.get("eventType")
    limit = int(params.get("limit", "25"))
    table = table_resource(webhook_events_table_name())

    if status:
        response = table.query(
            IndexName=status_index_name(),
            KeyConditionExpression=Key("status").eq(status),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = deserialize_items(response.get("Items", []))
    else:
        response = table.scan(Limit=min(limit, 100))
        items = deserialize_items(response.get("Items", []))
        items.sort(key=lambda item: item.get("receivedAt", ""), reverse=True)
        items = items[:limit]

    if source:
        items = [item for item in items if item.get("source") == source]

    if event_type:
        items = [item for item in items if item.get("eventType") == event_type]

    return json_response(
        200,
        {
            "items": items,
            "count": len(items),
        },
    )
