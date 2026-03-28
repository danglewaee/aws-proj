from boto3.dynamodb.conditions import Key

from shared.config import spend_cases_table_name, status_index_name
from shared.dynamo import deserialize_items, table_resource
from shared.http import json_response


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    status = params.get("status")
    source = params.get("source")
    service = params.get("service")
    severity = params.get("severity")
    limit = int(params.get("limit", "25"))
    table = table_resource(spend_cases_table_name())

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

    if service:
        items = [item for item in items if item.get("service") == service]

    if severity:
        items = [item for item in items if item.get("severity") == severity]

    return json_response(
        200,
        {
            "items": items,
            "count": len(items),
        },
    )
