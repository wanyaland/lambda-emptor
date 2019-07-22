"""
This modules handles extraction of page title
and storage of response to s3 and title to dynamoDB services
"""

import asyncio
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
        identifier = kwargs['identifier']
        url = kwargs['url']
        state = kwargs['state']
        client.put_item(
            TableName=table_name, 
            Item= {
                'identifier':{'S':identifier},
                'url':{'S':url},
                'state':{'S':state}
            }
        )
    except Exception as exc:
        logger.info(exc)
        sys.exit()
        return False

    return True


def get_data(table, identifier):
    try:
        data = client.get_item(TableName=table, key={"identifier": identifier})
    except Exception as exc:
        logger.info('get_data error')
        logger.info(exc)
        sys.exit()
    logger.info("{} returned by identifier {}".format(data, identifier))
    return data


def create_identifier(event, context):
    """
    Function that stores given url and creates an identifier that acts 
    as the key 
    """
    url = json.loads(event["body"])["url"]
    request_identifier = str(uuid.uuid4())

    # Store url keyed by identifier as well as state in Dynamo DB
    dynamodb_success = save_to_dynamo_db(
        URL_TABLE, identifier=request_identifier, url=url, state="PENDING"
    )

    if dynamodb_success:
        logger.info("{} stored in table {}".format(url, URL_TABLE))
    else:
        logger.info("{} failed to get stored in {}".format(url, URL_TABLE))

    # invoke extracts_title asynchronously
    lambda_client = boto3.client("lambda")
    response = lambda_client.invoke(
        FunctionName='lambda-emptor-dev-extracts_title',
        InvocationType='Event'
    )

    logger.info('Response {} from invoked asynchronous function '.format(response))

    body = {"url_identifier": request_identifier}

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response


def extracts_title(event, context):
    """ Handler that scrapes a web page via given url and
        returns json body that contains the title of the web page
    """
    logger.info("Event received: {}".format(json.dumps(event)))
    body = {
        "message": "{} - from the other function". format(event),
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }
    
    return response
    '''
    data = get_data(identifier)
    url = data['url']
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
        logger.info("{} added to {} bucket".format(json.dumps(body, indent=2), BUCKET))
    else:
        logger.info(
            "Failed to add {}  to {} bucket".format(json.dumps(body, indent=2), BUCKET)
        )

    # Store extracted title as a record in Dynamo DB
    dynamodb_success = store_title_dynamo_db(soup.title.string)

    if dynamodb_success:
        logger.info("{} stored in table {}".format(soup.title.string, TITLES_TABLE))
    else:
        logger.info(
            "{} failed to get stored in {}".format(soup.title.string, TITLES_TABLE)
        )

    body = {"title": soup.title.string, "s3_url": s3_url}
    response = {"statusCode": 200, "body": json.dumps(body)}

    logger.info("Response: {}".format(json.dumps(response)))

    return response
    '''
