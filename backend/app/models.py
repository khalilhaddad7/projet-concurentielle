from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    """Rôles applicatifs. 'admin' peut tout faire ; 'lecteur' ne fait que lire."""
    admin = "admin"
    lecteur = "lecteur"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class FeedbackEnum(str, enum.Enum):
    positif = "positif"
    negatif = "negatif"


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
    # Catégories ajoutées pour mieux couvrir les vrais sujets des articles.
    # ATTENTION : SQLAlchemy stocke le NOM du membre (ex: "securite"), pas la
    # valeur affichée ("Sécurité"). Ces noms sont donc les valeurs ajoutées au
    # type enum PostgreSQL par la migration Alembic correspondante.
    securite = "Sécurité"
    reglementation = "Réglementation"
    recherche = "Recherche"
    non_classe = "Non classé"


class SentimentEnum(str, enum.Enum):
    positif = "Positif"
    neutre = "Neutre"
    negatif = "Négatif"


class User(Base):
    """Compte utilisateur pouvant s'authentifier sur l'API."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # On ne stocke JAMAIS le mot de passe en clair : uniquement son hash bcrypt.
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.lecteur)
    created_at = Column(DateTime, server_default=func.now())

    action_logs = relationship("ActionLog", back_populates="user")


class ActionLog(Base):
    """Journal des actions sensibles (audit) : qui a fait quoi et quand."""
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    # user_id nullable : on garde la trace même si l'utilisateur est supprimé
    # (ou pour une action système sans utilisateur identifié).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # ex: "collecte_lancee"
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    details = Column(Text, nullable=True)  # texte libre ou JSON sérialisé

    user = relationship("User", back_populates="action_logs")


class SchedulerRun(Base):
    """Journal d'un cycle planifié (collecte → NLP → indexation)."""
    __tablename__ = "scheduler_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running / success / error
    articles_collected = Column(Integer, default=0)
    articles_processed = Column(Integer, default=0)
    articles_indexed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


class AlertConfig(Base):
    """Active/désactive les alertes par catégorie d'article (une ligne par catégorie)."""
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), unique=True, nullable=False, index=True)  # ex: "Finance"
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Conversation(Base):
    """Une conversation du chatbot RAG, rattachée à un utilisateur."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="Nouvelle conversation")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Supprimer une conversation supprime ses messages (pas d'orphelins).
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """Un message (utilisateur ou assistant) dans une conversation."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    sources_json = Column(JSON, nullable=True)  # sources citées par le RAG
    feedback = Column(Enum(FeedbackEnum), nullable=True)  # null tant que non noté
    created_at = Column(DateTime, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)

    # --- Contenu brut ---
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String(1000), unique=True, index=True)
    source = Column(String(150))  # ex: "TechCrunch", "Le Monde"
    author = Column(String(200), nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)  # filtré/trié par les stats
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
    is_critical = Column(Boolean, default=False, index=True)  # marqué comme événement majeur (filtré par les stats)

    # --- Vectorisation / RAG ---
    embedding_id = Column(String(100), nullable=True, index=True)  # référence vers l'ID du vecteur dans ChromaDB
    is_embedded = Column(Boolean, default=False)           # a été traité par Sentence-BERT ?

    # --- Métadonnées pipeline ---
    is_processed = Column(Boolean, default=False)          # NLP déjà exécuté ?
    processing_error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())