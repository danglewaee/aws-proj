import json

from shared.deliveries import update_delivery_status


def lambda_handler(event, context):
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        delivery_id = body.get("deliveryId")
        if not delivery_id:
            continue

        update_delivery_status(
            delivery_id,
            "DLQ_RECEIVED",
            0,
            "LeakGuard moved this delivery to the dead-letter queue after scan retries were exhausted.",
            scan_attempt_count=int(body.get("scanAttemptCount", 0)) or None,
        )

    return {"batchItemFailures": []}
