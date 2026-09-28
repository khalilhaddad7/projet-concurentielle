"""
Dependencies FastAPI pour protéger les routes.

- get_current_user : décode le JWT (header Authorization: Bearer ...), charge
  l'utilisateur en base, et lève 401 si le token est absent/invalide/expiré.
- require_admin : exige que l'utilisateur courant ait le rôle admin, sinon 403.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

import app.models as models
from app.database import get_db
from app.auth.security import decode_token

# tokenUrl sert surtout à la doc Swagger ("Authorize"). auto_error=False nous
# laisse renvoyer un message d'erreur clair en français plutôt que celui par défaut.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Non authentifié : token manquant, invalide ou expiré.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = decode_token(token, expected_type="access")
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != models.UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )
    return current_user
