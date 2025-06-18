from celery import Celery
from time import sleep 
import logging
import requests
from datetime import datetime 
import sys , os 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.utils import  index_stock_data , get_es
import redis

app = Celery('tasks' , broker= 'redis://localhost:6378' , backend= 'redis://localhost:6378')
# Configuration de la connexion Redis
REDIS_HOST = 'localhost'
REDIS_PORT = 6378
REDIS_DB_LAST_PRICES = 1 
ANOMALY_PERCENTAGE_THRESHOLD = 10.0 
TELEGRAM_BOT_TOKEN = "7566864990:AAFNU9cdUEA9yxfOMPXnGUNTOeyPikKMxBA" 
TELEGRAM_CHAT_ID = "7798334501" 

# Configuration du logging pour une meilleure visibilité
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_redis_client() -> redis.StrictRedis | None:
    """ Initialise et retourne un client Redis pour les derniers prix. """
    try:
        r = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB_LAST_PRICES,
            decode_responses=True # Pour obtenir des chaînes de caractères directement
        )
        r.ping() # Teste la connexion
        logging.info("Connexion à Redis établie.")
        return r
    except Exception as e:
        logging.error(f"Erreur de connexion à Redis: {e}")
        return None

def anomaly_detection(data: dict, redis_client: redis.StrictRedis) -> dict:
    stock = data.get('stock')
    date = data.get('date')
    open_price = data.get('open')
    current_price = data.get('close')
    volume = data.get('volume', 0) 

    data['is_anomaly'] = False
    data['anomaly_type'] = None 
    data['anomaly_score'] = None

    if open_price is None or current_price is None:
        logging.warning(f"Warning: Prix d'ouverture ou de clôture manquant pour {stock} à {date}. Impossible pour la détection d'anomalie.")
        return data

    # --- 1. Détection d'anomalie type: Chute intra-minute (open vs close) ---
    percentage_drop_intra = 0.0
    if open_price != 0: 
        percentage_drop_intra = ((open_price - current_price) / open_price) * 100
        percentage_drop_intra = round(percentage_drop_intra, 2) 
    
    if percentage_drop_intra >= ANOMALY_PERCENTAGE_THRESHOLD:
        data['is_anomaly'] = True
        data['anomaly_type'] = 'chute_intra_minute'
        data['anomaly_score'] = percentage_drop_intra
        logging.info(f"ANOMALIE DÉTECTÉE (intra-minute) pour {stock} à {date}: Chute de {percentage_drop_intra}% (Open: {open_price}, Close: {current_price})")
    
    # --- 2. Détection d'anomalie type: Chute/Hausse séquentielle (minute-à-minute via Redis) ---
    if redis_client:
        previous_close_price_str = redis_client.hget('last_prices', stock) # Récupère le dernier prix
        
        if previous_close_price_str:
            previous_close_price = float(previous_close_price_str)
            
            if previous_close_price != 0 and current_price is not None:
                percentage_change_seq = ((current_price - previous_close_price) / previous_close_price) * 100
                percentage_change_seq = round(percentage_change_seq, 2)

                # Détection de chute séquentielle
                if percentage_change_seq <= -ANOMALY_PERCENTAGE_THRESHOLD:
                    if not data['is_anomaly']: # Si pas déjà marquée par l'intra-minute
                        data['is_anomaly'] = True
                        data['anomaly_type'] = 'chute_sequentielle'
                        data['anomaly_score'] = abs(percentage_change_seq) # Score en valeur absolue
                        logging.info(f"ANOMALIE DÉTECTÉE (séquentielle) pour {stock} à {date}: Chute de {abs(percentage_change_seq)}% (Préc: {previous_close_price}, Actuel: {current_price})")
                    elif 'chute_intra_minute' in data['anomaly_type']: 
                        data['anomaly_type'] = "chute_intra_minute_et_sequentielle"
                        data['anomaly_score'] = max(data['anomaly_score'], abs(percentage_change_seq))
                        logging.info(f"ANOMALIE DÉTECTÉE (combinée) pour {stock} à {date}: Intra {percentage_drop_intra}%, Séquentielle {abs(percentage_change_seq)}%")
                
                # Détection de hausse séquentielle
                '''elif percentage_change_seq >= ANOMALY_PERCENTAGE_THRESHOLD: 
                    if not data['is_anomaly']: 
                        data['is_anomaly'] = True
                        data['anomaly_type'] = 'hausse_sequentielle'
                        data['anomaly_score'] = percentage_change_seq
                        logging.info(f"ANOMALIE DÉTECTÉE (séquentielle) pour {stock} à {date}: Hausse de {percentage_change_seq}% (Préc: {previous_close_price}, Actuel: {current_price})")'''

        
        if current_price is not None:
            redis_client.hset('last_prices', stock, str(current_price))
            logging.debug(f"Mis à jour le dernier prix de {stock} dans Redis: {current_price}")
    else:
        logging.warning("Client Redis non disponible. Détection séquentielle d'anomalies non effectuée.")

    return data

