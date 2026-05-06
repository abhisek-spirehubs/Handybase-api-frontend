from fastapi import WebSocket
from jose import jwt, JWTError
from app.core.config import settings
from app.models.user import User
import logging

logger = logging.getLogger(__name__)

async def get_current_user_ws(websocket: WebSocket):
    """
    Extract and validate JWT token from WebSocket query parameters
    """
    # Get token from query params
    token = websocket.query_params.get("token")
    
    logger.info(f"Auth - Token from query params: {'Present' if token else 'Missing'}")
    
    if not token:
        logger.error("Auth - No token provided")
        await websocket.close(code=1008, reason="No token provided")
        return None
    
    try:
        # Decode JWT token
        logger.info(f"Auth - Decoding token with algorithm: {settings.JWT_ALGORITHM}")
        
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        logger.info(f"Auth - Token payload: {payload}")
        
        user_id = payload.get("sub")
        if not user_id:
            logger.error("Auth - No 'sub' claim in token")
            await websocket.close(code=1008, reason="Invalid token payload")
            return None
        
        logger.info(f"Auth - Looking up user with ID: {user_id}")
        
        # Get user from database
        user = await User.get(user_id)
        if not user:
            logger.error(f"Auth - User not found with ID: {user_id}")
            await websocket.close(code=1008, reason="User not found")
            return None
        
        logger.info(f"Auth - User found: {user.id}")
        
        # Handle both role (from token) and user_type (from model)
        token_role = payload.get("role") or payload.get("user_type")
        if token_role:
            logger.info(f"Auth - Token role/user_type: {token_role}")
        
        logger.info(f"Auth - Database user_type: {user.user_type}")
        
        # Optional: Verify that the role in token matches user_type in database
        # Uncomment if you want this validation
        # if token_role and token_role != user.user_type:
        #     logger.error(f"Auth - Role mismatch: token={token_role}, db={user.user_type}")
        #     await websocket.close(code=1008, reason="Role mismatch")
        #     return None
        
        return user
        
    except jwt.ExpiredSignatureError:
        logger.error("Auth - Token has expired")
        await websocket.close(code=1008, reason="Token expired")
        return None
    except JWTError as e:
        logger.error(f"Auth - JWT error: {str(e)}")
        await websocket.close(code=1008, reason="Invalid token")
        return None
    except Exception as e:
        logger.error(f"Auth - Unexpected error: {str(e)}")
        await websocket.close(code=1011, reason="Authentication error")
        return None