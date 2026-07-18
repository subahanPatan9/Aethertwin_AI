from app.core import config
from pymongo import MongoClient

def get_mongo_client():
    return MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=1500)
