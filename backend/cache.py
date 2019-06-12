from functools import lru_cache

from loanscan_io import *

@lru_cache(maxsize=256)
def coin_agreement_protocols(symbol):
    return list(DB.agreements.distinct("agreementProtocol",{"tokenSymbol": symbol}))

@lru_cache(maxsize=1)
def yield_agreement_data():
    """Fetch all the agreements from database and projects into a list of tuples"""
    print("Getting agreements...")
    agreements = list(DB.agreements.find({"$where": "this.maturityDate > this.creationTime"}).sort("maturityTime", pymongo.DESCENDING))
    print("Done: ", len(agreements))

    print("Getting yields")
    def collateral(agreement):
        colat = agreement.get('effectiveCollateral', {})
        return f"{colat.get('currentAmount', '')} {colat.get('tokenSymbol', '')}"

    def principal(agreement):
        issuances = agreement.get('issuances',[])
        return ",".join([f"{i.get('principal','')} {i.get('tokenSymbol','')}" for i in issuances])

    yield_data = [(a["loanProtocol"], a["tokenSymbol"],datetime.strptime(a["creationTime"],date_format), round(a["interestRate"],5),
                   term_seconds(a["loanTerm"]), datetime.strptime(a["maturityDate"], date_format), collateral(a), principal(a)) for a in agreements]
    
    return yield_data
    
@lru_cache(maxsize=256)
def query_yield_data(protocol,symbol):
    """
    Queries yield data
    """
    _all_data = yield_agreement_data()

    if symbol == "*" and protocol == "*":
        return _all_data

    if protocol == "*":
        return [y for y in _all_data if y[1] == symbol]

    if symbol == "*":
        return [y for y in _all_data if y[0] == protocol]

    return [y for y in _all_data if y[1] == symbol and y[0] == protocol]
    
def empty_cache():
    print("Recalculating yield agreement  data")
    yield_agreement_data.cache_clear()

@lru_cache(maxsize=128)
def coin_list():
    return []
