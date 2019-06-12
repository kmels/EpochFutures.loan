#!/usr/bin/python3
""" Demonstrating Flask, using APScheduler. """

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from datetime import *
from loanscan_io import *
from backend import *

import pymongo

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

sched.add_job(empty_cache,'interval',minutes=240)

def yield_plot(protocol, symbol, plot_past = True):
    yield_data = query_yield_data(protocol,symbol)

    print("Sorted yields .. ")
    print([y[2].strftime(date_format) for y in sorted(yield_data, key=lambda x: x[2])[0:5]])
    print("Getting deltas...")

    if plot_past:
        timespot_diffs = [timedelta(hours=1), timedelta(hours=2), timedelta(hours=4), timedelta(days=1), timedelta(days=7)]
    else:
        timespot_diffs = [timedelta(seconds=0)]

    time_now = datetime.utcnow()

    epochs = {}
    for d in timespot_diffs:
        epochs[int(d.total_seconds())] = []

    print("Getting curves...")
    maturities = [3600, 7200, 86400, 86400*28, 86400*30, 86400*90, 86400*180] # in seconds
    
    for delta in timespot_diffs:
        timespot = time_now - delta
        time_ago = int(delta.total_seconds())

        agreements_before = [y for y in yield_data if y[2] <= timespot] #y[2] is creation time
        age_sorted = sorted(agreements_before, key = lambda y: y[2], reverse=True)
        
        time_ago_sorted = sorted(age_sorted, key=lambda y: y[4]) #y[4] is loan term in seconds
                
        for m in maturities:
            curve_points = [(y[4],y[3]) for y in time_ago_sorted if m == y[4]]
            if len(curve_points) == 0:
                epochs[time_ago].append(0)
                continue
            
            same_time_ago_dots = [y for y in curve_points if y[0] == m]
            if len(same_time_ago_dots) > 0:
                avg = 1.0*sum([c[1] for c in same_time_ago_dots]) / len(same_time_ago_dots)
                epochs[time_ago].append( avg*10000 ) # converto decimal to basis points (1% = 0.01 = 100 bps )
            else:
                epochs[time_ago].append( curve_points[0][1]*10000)

    print("Yield plot")
    return (epochs, maturities, yield_data)

@app.route("/yield_curve/<protocol>/<symbol>")
def yield_curve(protocol, symbol):
    epochs, maturities, raw_data = yield_plot(protocol, symbol, plot_past = True)
    
    ts = ",".join([repr(term_pretty(t)) for t in maturities])
    es = ",".join([repr(term_pretty(t)) for t in epochs.keys()])
    epochs = dict((term_pretty(k) + " ago", val) for k, val in epochs.items())
    coin_protocols = dict([(coin[0],max(coin[5],coin[6])) for coin in coin_list])

    return render_template('yield_curve.html', terms="[%s]" % ts , epochs="[%s]" % es, curves=epochs, time_ago_days=maturities, agreement_list = raw_data, term_pretty = term_pretty, coin_protocols = coin_protocols)

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
        rates = list(DB.interest_rates.find({
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
def index(protocol = '*'):
    coin_list = []

    coins = list(DB.agreements.distinct("tokenSymbol"))

    latest_rates = list(DB.interest_rates.find({}).sort("snapshotTime", pymongo.DESCENDING).limit(1))
    rates_today = latest_rates[0].get('interest_rates')
    yesterday = datetime.utcnow() - timedelta(days=1)

    rates_1d_ago = list(DB.interest_rates.find({
            "snapshotTime": {"$gt": yesterday.strftime(date_format)}
        }).sort("snapshotTime", pymongo.DESCENDING).limit(1))

    for coin in coins:
        if not coin:
            continue
        epochs, maturities, raw_data = yield_plot("*", coin, plot_past = False)
        ts = ",".join([repr(term_pretty(t)) for t in maturities])
        es = ",".join([repr(term_pretty(t)) for t in epochs.keys()])
        epochs = dict((term_pretty(k) + " ago", val) for k, val in epochs.items())

        borrow_rates = dict([(p['provider'],"%.2f" % (r['rate']*100)) for p in rates_today for r in p.get('borrow',[]) if r['symbol'] == coin])
        lend_rates = dict([(p['provider'],"%.2f " % (r['rate']*100)) for p in rates_today for r in p.get('supply',[]) if r['symbol'] == coin])

        coin_list.append((coin, epochs, maturities, ts, es, borrow_rates, lend_rates))

    if protocol == '*':
        coin_protocols = dict([(coin[0], set(list(coin[5].keys()) + list(coin[6].keys()))) for coin in coin_list])
        coin_protocol_len = dict([(coin, len(protocols)) for coin,protocols in coin_protocols.items()])
    else:
        coin_protocol_len = dict([(coin[0],1) for coin in coin_list])
        coin_protocols = dict([(coin[0], protocol) for coin in coin_list])

    return render_template('index.html', coin_list = coin_list, protocol = protocol, protocol_len = coin_protocol_len, protocols = coin_protocols)
    
if __name__ == "__main__":
    app.run(debug=True)
