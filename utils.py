from elasticsearch import Elasticsearch
from time import sleep
from config import api_key_es
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_es(max_retries ,time_sleep):
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


def create_stock_index_mapping(es_client, stock_symbol: str):
    """
    Crée un index Elasticsearch pour une action donnée si elle n'existe pas,
    avec un mapping pour s'assurer que les champs sont correctement typés.
    """
    index_name = stock_symbol.lower() # Les noms d'index sont généralement en minuscules
    if not es_client.indices.exists(index=index_name):
        print(f"Tentative de création de l'index '{index_name}' avec mapping...")
        mapping = {
            "mappings": {
                "properties": {
                    "stock": {"type": "keyword"}, 
                    "date": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSS||epoch_millis"}, 
                    "open": {"type": "float"},
                    "high": {"type": "float"},
                    "low": {"type": "float"},
                    "close": {"type": "float"},
                    "volume": {"type": "long"},
                    "is_anomaly": {"type": "boolean"},
                    "anomaly_type": {"type": "keyword"}, 
                    "anomaly_score": {"type": "float"},
                    # Si vous ajoutez des explications LLM plus tard:
                    # "llm_explanation": {"type": "text"},
                }
            }
        }
        try:
            es_client.indices.create(index=index_name, body=mapping)
            print(f"Index '{index_name}' créé avec succès.")
        except Exception as e:
            print(f"Erreur lors de la création de l'index '{index_name}': {e}")
    else:
        # print(f"Index '{index_name}' existe déjà.") # Décommenter pour voir cette info à chaque fois
        pass 

def index_stock_data(es_client, data: dict):
    """
    Indexe le dictionnaire de données d'une action dans Elasticsearch.
    L'index est nommé d'après le symbole de l'action.
    """
    if not es_client:
        print("Client Elasticsearch non disponible. Impossible d'indexer les données.")
        return

    stock_symbol = data.get('stock')
    if not stock_symbol:
        print("Symbole d'action manquant dans les données. Impossible d'indexer.")
        return

    index_name = stock_symbol.lower() # Nom de l'index en minuscules

    # S'assurer que l'index existe avec le bon mapping
    create_stock_index_mapping(es_client, stock_symbol)

    try:
        # Créer un ID unique pour le document, par exemple en combinant le symbole et la date
        # C'est important pour éviter les doublons si le même message Kafka est traité plusieurs fois.
        doc_id = f"{stock_symbol.lower()}_{data.get('date').replace(' ', '_').replace(':', '-')}"
        
        response = es_client.index(
            index=index_name,
            id=doc_id, # ID unique pour le document
            document=data # Le dictionnaire de données enrichi
        )
        print(f"Données de '{stock_symbol}' indexées dans '{index_name}' avec ID: {response['_id']}")
    except Exception as e:
        print(f"Erreur lors de l'indexation des données pour '{stock_symbol}' dans '{index_name}': {e}")
        # print(f"Données qui ont échoué: {data}") # Décommenter pour débogage



def anomaly_detection(data: dict) -> dict:
    stock = data.get('stock')
    date = data.get('date')
    open_price = data.get('open')
    current_price = data.get('close')

    data['is_anomaly'] = False
    data['anomaly_type'] = None
    data['anomaly_score'] = None

    if open_price is None or current_price is None:
        print(f"Avertissement: Prix d'ouverture ou de clôture manquant pour {stock} à {date}. Impossible de détecter l'anomalie.")
        return data

    percentage_drop = 0.0
    if open_price != 0:
        percentage_drop = ((open_price - current_price) / open_price) * 100
        percentage_drop = round(percentage_drop, 2)

    if percentage_drop >= 10:
        data['is_anomaly'] = True
        data['anomaly_type'] = 'chute_intra_minute'
        data['anomaly_score'] = percentage_drop
    
    
    return data