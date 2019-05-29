#!/usr/bin/python3
""" Demonstrating Flask, using APScheduler. """

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from loan_sdk.endpoints import *

def sense_history():
    """ Function for test purposes. """
    print("Scheduler is alive!")

    download_issuances()
    print("Scheduler is alive and well!")
    download_agreements()

def sense_rates():
    mark_event('interest_rates')

def sense_volume():
    download_volume('supply-volume')
    download_volume('borrow-volume')
    download_volume('repayment-volume')
    download_volume('outstanding-debt')

sched = BackgroundScheduler(daemon=True)
sched.add_job(sense_rates,'interval',minutes=60)
sched.add_job(sense_history,'interval',minutes=240)
sched.add_job(sense_volume,'interval',minutes=1440)
sched.start()

from flask import render_template, send_from_directory

app = Flask(__name__, template_folder='html', static_url_path='/static')

from loan_sdk.mongodb import *
import pymongo

@app.route("/")
def home():
    rates = db.interest_rates.find({}).sort("snapshotTime",pymongo.DESCENDING)
    return render_template('curve.html', rates=list(rates))

from datetime import *

@app.route("/yield_curve/<protocol>/<symbol>")
def yield_curve(protocol, symbol):
    # curve points
    # 30d, 2y, 10y, 30y AHEAD
    # if 30y == 3d => 15m, 6h, 1d, 3d AHEAD
    timespot_diffs = [timedelta(days=3), timedelta(days=1), timedelta(minutes=15), timedelta(hours=6)]
    time_now = datetime.utcnow()
    timespots = [time_now + diff for diff in timespot_diffs]
    borrow_curve_dots = []
    supply_curve_dots = []
    for t in timespots:
        rates = list(db.interest_rates.find({
            "snapshotTime": {"$lt": time_now.strftime(date_format)}
        }).sort("snapshotTime", pymongo.DESCENDING).limit(1))

        print(time_now.strftime(date_format),"Found rates",len(rates))
        for rate in rates:
            for interest_rate in rate['interest_rates']:
                if interest_rate['provider'] == protocol:
                    for borrow in interest_rate['borrow']:
                        if borrow['symbol'] == symbol:
                            borrow_curve_dots.append(borrow['rate'])
                    for supply in interest_rate['supply']:
                        if supply['symbol'] == symbol:
                            supply_curve_dots.append(supply['rate'])

    print("borrow dots",borrow_curve_dots)
    print("supply dots",supply_curve_dots)

    return render_template('curve.html', rates=[])

if __name__ == "__main__":
    app.run(debug=True)
