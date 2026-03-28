import json
from datetime import datetime, timezone

from shared.config import alert_archive_bucket_name, spend_cases_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import bad_request, not_found, json_response
from shared.storage import s3_client


def lambda_handler(event, context):
    case_id = (event.get("pathParameters") or {}).get("caseId")
    if not case_id:
        return not_found("Case id was not provided.")

    body = json.loads(event.get("body") or "{}")
    requested_status = (body.get("status") or "").upper()
    review_note = body.get("note", "Manual review update.")
    owner = body.get("owner")
    reviewed_at = datetime.now(timezone.utc).isoformat()

    if requested_status not in {"ACKNOWLEDGED", "RESOLVED"}:
        return bad_request("Status must be ACKNOWLEDGED or RESOLVED.")

    table = table_resource(spend_cases_table_name())
    response = table.get_item(Key={"caseId": case_id})
    item = response.get("Item")
    if not item:
        return not_found(f"Case {case_id} was not found.")

    payload_key = item.get("payloadS3Key")
    if payload_key:
        payload_response = s3_client.get_object(
            Bucket=alert_archive_bucket_name(),
            Key=payload_key,
        )
        original_payload = json.loads(payload_response["Body"].read().decode("utf-8"))
        review_key = f"reviews/{item['source']}/{reviewed_at}/{case_id}.json"
        s3_client.put_object(
            Bucket=alert_archive_bucket_name(),
            Key=review_key,
            Body=json.dumps(
                {
                    "reviewedAt": reviewed_at,
                    "status": requested_status,
                    "note": review_note,
                    "owner": owner or item.get("owner", "unassigned"),
                    "alertPayload": original_payload,
                }
            ).encode("utf-8"),
            ContentType="application/json",
        )

    review_count = int(item.get("reviewCount", 0)) + 1
    resolved_at = reviewed_at if requested_status == "RESOLVED" else item.get("resolvedAt")
    table.update_item(
        Key={"caseId": case_id},
        UpdateExpression=(
            "SET #status = :status, reviewCount = :review_count, lastReviewedAt = :reviewed_at, "
            "lastUpdatedAt = :reviewed_at, lastReviewNote = :note, owner = :owner, "
            "resolvedAt = :resolved_at"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": requested_status,
            ":review_count": review_count,
            ":reviewed_at": reviewed_at,
            ":note": review_note,
            ":owner": owner or item.get("owner", "unassigned"),
            ":resolved_at": resolved_at,
        },
    )

    updated = table.get_item(Key={"caseId": case_id}).get("Item", {})
    return json_response(
        200,
        {
            "message": "Case review recorded.",
            "case": deserialize_item(updated),
        },
    )
