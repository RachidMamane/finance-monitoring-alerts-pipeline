from kafka import KafkaConsumer
import json
import sys 
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from background.tasks import main
from time import sleep
from datetime import datetime
import logging



logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def read_kafka_messages():
    consumer = None 
    try:
        logging.info("Starting Kafka consumer...")
        consumer = KafkaConsumer(
            'market-data',
            bootstrap_servers='localhost:9092',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id='my-consumer-group',
            enable_auto_commit=True)
        for message in consumer:
            data = message.value
            timestamp = datetime.now().strftime('%d/%m/%Y ; %H:%M:%S')
            logging.info(f"Received message: {data} at {timestamp}")
            main.delay(data)
            logging.info(f"Dispatched anomaly detection task for stock: {data.get('stock', 'N/A')}")
            sleep(1)
    except KeyboardInterrupt:
        logging.info("Kafka consumer stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"An unexpected error occurred in Kafka consumer: {e}", exc_info=True)
    finally:
        if consumer:
            consumer.close()
            logging.info("Kafka consumer closed gracefully.")

if __name__ == "__main__":
    read_kafka_messages()