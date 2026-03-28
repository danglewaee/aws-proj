from decimal import Decimal

import boto3


_dynamodb = boto3.resource("dynamodb")


def table_resource(table_name):
    return _dynamodb.Table(table_name)


def deserialize_item(item):
    if isinstance(item, list):
        return [deserialize_item(value) for value in item]

    if isinstance(item, dict):
        return {key: deserialize_item(value) for key, value in item.items()}

    if isinstance(item, Decimal):
        if item % 1 == 0:
            return int(item)
        return float(item)

    return item


def deserialize_items(items):
    return [deserialize_item(item) for item in items]
