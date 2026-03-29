import json
from datetime import datetime, timezone

from shared.alerts import publish_finding_alert
from shared.config import disable_allowlist_users, evidence_bucket_name, findings_table_name
from shared.deliveries import update_delivery_status
from shared.dynamo import deserialize_item, table_resource
from shared.detectors import extract_aws_access_key_findings
from shared.github_diff import fetch_compare_diff, summarize_compare_window
from shared.iam_keys import get_access_key_details
from shared.storage import s3_client


def _load_payload(payload_key):
    payload_response = s3_client.get_object(
        Bucket=evidence_bucket_name(),
        Key=payload_key,
    )
    raw_payload = payload_response["Body"].read().decode("utf-8")
    return json.loads(raw_payload)


def _store_finding(table, delivery_id, compare_summary, payload_key, finding, allowed_users):
    finding_id = f"{delivery_id}#{finding['matchedKeyId']}"
    received_at = datetime.now(timezone.utc).isoformat()
    key_details = get_access_key_details(finding["matchedKeyId"])
    iam_user_name = key_details["userName"]
    disable_eligible = bool(iam_user_name and key_details["exists"])
    if allowed_users:
        disable_eligible = disable_eligible and iam_user_name in allowed_users

    item = {
        "eventId": finding_id,
        "findingId": finding_id,
        "status": "OPEN",
        "receivedAt": received_at,
        "lastUpdatedAt": received_at,
        "deliveryId": delivery_id,
        "secretType": finding["secretType"],
        "severity": finding["severity"],
        "confidence": finding["confidence"],
        "repoFullName": compare_summary["repoFullName"],
        "branch": compare_summary["branch"] or "unknown",
        "compareUrl": compare_summary["compareUrl"],
        "beforeSha": compare_summary["before"] or "unknown",
        "afterSha": compare_summary["after"] or "unknown",
        "matchedKeyIdRedacted": finding["matchedKeyIdRedacted"],
        "matchedKeyId": finding["matchedKeyId"],
        "iamUserName": iam_user_name,
        "keyExists": key_details["exists"],
        "lastUsedService": str(key_details["serviceName"] or ""),
        "lastUsedRegion": str(key_details["region"] or ""),
        "evidenceSnippet": finding["evidenceSnippet"],
        "payloadS3Key": payload_key,
        "disableCount": 0,
        "disableEligible": disable_eligible,
        "disableAllowlistApplied": bool(allowed_users),
        "lastActionNote": None,
        "confirmationRequired": True,
        "alertStatus": "PENDING",
        "alertChannel": "SNS",
        "alertPublishedAt": "",
        "alertMessageId": "",
        "alertError": "",
        "actionHistory": [
            {
                "action": "DETECTED",
                "actedAt": received_at,
                "note": "LeakGuard detected a high-confidence AWS access key pattern in this push.",
            }
        ],
    }
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(eventId)",
        )
    except Exception:
        return None

    alert_result = publish_finding_alert(item)
    item["alertStatus"] = alert_result["status"]
    item["alertChannel"] = alert_result["channel"]
    item["alertPublishedAt"] = alert_result["publishedAt"]
    item["alertMessageId"] = alert_result["messageId"]
    item["alertError"] = alert_result["error"]
    table.update_item(
        Key={"eventId": finding_id},
        UpdateExpression=(
            "SET alertStatus = :alert_status, alertChannel = :alert_channel, "
            "alertPublishedAt = :alert_published_at, alertMessageId = :alert_message_id, "
            "alertError = :alert_error"
        ),
        ExpressionAttributeValues={
            ":alert_status": item["alertStatus"],
            ":alert_channel": item["alertChannel"],
            ":alert_published_at": item["alertPublishedAt"],
            ":alert_message_id": item["alertMessageId"],
            ":alert_error": item["alertError"],
        },
    )
    return deserialize_item(item)


def _process_delivery(message):
    delivery_id = message["deliveryId"]
    payload_key = message["payloadS3Key"]
    payload = _load_payload(payload_key)
    compare_summary = summarize_compare_window(payload)

    update_delivery_status(
        delivery_id,
        "SCANNING",
        0,
        "LeakGuard worker started scanning this GitHub delivery.",
    )

    diff_text = fetch_compare_diff(payload)
    findings = extract_aws_access_key_findings(diff_text)
    if not findings:
        update_delivery_status(
            delivery_id,
            "PROCESSED_NO_FINDINGS",
            0,
            "No leaked AWS access key IDs detected in this delivery.",
        )
        return

    table = table_resource(findings_table_name())
    allowed_users = disable_allowlist_users()
    stored = []
    for finding in findings:
        stored_finding = _store_finding(
            table,
            delivery_id,
            compare_summary,
            payload_key,
            finding,
            allowed_users,
        )
        if stored_finding:
            stored.append(stored_finding)

    update_delivery_status(
        delivery_id,
        "FINDINGS_CREATED",
        len(stored),
        "LeakGuard stored findings for this GitHub push delivery.",
    )


def lambda_handler(event, context):
    records = event.get("Records", [])
    for record in records:
        message = json.loads(record["body"])
        try:
            _process_delivery(message)
        except Exception as exc:
            update_delivery_status(
                message["deliveryId"],
                "SCAN_FAILED",
                0,
                f"LeakGuard worker failed: {str(exc)[:240]}",
            )
            raise

    return {"batchItemFailures": []}
