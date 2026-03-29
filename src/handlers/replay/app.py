import json
from datetime import datetime, timezone

from shared.config import evidence_bucket_name, findings_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import bad_request, not_found, json_response
from shared.iam_keys import disable_access_key
from shared.storage import s3_client


def lambda_handler(event, context):
    finding_id = (event.get("pathParameters") or {}).get("findingId")
    if not finding_id:
        return not_found("Finding id was not provided.")

    body = json.loads(event.get("body") or "{}")
    action = (body.get("action") or "").upper()
    note = body.get("note", "Manual response action.")
    acted_at = datetime.now(timezone.utc).isoformat()

    if action not in {"DISABLE_KEY", "DISMISS"}:
        return bad_request("Action must be DISABLE_KEY or DISMISS.")

    table = table_resource(findings_table_name())
    response = table.get_item(Key={"eventId": finding_id})
    item = response.get("Item")
    if not item:
        return not_found(f"Finding {finding_id} was not found.")

    new_status = "DISMISSED"
    disable_count = int(item.get("disableCount", 0))
    if action == "DISABLE_KEY":
        user_name = item.get("iamUserName")
        access_key_id = item.get("matchedKeyId")
        if not user_name or not access_key_id:
            return bad_request("Finding does not have enough IAM data to disable a key.")
        disable_access_key(user_name, access_key_id)
        disable_count += 1
        new_status = "KEY_DISABLED"

    audit_key = f"actions/{item.get('repoFullName', 'unknown').replace('/', '__')}/{acted_at}/{finding_id}.json"
    s3_client.put_object(
        Bucket=evidence_bucket_name(),
        Key=audit_key,
        Body=json.dumps(
            {
                "findingId": finding_id,
                "action": action,
                "note": note,
                "actedAt": acted_at,
            }
        ).encode("utf-8"),
        ContentType="application/json",
    )

    table.update_item(
        Key={"eventId": finding_id},
        UpdateExpression=(
            "SET #status = :status, lastUpdatedAt = :acted_at, lastActionNote = :note, "
            "disableCount = :disable_count"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": new_status,
            ":acted_at": acted_at,
            ":note": note,
            ":disable_count": disable_count,
        },
    )

    updated = table.get_item(Key={"eventId": finding_id}).get("Item", {})
    return json_response(
        200,
        {
            "message": "Action recorded.",
            "finding": deserialize_item(updated),
        },
    )
