import json
import logging
import sys
import requests


from bs4 import BeautifulSoup

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def extracts_title(event, context):
    """ Handler that scrapes a web page via given url and
        returns json body that contains the title of the web page
    """
    logger.info('Event received: {}'.format(json.dumps(event)))
    url = json.loads(event['body'])['url']
    try:
        source = requests.get(url)
    except requests.exceptions.RequestException as exc:
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

    logger.info('Response: {}'.format(json.dumps(response)))

    return response
