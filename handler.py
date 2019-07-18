from bs4 import BeautifulSoup
import json
import requests
import logging 
import sys


def extracts_title(event, context):
    '''
     Handler that webscrapes a specified url and returns Page Title
    '''

    url = json.loads(event['body'])['url']
    try:
        source = requests.get(url)
    except requests.exceptions.RequestException as e:
        logging.info(e)
        sys.exit(1)

    soup = BeautifulSoup(source.text)
   
    body = {
        "title":soup.title.string
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response


