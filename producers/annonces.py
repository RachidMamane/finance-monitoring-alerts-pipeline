import random
import time
import json
from datetime import datetime, timedelta
from kafka import KafkaProducer 
from typing import Optional , Dict , Any


KAFKA_BROKER_URL = 'localhost:9092'
ANNOUNCEMENTS_TOPIC = 'stock_announcements' 
ANNOUNCEMENT_INTERVAL_SECONDS = 6
# Dictionnaire des entreprises (mis à jour)
COMPANIES = {
    "AAPL": "Apple Inc.",
    "TSLA": "Tesla Inc.",
    "AMZN": "Amazon.com Inc.",
    "GOOGL": "Alphabet Inc.",
    "NFLX": "Netflix Inc.",
    "MSFT": "Microsoft Corp.",
    "NVDA": "NVIDIA Corp.",
    "JPM": "JPMorgan Chase & Co.",
    "META": "Meta Platforms Inc.",
    "SMCI": "Super Micro Computer Inc."
}

# Secteurs d'activité
SECTORS = [
    "cloud computing", "véhicules électriques", "e-commerce", "intelligence artificielle",
    "médias en streaming", "logiciels d'entreprise", "semi-conducteurs", "services financiers",
    "biotechnologie", "énergies renouvelables", "cybersécurité", "robotique"
]

# Produits/Initiatives par entreprise
PRODUCTS = {
    "AAPL": ["Vision Pro 2", "iPhone 17", "puce M4", "plateforme de services financiers"],
    "TSLA": ["Cybertruck", "nouvelle Gigafactory au Mexique", "robot Optimus", "suite de conduite autonome FSD"],
    "AMZN": ["expansion d'AWS", "contenus originaux Prime Video", "nouvel hub logistique drone", "IA générative pour le retail"],
    "GOOGL": ["intégration Gemini", "Pixel Fold 2", "quantique computing en nuage", "projet de voiture autonome Waymo"],
    "NFLX": ["acquisition de studios", "croissance d'abonnés mondiale", "formule avec publicité", "lancement de jeux AAA"],
    "MSFT": ["Copilot Enterprise", "Azure AI services", "partenariat OpenAI", "nouvelle génération Xbox"],
    "NVDA": ["Blackwell GPU", "plateforme Isaac pour la robotique", "collaboration IA avancée", "solutions data center"],
    "JPM": ["innovation blockchain", "stratégie d'investissement durable", "expansion des services numériques"],
    "META": ["Metaverse Horizon Worlds", "lunettes Ray-Ban Meta", "puces IA personnalisées", "publicité ciblée"],
    "SMCI": ["serveurs IA haute densité", "solutions de refroidissement liquide", "partenariats avec les géants de l'IA"]
}

# Acteurs du marché (compétiteurs, partenaires, etc.)
ACTORS = [
    "Google", "Microsoft", "Amazon", "Apple", "NVIDIA", "Intel", "Samsung", "TSMC", "Qualcomm",
    "Oracle", "SAP", "Ford", "GM", "Rivian", "BYD", "Tencent", "Alibaba", "OpenAI", "Meta",
    "ASML", "Accenture", "Deloitte", "Goldman Sachs", "BlackRock"
]

# Régions géographiques
REGIONS = [
    "Europe", "Amérique du Nord", "Asie-Pacifique", "Amérique Latine", "Moyen-Orient", "Afrique"
]

# Cadres réglementaires / Juridiques
REGULATIONS = [
    "lois antitrust", "réglementations sur la vie privée (RGPD)", "normes environnementales",
    "droits du travail", "lois fiscales", "réglementations sur l'IA"
]

# Lieux
LOCATIONS = [
    "Silicon Valley", "Austin", "Dublin", "Singapour", "Munich", "Séoul", "Bangalore", "Londres", "Paris"
]

# Modèles d'annonces classés par impact
ANNOUNCEMENT_TEMPLATES = {
    "positive": [
        {"template": "{company} a annoncé un **lancement révolutionnaire** : le {product} qui promet de dominer le marché du {sector}.", "vars": ["product", "sector"]},
        {"template": "Les résultats trimestriels de {company} ont **explosé les attentes**, affichant une croissance de {percent}% de leur chiffre d'affaires, un véritable tour de force dans le {sector}.", "vars": ["percent", "sector"]},
        {"template": "{company} a **scellé un partenariat stratégique majeur** avec {partner}, débloquant des opportunités inédites dans le domaine de {technology}.", "vars": ["partner", "technology"]},
        {"template": "Un rapport d'analystes de {actor} prédit que {company} est en passe de **capturer une part significative** du marché {sector} en {region}.", "vars": ["actor", "sector", "region"]},
        {"template": "{company} a dévoilé un **investissement massif** de ${investment} millions dans un pôle de R&D à {location}, signalant une confiance forte dans l'avenir.", "vars": ["investment", "location"]},
        {"template": "{company} a obtenu une **approbation réglementaire clé** pour son {product} dans la région {region}, ouvrant la voie à une expansion rapide.", "vars": ["product", "region"]}
    ],
    "negative": [
        {"template": "{company} fait face à des **vents contraires inattendus** avec une chute de {percent}% des bénéfices trimestriels, suscitant l'inquiétude des investisseurs.", "vars": ["percent"]},
        {"template": "Une fuite interne chez {company} révèle un **plan de licenciement massif** de {number} employés, une nouvelle qui ébranle la confiance.", "vars": ["number"]},
        {"template": "{company} est plongée dans une **crise juridique** majeure en {region} suite à des accusations de non-conformité avec les {regulation}.", "vars": ["region", "regulation"]},
        {"template": "Le lancement du {product} de {company} a été **reporté indéfiniment** en raison de problèmes techniques critiques, impactant négativement les prévisions de vente.", "vars": ["product"]},
        {"template": "{company} a perdu un **contrat clé** de {investment} millions de dollars au profit de {competitor}, un coup dur pour sa position sur le marché {sector}.", "vars": ["investment", "competitor", "sector"]},
        {"template": "Des analystes de {actor} ont **dégradé la note** de {company} en raison de l'intensification de la concurrence dans le secteur {sector}, prévoyant un ralentissement.", "vars": ["actor", "sector"]}
    ],
    "neutral": [
        {"template": "{company} a **remanié sa structure de direction**, avec {new_leader} prenant les rênes du département {department}.", "vars": ["new_leader", "department"]},
        {"template": "Le programme de test bêta du {product} de {company} a révélé des **défis inattendus**, nécessitant des ajustements avant le déploiement général.", "vars": ["product"]},
        {"template": "{company} explore de **nouvelles avenues de financement** pour son projet {project_name}, sans impact immédiat sur les opérations.", "vars": ["project_name"]}
    ]
}

