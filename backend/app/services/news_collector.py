import requests
from datetime import datetime, timedelta
from typing import List, Dict
from app.config import NEWSAPI_KEY

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Mapping entre le nom affiché (Enum) et les mots-clés de recherche NewsAPI
COMPETITOR_QUERIES = {
    "Mistral AI": "Mistral AI",
    "Hugging Face": "Hugging Face",
    "OpenAI": "OpenAI",
    "Anthropic": "Anthropic",
    "Google DeepMind": "Google DeepMind",
}


def fetch_articles_for_competitor(competitor_name: str, query: str, days_back: int = 7, page_size: int = 20) -> List[Dict]:
    """
    Récupère les articles NewsAPI pour un concurrent donné.
    Utilise qInTitle (recherche dans le titre uniquement) pour s'assurer que
    le concurrent est bien le sujet principal de l'article, et non une simple
    mention en passant dans le corps du texte.
    """
    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    params = {
        "qInTitle": f'"{query}"',  # recherche exacte, dans le titre uniquement
        "from": from_date,
        "sortBy": "publishedAt",
        "language": "fr",  # tu peux aussi faire une 2e requête en "en"
        "pageSize": page_size,
        "apiKey": NEWSAPI_KEY,
    }

    response = requests.get(NEWSAPI_URL, params=params)

    if response.status_code != 200:
        print(f"[ERREUR] NewsAPI a répondu {response.status_code} pour '{competitor_name}': {response.text}")
        return []

    data = response.json()
    raw_articles = data.get("articles", [])

    articles = []
    for item in raw_articles:
        # On ignore les articles sans contenu exploitable
        if not item.get("title") or not item.get("url"):
            continue

        articles.append({
            "title": item.get("title"),
            "content": item.get("content") or item.get("description") or "",
            "url": item.get("url"),
            "source": item.get("source", {}).get("name", "Inconnu"),
            "author": item.get("author"),
            "published_at": item.get("publishedAt"),
            "language": "fr",
            "competitor": competitor_name,
        })

    return articles


def fetch_all_competitors(days_back: int = 7) -> List[Dict]:
    """
    Récupère les articles pour les 5 concurrents suivis.
    """
    all_articles = []
    for competitor_name, query in COMPETITOR_QUERIES.items():
        print(f"Collecte pour : {competitor_name}...")
        articles = fetch_articles_for_competitor(competitor_name, query, days_back=days_back)
        print(f"  -> {len(articles)} article(s) trouvé(s)")
        all_articles.extend(articles)

    return all_articles