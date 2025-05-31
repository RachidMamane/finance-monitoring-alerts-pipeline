from fastapi import FastAPI , HTTPException , status , Query
from utils  import get_es
from typing import Dict , Any , List
import logging
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
origins = [
    "http://localhost:8080",  
    "http://127.0.0.1:8080",
    "http://localhost",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





@app.get("/")
def index(): 
    return {"message" :  "Hello World"}

@app.get("/anomaly")
def all_anomaly(
    from_offset:int = Query(0 , ge= 0 , description= "Offset pour la pagination (nombre de documents à ignorer)")
, size : int = Query(10 , le = 1000 , description="Nombre de documents à retourner par page (max 10000)"))-> Dict[str, Any]:
    es = get_es(4, 2)
    if not es.ping():
        print("#-----------#")
        raise HTTPException(status_code=500 , detail="Impossible de se connecter ")
    try: 
        response = es.search(
            index='_all', 
            body={
                "query": {
                    "term": {
                        "is_anomaly": True 
                    }
                },
                "from": from_offset, 
                "size": size         
            }
        )
        total_anomalies = response['hits']['total']['value'] 
        anomalies = [hit['_source'] for hit in response['hits']['hits']]
        start_index = from_offset + 1
        end_index = from_offset + len(anomalies)
        print(f"Nombre total de documents anormaux trouvés dans tous les index : {total_anomalies}")
        print(f"Affichage des documents de {start_index} à {end_index}")
        return {
            "message": "Données d'anomalies récupérées avec succès",
            "total_anomalies": total_anomalies,
            "current_page_results": len(anomalies), # Nombre de résultats sur la page actuelle
            "start_index": start_index,
            "end_index": end_index,
            "anomalies": anomalies # Les données d'anomalies elles-mêmes
        }
    except Exception as e :
        print(f"Une erreur est survenue lors de la recherche Elasticsearch : {e}")
        raise HTTPException(status_code=500, detail=f"Échec de la récupération des données d'anomalies : {e}")
    
    
    
@app.get('/anomaly/{stock}')
async def anomaly_for_stock(stock:str , from_offset:int = Query(20 , ge= 0 ) , size:int= Query(10 , ge= 1)):
    es  = get_es(4,2)
    try : 
        search_query = {
            "query": {
                "bool": {
                    'must' :[
                        {
                            "term":{
                                "is_anomaly": True
                            }
                        },
                        {
                            "term":{
                                "stock":stock
                            }
                        }
                    ]
                }
            },
            'from': from_offset,
            'size':size
        }
        response = es.search(index = '_all', body = search_query)
        total_anomalies_for_stock = response['hits']['total']['value']
        anomalies_for_stock = [hit['_source'] for hit in response['hits']['hits']]
        start_index = from_offset + 1
        end_index = from_offset + len(anomalies_for_stock)
        return {
            "message": f"Données d'anomalies pour le stock '{stock}' récupérées avec succès",
            "stock": stock,
            "total_anomalies": total_anomalies_for_stock,
            "current_page_results": len(anomalies_for_stock),
            "start_index": start_index,
            "end_index": end_index,
            "anomalies": anomalies_for_stock
        }
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Échec de la récupération des données d'anomalies pour '{stock}' : {e}") 

@app.get('/number/{stock}')
async def get_number(stock:str):
    es = get_es(4,1)
    response = es.count(index =stock)
    return {"number": response['count']}
@app.get('/description_stock/{stock_symbol}')
async def description_stock(stock_symbol:str):
    es  = get_es(4,2)
    document_id = stock_symbol.lower()
    index_name = 'company_descriptions'
    try : 
        response = es.get(index=index_name, id=document_id)
        if response.get('found'):
            description = response['_source'].get('description')
            if description:
                logging.info(f"Description found for {stock_symbol}.")
                return {'description': description}
            else:
                logging.warning(f"Description field missing for {stock_symbol} (ID: {document_id}).")
                raise HTTPException(status_code=404, detail=f"Description for {stock_symbol} found but content is empty.")
        else:
            logging.warning(f"No description found for {stock_symbol} (ID: {document_id}).")
            raise HTTPException(status_code=404, detail=f"Description for {stock_symbol} not found.")
    except Exception as e:
        logging.error(f"An error occurred while fetching description for {stock_symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching description for {stock_symbol}.")