def generate_random_announcement(stock_symbol: str, impact: Optional[str] = None) -> Dict[str, Any]:
    """
    Génère une annonce réaliste et figurative pour un symbole boursier donné.
    Peut spécifier l'impact souhaité (positive, negative, neutral) ou le laisser aléatoire.
    """
    company_name = COMPANIES.get(stock_symbol, stock_symbol)

    # Définir le type de templates à choisir
    if impact and impact in ANNOUNCEMENT_TEMPLATES:
        templates_to_use = ANNOUNCEMENT_TEMPLATES[impact]
    else: # Choisir aléatoirement si l'impact n'est pas spécifié ou invalide
        all_impacts = list(ANNOUNCEMENT_TEMPLATES.keys())
        chosen_impact_category = random.choice(all_impacts)
        templates_to_use = ANNOUNCEMENT_TEMPLATES[chosen_impact_category]
        impact = chosen_impact_category # Pour l'enregistrement dans la sortie

    if not templates_to_use:
        return {} # Pas de templates disponibles pour ce type

    template_data = random.choice(templates_to_use)
    template_text = template_data["template"]
    
    # Préparer les variables pour le formatage
    format_vars = {
        "company": company_name,
        "product": random.choice(PRODUCTS.get(stock_symbol, PRODUCTS["AAPL"])),
        "sector": random.choice(SECTORS),
        "percent": random.randint(5, 30) if impact == "positive" else random.randint(5, 20), # Plus de % pour positif, moins pour négatif
        "number": random.randint(500, 5000),
        "partner": random.choice([a for a in ACTORS if a != company_name.split()[0]]), 
        "technology": random.choice(["IA générative", "calcul quantique", "batteries solides", "biotechnologies de pointe", "réalité augmentée"]),
        "region": random.choice(REGIONS),
        "regulation": random.choice(REGULATIONS),
        "investment": random.randint(100, 1000) if impact == "positive" else random.randint(10, 200), 
        "location": random.choice(LOCATIONS),
        "competitor": random.choice([a for a in ACTORS if a != company_name.split()[0]]),
        "new_leader": random.choice(["un nouveau PDG", "un PDG par intérim", "un nouveau CTO", "un directeur financier expérimenté"]),
        "department": random.choice(["R&D", "stratégie produit", "opérations globales", "affaires juridiques"]),
        "project_name": random.choice(["Aurora", "Projet Titan", "Initiative Phoenix", "Quantum Leap"])
    }
    
    # S'assurer que le bon 'actor' est utilisé si le template l'exige
    if "actor" in template_data.get("vars", []):
         format_vars["actor"] = random.choice([a for a in ACTORS if a != company_name.split()[0]])

    text = template_text.format(**format_vars)
    
    # Add a slight random offset to the timestamp for realism
    offset_seconds = random.uniform(0, 1) 
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "stock": stock_symbol,
        "announcement": text,
        "impact": impact,
        "timestamp": timestamp
    }

def produce_announcements():
    """
    Initialise le producteur Kafka et envoie des annonces simulées au topic.
    """
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"Producteur Kafka pour les annonces connecté à {KAFKA_BROKER_URL}. Envoi au topic '{ANNOUNCEMENTS_TOPIC}'.")
    except Exception as e:
        print(f"Erreur de connexion Kafka pour le producteur d'annonces: {e}")
        return

    company_symbols = list(COMPANIES.keys())
    
    while True:
        try:
            # Décider si une annonce sera générée maintenant (par exemple, 50% de chance)
            if random.random() < 0.5: # 50% de chance d'avoir une annonce à chaque intervalle
                # Choisir une ou deux entreprises pour lesquelles générer une annonce
                num_companies_with_news = random.choice([1, 2])
                selected_companies = random.sample(company_symbols, num_companies_with_news)

                for symbol in selected_companies:
                    # Choisir aléatoirement l'impact de l'annonce (plus de neutre, moins d'extrême)
                    impact_choice = random.choices(['positive', 'negative', 'neutral'], weights=[0.2, 0.2, 0.6], k=1)[0]
                    
                    announcement = generate_random_announcement(symbol, impact=impact_choice)
                    if announcement:
                        producer.send(ANNOUNCEMENTS_TOPIC, announcement)
                        print(f"[{announcement['timestamp']}] Annonce pour {announcement['stock']} ({announcement['impact']}): {announcement['announcement'][:80]}...")
            
            time.sleep(ANNOUNCEMENT_INTERVAL_SECONDS) # Attendre avant la prochaine tentative d'annonce

        except Exception as e:
            print(f"Erreur lors de l'envoi de l'annonce à Kafka: {e}")
            time.sleep(5) 

if __name__ == "__main__":
    produce_announcements()