import json

from shared.config import alert_archive_bucket_name, spend_cases_table_name
from shared.dynamo import deserialize_item, table_resource
from shared.http import not_found, json_response
from shared.storage import s3_client


def lambda_handler(event, context):
    case_id = (event.get("pathParameters") or {}).get("caseId")
    if not case_id:
        return not_found("Case id was not provided.")

    table = table_resource(spend_cases_table_name())
    response = table.get_item(Key={"caseId": case_id})
    item = response.get("Item")
    if not item:
        return not_found(f"Case {case_id} was not found.")

    case_summary = deserialize_item(item)
    payload_key = case_summary.get("payloadS3Key")

    payload_body = None
    if payload_key:
        payload_response = s3_client.get_object(
            Bucket=alert_archive_bucket_name(),
            Key=payload_key,
        )
        payload_body = payload_response["Body"].read().decode("utf-8")

    try:
        parsed_payload = json.loads(payload_body) if payload_body else None
    except json.JSONDecodeError:
        parsed_payload = {"rawPayload": payload_body}

    return json_response(
        200,
        {
            "case": case_summary,
            "payload": parsed_payload,
        },
    )
