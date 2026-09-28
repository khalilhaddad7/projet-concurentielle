from pydantic import BaseModel, HttpUrl, Field, EmailStr
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models import CompetitorEnum, AlertCategoryEnum, SentimentEnum, UserRole, MessageRole, FeedbackEnum


# ─── Authentification ────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Inscription : email + mot de passe (min. 8 caractères)."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    """Infos publiques d'un utilisateur (jamais le mot de passe)."""
    id: int
    email: EmailStr
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ─── Scheduler & Alertes ─────────────────────────────────────────────

class SchedulerRunResponse(BaseModel):
    id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    articles_collected: int
    articles_processed: int
    articles_indexed: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SchedulerStatusResponse(BaseModel):
    scheduler_running: bool
    next_run: Optional[datetime] = None
    interval_hours: float
    history: List[SchedulerRunResponse]


class AlertConfigResponse(BaseModel):
    id: int
    category: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertConfigUpdate(BaseModel):
    enabled: bool


# ─── Chatbot conversationnel ─────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[int] = None
    n_results: int = 5


class MessageResponse(BaseModel):
    id: int
    role: MessageRole
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    feedback: Optional[FeedbackEnum] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    conversation_id: int
    assistant_message_id: Optional[int] = None
    query: str
    answer: str
    sources: List[Dict[str, Any]] = []
    success: bool


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    id: int
    title: str
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True


class FeedbackRequest(BaseModel):
    feedback: FeedbackEnum


class SuggestionsResponse(BaseModel):
    suggestions: List[str]


class Token(BaseModel):
    """Réponse de /auth/login : access + refresh tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    """Réponse de /auth/refresh : uniquement un nouvel access token."""
    access_token: str
    token_type: str = "bearer"


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