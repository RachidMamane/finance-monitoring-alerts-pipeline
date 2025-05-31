import requests
from bs4 import BeautifulSoup
import time
import logging
from requests.exceptions import RequestException, HTTPError, Timeout
from elasticsearch import Elasticsearch, ConnectionError, TransportError
import utils
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Your existing get_company_description function (with slight modification for return) ---
def get_company_description(symbol: str = "AAPL", max_retries: int = 3, delay_seconds: int = 2) -> str | None:
    """
    Retrieves the company description from Yahoo Finance for a given stock symbol.

    Args:
        symbol (str): The stock ticker symbol (e.g., "AAPL", "GOOG"). Defaults to "AAPL".
        max_retries (int): The maximum number of retries for a failed request. Defaults to 3.
        delay_seconds (int): The delay in seconds between requests to avoid overloading the server.
                             Defaults to 2 seconds.

    Returns:
        str | None: The company description if found, otherwise None.
    """
    url = f"https://finance.yahoo.com/quote/{symbol}/profile"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Connection": "keep-alive",
    }

    for attempt in range(max_retries):
        try:
            logging.info(f"Attempt {attempt + 1}/{max_retries} to fetch description for {symbol} from {url}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            description_section = soup.find('section', {"data-testid": "description"})
            
            if description_section:
                description_paragraph = description_section.find("p")
                if description_paragraph:
                    description = description_paragraph.get_text(strip=True)
                    logging.info(f"Successfully retrieved description for {symbol}.")
                    return description
                else:
                    logging.warning(f"Could not find a <p> tag within the description section for {symbol}.")
            else:
                logging.warning(f"Could not find a section with data-testid='description' for {symbol}.")

            logging.warning(f"Description not found for {symbol} on attempt {attempt + 1}. Retrying...")
            time.sleep(delay_seconds)
            
        except HTTPError as e:
            if e.response.status_code == 404:
                logging.error(f"HTTP Error 404: Page not found for symbol {symbol}. It might be an invalid symbol.")
                return None
            elif e.response.status_code == 429:
                logging.warning(f"HTTP Error 429: Too many requests for {symbol}. Waiting longer before retrying.")
                time.sleep(delay_seconds * (2 ** attempt))
            else:
                logging.error(f"HTTP Error {e.response.status_code} for {symbol}: {e}")
                time.sleep(delay_seconds)
        except Timeout:
            logging.warning(f"Request timed out for {symbol}. Retrying...")
            time.sleep(delay_seconds)
        except RequestException as e:
            logging.error(f"Network or request error for {symbol}: {e}. Retrying...")
            time.sleep(delay_seconds)
        except Exception as e:
            logging.error(f"An unexpected error occurred for {symbol}: {e}", exc_info=True)
            return None

    logging.error(f"Failed to retrieve description for {symbol} after {max_retries} attempts.")
    return None

# --- New Elasticsearch Integration ---



def create_index_if_not_exists(es_client: Elasticsearch, index_name: str):
    """
    Creates an Elasticsearch index with a specific mapping if it doesn't already exist.
    """
    if not es_client.indices.exists(index=index_name):
        # Define a simple mapping. 'description' is text, 'symbol' is keyword for exact matching.
        mapping = {
            "mappings": {
                "properties": {
                    "symbol": {"type": "keyword"},
                    "description": {"type": "text"}
                }
            }
        }
        try:
            es_client.indices.create(index=index_name, body=mapping)
            logging.info(f"Index '{index_name}' created with mapping.")
        except TransportError as e:
            logging.error(f"Error creating index '{index_name}': {e}")
    else:
        logging.info(f"Index '{index_name}' already exists.")

def store_description_in_elasticsearch(
    es_client: Elasticsearch,
    index_name: str,
    symbol: str,
    description: str
) -> bool:
    """
    Stores a company description and its symbol in Elasticsearch.

    Args:
        es_client (Elasticsearch): The connected Elasticsearch client.
        index_name (str): The name of the Elasticsearch index.
        symbol (str): The stock ticker symbol.
        description (str): The company description.

    Returns:
        bool: True if the document was successfully indexed, False otherwise.
    """
    document = {
        "symbol": symbol,
        "description": description,
        "timestamp": int(time.time()) # Add a timestamp for when it was stored
    }
    
    # Use the symbol as the document ID for easy retrieval/updates
    document_id = symbol.lower()

    try:
        response = es_client.index(index=index_name, id=document_id, document=document)
        logging.info(f"Successfully indexed document for symbol '{symbol}' (ID: {response['_id']})")
        return True
    except TransportError as e:
        logging.error(f"Error indexing document for '{symbol}': {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while storing data for '{symbol}': {e}", exc_info=True)
        return False

# --- Main execution logic ---
if __name__ == "__main__":
    ELASTICSEARCH_HOST = "localhost"
    ELASTICSEARCH_PORT = 9200
    ELASTICSEARCH_INDEX = "company_descriptions" # Your chosen index name

    # 1. Connect to Elasticsearch
    es_client = utils.get_es(3,1)
    if es_client:
        # 2. Ensure the index exists with the correct mapping
        create_index_if_not_exists(es_client, ELASTICSEARCH_INDEX)

        # List of symbols to process
        symbols_to_process = ["AAPL", "GOOG", "MSFT", "TSLA", "AMZN", "NVDA", "INVALIDSYM"]

        for symbol in symbols_to_process:
            print(f"\n--- Processing {symbol} ---")
            
            # 3. Get the company description
            description = get_company_description(symbol)

            if description:
                # 4. Store the description in Elasticsearch
                logging.info(f"Storing description for {symbol} in Elasticsearch...")
                success = store_description_in_elasticsearch(es_client, ELASTICSEARCH_INDEX, symbol, description)
                if success:
                    print(f"Stored {symbol} description successfully.")
                else:
                    print(f"Failed to store {symbol} description.")
            else:
                logging.warning(f"Skipping storage for {symbol} due to missing description.")

    else:
        print("Could not connect to Elasticsearch. Please ensure it's running.")

    print("\n--- Processing complete ---")

    # Example of how to retrieve data (optional, for verification)
    if es_client and es_client.ping():
        print("\n--- Verifying data in Elasticsearch ---")
        try:
            # Search for all documents
            search_results = es_client.search(index=ELASTICSEARCH_INDEX, query={"match_all": {}})
            print(f"Found {search_results['hits']['total']['value']} documents in '{ELASTICSEARCH_INDEX}':")
            for hit in search_results['hits']['hits']:
                source = hit['_source']
                print(f"  Symbol: {source['symbol']}, Description: {source['description'][:100]}...")
        except Exception as e:
            print(f"Error during verification search: {e}")