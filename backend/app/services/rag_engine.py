import ollama
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import app.models as models
import chromadb
from chromadb.config import Settings
from groq import Groq
from app.config import GROQ_API_KEY

# ─── Configuration ───────────────────────────────────────────────

EMBEDDING_MODEL = "nomic-embed-text"      # Ollama reste pour les embeddings
LLM_MODEL = "openai/gpt-oss-120b"   # ✅ Modèle Groq actuel et rapide
CHROMA_PATH = "./chroma_db"

# La clé API Groq provient de la variable d'environnement GROQ_API_KEY
# (chargée et validée dans app.config), jamais codée en dur.
groq_client = Groq(api_key=GROQ_API_KEY)

# Mots-clés pour détecter une salutation / conversation générale
GREETINGS = [
    "bonjour", "salut", "hello", "hi", "hey", "coucou", "bonsoir",
    "ça va", "ca va", "comment vas-tu", "comment allez-vous",
    "comment ça va", "quoi de neuf", "yo", "bonjour comment",
]

# ─── Client ChromaDB ───────────────────────────────────────────────

def get_chroma_client():
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )
    return client


def get_articles_collection(client=None):
    if client is None:
        client = get_chroma_client()
    return client.get_or_create_collection(
        name="articles",
        metadata={"description": "Articles de veille concurrentielle"}
    )


# ─── Embeddings (reste sur Ollama) ─────────────────────────────────

def embed_text(text: str) -> List[float]:
    """Génère un vecteur d'embedding via Ollama (nomic-embed-text)."""
    response = ollama.embeddings(
        model=EMBEDDING_MODEL,
        prompt=text
    )
    return response["embedding"]


# ─── Indexation ────────────────────────────────────────────────────

def index_article(article: models.Article, collection=None) -> bool:
    if collection is None:
        collection = get_articles_collection()

    if not article.title and not article.content:
        return False

    text_to_embed = f"{article.title or ''}\n\n{article.content or ''}"[:4000]

    metadata = {
        "title": article.title or "",
        "url": article.url or "",
        "source": article.source or "",
        "competitor": article.competitor or "",
        "alert_category": article.alert_category.value if article.alert_category else "Non classé",
        "sentiment": article.sentiment.value if article.sentiment else "Inconnu",
        "published_at": article.published_at.isoformat() if article.published_at else "",
        "summary": article.summary or "",
    }

    try:
        collection.upsert(
            ids=[str(article.id)],
            documents=[text_to_embed],
            metadatas=[metadata],
            embeddings=[embed_text(text_to_embed)]
        )
        return True
    except Exception as e:
        print(f"[ERREUR Indexation] Article {article.id} : {e}")
        return False


def index_all_articles(db: Session, limit: Optional[int] = None) -> Dict[str, Any]:
    collection = get_articles_collection()
    query = db.query(models.Article).filter(models.Article.is_processed == True)
    if limit:
        query = query.limit(limit)

    articles = query.all()
    indexed = 0
    errors = 0

    for article in articles:
        if index_article(article, collection):
            indexed += 1
        else:
            errors += 1

    return {
        "indexed": indexed,
        "errors": errors,
        "total_in_db": len(articles)
    }


# ─── Recherche sémantique ──────────────────────────────────────────

def search_articles(
    query: str,
    n_results: int = 5,
    competitor_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    collection = get_articles_collection()
    query_embedding = embed_text(query)

    where_filter = None
    if competitor_filter:
        where_filter = {"competitor": competitor_filter}

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["metadatas", "distances", "documents"]
        )
    except Exception as e:
        print(f"[ERREUR Recherche] {e}")
        return []

    articles = []
    if results and results["ids"]:
        for i, article_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            doc = results["documents"][0][i] if results["documents"] else ""

            articles.append({
                "id": article_id,
                "title": meta.get("title", ""),
                "summary": meta.get("summary", ""),
                "url": meta.get("url", ""),
                "competitor": meta.get("competitor", ""),
                "alert_category": meta.get("alert_category", "Non classé"),
                "sentiment": meta.get("sentiment", "Inconnu"),
                "distance": round(distance, 4),
                "content_preview": doc[:300] + "..." if len(doc) > 300 else doc
            })

    return articles


# ─── Génération RAG ────────────────────────────────────────────────

def build_rag_prompt(query: str, articles: List[Dict[str, Any]]) -> str:
    if not articles:
        context = "Aucun article pertinent n'a été trouvé dans la base de connaissances."
    else:
        context_parts = []
        for i, art in enumerate(articles, 1):
            part = (
                f"--- Article {i} ---\n"
                f"Titre : {art['title']}\n"
                f"Catégorie : {art['alert_category']}\n"
                f"Résumé : {art['summary'] or art['content_preview']}\n"
                f"Source : {art['url']}\n"
            )
            context_parts.append(part)
        context = "\n".join(context_parts)

    prompt = (
        "Tu es un assistant de veille stratégique spécialisé. Tu as accès à une base "
        "d'articles de veille concurrentielle.\n\n"
        "RÈGLES STRICTES :\n"
        "1. Réponds UNIQUEMENT en te basant sur les articles fournis ci-dessous.\n"
        "2. Tu ne dois JAMAIS inventer d'informations.\n"
        "3. Si les articles ne contiennent pas la réponse, dis explicitement : "
        "\"Je n'ai pas trouvé d'information à ce sujet dans les articles indexés.\"\n"
        "4. Sois factuel, concis, et cite les titres des articles quand tu t'y réfères.\n\n"
        f"QUESTION : {query}\n\n"
        f"ARTICLES :\n{context}\n\n"
        "RÉPONSE :"
    )
    return prompt


def is_greeting(query: str) -> bool:
    """Détecte si la question est une salutation ou conversation générale."""
    q = query.lower().strip()
    if len(q.split()) > 5:
        return False
    return any(g in q for g in GREETINGS)


def chat_rag(query: str, n_results: int = 3) -> Dict[str, Any]:
    """
    Pipeline complet RAG avec Groq (LLM rapide) + Ollama (embeddings).
    """
    # 1. Si c'est une salutation, répondre directement via Groq
    if is_greeting(query):
        try:
            response = groq_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{
                    "role": "user",
                    "content": (
                        f"L'utilisateur dit : '{query}'. "
                        "Réponds de manière naturelle, polie et concise en français. "
                        "Présente-toi brièvement comme un assistant de veille stratégique "
                        "et propose de l'aider sur les articles collectés."
                    )
                }],
                temperature=0.7,
                max_tokens=150,
            )
            return {
                "query": query,
                "answer": response.choices[0].message.content.strip(),
                "sources": [],
                "success": True
            }
        except Exception:
            return {
                "query": query,
                "answer": "Bonjour ! Je suis votre assistant de veille stratégique. Comment puis-je vous aider aujourd'hui ?",
                "sources": [],
                "success": True
            }

    # 2. Recherche sémantique normale
    articles = search_articles(query, n_results=n_results)

    # 3. Prompt + Génération Groq
    prompt = build_rag_prompt(query, articles)

    try:
        response = groq_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=250,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return {
            "query": query,
            "answer": f"[ERREUR Groq] Impossible de générer la réponse : {e}",
            "sources": [],
            "success": False
        }

    return {
        "query": query,
        "answer": answer,
        "sources": [
            {
                "title": a["title"],
                "url": a["url"],
                "competitor": a["competitor"],
                "category": a["alert_category"],
                "relevance_score": a["distance"]
            }
            for a in articles
        ],
        "success": True
    }