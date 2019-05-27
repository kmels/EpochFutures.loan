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

sched = BackgroundScheduler(daemon=True)
sched.add_job(sense_rates,'interval',minutes=60)
sched.add_job(sense_history,'interval',minutes=240)
sched.start()

app = Flask(__name__)

@app.route("/home")
def home():
    """ Function for test purposes. """
    return "Welcome Home :) !"

if __name__ == "__main__":
    app.run(debug=True)
