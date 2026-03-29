from shared.config import deliveries_table_name
from shared.dynamo import deserialize_items, table_resource
from shared.http import json_response


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    status = params.get("status")
    repo = params.get("repo")
    limit = int(params.get("limit", "25"))

    table = table_resource(deliveries_table_name())
    response = table.scan(Limit=min(limit, 100))
    items = deserialize_items(response.get("Items", []))
    items.sort(key=lambda item: item.get("receivedAt", ""), reverse=True)

    if status:
        items = [item for item in items if item.get("status") == status]

    if repo:
        items = [item for item in items if item.get("repoFullName") == repo]

    items = items[:limit]
    return json_response(200, {"items": items, "count": len(items)})
