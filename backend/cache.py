from functools import lru_cache

from loanscan_io import *

@lru_cache(maxsize=1)
def yield_agreement_data():
    """Fetch all the agreements from database and projects into a list of tuples"""
    print("Getting agreements...")
    agreements = list(DB.agreements.find({"$where": "this.maturityDate > this.creationTime"}).sort("maturityTime", pymongo.DESCENDING))

    print("Getting yields")
    def collateral(agreement):
        colat = agreement.get('effectiveCollateral', {})
        return f"{colat.get('currentAmount', '')} {colat.get('tokenSymbol', '')}"

    yield_data = [(agreement["loanProtocol"], agreement["tokenSymbol"],datetime.strptime(agreement["creationTime"],date_format), agreement["interestRate"],
                   term_minutes(agreement["loanTerm"]), datetime.strptime(agreement["maturityDate"], date_format), collateral(agreement)) for agreement in agreements]
    
    return yield_data
    
@lru_cache(maxsize=256)
def query_yield_data(protocol,symbol):
    """
    Queries yield data
    """
    _all_data = yield_agreement_data()
    
    if symbol == "*" and protocol == "*":
        return _all_data
    
    if symbol != "*" and protocol != "*":
        return [y for y in _all_data if y[1] == symbol and y[0] == protocol]
    
    if symbol == "*":
        return [y for y in _all_data if y[0] == protocol]
    
    if protocol == "*":
        return [y for y in _all_data if y[1] == symbol]
    
def empty_cache():
    print("Recalculating yield agreement  data")
    yield_agreement_data.cache_clear()

@lru_cache(maxsize=128)
def coin_list():
    return []
