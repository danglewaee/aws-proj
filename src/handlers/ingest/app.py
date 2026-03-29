import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from shared.alerts import publish_finding_alert
from shared.config import (
    disable_allowlist_users,
    evidence_bucket_name,
    findings_table_name,
    github_webhook_secret,
)
from shared.detectors import extract_aws_access_key_findings
from shared.dynamo import deserialize_item, table_resource
from shared.github_diff import fetch_compare_diff, raw_payload_bytes, summarize_compare_window
from shared.http import bad_request, json_response, unauthorized
from shared.iam_keys import get_access_key_details
from shared.storage import s3_client


def _read_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def _verify_signature(raw_body, event):
    secret = github_webhook_secret()
    if not secret:
        return True

    signature = ((event.get("headers") or {}).get("x-hub-signature-256") or "").strip()
    if not signature.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def _archive_payload(repo_name, finding_id, payload):
    received_at = datetime.now(timezone.utc).isoformat()
    payload_key = f"findings/{repo_name}/{received_at}/{finding_id}.json".replace("//", "/")
    s3_client.put_object(
        Bucket=evidence_bucket_name(),
        Key=payload_key,
        Body=raw_payload_bytes(payload),
        ContentType="application/json",
    )
    return payload_key


def lambda_handler(event, context):
    headers = event.get("headers") or {}
    raw_body = _read_body(event)
    if not raw_body:
        return bad_request("Webhook body must not be empty.")

    if not _verify_signature(raw_body, event):
        return unauthorized("Webhook signature verification failed.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return bad_request("Webhook body must be valid JSON.")

    if payload.get("deleted"):
        return json_response(202, {"message": "Deleted branch push ignored.", "findings": []})

    compare_summary = summarize_compare_window(payload)
    diff_text = fetch_compare_diff(payload)
    findings = extract_aws_access_key_findings(diff_text)
    if not findings:
        return json_response(202, {"message": "No leaked AWS access keys detected.", "findings": []})

    repo_name = compare_summary["repoFullName"].replace("/", "__")
    table = table_resource(findings_table_name())
    delivery_id = headers.get("x-github-delivery") or headers.get("X-GitHub-Delivery")
    allowed_users = disable_allowlist_users()
    stored = []

    for finding in findings:
        finding_id = (
            f"{delivery_id}#{finding['matchedKeyId']}"
            if delivery_id
            else str(uuid.uuid4())
        )
        received_at = datetime.now(timezone.utc).isoformat()
        key_details = get_access_key_details(finding["matchedKeyId"])
        payload_key = _archive_payload(repo_name, finding_id, payload)
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
            "deliveryId": delivery_id or finding_id,
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
            continue
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
        stored.append(deserialize_item(item))

    return json_response(
        202,
        {
            "message": "LeakGuard captured leaked key findings.",
            "findings": stored,
        },
    )
