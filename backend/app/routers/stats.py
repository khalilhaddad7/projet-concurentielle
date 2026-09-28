"""
Endpoints de statistiques pour le Dashboard.

Toutes les routes sont protégées par get_current_user (connexion requise), comme
les routes de lecture existantes. Les agrégations sont faites EN SQL (GROUP BY +
AVG/COUNT/FILTER), jamais côté Python, pour rester performantes.

Note sur le "sentiment moyen" :
    La colonne `sentiment` est catégorielle (Positif/Neutre/Négatif) et
    `sentiment_score` est la CONFIANCE du modèle (0..1), pas une polarité. On ne
    peut donc pas moyenner sentiment_score. On construit une polarité numérique en
    SQL via un CASE : Positif=+1, Neutre=0, Négatif=-1. La moyenne de cette polarité
    donne un indice dans [-1, +1] (négatif = tonalité globale négative).
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import app.models as models
from app.models import CompetitorEnum, AlertCategoryEnum, SentimentEnum
from app.database import get_db
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/stats", tags=["Statistiques"])

# Polarité numérique du sentiment, calculée côté SQL (réutilisée par plusieurs routes).
_sentiment_polarity = case(
    (models.Article.sentiment == SentimentEnum.positif, 1.0),
    (models.Article.sentiment == SentimentEnum.negatif, -1.0),
    (models.Article.sentiment == SentimentEnum.neutre, 0.0),
    else_=None,
)


@router.get("/timeline")
def stats_timeline(
    competitor: Optional[CompetitorEnum] = None,
    period: int = Query(30, ge=1, le=365, description="Fenêtre en jours"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Évolution du sentiment moyen et du volume d'articles dans le temps.
    Agrégation par jour, ou par semaine si period > 60 jours (pour éviter des
    séries trop bruitées / trop de points sur une longue période).
    Filtrable sur un concurrent (sinon : tous concurrents confondus).
    """
    since = datetime.utcnow() - timedelta(days=period)
    grain = "week" if period > 60 else "day"

    # date_trunc regroupe les timestamps sur le début du jour/semaine (PostgreSQL).
    bucket = func.date_trunc(grain, models.Article.published_at).label("bucket")

    query = db.query(
        bucket,
        func.avg(_sentiment_polarity).label("sentiment_moyen"),
        func.count(models.Article.id).label("nombre_articles"),
    ).filter(models.Article.published_at >= since)

    if competitor is not None:
        query = query.filter(models.Article.competitor == competitor)

    rows = query.group_by(bucket).order_by(bucket).all()

    return [
        {
            "date": row.bucket.date().isoformat(),
            "sentiment_moyen": round(row.sentiment_moyen, 3) if row.sentiment_moyen is not None else None,
            "nombre_articles": row.nombre_articles,
        }
        for row in rows
    ]


@router.get("/comparison")
def stats_comparison(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Comparatif par concurrent en UNE seule requête agrégée : total d'articles,
    nombre d'alertes par catégorie (via COUNT ... FILTER), sentiment moyen, et
    date du dernier article.
    """
    rows = (
        db.query(
            models.Article.competitor.label("competitor"),
            func.count(models.Article.id).label("total"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.produit).label("produit"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.finance).label("finance"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.rh).label("rh"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.strategie).label("strategie"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.securite).label("securite"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.reglementation).label("reglementation"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.recherche).label("recherche"),
            func.count().filter(models.Article.alert_category == AlertCategoryEnum.non_classe).label("non_classe"),
            func.avg(_sentiment_polarity).label("sentiment_moyen"),
            func.max(models.Article.published_at).label("last_article"),
        )
        .group_by(models.Article.competitor)
        .all()
    )

    result = [
        {
            "competitor": row.competitor.value if row.competitor else None,
            "total_articles": row.total,
            "alerts": {
                "Produit": row.produit,
                "Finance": row.finance,
                "Ressources Humaines": row.rh,
                "Stratégie": row.strategie,
                "Sécurité": row.securite,
                "Réglementation": row.reglementation,
                "Recherche": row.recherche,
                "Non classé": row.non_classe,
            },
            "sentiment_moyen": round(row.sentiment_moyen, 3) if row.sentiment_moyen is not None else None,
            "last_article_date": row.last_article.isoformat() if row.last_article else None,
        }
        for row in rows
    ]
    result.sort(key=lambda item: item["total_articles"], reverse=True)
    return result


@router.get("/critical-timeline")
def stats_critical_timeline(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Articles marqués critiques (is_critical=True), triés du plus récent au plus
    ancien, limités à `limit` résultats.
    """
    rows = (
        db.query(models.Article)
        .filter(models.Article.is_critical == True)  # noqa: E712 (comparaison SQL)
        .order_by(models.Article.published_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": article.id,
            "date": article.published_at.isoformat() if article.published_at else None,
            "competitor": article.competitor.value if article.competitor else None,
            "category": article.alert_category.value if article.alert_category else None,
            "title": article.title,
            "url": article.url,
        }
        for article in rows
    ]
