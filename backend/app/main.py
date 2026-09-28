import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import List, Optional
import app.models as models
import app.schemas as schemas
from app.database import get_db, SessionLocal
from app.services.rag_engine import index_all_articles
from app.services import pipeline
from app.services import notifications
from app.services import scheduler as scheduler_service
from app.models import AlertCategoryEnum
from fastapi.middleware.cors import CORSMiddleware

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD
from app.routers import auth as auth_router
from app.routers import stats as stats_router
from app.routers import scheduler as scheduler_router
from app.routers import alerts as alerts_router
from app.routers import chat as chat_router
from app.routers import export as export_router
from app.auth.dependencies import get_current_user, require_admin
from app.auth.security import hash_password

logger = logging.getLogger(__name__)


def log_action(db: Session, user_id: Optional[int], action: str, details: Optional[str] = None) -> None:
    """
    Enregistre une action sensible dans ActionLog (audit).
    Ne doit jamais faire échouer la requête principale : en cas d'erreur, on log
    et on continue.
    """
    try:
        db.add(models.ActionLog(user_id=user_id, action=action, details=details))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("Impossible d'enregistrer l'action '%s' dans ActionLog.", action, exc_info=True)


def create_default_admin() -> None:
    """
    Crée un compte admin par défaut au démarrage à partir de ADMIN_EMAIL /
    ADMIN_PASSWORD. Log un avertissement si ces variables ne sont pas définies,
    afin de ne pas rester bloqué dehors sans le savoir.
    """
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        logger.warning(
            "ADMIN_EMAIL / ADMIN_PASSWORD non définis : aucun compte admin par défaut créé. "
            "Renseignez-les dans backend/.env pour créer automatiquement un administrateur."
        )
        return

    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()
        if existing:
            logger.info("Compte admin par défaut déjà présent (%s).", ADMIN_EMAIL)
            return
        admin = models.User(
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=models.UserRole.admin,
        )
        db.add(admin)
        db.commit()
        logger.info("Compte admin par défaut créé : %s", ADMIN_EMAIL)
    except SQLAlchemyError:
        db.rollback()
        logger.error("Impossible de créer le compte admin par défaut.", exc_info=True)
    finally:
        db.close()


def seed_alert_configs() -> None:
    """Crée une AlertConfig (activée) pour chaque catégorie alertable si absente."""
    db = SessionLocal()
    try:
        for cat in AlertCategoryEnum:
            if cat == AlertCategoryEnum.non_classe:
                continue  # "Non classé" ne déclenche jamais d'alerte
            exists = db.query(models.AlertConfig).filter(models.AlertConfig.category == cat.value).first()
            if not exists:
                db.add(models.AlertConfig(category=cat.value, enabled=True))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("Impossible d'initialiser les AlertConfig.", exc_info=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─── Démarrage ───
    # Le schéma de la base est géré par Alembic (alembic upgrade head), plus par
    # create_all(). On initialise ici l'admin, la config d'alertes, et le scheduler.
    create_default_admin()
    seed_alert_configs()
    notifications.log_notification_startup_state()
    try:
        scheduler_service.start_scheduler()
    except Exception:  # noqa: BLE001 — un scheduler qui échoue ne doit pas empêcher l'API de démarrer
        logger.error("Impossible de démarrer le scheduler.", exc_info=True)

    yield

    # ─── Extinction ───
    scheduler_service.shutdown_scheduler()


# Créer l'application FastAPI
app = FastAPI(
    title="Veille Concurrentielle API",
    description="API pour la plateforme de veille stratégique",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # URL du frontend Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes d'authentification (/auth/register, /auth/login, /auth/refresh, /auth/me)
app.include_router(auth_router.router)
# Routes de statistiques pour le Dashboard (/stats/timeline, /comparison, /critical-timeline)
app.include_router(stats_router.router)
# Scheduler (/scheduler/status, /scheduler/trigger) et alertes (/alert-config, /alerts/test)
app.include_router(scheduler_router.router)
app.include_router(alerts_router.router)
# Chatbot conversationnel (/chat, /conversations, /messages/{id}/feedback, /chat/suggestions)
app.include_router(chat_router.router)
# Exports (/export/articles, /export/report/{competitor}, /export/weekly-report)
app.include_router(export_router.router)


@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API Veille Concurrentielle !"}


@app.get("/articles", response_model=List[schemas.ArticleResponse])
def get_articles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # lecture : connexion requise
):
    try:
        articles = db.query(models.Article).offset(skip).limit(limit).all()
        return articles
    except SQLAlchemyError:
        logger.error("Erreur base de données lors de la lecture des articles.", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="La base de données est momentanément indisponible. Merci de réessayer plus tard.",
        )


@app.post("/articles", response_model=schemas.ArticleResponse)
def create_article(
    article: schemas.ArticleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),  # création manuelle : admin
):
    try:
        db_article = models.Article(**article.model_dump())
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        return db_article
    except SQLAlchemyError:
        db.rollback()
        logger.error("Erreur base de données lors de la création d'un article.", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Impossible d'enregistrer l'article : la base de données est momentanément indisponible.",
        )


@app.post("/collect")
def collect_articles(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),  # réservé aux admins
):
    try:
        result = pipeline.run_collect(db, days_back=days_back)
        # Journalise l'action sensible (audit) avec l'id de l'utilisateur.
        log_action(
            db,
            user_id=current_user.id,
            action="collecte_lancee",
            details=json.dumps(
                {
                    "days_back": days_back,
                    "inserted": result.get("inserted"),
                    "skipped_duplicates": result.get("skipped_duplicates"),
                },
                ensure_ascii=False,
            ),
        )
        return result
    except SQLAlchemyError:
        db.rollback()
        logger.error("Erreur base de données lors de la collecte des articles.", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Impossible d'enregistrer les articles collectés : la base de données est momentanément indisponible.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.error("Erreur inattendue lors de la collecte des articles.", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Une erreur est survenue pendant la collecte des articles. Merci de réessayer plus tard.",
        )


@app.post("/process-nlp")
def process_nlp(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),  # réservé aux admins
):
    # La logique (Option A + réinitialisation de processing_error + alertes sur
    # articles critiques) vit dans pipeline.run_nlp, partagée avec le scheduler.
    return pipeline.run_nlp(db, limit=limit)


# ═══════════════════════════════════════════════════════════════
# PHASE 4 — EMBEDDINGS + RAG
# ═══════════════════════════════════════════════════════════════

@app.post("/index-articles")
def index_articles_endpoint(
    limit: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),  # réservé aux admins
):
    """
    Indexe les articles déjà traités (is_processed=true) dans ChromaDB
    pour permettre la recherche sémantique et le chatbot RAG.
    """
    result = index_all_articles(db, limit=limit)
    return {
        "message": "Indexation terminée",
        **result
    }


# Le chatbot RAG (/chat) est désormais géré par app/routers/chat.py (mode
# conversationnel : conversations, historique, feedback, suggestions).