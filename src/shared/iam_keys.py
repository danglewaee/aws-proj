from botocore.exceptions import ClientError
import boto3


iam_client = boto3.client("iam")


def get_access_key_details(access_key_id):
    try:
        response = iam_client.get_access_key_last_used(AccessKeyId=access_key_id)
        return {
            "exists": True,
            "userName": response.get("UserName"),
            "lastUsed": response.get("AccessKeyLastUsed", {}).get("LastUsedDate"),
            "serviceName": response.get("AccessKeyLastUsed", {}).get("ServiceName"),
            "region": response.get("AccessKeyLastUsed", {}).get("Region"),
        }
    except ClientError:
        return {
            "exists": False,
            "userName": None,
            "lastUsed": None,
            "serviceName": None,
            "region": None,
        }


def disable_access_key(user_name, access_key_id):
    iam_client.update_access_key(
        UserName=user_name,
        AccessKeyId=access_key_id,
        Status="Inactive",
    )
