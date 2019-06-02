from .mongodb import db as DB
from .settings import *

date_format = "%Y-%m-%dT%H:%M:%SZ"

db = {
    'agreements': DB.agreements,
    'interest_rates': DB.interest_rates,
    'issuances': DB.issuances,
    'supply-volume': DB.supply_volume,
    'borrow-volume': DB.borrow_volume,
    'repayment-volume': DB.repayment_volume,
    'outstanding-debt': DB.outstanding_debt,
    'collateral-ratio': DB.collateral_ratio,
    'top-borrowed-assets': DB.top_borrowed_assets,
    'top-supplied-assets': DB.top_supplied_assets,
    'top-outstanding-debt-assets': DB.outstanding_debt_assets,
    'top-repaid-assets': DB.top_repaid_assets,
    'top-borrowed-protocols': DB.top_borrowed_protocols,
    'top-supplied-protocols': DB.top_supplied_protocols,
    'top-repaid-protocols': DB.top_repaid_protocols,
    'metadata': DB.debt_issuance_metadata,
    'dipor': DB.dipor
}
headers = {
    'x-api-key': API_KEY
}
parameters = {
    'agreements': { 'limit': 100 },
    'interest_rates': {},
    'issuances': { 'limit': 100 },
    'supply-volume': {'intervalType': "Day"},
    'borrow-volume': {'intervalType': "Day"},
    'repayment-volume': {'intervalType': "Day"}
}
protocols = ['Dharma','MakerDao','Compound','CompoundV2']
urls = {
    'agreements': "https://api.loanscan.io/v1/agreements",
    'interest_rates': "https://api.loanscan.io/v1/interest-rates",
    'issuances': "https://api.loanscan.io/v1/issuances",
    'supply-volume': 'https://api.loanscan.io/v1/stats/supply-volume',
    'borrow-volume': 'https://api.loanscan.io/v1/stats/borrow-volume',
    'repayment-volume': 'https://api.loanscan.io/v1/stats/repayment-volume'
}

import requests
import json
from datetime import datetime

class ForbiddenAccess(Exception):
    status_code = 403
    def __init__(self, endpoint, message="Forbidden accesss"):
        Exception.__init__(self)
        self.message = message
        self.endpoint = endpoint

def get_response(endpoint, page = 1) -> dict:
    limit = parameters[endpoint].get('limit')

    if page and limit:
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
    if len(text) == 0:
        return {}
    print(len(text), "bytes")
    if response.status_code == requests.codes.forbidden:
        raise ForbiddenAccess(endpoint, "Forbidden access")
    
    payload = json.loads(text)

    if page and limit:
        del parameters[endpoint]['offset']
    return payload

def mark_event(endpoint):
    snapshot = {
        'snapshotTime': datetime.utcnow().strftime(date_format)
    }
    snapshot[endpoint] = get_response(endpoint, page = False)
    print("Inserting one ", endpoint, " ...")
    db[endpoint].insert_one(snapshot)

def scan_history(endpoint, page_n, stop_criteria):
    page = get_response(endpoint, page_n)
    if 'message' in page and not 'dataSlice' in page:
        print(endpoint, "warn", page['message'])
        return 
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

def scan_stats(endpoint, page_n, stop_criteria, sort_key = 'date'):
    print("Scanning stats ... ")
    page = get_response(endpoint, page_n)
    page_items = page

    end = False
    print("page items: ", len(page_items))
    for item in page_items:
        if not item:
            continue
        item_type = type(item)

        assert(item_type is dict, "Wrong item type. Expected: dict. Actual: ", item_type)
        
        if stop_criteria(item):
            print("Stopping @ ", item[sort_key])
            end = True
            return
        else:
            print("Saving ", item['date'])
            item['protocol'] = parameters[endpoint]['protocol']
            db[endpoint].insert_one(item)
    end = True
    #if not end:
    #    scan_stats(endpoint, page_n + 1, stop_criteria)

import pymongo

def get_latest_record_dot(endpoint, sort_key = "creationTime") -> str:
    stop_at = "1970-01-01T00:00:00Z" # first record ever possible
    _newest = db[endpoint].find({}).sort(sort_key, pymongo.DESCENDING).limit(1)
    for i in _newest:
        stop_at = i[sort_key]
    print(endpoint, " stops at ", stop_at)
    return stop_at

def download_history(endpoint, sort_key = "creationTime"):
    print("Downloading ", endpoint, " history ...")
    stop_at = get_latest_record_dot(endpoint, sort_key)
    scan_history(endpoint, page_n = 1,
        stop_criteria = lambda it: it[sort_key] <= stop_at)

def download_volume(endpoint):
    print("Downloading ", endpoint, " volume ...")
    
    stop_at = get_latest_record_dot(endpoint, 'date')

    for protocol in protocols:
        print(protocol," Stop at ", stop_at)
        parameters[endpoint]['protocol'] = protocol
        scan_stats(endpoint, page_n = 1,
            stop_criteria = lambda it: it['date'] <= stop_at)
        del parameters[endpoint]['protocol']

