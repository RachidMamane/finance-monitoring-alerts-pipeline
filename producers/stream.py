
import logging
import time
import random as rd
import json
from datetime import datetime, timedelta
from kafka import KafkaProducer

def stream_data_real_time(stocks):
    producer = KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )

    start_prices = {stock: round(rd.uniform(200, 5000), 2) for stock in stocks}
    simulated_time = datetime.utcnow()

    try:
        while True:
            for stock in stocks:
                open_price = start_prices[stock]

                # Anomalie possible : 15% de chance
                if rd.random() < 0.15:
                    close_price = round(open_price * rd.uniform(0.88, 0.92), 2)
                else:
                    variation = rd.uniform(-0.02, 0.02)
                    close_price = round(open_price * (1 + variation), 2)

                high_price = round(max(open_price, close_price) + rd.uniform(0, 1), 2)
                low_price = round(min(open_price, close_price) - rd.uniform(0, 1), 2)
                volume = rd.randint(1000, 10000)

                record = {
                    "stock": stock,
                    "date": simulated_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume
                }

                producer.send('market-data', value=record)
                print(f"{record["date"]} Sent {stock} data.")

                start_prices[stock] = close_price

            simulated_time += timedelta(minutes=1)  # Avancer le temps simulé
            time.sleep(1)  # Attente réelle de 1 seconde
    except Exception as e: 
        logging.error(e)

    finally:
        producer.flush()
        producer.close()


stream_data_real_time(["AAPL", "GOOGL", "TSLA", "BTC", "ETH","NFLX" ,"SBUX","NVDA"])

