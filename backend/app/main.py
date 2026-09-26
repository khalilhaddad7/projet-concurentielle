from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import app.models as models
import app.schemas as schemas
from app.database import engine, get_db
from app.services.news_collector import fetch_all_competitors
from datetime import datetime
from app.services.nlp_pipeline import (
    extract_entities,
    extract_financial_amount,
    analyze_sentiment,
    classify_alert_category,
    generate_summary,
)
from app.services.rag_engine import index_all_articles, chat_rag
from app.models import SentimentEnum, AlertCategoryEnum
from fastapi.middleware.cors import CORSMiddleware

# Créer les tables dans la base de données
models.Base.metadata.create_all(bind=engine)

# Créer l'application FastAPI
app = FastAPI(
    title="Veille Concurrentielle API",
    description="API pour la plateforme de veille stratégique",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # URL du frontend Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API Veille Concurrentielle !"}


@app.get("/articles", response_model=List[schemas.ArticleResponse])
def get_articles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    articles = db.query(models.Article).offset(skip).limit(limit).all()
    return articles


@app.post("/articles", response_model=schemas.ArticleResponse)
def create_article(article: schemas.ArticleCreate, db: Session = Depends(get_db)):
    db_article = models.Article(**article.model_dump())
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article


@app.post("/collect")
def collect_articles(days_back: int = 7, db: Session = Depends(get_db)):
    raw_articles = fetch_all_competitors(days_back=days_back)

    inserted = 0
    skipped = 0
    seen_urls_this_batch = set()

    for item in raw_articles:
        url = item["url"]

        if url in seen_urls_this_batch:
            skipped += 1
            continue

        existing = db.query(models.Article).filter(models.Article.url == url).first()
        if existing:
            skipped += 1
            continue

        seen_urls_this_batch.add(url)

        published_at = None
        if item.get("published_at"):
            try:
                published_at = datetime.strptime(item["published_at"], "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                published_at = None

        db_article = models.Article(
            title=item["title"],
            content=item["content"],
            url=url,
            source=item["source"],
            author=item.get("author"),
            published_at=published_at,
            language=item.get("language", "fr"),
            competitor=item["competitor"],
        )
        db.add(db_article)
        inserted += 1

    db.commit()

    return {
        "message": "Collecte terminée",
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "total_fetched": len(raw_articles)
    }


@app.post("/process-nlp")
def process_nlp(limit: int = 20, db: Session = Depends(get_db)):
    articles = db.query(models.Article).filter(models.Article.is_processed == False).limit(limit).all()

    processed = 0
    errors = 0

    for article in articles:
        try:
            text = f"{article.title}. {article.content or ''}"

            entities = extract_entities(text)
            financial_amount = extract_financial_amount(text)
            sentiment = analyze_sentiment(text)
            alert_result = classify_alert_category(text)
            summary = generate_summary(text)

            article.entities = entities
            article.financial_amount = financial_amount

            if sentiment["label"]:
                article.sentiment = SentimentEnum(sentiment["label"])
                article.sentiment_score = sentiment["score"]

            article.alert_category = AlertCategoryEnum(alert_result["category"])
            article.is_critical = (
                alert_result["category"] != "Non classé"
                and (alert_result.get("confidence") or 0) > 0.6
            )

            article.summary = summary

            article.is_processed = True

            processed += 1
        except Exception as e:
            article.processing_error = str(e)
            errors += 1

    db.commit()

    return {
        "message": "Traitement NLP terminé",
        "processed": processed,
        "errors": errors,
        "remaining": db.query(models.Article).filter(models.Article.is_processed == False).count()
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 4 — EMBEDDINGS + RAG
# ═══════════════════════════════════════════════════════════════

@app.post("/index-articles")
def index_articles_endpoint(limit: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Indexe les articles déjà traités (is_processed=true) dans ChromaDB
    pour permettre la recherche sémantique et le chatbot RAG.
    """
    result = index_all_articles(db, limit=limit)
    return {
        "message": "Indexation terminée",
        **result
    }


@app.post("/chat")
def chat_endpoint(query: str, n_results: int = 5):
    """
    Chatbot RAG : pose une question, il cherche dans les articles
    et génère une réponse factuelle basée sur tes données.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")

    result = chat_rag(query, n_results=n_results)
    return result