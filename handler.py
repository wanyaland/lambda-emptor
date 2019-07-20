"""
This modules handles extraction of page title
and storage of response to s3 and title to dynamoDB services
"""
import json
import logging
import sys
import requests
import boto3


from bs4 import BeautifulSoup
from botocore.exceptions import ClientError
from requests.exceptions import HTTPError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def store_response_to_s3(bucket,title,response):
    """Function that handles storage of the handler response
    :param bucket: s3.Bucket
    :param key: string
    :param response: dict
    :return: True if response is added to bucket else False
    """
    #Store response body to the s3 bucket
    try:
        key = 'paged_title_{}'.format(title)
        bucket.put_object(Body=bytes(json.dumps(response,indent=2).encode('utf-8')),Key=key)
    except Exception as e:
        logger.error(e)
        return False
    
    return True


def extracts_title(event, context):
    """ Handler that scrapes a web page via given url and
        returns json body that contains the title of the web page
    """
    s3 = boto3.resource('s3')
    bucket_name = 'emptor-title'
    bucket = s3.Bucket(bucket_name)
    logger.info('Event received: {}'.format(json.dumps(event)))
    url = json.loads(event['body'])['url']
    try:
        source = requests.get(url)
    except HTTPError as exc:
        logger.info(exc)
        sys.exit(1)

    soup = BeautifulSoup(source.text, 'html.parser')

    body = {
        "title": soup.title.string
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    #Store response to s3 bucket
    success = store_response_to_s3(bucket,soup.title.string,response)
    if success:
        logger.info('{} added to {} bucket'.format(json.dumps(response,indent=2),bucket_name))
    else:
        logger.info('Failed to add {}  to {} bucket'.format(json.dumps(response,indent=2),bucket_name))

    #Store extracted title as a record in Dynamo DB


    logger.info('Response: {}'.format(json.dumps(response)))

    return response
