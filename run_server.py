#!/usr/bin/python3
""" Demonstrating Flask, using APScheduler. """

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from loanscan_io.endpoints import *
from loanscan_io.mongodb import *

from functools import lru_cache

def sense_history():
    download_history('issuances')
    download_history('agreements')

def sense_rates():
    mark_event('interest_rates')

def sense_volume():
    download_volume('supply-volume')
    download_volume('borrow-volume')
    download_volume('repayment-volume')
    #download_volume('outstanding-debt')

sched = BackgroundScheduler(daemon=True)
sched.add_job(sense_rates,'interval',minutes=60)
sched.add_job(sense_history,'interval',minutes=240)
sched.add_job(sense_volume,'interval',minutes=1440)
sched.start()

from flask import render_template, send_from_directory

app = Flask(__name__, template_folder='html', static_url_path='/static')

import pymongo

def term_pretty(seconds):
    day = 3600*24
    if seconds < day:
        return "%dh" % (seconds/3600)
    return "%dd" % (seconds/day)

def term_minutes(term):
    parts = term.split(".")
    
    if len(parts) == 1:
        days = 0
        subparts = parts[0].split(":")
    else:
        days = int(parts[0])
        subparts = parts[1].split(":")

    hours = int(subparts[0])
    minutes = int(subparts[1])
        
    return days*1440 + hours*60 + minutes

@lru_cache(maxsize=256)
def yield_agreement_data(protocol,symbol):
    print("Getting agreements...")
    agreements = list(db.agreements.find({"$where": "this.maturityDate > this.creationTime"}).sort("maturityTime", pymongo.DESCENDING))

    print("Getting yields")
    yield_data = [(agreement["loanProtocol"], agreement["tokenSymbol"],datetime.strptime(agreement["creationTime"],date_format), agreement["interestRate"],
                   term_minutes(agreement["loanTerm"]), datetime.strptime(agreement["maturityDate"], date_format)) for agreement in agreements]

    if symbol == "*" and protocol == "*":
        return yield_data
    
    if symbol != "*" and protocol != "*":
        return [y for y in yield_data if y[1] == symbol and y[0] == protocol]
    
    if symbol == "*":
        return [y for y in yield_data if y[0] == protocol]
    
    if protocol == "*":
        return [y for y in yield_data if y[1] == symbol]
    
def empty_cache():
    print("Clearing cache")
    yield_agreement_data.cache_clear()

sched.add_job(empty_cache,'interval',minutes=240)

@app.route("/yield_curve/<protocol>/<symbol>")
def yield_curve(protocol, symbol):
    yield_data = yield_agreement_data(protocol,symbol)

    print("Sorted yields .. ")
    print([y[2].strftime(date_format) for y in sorted(yield_data, key=lambda x: x[2])[0:5]])
    print("Getting deltas...")
    timespot_diffs = [timedelta(minutes=30), timedelta(hours=1), timedelta(hours=2), timedelta(days=1), timedelta(days=7), timedelta(days=15), timedelta(days=21), timedelta(days=28), timedelta(days=30), timedelta(days=60), timedelta(days=90), timedelta(days=180), timedelta(days=360)]
    time_now = datetime.utcnow()

    epochs = {}
    for d in timespot_diffs:
        epochs[int(d.total_seconds())] = []

    print("Getting curves...")
    maturities = [3600, 7200, 86400, 86400*28, 86400*30, 86400*90, 86400*180]
    
    for ti, delta in enumerate(timespot_diffs[0:-1]):
        timespot = time_now - delta
        time_ago = int(delta.total_seconds())
        next_timespot = time_now - timespot_diffs[ti+1]
        agreements_before = [y for y in yield_data if y[2] <= timespot] #y[2] is creation time
        age_sorted = sorted(agreements_before, key = lambda y: y[2], reverse=True)
        
        time_ago_sorted = sorted(age_sorted, key=lambda y: y[4]) #y[4] is loan term
                
        for m in maturities:
            curve_points = [(60*y[4],y[3]) for y in time_ago_sorted if m == 60*y[4]] # m is seconds, y[4] is minutes
            if len(curve_points) == 0:
                epochs[time_ago].append(0)
                continue
            
            same_time_ago_dots = [y for y in curve_points if y[0] == m]
            if len(same_time_ago_dots) > 0:
                avg = 1.0*sum([c[1] for c in same_time_ago_dots]) / len(same_time_ago_dots)
                epochs[time_ago].append( avg*10000 ) # converto decimal to basis points (1% = 0.01 = 100 bps )
            else:
                epochs[time_ago].append( curve_points[0][1]*10000)

    ts = ",".join([repr(term_pretty(t)) for t in maturities])
    return render_template('yield_curve.html', terms="[%s]" % ts , curves=epochs, time_ago_days=maturities)

from datetime import *

@app.route("/rate_spread/<protocol>/<symbol>")
def rate_curve(protocol, symbol):
    # curve points
    # 30d, 2y, 10y, 30y AHEAD
    # if 30y == 3d => 15m, 6h, 1d, 3d AHEAD
    timespot_diffs = [timedelta(days=3), timedelta(days=1), timedelta(minutes=15), timedelta(hours=6)]
    time_now = datetime.utcnow()
    timespots = sorted([time_now - diff for diff in timespot_diffs])
    borrow_curve_dots = []
    supply_curve_dots = []
    for t in timespots:
        rates = list(db.interest_rates.find({
            "snapshotTime": {"$lt": t.strftime(date_format)}
        }).sort("snapshotTime", pymongo.DESCENDING).limit(1))

        for rate in rates:
            for interest_rate in rate['interest_rates']:
                if interest_rate['provider'] == protocol:

                    for borrow in interest_rate['borrow']:
                        if borrow['symbol'].upper() == symbol.upper():
                            borrow_curve_dots.append(borrow['rate']*10000)
                    for supply in interest_rate['supply']:
                        if supply['symbol'].upper() == symbol.upper():
                            supply_curve_dots.append(supply['rate']*10000)

    return render_template('rate_spread.html', borrow_dots=",".join(map(str,borrow_curve_dots)), supply_dots=",".join(map(str, supply_curve_dots)))

@app.route("/")
def index():
    coin_list = list(db.agreements.distinct("tokenSymbol"))
    return render_template('index.html', coin_list = enumerate(coin_list))
    
if __name__ == "__main__":
    app.run(debug=True)
