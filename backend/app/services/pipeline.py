"""
Logique métier du pipeline : collecte → traitement NLP → indexation.

Ces fonctions sont partagées entre les endpoints (/collect, /process-nlp) et le
scheduler (cycle planifié / déclenchement manuel), pour éviter toute duplication.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

import app.models as models
from app.models import SentimentEnum, AlertCategoryEnum
from app.services.news_collector import fetch_all_competitors
from app.services.nlp_pipeline import (
    extract_entities,
    extract_financial_amount,
    analyze_sentiment,
    classify_alert_category,
    generate_summary,
)
from app.services.rag_engine import index_all_articles
from app.services import notifications

logger = logging.getLogger(__name__)


def run_collect(db: Session, days_back: int = 7) -> Dict[str, Any]:
    """Collecte les articles NewsAPI et insère les nouveaux (dédup par URL)."""
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

        db.add(models.Article(
            title=item["title"],
            content=item["content"],
            url=url,
            source=item["source"],
            author=item.get("author"),
            published_at=published_at,
            language=item.get("language", "fr"),
            competitor=item["competitor"],
        ))
        inserted += 1

    db.commit()
    return {
        "message": "Collecte terminée",
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "total_fetched": len(raw_articles),
    }


def run_nlp(db: Session, limit: int = 20) -> Dict[str, Any]:
    """
    Traite les articles non traités (spaCy/CamemBERT/mDeBERTa + résumé Ollama).
    Un article n'est marqué is_processed=True que si toutes les étapes réussissent
    (résumé + sentiment). Déclenche une alerte pour chaque article critique
    nouvellement traité — l'échec d'une alerte ne bloque jamais le traitement.
    """
    articles = db.query(models.Article).filter(models.Article.is_processed == False).limit(limit).all()

    processed = 0
    incomplete = 0
    errors = 0
    newly_critical = []

    for article in articles:
        # On réinitialise l'erreur avant chaque tentative (re-remplie seulement si échec).
        article.processing_error = None
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
            # is_critical repose désormais sur le booléen "critique" renvoyé par le
            # classifieur (événement majeur), et non plus sur un score de confiance :
            # Groq est presque toujours très confiant, donc la confiance seule ne
            # discriminait plus rien. Un article "Non classé" n'est jamais critique.
            article.is_critical = (
                alert_result["category"] != "Non classé"
                and bool(alert_result.get("is_critical"))
            )

            article.summary = summary

            missing = []
            if not summary:
                missing.append("résumé (Ollama)")
            if not sentiment["label"]:
                missing.append("sentiment")

            if not missing:
                article.is_processed = True
                processed += 1
                if article.is_critical:
                    newly_critical.append(article)
            else:
                article.processing_error = "Traitement incomplet : " + ", ".join(missing)
                incomplete += 1
        except Exception as e:  # noqa: BLE001
            article.processing_error = str(e)
            errors += 1

    db.commit()

    # Alertes APRÈS commit (l'état est persisté). notify_critical_article ne lève jamais.
    for article in newly_critical:
        notifications.notify_critical_article(db, article)

    return {
        "message": "Traitement NLP terminé",
        "processed": processed,
        "incomplete": incomplete,
        "errors": errors,
        "critical": len(newly_critical),
        "remaining": db.query(models.Article).filter(models.Article.is_processed == False).count(),
    }


def execute_full_cycle(db: Session, days_back: int = 7, nlp_limit: int = 50) -> models.SchedulerRun:
    """
    Cycle complet collecte → NLP → indexation, journalisé dans SchedulerRun.
    Renvoie l'enregistrement SchedulerRun (avec status et chiffres).
    """
    run = models.SchedulerRun(status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("Cycle planifié #%s démarré.", run.id)

    try:
        collect_result = run_collect(db, days_back=days_back)
        nlp_result = run_nlp(db, limit=nlp_limit)
        index_result = index_all_articles(db)

        run.articles_collected = collect_result.get("inserted", 0)
        run.articles_processed = nlp_result.get("processed", 0)
        run.articles_indexed = index_result.get("indexed", 0)
        run.status = "success"
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.info(
            "Cycle #%s terminé : %s collectés, %s traités, %s indexés.",
            run.id, run.articles_collected, run.articles_processed, run.articles_indexed,
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        run.status = "error"
        run.error_message = str(e)[:2000]
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.error("Cycle planifié #%s en échec : %s", run.id, e, exc_info=True)

    return run
