from elasticsearch import Elasticsearch 
import logging
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG
from time import sleep
from datetime import datetime, timedelta
import requests
logger = logging.getLogger(__name__)
api_key_es = "OUhtR0VaY0I3cTZVQkwxa2VzcWs6eTU2QkZXUWs2Rl91LXR2MHQxTlRrdw=="
bot = '7818095952:AAEjP3hGXKVcaFg57q5EA9aDrQEcnlfwYSo'
chat_id = "7798334501"

def get_es(max_retries = 3 ,time_sleep = 1):
    i = 0 
    while i < max_retries : 
        try: 
            es = Elasticsearch("http://es01:9200" , api_key= api_key_es)
            print("Connecting to Elasticsearch")
            return es 
        except Exception as e :
            logging.error(f" Something want wrong: {e}, retrying.....")
            sleep(time_sleep)
            i += 1
    raise ConnectionError("Failed to connected to elasticsearch ....")

def fetch_anomaly_data(**kwargs):
    es = get_es(3,1)
    """query = {
            "size": 0,
  "query": {
    "bool": {
      "filter": [
        {
          "term": {
            "is_anomaly": True
          }
        },
        {
          "range": {
            "date": {
              "lte": "now/d"
            }
          }
        }
      ]
    }
  }
    }"""
    query ={
    'size' :0,
    'query': {
        'term' : {
            'is_anomaly' : True , 
        } ,
    } , 
    'aggs' : {
        'per_stock' :{
            'terms' : {
                "field" : 'stock'
            } ,
            'aggs' : {
            'avg_score' : {
                'avg' : {
                    'field' : 'anomaly_score'
                }
            }
        } , 
        
        } , 
        
    }}
    response = es.search(index ='_all' , body = query)
    anomaly_data= response["aggregations"]['per_stock']['buckets']
    return anomaly_data
def generate_anomaly_summary(**kwargs):
  ti = kwargs['ti']
  anomaly_data = ti.xcom_pull(task_ids='fetch_anomaly_data_task', key='return_value')
  if not anomaly_data:
    return "Aucune donnée d'anomalie trouvée pour générer un rapport."
  sorted_data = sorted(anomaly_data, key=lambda x: x['avg_score']['value'], reverse=True)
  summary_parts = []
  if sorted_data:
    stock_info = []
    for i , item in enumerate(sorted_data[:3]):
       stock_name = item["key"]
       avg_score = item['avg_score']['value']
       doc_count = item['doc_count']
       stock_info.append(f"{stock_name} (score moyen: {avg_score:.2f}, {doc_count} anomalies)")
    if len(stock_info)==1 : 
      summary_parts.append(f"Le stock le plus impacté est {stock_info[0]}.")
    elif len(stock_info)==2:
      summary_parts.append(f"Les principaux stocks impactés sont {stock_info[0]} et {stock_info[1]}.")
    else:
      summary_parts.append(f"Les stocks les plus impactés sont {', '.join(stock_info[:-1])} et {stock_info[-1]}.")
    summary_parts.append(f"Le score moyen le plus élevé observé est de {sorted_data[0]['avg_score']['value']:.2f} pour {sorted_data[0]['key']}.")
  all_scores = [item['avg_score']['value'] for item in anomaly_data]
  min_overall_score = min(all_scores)
  max_overall_score = max(all_scores)
  summary_parts.append(f"Les scores d'anomalie moyens pour les stocks listés varient de {min_overall_score:.2f} à {max_overall_score:.2f}.")
  if len(sorted_data) > 2:
    highest_avg = sorted_data[0]['avg_score']['value']
    lowest_avg = sorted_data[-1]['avg_score']['value']
    if highest_avg / lowest_avg > 5:
      summary_parts.append("Cette disparité indique une variabilité notable dans la sévérité des anomalies d'un stock à l'autre.")
    else:
      summary_parts.append("Les scores moyens montrent une certaine diversité dans l'intensité des anomalies détectées.")

  final_summary = "\n".join(summary_parts)
  final_summary += "\n\nCette analyse met en lumière les entités les plus affectées et l'étendue des scores d'anomalie détectés."
  return final_summary


def send_report(**kwargs):
  ti =  kwargs['ti']
  final_summary = ti.xcom_pull(task_ids= 'generate_anomaly_summary_task' , key='return_value')
  if not final_summary:
    final_summary = "Rapport d'anomalies vide : impossible de récupérer le résumé."
    print(final_summary)
  url = f"https://api.telegram.org/bot{bot}/sendMessage"
  payload ={
      'chat_id' : chat_id , 
      'text' : final_summary
  }
  try :
    print("envoie du message ") 
    response = requests.post(url ,payload ,timeout=10)
    response.raise_for_status()
    logger.info(f"Message Telegram envoyé avec succès. Réponse: {response.json()}")
  except Exception as e : 
    logger.error(f"Échec de l'envoi du message Telegram : {e}")
    raise

       
    

with DAG(
    'report',
    default_args={
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),}, 
        description="daily report dag ",
        schedule="0 18 * * *",
        start_date=datetime(2021, 1, 1),
        catchup=False,
        tags=["example"],
) as dag :
    fetch_anomaly_data_task = PythonOperator(
       task_id = 'fetch_anomaly_data_task', 
       python_callable=fetch_anomaly_data,
    ) 
    generate_anomaly_summary_task = PythonOperator(
       task_id = 'generate_anomaly_summary_task', 
       python_callable = generate_anomaly_summary,
    )
    send_telegram_report_task = PythonOperator(
       task_id ='send_telegram_report_task',
       python_callable= send_report,
    )

    fetch_anomaly_data_task >> generate_anomaly_summary_task >> send_telegram_report_task
