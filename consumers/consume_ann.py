from kafka import KafkaConsumer
import json
import sys , os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from background.ann_task import tache
import logging
from datetime import datetime 
from time import sleep

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

topic = 'stock_announcements'
broker = 'localhost:9092'


def consume_annonce(): 
    consumer = None 
    try:
        logging.info("Starting Kafka consumer...")
        consumer = KafkaConsumer(
        topic ,
        bootstrap_servers = broker ,
        value_deserializer = lambda m : json.loads(m.decode('utf-8')), 
        auto_offset_reset='earliest',
        enable_auto_commit=True
        )
        for message in consumer : 
            data = message.value
            timestamp = datetime.now().strftime('%d/%m/%Y ; %H:%M:%S')
            logging.info(f"Received message: {data} at {timestamp}")
            tache.delay(data)
            logging.info(f"inserting data into elastivcsearch {data}")
            sleep(1)
    except KeyboardInterrupt:
        logging.info("Kafka consumer stopped by user (KeyboardInterrupt).")
    except Exception as e : 
        logging.error(f"An unexpected error occurred in Kafka consumer: {e}", exc_info=True)
    finally:
        if consumer:
            consumer.close()
            logging.info("Kafka consumer closed gracefully.")

if __name__ == "__main__":
    consume_annonce()

