import base64
import json
import uuid
from datetime import datetime, timezone

from shared.config import alert_archive_bucket_name, spend_cases_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import bad_request, json_response
from shared.storage import s3_client


ALERT_SOURCE_PROFILES = {
    "budgets": {
        "label": "AWS Budgets",
        "default_title": "Monthly spend crossed a budget threshold",
        "default_action": "Review the tagged resources behind the budget and stop anything idle first.",
    },
    "anomaly-detection": {
        "label": "Cost Anomaly Detection",
        "default_title": "Unexpected AWS spend increase detected",
        "default_action": "Open the suspicious service first and compare yesterday's usage against normal baseline.",
    },
    "compute-optimizer": {
        "label": "Compute Optimizer",
        "default_title": "Potential savings opportunity detected",
        "default_action": "Review the recommended downsizing candidates and confirm they are safe to change.",
    },
    "manual": {
        "label": "Manual Review",
        "default_title": "Spend issue reported manually",
        "default_action": "Capture the likely cause and assign one owner before the next billing cycle.",
    },
}


def _read_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def _resolve_source_profile(source):
    normalized = (source or "").strip().lower()
    return ALERT_SOURCE_PROFILES.get(normalized, ALERT_SOURCE_PROFILES["manual"])


def _normalize_severity(raw_value, estimated_impact):
    if raw_value:
        normalized = raw_value.strip().upper()
        if normalized in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            return normalized

    if estimated_impact >= 500:
        return "CRITICAL"
    if estimated_impact >= 200:
        return "HIGH"
    if estimated_impact >= 75:
        return "MEDIUM"
    return "LOW"


def lambda_handler(event, context):
    source = (event.get("pathParameters") or {}).get("source")
    if not source:
        return bad_request("Missing alert source path parameter.")

    raw_body = _read_body(event)
    if not raw_body:
        return bad_request("Alert body must not be empty.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return bad_request("Alert body must be valid JSON.")

    case_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc).isoformat()
    source_profile = _resolve_source_profile(source)
    correlation_id = (
        payload.get("correlationId")
        or (event.get("headers") or {}).get("x-correlation-id")
        or case_id
    )

    estimated_impact = float(payload.get("estimatedImpactUsd", 0))
    severity = _normalize_severity(payload.get("severity"), estimated_impact)
    service = payload.get("service", "Unknown AWS service")
    title = payload.get("title") or source_profile["default_title"]
    likely_cause = payload.get("likelyCause", "The source alert did not include a likely cause yet.")
    suggested_action = payload.get("suggestedAction") or source_profile["default_action"]
    alert_type = payload.get("alertType", "ANOMALY")
    resource_hints = payload.get("resourceHints", [])
    owner = payload.get("owner", "unassigned")
    payload_key = f"alerts/{source}/{received_at}/{case_id}.json"

    s3_client.put_object(
        Bucket=alert_archive_bucket_name(),
        Key=payload_key,
        Body=raw_body.encode("utf-8"),
        ContentType="application/json",
    )

    table = table_resource(spend_cases_table_name())
    item = {
        "caseId": case_id,
        "title": title,
        "source": source,
        "sourceLabel": source_profile["label"],
        "status": "NEW",
        "service": service,
        "severity": severity,
        "alertType": alert_type,
        "estimatedImpactUsd": estimated_impact,
        "likelyCause": likely_cause,
        "suggestedAction": suggested_action,
        "resourceHints": resource_hints,
        "owner": owner,
        "receivedAt": received_at,
        "lastUpdatedAt": received_at,
        "correlationId": correlation_id,
        "payloadS3Key": payload_key,
        "reviewCount": 0,
        "lastReviewNote": None,
        "lastReviewedAt": None,
    }
    table.put_item(Item=item)

    return json_response(
        202,
        {
            "message": "Spend alert captured.",
            "case": deserialize_item(item),
        },
    )
