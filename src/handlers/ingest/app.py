import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from shared.config import evidence_bucket_name, findings_table_name, github_webhook_secret
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
    stored = []

    for finding in findings:
        finding_id = str(uuid.uuid4())
        received_at = datetime.now(timezone.utc).isoformat()
        key_details = get_access_key_details(finding["matchedKeyId"])
        payload_key = _archive_payload(repo_name, finding_id, payload)

        item = {
            "eventId": finding_id,
            "findingId": finding_id,
            "status": "OPEN",
            "receivedAt": received_at,
            "lastUpdatedAt": received_at,
            "secretType": finding["secretType"],
            "repoFullName": compare_summary["repoFullName"],
            "branch": compare_summary["branch"] or "unknown",
            "compareUrl": compare_summary["compareUrl"],
            "beforeSha": compare_summary["before"] or "unknown",
            "afterSha": compare_summary["after"] or "unknown",
            "matchedKeyIdRedacted": finding["matchedKeyIdRedacted"],
            "matchedKeyId": finding["matchedKeyId"],
            "iamUserName": key_details["userName"],
            "keyExists": key_details["exists"],
            "lastUsedService": str(key_details["serviceName"] or ""),
            "lastUsedRegion": str(key_details["region"] or ""),
            "evidenceSnippet": finding["evidenceSnippet"],
            "payloadS3Key": payload_key,
            "disableCount": 0,
            "lastActionNote": None,
        }
        table.put_item(Item=item)
        stored.append(deserialize_item(item))

    return json_response(
        202,
        {
            "message": "LeakGuard captured leaked key findings.",
            "findings": stored,
        },
    )
