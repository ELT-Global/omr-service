"""
Authentication guard for FastAPI
Implements JWT/Token-based authentication similar to NestJS AuthGuard
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.database import UnitOfWork
from src.database.models import Operator
from src.logger import logger


# Create HTTPBasic security scheme - this will show the "Authorize" button in Swagger UI
security = HTTPBasic()


def get_current_operator(credentials: HTTPBasicCredentials = Depends(security)) -> Operator:
    """
    Validate authorization token and return authenticated operator
    
    This uses HTTP Basic Authentication where:
    - username: can be anything (e.g., "api", "user", etc.) - it's ignored
    - password: your operator UUID token
    
    Args:
        credentials: HTTP Basic credentials from request
        
    Returns:
        Operator: Authenticated operator with full details
        
    Raises:
        HTTPException 401: If authorization fails
        
    Usage in Swagger UI:
        1. Click the "Authorize" 🔓 button at the top right
        2. Username: anything (e.g., "api")
        3. Password: your operator UUID (e.g., "test-uuid")
        4. Click "Authorize"
    
    Usage in curl:
        curl -u "api:test-uuid" http://localhost:8000/omr:parse-sheet ...
    
    Usage in Python:
        requests.post(url, auth=("api", "test-uuid"), ...)
    """
    # The token is in the password field
    token = credentials.password
    
    # Validate token against database
    try:
        uow = UnitOfWork()
        operator = uow.operators.find_by_uuid(token)
        
        if not operator:
            logger.warning(f"Authentication failed: Invalid token {token}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        logger.info(f"Authentication successful: operator_id={operator.id}")
        return operator
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal authentication error"
        )


def get_optional_operator(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> Optional[Operator]:
    """
    Optional authentication - returns None if no credentials provided
    
    Args:
        credentials: HTTP Basic credentials from request (optional)
        
    Returns:
        Optional[Operator]: Authenticated operator or None
    """
    if not credentials:
        return None
    
    try:
        return get_current_operator(credentials)
    except HTTPException:
        return None


def get_operator_id(operator: Operator = Depends(get_current_operator)) -> str:
    """
    Helper function to extract operator ID
    
    Usage:
        @app.post("/endpoint")
        async def endpoint(operator_id: str = Depends(get_operator_id)):
            # operator_id is available directly
            pass
    """
    return operator.id
