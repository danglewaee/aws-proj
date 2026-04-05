from datetime import datetime

from shared.config import deliveries_table_name, findings_table_name
from shared.dynamo import deserialize_items, table_resource
from shared.http import json_response


def _scan_all_items(table_name):
    table = table_resource(table_name)
    items = []
    response = table.scan()
    items.extend(deserialize_items(response.get("Items", [])))
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(deserialize_items(response.get("Items", [])))
    return items


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _count_by(items, key, default="UNKNOWN"):
    counts = {}
    for item in items:
        label = item.get(key) or default
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _compute_time_to_finding(findings, deliveries_by_id):
    latencies = []
    for finding in findings:
        delivery = deliveries_by_id.get(finding.get("deliveryId"))
        received_at = _parse_iso(delivery.get("receivedAt")) if delivery else None
        finding_at = _parse_iso(finding.get("receivedAt"))
        if not received_at or not finding_at:
            continue
        latencies.append((finding_at - received_at).total_seconds() * 1000)
    return latencies


def lambda_handler(event, context):
    deliveries = _scan_all_items(deliveries_table_name())
    findings = _scan_all_items(findings_table_name())
    deliveries_by_id = {
        item["deliveryId"]: item for item in deliveries if item.get("deliveryId")
    }

    scan_attempts = [
        int(item.get("scanAttemptCount", 0))
        for item in deliveries
        if item.get("scanAttemptCount") is not None
    ]
    time_to_finding_ms = _compute_time_to_finding(findings, deliveries_by_id)

    payload = {
        "deliveries": {
            "total": len(deliveries),
            "byStatus": _count_by(deliveries, "status"),
            "retryEligible": sum(
                1 for item in deliveries if item.get("status") in {"SCAN_FAILED", "DLQ_RECEIVED", "RETRY_QUEUED"}
            ),
            "maxScanAttempts": max(scan_attempts) if scan_attempts else 0,
        },
        "findings": {
            "total": len(findings),
            "open": sum(1 for item in findings if item.get("status") == "OPEN"),
            "keyDisabled": sum(1 for item in findings if item.get("status") == "KEY_DISABLED"),
            "dismissed": sum(1 for item in findings if item.get("status") == "DISMISSED"),
            "alertsPublished": sum(1 for item in findings if item.get("alertStatus") == "PUBLISHED"),
            "autoDisabled": sum(1 for item in findings if item.get("autoDisableStatus") == "DISABLED"),
            "byDiffSource": _count_by(findings, "diffSource"),
            "bySeverity": _count_by(findings, "severity"),
        },
        "performance": {
            "timeToFindingMs": {
                "count": len(time_to_finding_ms),
                "p50": round(_percentile(time_to_finding_ms, 0.50), 1) if time_to_finding_ms else None,
                "p95": round(_percentile(time_to_finding_ms, 0.95), 1) if time_to_finding_ms else None,
                "max": round(max(time_to_finding_ms), 1) if time_to_finding_ms else None,
            },
            "scanAttempts": {
                "count": len(scan_attempts),
                "p50": round(_percentile(scan_attempts, 0.50), 1) if scan_attempts else None,
                "p95": round(_percentile(scan_attempts, 0.95), 1) if scan_attempts else None,
                "max": max(scan_attempts) if scan_attempts else 0,
            },
        },
    }

    return json_response(200, payload)
