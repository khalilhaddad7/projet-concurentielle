"""
Chatbot RAG conversationnel : conversations liées à l'utilisateur, historique,
feedback et suggestions. Toutes les routes exigent une connexion (get_current_user).
"""

import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.models import AlertCategoryEnum
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.services.rag_engine import chat_rag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chatbot"])


def _title_from_query(query: str) -> str:
    q = query.strip()
    return (q[:60] + "…") if len(q) > 60 else (q or "Nouvelle conversation")


def _log_action(db: Session, user_id: int, action: str, details: str) -> None:
    try:
        db.add(models.ActionLog(user_id=user_id, action=action, details=details))
        db.commit()
    except Exception:  # noqa: BLE001 — l'audit ne doit jamais casser la requête
        db.rollback()


def _get_owned_conversation(db: Session, conversation_id: int, user: models.User) -> models.Conversation:
    conv = db.get(models.Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    if conv.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cette conversation ne vous appartient pas.")
    return conv


@router.post("/chat", response_model=schemas.ChatResponse)
def chat_endpoint(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")

    # 1. Conversation : existante (vérif appartenance) ou nouvelle.
    if payload.conversation_id is not None:
        conv = _get_owned_conversation(db, payload.conversation_id, current_user)
    else:
        conv = models.Conversation(user_id=current_user.id, title=_title_from_query(query))
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # 2. Historique AVANT d'ajouter le nouveau message (contexte pour Groq).
    history = [{"role": m.role.value, "content": m.content} for m in conv.messages]

    # 3. Enregistre le message utilisateur.
    db.add(models.Message(conversation_id=conv.id, role=models.MessageRole.user, content=query))
    db.commit()

    # 4. RAG avec historique.
    result = chat_rag(query, history=history, n_results=payload.n_results)
    sources = result.get("sources") or []

    # 5. Enregistre la réponse de l'assistant (avec ses sources).
    assistant = models.Message(
        conversation_id=conv.id,
        role=models.MessageRole.assistant,
        content=result.get("answer", ""),
        sources_json=sources,
    )
    db.add(assistant)
    conv.updated_at = datetime.utcnow()  # remonte la conversation en tête de liste
    db.commit()
    db.refresh(assistant)

    _log_action(db, current_user.id, "chat_question", query[:1000])

    return schemas.ChatResponse(
        conversation_id=conv.id,
        assistant_message_id=assistant.id,
        query=query,
        answer=result.get("answer", ""),
        sources=sources,
        success=result.get("success", True),
    )


@router.get("/conversations", response_model=List[schemas.ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user.id)
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )


@router.get("/conversations/{conversation_id}", response_model=schemas.ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_owned_conversation(db, conversation_id, current_user)
    messages = [
        schemas.MessageResponse(
            id=m.id, role=m.role, content=m.content,
            sources=m.sources_json, feedback=m.feedback, created_at=m.created_at,
        )
        for m in conv.messages
    ]
    return schemas.ConversationDetailResponse(id=conv.id, title=conv.title, messages=messages)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_owned_conversation(db, conversation_id, current_user)
    db.delete(conv)  # cascade -> supprime aussi les messages (pas d'orphelins)
    db.commit()
    return {"deleted": True, "conversation_id": conversation_id}


@router.post("/messages/{message_id}/feedback", response_model=schemas.MessageResponse)
def set_message_feedback(
    message_id: int,
    payload: schemas.FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    msg = db.get(models.Message, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Message introuvable.")
    # Appartenance via la conversation.
    conv = db.get(models.Conversation, msg.conversation_id)
    if conv is None or conv.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ce message ne vous appartient pas.")
    if msg.role != models.MessageRole.assistant:
        raise HTTPException(status_code=400, detail="Le feedback ne s'applique qu'aux réponses de l'assistant.")

    msg.feedback = payload.feedback
    db.commit()
    db.refresh(msg)
    return schemas.MessageResponse(
        id=msg.id, role=msg.role, content=msg.content,
        sources=msg.sources_json, feedback=msg.feedback, created_at=msg.created_at,
    )


@router.get("/chat/suggestions", response_model=schemas.SuggestionsResponse)
def chat_suggestions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Suggestions basées sur les concurrents/catégories les plus actifs des 7 derniers jours."""
    since = datetime.utcnow() - timedelta(days=7)
    suggestions: List[str] = []

    # Combos (concurrent, catégorie) les plus fréquents, hors "Non classé".
    rows = (
        db.query(
            models.Article.competitor,
            models.Article.alert_category,
            func.count(models.Article.id).label("n"),
        )
        .filter(
            models.Article.published_at >= since,
            models.Article.alert_category != AlertCategoryEnum.non_classe,
        )
        .group_by(models.Article.competitor, models.Article.alert_category)
        .order_by(func.count(models.Article.id).desc())
        .limit(5)
        .all()
    )
    for comp, cat, _n in rows:
        if comp and cat:
            suggestions.append(f"Quelles alertes {cat.value} chez {comp.value} cette semaine ?")

    # Complément : concurrents les plus actifs (toutes catégories) sur 7 jours.
    if len(suggestions) < 3:
        comp_rows = (
            db.query(models.Article.competitor, func.count(models.Article.id))
            .filter(models.Article.published_at >= since)
            .group_by(models.Article.competitor)
            .order_by(func.count(models.Article.id).desc())
            .limit(3)
            .all()
        )
        for comp, _n in comp_rows:
            if comp:
                q = f"Quelles sont les dernières actualités de {comp.value} cette semaine ?"
                if q not in suggestions:
                    suggestions.append(q)

    # Filet de sécurité si la base est vide sur 7 jours.
    for fallback in (
        "Quels sont les événements critiques récents ?",
        "Quelles sont les dernières annonces produit ?",
        "Y a-t-il eu des levées de fonds récemment ?",
    ):
        if len(suggestions) >= 5:
            break
        if fallback not in suggestions:
            suggestions.append(fallback)

    return schemas.SuggestionsResponse(suggestions=suggestions[:5])
