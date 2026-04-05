from shared.deliveries import get_delivery, update_delivery_status
from shared.http import bad_request, json_response, not_found
from shared.operator_auth import require_operator_auth
from shared.queue import enqueue_scan_job


RETRYABLE_STATUSES = {"SCAN_FAILED", "DLQ_RECEIVED", "RETRY_QUEUED"}


def lambda_handler(event, context):
    delivery_id = (event.get("pathParameters") or {}).get("deliveryId")
    if not delivery_id:
        return not_found("Delivery id was not provided.")

    operator_id, auth_error = require_operator_auth(event)
    if auth_error:
        return auth_error

    delivery = get_delivery(delivery_id)
    if not delivery:
        return not_found(f"Delivery {delivery_id} was not found.")

    status = delivery.get("status")
    if status not in RETRYABLE_STATUSES:
        return bad_request(f"Delivery {delivery_id} is not retryable from status {status}.")

    payload_s3_key = delivery.get("payloadS3Key")
    if not payload_s3_key:
        return bad_request("Delivery does not have archived payload evidence for retry.")

    enqueue_scan_job(
        {
            "deliveryId": delivery_id,
            "eventName": delivery.get("eventName") or "push",
            "repoFullName": delivery.get("repoFullName") or "unknown",
            "payloadS3Key": payload_s3_key,
        }
    )
    update_delivery_status(
        delivery_id,
        "RETRY_QUEUED",
        int(delivery.get("findingCount", 0)),
        f"LeakGuard manually re-queued this delivery from the delivery audit view. Actor={operator_id}",
        scan_attempt_count=int(delivery.get("scanAttemptCount", 0)),
    )

    return json_response(
        202,
        {
            "message": "Delivery re-queued for scan.",
            "deliveryId": delivery_id,
        },
    )
