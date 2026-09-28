"""
Endpoints d'authentification : /auth/register, /auth/login, /auth/refresh, /auth/me.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.models as models
import app.schemas as schemas
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """Crée un compte avec le rôle 'lecteur' par défaut."""
    try:
        existing = db.query(models.User).filter(models.User.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un compte existe déjà avec cet email.",
            )

        user = models.User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            role=models.UserRole.lecteur,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.error("Erreur base de données lors de l'inscription.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impossible de créer le compte : base de données indisponible.",
        )


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Vérifie les identifiants et renvoie un access token + un refresh token."""
    try:
        user = db.query(models.User).filter(models.User.email == payload.email).first()
    except SQLAlchemyError:
        logger.error("Erreur base de données lors de la connexion.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connexion impossible : base de données indisponible.",
        )

    # Message identique que l'email existe ou non : évite d'indiquer à un
    # attaquant quels emails sont enregistrés.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
        )

    return schemas.Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=schemas.AccessTokenResponse)
def refresh(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    """Renvoie un nouvel access token à partir d'un refresh token valide."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalide ou expiré.",
    )
    try:
        data = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(data.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise invalid

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise invalid

    return schemas.AccessTokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=schemas.UserResponse)
def me(current_user: models.User = Depends(get_current_user)):
    """Retourne les infos de l'utilisateur connecté (déduites du token)."""
    return current_user