def send_simple_telegram_message(message_text: str, bot_token: str, chat_id: str) -> bool:
    """
    Envoie un message texte simple via l'API Bot Telegram.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text
        
    }
    
    try:
        logging.info(f"Tentative d'envoi d'un message Telegram (chat ID: {chat_id})...")
        response = requests.post(url, json=payload, timeout=10) # Ajout d'un timeout
        response.raise_for_status() 
        logging.info("Message Telegram envoyé avec succès !")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Échec de l'envoi du message Telegram: {e}")
        return False
    except Exception as e:
        logging.error(f"Une erreur inattendue est survenue lors de l'envoi du message Telegram: {e}")
        return False

# --- Tâche Celery principale ---
@app.task(bind=True, default_retry_delay=30, max_retries=3) 
def main(self, data: dict):
    logging.info(f"Tâche Celery [Main]: Début du traitement pour {data.get('stock')} à {data.get('date')}")

    # 1. Obtenir le client Elasticsearch
    es_client = get_es(3,1) 
    if es_client is None:
        logging.error("Tâche Celery [Main]: Impossible de se connecter à Elasticsearch. Réessai de la tâche.")
        raise self.retry() 

    # 2. Obtenir le client Redis (NOUVEAU)
    redis_client = get_redis_client()
    if redis_client is None:
        logging.error("Tâche Celery [Main]: Impossible de se connecter à Redis. Réessai de la tâche.")
        raise self.retry() 

    # 3. Processus de détection d'anomalie
    #data['processed_at'] = datetime.now().isoformat()
    processed_data = anomaly_detection(data.copy(), redis_client) 

    logging.info(f"Tâche Celery [Main]: Détection pour {processed_data.get('stock')}: Anomalie={processed_data['is_anomaly']}")

    # 4. Si anomalie => envoie alerte sur Telegram (appel SYNCHRONE)
    if processed_data['is_anomaly']:
        alert_message = (
            f"ALERTE ANOMALIE BOURSIERE\n\n"
            f"Action : {processed_data['stock']}\n"
            f"Date/Heure : {processed_data['date']}\n"
            f"Type : {processed_data['anomaly_type'].replace('_', ' ').title()}\n"
            f"Score : {processed_data['anomaly_score']:.2f}%\n"
            f"Prix Clôture : {processed_data['close']:.2f}\n"
            f"Prix Ouverture : {processed_data['open']:.2f}\n"
            f"Volume : {processed_data.get('volume', 'N/A')}\n\n" 
            f"(Veuillez vérifier les données sur Kibana)"
        )
        logging.info(f"Tâche Celery [Main]: Anomalie détectée pour {processed_data['stock']}. Envoi immédiat de l'alerte.")
        send_simple_telegram_message(alert_message, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) 

    # 5. Stockage dans Elasticsearch
    try:
        index_stock_data(es_client, processed_data)
        logging.info(f"Tâche Celery [Main]: Données indexées dans ES pour {processed_data.get('stock')}.")
    except Exception as e:
        logging.error(f"Tâche Celery [Main]: Échec du stockage dans Elasticsearch pour {processed_data.get('stock')}: {e}")
    
    logging.info(f"Données finales traitées et envoyées à ES: {processed_data}")
    logging.info(f"Tâche Celery [Main]: Fin du traitement pour {data.get('stock')}.")