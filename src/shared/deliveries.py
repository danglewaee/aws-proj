from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from shared.config import deliveries_table_name, delivery_ttl_days
from shared.dynamo import table_resource


def _expiry_timestamp():
    expires_at = datetime.now(timezone.utc) + timedelta(days=delivery_ttl_days())
    return int(expires_at.timestamp())


def register_delivery(delivery_id, event_name, repo_full_name):
    table = table_resource(deliveries_table_name())
    received_at = datetime.now(timezone.utc).isoformat()
    try:
        table.put_item(
            Item={
                "deliveryId": delivery_id,
                "eventName": event_name,
                "repoFullName": repo_full_name,
                "receivedAt": received_at,
                "status": "RECEIVED",
                "findingCount": 0,
                "expiresAt": _expiry_timestamp(),
            },
            ConditionExpression="attribute_not_exists(deliveryId)",
        )
        return True
    except ClientError as exc:
        error_code = (exc.response.get("Error") or {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            return False
        raise


def update_delivery_status(delivery_id, status, finding_count=0, note=""):
    table = table_resource(deliveries_table_name())
    table.update_item(
        Key={"deliveryId": delivery_id},
        UpdateExpression=(
            "SET #status = :status, processedAt = :processed_at, "
            "findingCount = :finding_count, statusNote = :status_note"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": status,
            ":processed_at": datetime.now(timezone.utc).isoformat(),
            ":finding_count": finding_count,
            ":status_note": note,
        },
    )


def delete_delivery(delivery_id):
    table = table_resource(deliveries_table_name())
    table.delete_item(Key={"deliveryId": delivery_id})
