from celery import Celery
from time import sleep
from typing import Dict
from datetime import datetime
from utils.utils import create_annonces_index , index_annoucement 


broker = 'redis://localhost:6378'

app = Celery('announce',broker=broker , backend=broker)
@app.task(name ='announce.tache')
#----Indexer des données ---#
def tache(data : Dict) :
    create_annonces_index('stock_announcements')
    index_annoucement('stock_announcements' , data)
    print(data)


