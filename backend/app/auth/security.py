"""
Primitives de sécurité : hachage des mots de passe (bcrypt) et JWT (python-jose).

NOTE sur le choix de bcrypt « en direct » plutôt que passlib :
    Le projet dépend de chromadb, qui épingle bcrypt==5.0.0. Or passlib 1.7.4
    (non maintenu depuis 2020) est incompatible avec bcrypt >= 4.1 / 5.0
    (attribut __about__ supprimé + limite stricte des 72 octets). On utilise donc
    directement la bibliothèque bcrypt, dont l'API est stable, ce qui satisfait
    l'exigence « hacher avec bcrypt, jamais en clair » sans conflit de version.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Union

import bcrypt
from jose import jwt, JWTError

from app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
)

logger = logging.getLogger(__name__)

# bcrypt ne prend en compte que les 72 premiers octets du mot de passe et, depuis
# la version 5, lève une erreur au-delà. On tronque donc explicitement à 72 octets
# (comportement standard et sûr) pour éviter tout plantage sur un mot de passe long.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


# ─── Mots de passe ───────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Retourne le hash bcrypt (avec sel intégré) d'un mot de passe en clair."""
    hashed = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond au hash stocké."""
    try:
        return bcrypt.checkpw(_password_bytes(password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash mal formé en base : on refuse plutôt que de planter.
        return False


# ─── JWT ─────────────────────────────────────────────────────────────

def _create_token(subject: Union[str, int], token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),          # identifiant de l'utilisateur (id)
        "type": token_type,           # "access" ou "refresh"
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(subject: Union[str, int]) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(subject: Union[str, int]) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Décode et valide un JWT (signature + expiration via python-jose).
    Vérifie aussi que le type correspond (un refresh token ne peut pas servir
    d'access token et inversement). Lève JWTError si invalide/expiré.
    """
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError(
            f"Type de token invalide : attendu '{expected_type}', reçu '{payload.get('type')}'."
        )
    return payload
