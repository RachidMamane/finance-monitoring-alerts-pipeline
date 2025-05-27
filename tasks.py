from celery import Celery
from time import sleep 
import logging
import requests
from datetime import datetime 
from utils import create_stock_index_mapping , index_stock_data , get_es


app = Celery('tasks' , broker= 'redis://localhost:6378' , backend= 'redis://localhost:6378')




# Dictionnaire temporaire pour stocker les derniers prix

def anomaly_detection(data: dict) -> dict:
    stock = data.get('stock')
    date = data.get('date')
    open_price = data.get('open')
    current_price = data.get('close')
#------- Some initialiwation------#
    data['is_anomaly'] = False
    data['anomaly_type'] = None 
    data['anomaly_score'] = None
    #----To make sure everything is such fine----#
    if open_price is None or current_price is None:
        print(f"warning: missing one of them {stock} at {date}. Impossible for anoamly detection.")
        return data
    percentage_drop = 0.0
    if open_price != 0: # 
        percentage_drop = ((open_price - current_price) / open_price) * 100
        percentage_drop = round(percentage_drop, 2) 
    if percentage_drop >= 10:
        data['is_anomaly'] = True
        data['anomaly_type'] = 'chute_intra_minute'
        data['anomaly_score'] = percentage_drop
    return data


def send_simple_telegram_message(message_text: str, bot_token: str, chat_id: str) -> bool:
    """
    Envoie un message texte simple via l'API Bot Telegram.

    Args:
        message_text (str): Le texte du message à envoyer.
        bot_token (str): Le token de votre bot Telegram.
        chat_id (str): L'ID du chat où envoyer le message.

    Returns:
        bool: True si le message a été envoyé avec succès, False sinon.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text
    }
    
    try:
        logging.info(f"Tentative d'envoi d'un message à Telegram (chat ID: {chat_id})...")
        response = requests.post(url, json=payload)
        response.raise_for_status() # Lève une exception pour les codes d'état HTTP d'erreur
        logging.info("Message Telegram envoyé avec succès !")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Échec de l'envoi du message Telegram: {e}")
        return False
    except Exception as e:
        logging.error(f"Une erreur inattendue est survenue: {e}")
        return False
@app.task
def main(data):
    es_client = get_es(3,1)
    #Process des données
    processed_data = anomaly_detection(data)
    if processed_data['is_anomaly']:
        message_text = (
            f"ALERTE ANOMALIE BOURSIERE\n\n"
            f"Action : {processed_data['stock']}\n"
            f"Date/Heure : {processed_data['date']}\n"
            f"Type : {processed_data['anomaly_type'].replace('_', ' ').title()}\n"
            f"Score : {processed_data['anomaly_score']:.2f}%\n"
            f"Prix Clôture : {processed_data['close']:.2f}\n"
            f"Prix Ouverture : {processed_data['open']:.2f}\n"
            f"Volume : {processed_data['volume']}\n\n"
            f"(Veuillez vérifier les données sur Kibana)"
        )
        logging.info(f"Tâche Celery [Main]: Anomalie détectée pour {processed_data['stock']}. Délégation de l'alerte à Celery.")
        send_simple_telegram_message(message_text,"7566864990:AAFNU9cdUEA9yxfOMPXnGUNTOeyPikKMxBA" ,"7798334501") 

    try:
        index_stock_data(es_client, processed_data)
        logging.info(f"Tâche Celery [Main]: Données indexées dans ES pour {processed_data.get('stock')}.")
    except Exception as e:
        logging.error(f"Tâche Celery [Main]: Échec du stockage dans Elasticsearch pour {processed_data.get('stock')}: {e}")
    
    # Laisser des traces 
    logging.info(f"Données finales traitées et envoyées à ES: {processed_data}")

