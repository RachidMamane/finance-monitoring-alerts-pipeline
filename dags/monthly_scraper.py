import sys , os 
sys.path.append('/opt/airflow')
from web_scraping.scraping import get_company_description
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG 
from datetime import timedelta , datetime
from elasticsearch import Elasticsearch
from time import sleep 
import logging
from typing import List 
from dotenv import load_dotenv
logger = logging.getLogger(__name__)
load_dotenv()

api_key_es = "OUhtR0VaY0I3cTZVQkwxa2VzcWs6eTU2QkZXUWs2Rl91LXR2MHQxTlRrdw=="

def get_es(max_retries = 3 ,time_sleep = 1):
    i = 0 
    while i < max_retries : 
        try: 
            es = Elasticsearch("http://es01:9200" , api_key= api_key_es)
            print("Connecting to Elasticsearch")
            return es 
        except Exception as e :
            print(f"erreur {e}")
            sleep(time_sleep)
            i += 1
    raise ConnectionError("Failed to connected to elasticsearch ....")

"""def delete_document(index_name:str , doc_id:str) :
    es = get_es(3,1)
    if not es.indices.exists(index = index_name) :
        print(f'The index : {index_name} does not exist')
    try : 
        response =  es.delete(index = index_name , id = doc_id)
        print(f'document with id {doc_id} deleted succesfully')
        print(response['result'])
    except Exception as e : 
        print(f"an error occured {e}")"""
def get_stocks()-> List[str]:
    return ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "INVALIDSYM"]
def scrape_and_store_descriptions(**kwargs):
    ti = kwargs['ti']
    index_name = kwargs['index_name']
    #es = ti.xcom_pull(task_id = "elastic_connection" ,key='return_value')
    es = get_es(3,1)
    if not es:
        raise ValueError("L'objet Elasticsearch client n'a pas pu être récupéré via XCom.")
    stocks = get_stocks() 
    descriptions = {}
    for stock in stocks : 
        description = get_company_description(stock)
        descriptions[stock]=description
    if not es.indices.exists(index =index_name):
        print(f"L'index '{index_name}' n'existe pas. Création...")
        mapping = {
            "mappings": {
                "properties": {
                    "stock": {"type": "keyword"},
                    "description": {"type": "text"}
                }
            }
        }
        try : 
            es.indices.create(index=index_name, body=mapping)
            print(f"index créée avec succes ")

        except Exception as e:
            print(f"Error creating index '{index_name}': {e}")
    try : 
        for key, value in descriptions.items():
            doc_id = key.lower()
            document_body = {"stock": key, "description": value}
            response = es.update(
                index=index_name,
                id=doc_id,
                body={"doc": document_body, "doc_as_upsert": True})
            print(f"Document pour '{key}' (ID: '{doc_id}') indexé/mis à jour. Résultat: {response['result']}")
    except Exception as e:
        print(f"Une erreur s'est produite lors du stockage des descriptions : {e}")
        raise  




with DAG (
    'Monthly_scraper' , 
    default_args= {
        'depends_on_past' : False ,
        'retries' : 1 , 
        'retry_delay' : timedelta(minutes=5) , 
        },
        description = "A dag to scrap a web site once monthly" , 
        schedule = "0 0 1 * *" , 
        start_date=datetime(2021, 1, 1),
        catchup=False,
        tags=["scraping", "elasticsearch", "monthly"]

) as dag : 
    t_store = PythonOperator(
        task_id = 'stock_store_task' , 
        python_callable=  scrape_and_store_descriptions,
        op_kwargs={"index_name": "description_stocks"}

    )
    t_store