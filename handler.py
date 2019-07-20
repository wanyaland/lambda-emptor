"""
This modules handles extraction of page title
and storage of response to s3 and title to dynamoDB services
"""

import json
import logging
import sys
import os


import boto3
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TITLES_TABLE = os.environ['TITLES_TABLE']
BUCKET = os.environ['BUCKET']

def store_response_to_s3(title, response):
    """Function that handles storage of the handler response
    :param bucket: s3.Bucket
    :param key: string
    :param response: dict
    :return: tuple of True if response is added to bucket else False
    and url of stored object
    """
    #Store response body to the s3 bucket
    try:
        s3_client = boto3.client('s3')
        key = 'paged_title_{}'.format(title)
        s3_client.put_object(Bucket=BUCKET, Body=bytes(json.dumps(response, indent=2).encode('utf-8')), Key=key)
        s3_url = '%s/%s/%s' % (s3_client.meta.endpoint_url, BUCKET, key)

    except Exception as exc:
        logger.error(exc)
        return (False, None)

    return (True, s3_url)

def store_title_dynamo_db(title):
    """Handles insertion of title in DynamoDB
    :param title: string
    :return: True if given title is saved in the dynamodb Table
    """
    try:
        client = boto3.client('dynamodb')
        client.put_item(
            TableName=TITLES_TABLE,
            Item={
                'titleId':{'S':title}
            }
        )
    except Exception as exc:
        logger.info(exc)
        return False

    return True


def extracts_title(event, context):
    """ Handler that scrapes a web page via given url and
        returns json body that contains the title of the web page
    """
    logger.info('Event received: {}'.format(json.dumps(event)))
    url = json.loads(event['body'])['url']
    try:
        source = requests.get(url)
    except HTTPError as exc:
        logger.info(exc)
        sys.exit(1)

    soup = BeautifulSoup(source.text, 'html.parser')

    body = {
        "title": soup.title.string,
    }


    #Store response body to s3 bucket
    extracted_title = soup.title.string
    s3_success, s3_url = store_response_to_s3(extracted_title, body)
    if s3_success:
        logger.info('{} added to {} bucket'.format(json.dumps(body, indent=2), BUCKET))
    else:
        logger.info('Failed to add {}  to {} bucket'.format(json.dumps(body, indent=2), BUCKET))

    #Store extracted title as a record in Dynamo DB
    dynamodb_success = store_title_dynamo_db(soup.title.string)

    if dynamodb_success:
        logger.info('{} stored in table {}'.format(soup.title.string, TITLES_TABLE))
    else:
        logger.info('{} failed to get stored in {}'.format(soup.title.string, TITLES_TABLE))

    body = {
        "title": soup.title.string,
        "s3_url": s3_url
    }
    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    logger.info('Response: {}'.format(json.dumps(response)))


    return response
