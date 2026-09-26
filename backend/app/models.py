from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class CompetitorEnum(str, enum.Enum):
    mistral_ai = "Mistral AI"
    hugging_face = "Hugging Face"
    openai = "OpenAI"
    anthropic = "Anthropic"
    google_deepmind = "Google DeepMind"


class AlertCategoryEnum(str, enum.Enum):
    produit = "Produit"
    finance = "Finance"
    rh = "Ressources Humaines"
    strategie = "Stratégie"
    non_classe = "Non classé"


class SentimentEnum(str, enum.Enum):
    positif = "Positif"
    neutre = "Neutre"
    negatif = "Négatif"


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)

    # --- Contenu brut ---
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String(1000), unique=True, index=True)
    source = Column(String(150))  # ex: "TechCrunch", "Le Monde"
    author = Column(String(200), nullable=True)
    published_at = Column(DateTime, nullable=True)
    language = Column(String(10), default="fr")  # fr / en

    # --- Ciblage concurrent ---
    competitor = Column(Enum(CompetitorEnum), nullable=False, index=True)

    # --- Résultats du pipeline NLP ---
    summary = Column(Text, nullable=True)                # généré par BART
    sentiment = Column(Enum(SentimentEnum), nullable=True)  # CamemBERT
    sentiment_score = Column(Float, nullable=True)        # score de confiance
    entities = Column(JSON, nullable=True)                # sortie spaCy : {"ORG": [...], "MONEY": [...], "PERSON": [...]}

    # --- Détection d'événements ---
    alert_category = Column(Enum(AlertCategoryEnum), default=AlertCategoryEnum.non_classe, index=True)
    financial_amount = Column(Float, nullable=True)       # montant extrait si Finance (en millions $)
    is_critical = Column(Boolean, default=False)          # marqué comme événement majeur

    # --- Vectorisation / RAG ---
    embedding_id = Column(String(100), nullable=True, index=True)  # référence vers l'ID du vecteur dans ChromaDB
    is_embedded = Column(Boolean, default=False)           # a été traité par Sentence-BERT ?

    # --- Métadonnées pipeline ---
    is_processed = Column(Boolean, default=False)          # NLP déjà exécuté ?
    processing_error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())