from pymongo import MongoClient
from .settings import *

client = MongoClient(MONGO_HOST, MONGO_PORT)
db = client.get_database(MONGO_DBNAME)
