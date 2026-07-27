from fastapi import Header, HTTPException, status

from common.config import INTERNAL_API_KEY


def require_internal_key(x_internal_api_key: str | None = Header(default=None)) -> None:
    """Protege a comunicação privada entre os microsserviços."""
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave interna inválida",
        )

