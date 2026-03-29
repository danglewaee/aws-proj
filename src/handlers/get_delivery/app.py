import json

from boto3.dynamodb.conditions import Attr

from shared.config import deliveries_table_name, evidence_bucket_name, findings_table_name
from shared.dynamo import deserialize_item, deserialize_items, table_resource
from shared.http import not_found, json_response
from shared.storage import s3_client


def _load_payload(payload_key):
    if not payload_key:
        return None

    payload_response = s3_client.get_object(
        Bucket=evidence_bucket_name(),
        Key=payload_key,
    )
    payload_body = payload_response["Body"].read().decode("utf-8")
    try:
        return json.loads(payload_body)
    except json.JSONDecodeError:
        return {"rawPayload": payload_body}


def lambda_handler(event, context):
    delivery_id = (event.get("pathParameters") or {}).get("deliveryId")
    if not delivery_id:
        return not_found("Delivery id was not provided.")

    deliveries_table = table_resource(deliveries_table_name())
    delivery = deliveries_table.get_item(Key={"deliveryId": delivery_id}).get("Item")
    if not delivery:
        return not_found(f"Delivery {delivery_id} was not found.")

    delivery = deserialize_item(delivery)

    findings_table = table_resource(findings_table_name())
    findings_response = findings_table.scan(
        FilterExpression=Attr("deliveryId").eq(delivery_id),
    )
    findings = deserialize_items(findings_response.get("Items", []))
    findings.sort(key=lambda item: item.get("receivedAt", ""), reverse=True)

    payload = _load_payload(delivery.get("payloadS3Key"))

    return json_response(
        200,
        {
            "delivery": delivery,
            "findings": findings,
            "payload": payload,
        },
    )
