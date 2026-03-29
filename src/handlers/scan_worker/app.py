import json
from datetime import datetime, timezone

from shared.alerts import publish_finding_alert
from shared.config import (
    auto_disable_mode,
    disable_allowlist_users,
    evidence_bucket_name,
    findings_table_name,
)
from shared.deliveries import update_delivery_status
from shared.dynamo import deserialize_item, table_resource
from shared.detectors import extract_aws_access_key_findings
from shared.github_diff import fetch_compare_diff, summarize_compare_window
from shared.iam_keys import disable_access_key, get_access_key_details
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
        "diffSource": compare_summary["diffSource"],
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
        "autoDisableMode": auto_disable_mode(),
        "autoDisableStatus": "NOT_ENABLED",
        "autoDisableAttemptedAt": "",
        "autoDisableReason": "",
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


def _maybe_auto_disable(table, item):
    mode = auto_disable_mode()
    finding_id = item["findingId"]
    attempted_at = datetime.now(timezone.utc).isoformat()
    status = "NOT_ENABLED"
    reason = "Auto-disable is disabled."
    updated_status = item["status"]
    disable_count = int(item.get("disableCount", 0))
    action_history = list(item.get("actionHistory", []))

    if mode == "ALLOWLIST_HIGH_CONFIDENCE":
        if not item.get("keyExists"):
            status = "SKIPPED"
            reason = "Key could not be verified in IAM."
        elif item.get("confidence") != "HIGH":
            status = "SKIPPED"
            reason = "Finding confidence was not HIGH."
        elif not item.get("disableEligible", False):
            status = "SKIPPED"
            reason = "Finding is outside the current disable policy."
        else:
            try:
                disable_access_key(item["iamUserName"], item["matchedKeyId"])
                status = "DISABLED"
                reason = "LeakGuard auto-disabled a verified AWS access key under the allowlist policy."
                updated_status = "KEY_DISABLED"
                disable_count += 1
                action_history.append(
                    {
                        "action": "AUTO_DISABLED",
                        "actedAt": attempted_at,
                        "note": reason,
                        "confirmed": True,
                    }
                )
            except Exception as exc:
                status = "FAILED"
                reason = f"Auto-disable attempt failed: {str(exc)[:240]}"
                action_history.append(
                    {
                        "action": "AUTO_DISABLE_FAILED",
                        "actedAt": attempted_at,
                        "note": reason,
                        "confirmed": True,
                    }
                )
    elif mode != "OFF":
        status = "SKIPPED"
        reason = f"Unknown auto-disable mode {mode}."

    if status == "SKIPPED":
        action_history.append(
            {
                "action": "AUTO_DISABLE_SKIPPED",
                "actedAt": attempted_at,
                "note": reason,
                "confirmed": False,
            }
        )

    table.update_item(
        Key={"eventId": finding_id},
        UpdateExpression=(
            "SET #status = :status, lastUpdatedAt = :attempted_at, lastActionNote = :note, "
            "disableCount = :disable_count, actionHistory = :action_history, "
            "autoDisableMode = :auto_disable_mode, autoDisableStatus = :auto_disable_status, "
            "autoDisableAttemptedAt = :auto_disable_attempted_at, autoDisableReason = :auto_disable_reason"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": updated_status,
            ":attempted_at": attempted_at,
            ":note": reason,
            ":disable_count": disable_count,
            ":action_history": action_history,
            ":auto_disable_mode": mode,
            ":auto_disable_status": status,
            ":auto_disable_attempted_at": attempted_at,
            ":auto_disable_reason": reason,
        },
    )
    updated = table.get_item(Key={"eventId": finding_id}).get("Item", {})
    return deserialize_item(updated)


def _process_delivery(message, attempt_count):
    delivery_id = message["deliveryId"]
    payload_key = message["payloadS3Key"]
    payload = _load_payload(payload_key)
    compare_summary = summarize_compare_window(payload)

    update_delivery_status(
        delivery_id,
        "SCANNING",
        0,
        "LeakGuard worker started scanning this GitHub delivery.",
        scan_attempt_count=attempt_count,
    )

    diff_result = fetch_compare_diff(payload)
    compare_summary["diffSource"] = diff_result["source"]
    diff_text = diff_result["diffText"]
    findings = extract_aws_access_key_findings(diff_text)
    if not diff_text:
        update_delivery_status(
            delivery_id,
            "SCAN_FAILED",
            0,
            f"LeakGuard could not load a diff for scanning. Source={diff_result['source']}. {diff_result['error']}",
            scan_attempt_count=attempt_count,
        )
        return

    if not findings:
        update_delivery_status(
            delivery_id,
            "PROCESSED_NO_FINDINGS",
            0,
            f"No leaked AWS access key IDs detected in this delivery. Diff source={diff_result['source']}.",
            scan_attempt_count=attempt_count,
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
            stored.append(_maybe_auto_disable(table, stored_finding))

    update_delivery_status(
        delivery_id,
        "FINDINGS_CREATED",
        len(stored),
        f"LeakGuard stored findings for this GitHub push delivery. Diff source={diff_result['source']}.",
        scan_attempt_count=attempt_count,
    )


def lambda_handler(event, context):
    records = event.get("Records", [])
    for record in records:
        message = json.loads(record["body"])
        attempt_count = int((record.get("attributes") or {}).get("ApproximateReceiveCount", "1"))
        try:
            _process_delivery(message, attempt_count)
        except Exception as exc:
            update_delivery_status(
                message["deliveryId"],
                "SCAN_FAILED",
                0,
                f"LeakGuard worker failed: {str(exc)[:240]}",
                scan_attempt_count=attempt_count,
            )
            raise

    return {"batchItemFailures": []}
