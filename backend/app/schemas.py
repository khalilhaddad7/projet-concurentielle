from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models import CompetitorEnum, AlertCategoryEnum, SentimentEnum


class ArticleBase(BaseModel):
    title: str
    content: str
    url: str
    source: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    language: Optional[str] = "fr"
    competitor: CompetitorEnum


class ArticleCreate(ArticleBase):
    """Utilisé lors de l'ingestion brute (collecte), avant traitement NLP."""
    pass


class ArticleUpdateNLP(BaseModel):
    """Utilisé par le pipeline NLP pour mettre à jour un article après traitement."""
    summary: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    sentiment_score: Optional[float] = None
    entities: Optional[Dict[str, Any]] = None
    alert_category: Optional[AlertCategoryEnum] = None
    financial_amount: Optional[float] = None
    is_critical: Optional[bool] = None
    is_processed: Optional[bool] = None


class ArticleResponse(ArticleBase):
    id: int
    summary: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    sentiment_score: Optional[float] = None
    entities: Optional[Dict[str, Any]] = None
    alert_category: Optional[AlertCategoryEnum] = None
    financial_amount: Optional[float] = None
    is_critical: bool = False
    is_processed: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    """Réponse paginée pour lister les articles."""
    total: int
    items: List[ArticleResponse]