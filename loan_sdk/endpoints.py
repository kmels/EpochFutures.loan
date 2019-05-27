from .mongodb import db as DB
from .settings import *

db = {
    'agreements': DB.agreements,
    'interest_rates': DB.interest_rates,
    'issuances': DB.issuances
}
headers = {
    'x-api-key': API_KEY
}
parameters = {
    'agreements': { 'limit': 100 },
    'interest_rates': {},
    'issuances': { 'limit': 100 }
}
urls = {
    'agreements': "https://api.loanscan.io/v1/agreements",
    'interest_rates': "https://api.loanscan.io/v1/interest-rates",
    'issuances': "https://api.loanscan.io/v1/issuances"
}

import requests
import json
from datetime import datetime

def get_response(endpoint, page = 1) -> dict:
    limit = parameters[endpoint].get('limit')

    if page:
        offset = (page-1)*limit
        parameters[endpoint]['offset'] = offset
    url = urls[endpoint]

    print("Getting ", url, " ...")
    response = requests.get(
        url,
        headers = headers,
        params = parameters[endpoint]
    )
    text = response.content
    print(len(text), " bytes")
    payload = json.loads(text)
    if page:
        del parameters[endpoint]['offset']
    return payload

def mark_event(endpoint):
    snapshot = {
        'snapshotTime': datetime.utcnow().strftime("%Y-%m-%DT%H:%M:%SZ")
    }
    snapshot[endpoint] = get_response(endpoint, page = False)
    print("Inserting one ", endpoint, " ...")
    db[endpoint].insert_one(snapshot)

# Used for time series
def scan_history(endpoint, page_n, stop_criteria):
    page = get_response(endpoint, page_n)
    page_items = page['dataSlice']

    end = False
    for item in page_items:
        if not item:
            continue
        if stop_criteria(item):
            print("Stopping @ ", item['creationTime'])
            end = True
            return
        else:
            print("Saving ", item['creationTime'])
            db[endpoint].insert_one(item)
    if not end:
        scan_history(endpoint, page_n + 1, stop_criteria)

import pymongo
def download_issuances():
    """Returns sorted by date"""
    endpoint = 'issuances'
    stop_at = "1970-01-01T00:00:00Z" # first record ever
    _newest = db[endpoint].find({}).sort("creationTime", pymongo.DESCENDING).limit(1)
    for i in _newest:
        stop_at = i['creationTime']
    print("Stop at ", stop_at)
    scan_history(endpoint, page_n = 1,
        stop_criteria = lambda it: it['creationTime'] <= stop_at)

def download_agreements():
    """Returns sorted by date"""
    endpoint = 'agreements'
    stop_at = "1970-01-01T00:00:00Z" # first record ever
    _newest = db[endpoint].find({}).sort("creationTime", pymongo.DESCENDING).limit(1)
    for i in _newest:
        stop_at = i['creationTime']
    print("Stop at ", stop_at)
    scan_history(endpoint, page_n = 1,
        stop_criteria = lambda it: it['creationTime'] <= stop_at)
