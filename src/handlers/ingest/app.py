import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

from shared.config import (
    evidence_bucket_name,
    github_webhook_secret,
)
from shared.deliveries import (
    attach_delivery_context,
    delete_delivery,
    register_delivery,
    update_delivery_status,
)
from shared.github_diff import raw_payload_bytes, summarize_compare_window
from shared.http import bad_request, json_response, unauthorized
from shared.queue import enqueue_scan_job
from shared.storage import s3_client


def _read_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def _verify_signature(raw_body, headers):
    secret = github_webhook_secret()
    if not secret:
        return True

    signature = (headers.get("x-hub-signature-256") or "").strip()
    if not signature.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def _archive_delivery_payload(repo_name, delivery_id, payload):
    received_at = datetime.now(timezone.utc).isoformat()
    payload_key = f"deliveries/{repo_name}/{received_at}/{delivery_id}.json".replace("//", "/")
    s3_client.put_object(
        Bucket=evidence_bucket_name(),
        Key=payload_key,
        Body=raw_payload_bytes(payload),
        ContentType="application/json",
    )
    return payload_key


def lambda_handler(event, context):
    headers = {(key or "").lower(): value for key, value in (event.get("headers") or {}).items()}
    raw_body = _read_body(event)
    if not raw_body:
        return bad_request("Webhook body must not be empty.")

    if not _verify_signature(raw_body, headers):
        return unauthorized("Webhook signature verification failed.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return bad_request("Webhook body must be valid JSON.")

    delivery_id = headers.get("x-github-delivery")
    if not delivery_id:
        return bad_request("X-GitHub-Delivery header is required.")

    github_event = (headers.get("x-github-event") or "").strip().lower()
    if github_event and github_event != "push":
        return json_response(
            202,
            {
                "message": f"GitHub event {github_event} ignored.",
                "findings": [],
            },
        )

    if payload.get("deleted"):
        compare_summary = summarize_compare_window(payload)
        if register_delivery(delivery_id, github_event or "push", compare_summary["repoFullName"]):
            update_delivery_status(
                delivery_id,
                "IGNORED_DELETED",
                0,
                "Deleted branch push ignored by LeakGuard.",
            )
        return json_response(202, {"message": "Deleted branch push ignored.", "findings": []})

    compare_summary = summarize_compare_window(payload)
    if not register_delivery(delivery_id, github_event or "push", compare_summary["repoFullName"]):
        return json_response(
            202,
            {
                "message": "Duplicate GitHub delivery ignored.",
                "findings": [],
                "deliveryId": delivery_id,
            },
        )

    try:
        repo_name = compare_summary["repoFullName"].replace("/", "__")
        payload_key = _archive_delivery_payload(repo_name, delivery_id, payload)
        attach_delivery_context(
            delivery_id,
            payload_key,
            branch=compare_summary["branch"] or "",
            compare_url=compare_summary["compareUrl"] or "",
            before_sha=compare_summary["before"] or "",
            after_sha=compare_summary["after"] or "",
        )
        enqueue_scan_job(
            {
                "deliveryId": delivery_id,
                "eventName": github_event or "push",
                "repoFullName": compare_summary["repoFullName"],
                "payloadS3Key": payload_key,
            }
        )
        update_delivery_status(
            delivery_id,
            "QUEUED_FOR_SCAN",
            0,
            "LeakGuard accepted the GitHub delivery and queued it for scanning.",
        )

        return json_response(
            202,
            {
                "message": "GitHub delivery accepted and queued for scanning.",
                "deliveryId": delivery_id,
            },
        )
    except Exception:
        delete_delivery(delivery_id)
        raise
