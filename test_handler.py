import json
import os
import time

import boto3
import mock 

from moto import mock_s3,mock_dynamodb2,mock_dynamodbstream
from handler import create_identifier,extracts_title

from contextlib import contextmanager


BUCKET = os.environ['BUCKET']
URL_TABLE = os.environ['URL_TABLE']

@contextmanager
def do_test_setup():
    with mock_s3():
        with mock_dynamodb2():
            set_up_s3()
            set_up_dynamodb()
            yield
                  
def set_up_s3():
    conn = boto3.resource('s3',region_name='us-east-2')
    conn.create_bucket(Bucket=BUCKET)

def set_up_dynamodb():
    client = boto3.client('dynamodb', 
                           region_name='us-east-2')
    client.create_table(
        AttributeDefinitions=[
            {
                'AttributeName':'identifier',
                'AttributeType': 'S'
            }
        ],
        KeySchema = [
            {
                'AttributeName':'identifier',
                'KeyType':'HASH'
            }
        ],
        TableName = URL_TABLE,
        ProvisionedThroughput = {
            'ReadCapacityUnits':10,
            'WriteCapacityUnits':10
        },
        StreamSpecification = {
            'StreamViewType' : 'NEW_IMAGE'
        }
    )
    
def create_http_event():
    json_data = {
        'body': '{"url":"http://google.com"}',
    }
    return json_data


def test_create_identifier():
    with do_test_setup():
        response = create_identifier(create_http_event(),None)
        assert response['statusCode'] == 200

@mock_dynamodbstream
def test_extracts_title():
    with do_test_setup():
        response = create_identifier(create_http_event(),None)
        identifier = json.loads(response['body'])['url_identifier']
        #extracts_title(response,None)
        client = boto3.client('dynamodb')
        record = client.get_item(TableName=URL_TABLE, Key={"identifier": {"S": identifier}})
        assert record['Item']['status']['S'] == 'PROCESSED'

        





