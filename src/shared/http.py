import json


def _headers():
    return {
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,POST,OPTIONS",
        "access-control-allow-headers": "content-type,x-correlation-id,x-source-token,x-github-delivery,x-github-event,x-hub-signature-256",
    }


def json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": _headers(),
        "body": json.dumps(body),
    }


def bad_request(message):
    return json_response(400, {"message": message})


def not_found(message):
    return json_response(404, {"message": message})


def unauthorized(message):
    return json_response(401, {"message": message})
