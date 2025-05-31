from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.bash import BashOperator

from airflow.sdk import DAG
import sys
import os
from datetime import timedelta
from time import sleep
from elasticsearch import Elasticsearch
import pendulum
import logging 

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
api_key_es = "OUhtR0VaY0I3cTZVQkwxa2VzcWs6eTU2QkZXUWs2Rl91LXR2MHQxTlRrdw=="

def get_es(max_retries = 3 ,time_sleep = 1):
    i = 0 
    while i < max_retries : 
        try: 
            es = Elasticsearch("http://localhost:9200" , api_key= api_key_es)
            print("Connecting to Elasticsearch")
            return es 
        except Exception as e :
            logging.error(f" Something want wrong: {e}, retrying.....")
            sleep(time_sleep)
            i += 1
    raise ConnectionError("Failed to connected to elasticsearch ....")

def get_query_result(**kwargs):
    ti = kwargs['ti']
    es = ti.xcom_pull(task_ids='connect_es')

    if not es:
        raise ValueError("Erreur: Impossible de récupérer la connexion Elasticsearch via XComs.")

    query = {
        "query": {
            "match_all": {}
        }
    }
    print("Exécution de la requête Elasticsearch...")
    response = es.search(index='aapl', body=query)
    print("Requête Elasticsearch terminée.")
    return response


with DAG(
    'daily_report',
    default_args={
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    description="A simple tutorial DAG",
    schedule=None,
    start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
    catchup=False,
    tags=["example"],
) as dag:
    start_task = BashOperator(
        task_id='start_message',
        bash_command="echo 'Début du rapport quotidien.'",
    )

    connect_to_es = PythonOperator(
        task_id='connect_es',
        python_callable=get_es,
    )

    confirmation = BashOperator(
        task_id='connection_confirmed',
        bash_command="echo 'Connexion Elasticsearch établie avec succès !'",
    )

    get_answer = PythonOperator(
        task_id='query_es_data',
        python_callable=get_query_result,
    )

    end_task = BashOperator(
        task_id='end_pipeline',
        bash_command="echo 'Rapport quotidien terminé !'"
    )

    start_task >> connect_to_es >> confirmation >> get_answer >> end_task