import json

from shared.config import evidence_bucket_name, findings_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import not_found, json_response
from shared.storage import s3_client


def lambda_handler(event, context):
    finding_id = (event.get("pathParameters") or {}).get("findingId")
    if not finding_id:
        return not_found("Finding id was not provided.")

    table = table_resource(findings_table_name())
    response = table.get_item(Key={"eventId": finding_id})
    item = response.get("Item")
    if not item:
        return not_found(f"Finding {finding_id} was not found.")

    finding = deserialize_item(item)
    payload_key = finding.get("payloadS3Key")

    payload_body = None
    if payload_key:
        payload_response = s3_client.get_object(
            Bucket=evidence_bucket_name(),
            Key=payload_key,
        )
        payload_body = payload_response["Body"].read().decode("utf-8")

    try:
        parsed_payload = json.loads(payload_body) if payload_body else None
    except json.JSONDecodeError:
        parsed_payload = {"rawPayload": payload_body}

    return json_response(200, {"finding": finding, "payload": parsed_payload})
