#!/usr/bin/python3
""" Demonstrating Flask, using APScheduler. """

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from loan_sdk.endpoints import *

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
#sched.add_job(sense_rates,'interval',minutes=60)
#sched.add_job(sense_history,'interval',minutes=240)
#sched.add_job(sense_volume,'interval',minutes=1440)
sched.start()

from flask import render_template, send_from_directory

app = Flask(__name__, template_folder='html', static_url_path='/static')

from loan_sdk.mongodb import *
import pymongo

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

@app.route("/")
def home():
    print("Getting agreements...")
    agreements = list(db.agreements.find({"$where": "this.maturityDate > this.creationTime"}).sort("maturityTime", pymongo.DESCENDING))

    print("Getting yields")
    yield_data = [(agreement["loanProtocol"], agreement["tokenSymbol"],datetime.strptime(agreement["creationTime"],date_format), agreement["interestRate"],
                   term_minutes(agreement["loanTerm"]), datetime.strptime(agreement["maturityDate"], date_format)) for agreement in agreements]

    # filter by token protocol (temporarily)
    yield_data = [y for y in yield_data if y[1] == "DAI"]

    print("Getting deltas...")
    timespot_diffs = [timedelta(days=1), timedelta(days=7), timedelta(days=15), timedelta(days=21), timedelta(days=30), timedelta(days=45), timedelta(days=60), timedelta(days=90)]#, timedelta(days=90)]
    time_now = datetime.utcnow()

    yields = {}
    for d in timespot_diffs:
        yields[d.days] = []

    print("Getting curves...")
    maturities = [1,7,15,21,30,45,60,90,120,150,180,210,240,270,360]
    
    for delta in timespot_diffs:
        timespot = time_now - delta
        nearest_yields = [y for y in yield_data if timespot <= y[2]]
        maturity_sorted = sorted(nearest_yields, key=lambda y: y[2])

        curve_points = maturity_sorted
        
        for m in maturities:
            curve_points = [y for y in curve_points if y[4] >= 1440*m]
            if len(curve_points) == 0:
                continue
            yields[delta.days].append( curve_points[0][3]*10000 )
            curve_points = [y for y in curve_points if y[4] >= 1440*m]
            print(delta.days, m, [y[3] for y in curve_points[0:5]])

    return render_template('home.html', curves=yields, maturity_days=maturities)

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

        print(t.strftime(date_format),"Found rates",len(rates))
        for rate in rates:
            for interest_rate in rate['interest_rates']:
                if interest_rate['provider'] == protocol:

                    for borrow in interest_rate['borrow']:
                        if borrow['symbol'].upper() == symbol.upper():
                            borrow_curve_dots.append(borrow['rate']*10000)
                    for supply in interest_rate['supply']:
                        if supply['symbol'].upper() == symbol.upper():
                            supply_curve_dots.append(supply['rate']*10000)

    print("borrow dots",borrow_curve_dots)
    print("supply dots",supply_curve_dots)

    return render_template('rate_spread.html', borrow_dots=",".join(map(str,borrow_curve_dots)), supply_dots=",".join(map(str, supply_curve_dots)))

if __name__ == "__main__":
    app.run(debug=True)
