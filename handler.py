"""
This modules handles extraction of page title
and storage of response to s3 and title to dynamoDB services
"""

import json
import logging
import sys
import os
import uuid


import boto3
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError


client = boto3.client("dynamodb")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

URL_TABLE = os.environ["URL_TABLE"]
BUCKET = os.environ["BUCKET"]
SERVICE = os.environ["SERVICE"]
STAGING = os.environ["STAGING"]


def store_response_to_s3(title, response):
    """Function that handles storage of the handler response
    :param bucket: s3.Bucket
    :param key: string
    :param response: dict
    :return: tuple of True if response is added to bucket else False
    and url of stored object
    """
    # Store response body to the s3 bucket
    try:
        s3_client = boto3.client("s3")
        key = "paged_title_{}".format(title)
        s3_client.put_object(
            Bucket=BUCKET,
            Body=bytes(json.dumps(response, indent=2).encode("utf-8")),
            Key=key,
        )
        s3_url = "%s/%s/%s" % (s3_client.meta.endpoint_url, BUCKET, key)

    except Exception as exc:
        logger.error(exc)
        return (False, None)

    return (True, s3_url)


def save_to_dynamo_db(table_name, **kwargs):
    """Saves record to DynamoDB Table
    :param table_name: Table to be saved to
    :return: True if saved to dynamo_db
    """
    try:
        identifier = kwargs["identifier"]
        url = kwargs["url"]
        state = kwargs["status"]
        client.put_item(
            TableName=table_name,
            Item={
                "identifier": {"S": identifier},
                "url": {"S": url},
                "status": {"S": state},
            },
        )
    except Exception as exc:
        logger.info(exc)
        sys.exit()

    return True


def update_dynamo_db_record(table_name, identifier, attributes, **kwargs):
    """Function that updates a given record in aws dynamo_db
       with s3_url , status and extracted title
       :param table_name: Table to be updated
       :identifier: Key that identifies the record
       :attributes: List of attributes existing in record
       :**kwargs: keyword args for records to be updated in the table
       that contains attribute and value to be updated
    """
    try:
        for key, value in kwargs.items():
            attribute_name = "#{}".format(str(key[:2])) if key in attributes else key
            update_params = {
                "TableName": table_name,
                "Key": {"identifier": {"S": identifier}},
                "UpdateExpression": "SET {} = :val1".format(attribute_name),
                "ExpressionAttributeValues": {":val1": value},
            }
            if key in attributes:
                update_params["ExpressionAttributeNames"] = {attribute_name: key}

            client.update_item(**update_params)

    except Exception as exc:
        logger.info(exc)
        sys.exit()
    return True


def get_data(table, identifier):
    try:
        data = client.get_item(TableName=table, Key={"identifier": {"S": identifier}})
    except Exception as exc:
        logger.info("get_data error")
        logger.info(exc)
        sys.exit()
    logger.info("{} returned by identifier {}".format(data, identifier))
    return data


def create_identifier(event, context):
    """
    Handler  that stores given url , creates an identifier that acts 
    as the key and invokes the extract_title handler asynchronously
    """
    url = json.loads(event["body"])["url"]
    request_identifier = str(uuid.uuid4())

    # Store url keyed by identifier as well as pending state in Dynamo DB
    dynamodb_success = save_to_dynamo_db(
        URL_TABLE, identifier=request_identifier, url=url, status="PENDING"
    )

    if dynamodb_success:
        logger.info("{} stored in table {}".format(url, URL_TABLE))
    else:
        logger.info("{} failed to get stored in {}".format(url, URL_TABLE))

    """
    # invoke extracts_title asynchronously
    lambda_client = boto3.client("lambda")
    payload = {"identifier": request_identifier}
    lambda_client.invoke(
        FunctionName="{}-{}-extracts_title".format(SERVICE, STAGING),
        InvocationType="Event",
        Payload=json.dumps(payload),
    )
    """

    body = {"url_identifier": request_identifier}

    response = {"statusCode": 200, "body": json.dumps(body)}

    logger.info("Response {} from create_identifier handler ".format(response))

    return response


def extracts_title(event, context):
    """ Handler that is invoked by DB stream activity .
        Scrapes a web page via given identifier tied to a url
        and returns json body that contains the title of the web page
    """
    logger.info("Event received: {}".format(event))
    for record in event.get("Records"):
        if record.get("eventName") == "INSERT":
            identifier = record["dynamodb"]["NewImage"]["identifier"]["S"]
            data = get_data(URL_TABLE, identifier)
            logger.info(data)
            url = data["Item"]["url"]["S"]
            # url = json.loads(event['body'])['url']
            try:
                source = requests.get(url)
            except HTTPError as exc:
                logger.info(exc)
                sys.exit(1)
            soup = BeautifulSoup(source.text, "html.parser")
            body = {"title": soup.title.string}
            # Store response body to s3 bucket
            extracted_title = soup.title.string
            s3_success, s3_url = store_response_to_s3(extracted_title, body)
            if s3_success:
                logger.info(
                    "{} added to {} bucket".format(json.dumps(body, indent=2), BUCKET)
                )
            else:
                logger.info(
                    "Failed to add {}  to {} bucket".format(
                        json.dumps(body, indent=2), BUCKET
                    )
                )

            # Update record identified by identifier key

            success_updated = update_dynamo_db_record(
                URL_TABLE,
                identifier,
                ["status", "url"],
                title={"S": soup.title.string},
                s3_url={"S": s3_url},
                status={"S": "PROCESSED"},
            )

            if success_updated:
                logger.info("{} record updated".format(identifier))
            else:
                logger.info(
                    "Failed to update record identified by {}".format(identifier)
                )
