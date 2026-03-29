import json
from datetime import datetime, timezone

import boto3

from shared.config import alert_topic_arn


_sns_client = boto3.client("sns")


def publish_finding_alert(finding):
    topic_arn = alert_topic_arn().strip()
    if not topic_arn:
        return {
            "status": "NOT_CONFIGURED",
            "channel": "NONE",
            "publishedAt": "",
            "messageId": "",
            "error": "",
        }

    message = {
        "findingId": finding.get("findingId"),
        "status": finding.get("status"),
        "repoFullName": finding.get("repoFullName"),
        "branch": finding.get("branch"),
        "secretType": finding.get("secretType"),
        "severity": finding.get("severity"),
        "confidence": finding.get("confidence"),
        "matchedKeyIdRedacted": finding.get("matchedKeyIdRedacted"),
        "iamUserName": finding.get("iamUserName"),
        "compareUrl": finding.get("compareUrl"),
        "receivedAt": finding.get("receivedAt"),
        "deliveryId": finding.get("deliveryId"),
    }
    subject = f"LeakGuard finding: {finding.get('repoFullName', 'unknown repo')}"

    try:
        response = _sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject[:100],
            Message=json.dumps(message, indent=2),
        )
        return {
            "status": "PUBLISHED",
            "channel": "SNS",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "messageId": response.get("MessageId", ""),
            "error": "",
        }
    except Exception as exc:
        return {
            "status": "FAILED",
            "channel": "SNS",
            "publishedAt": "",
            "messageId": "",
            "error": str(exc)[:300],
        }
