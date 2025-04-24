from fastapi import Request, status
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeSerializer
from sqlalchemy.orm import Session
from typing import Optional

from config import config
from models.database import get_db
from models.users import SSOUser
from services.logging_config import get_logger

logger = get_logger(__name__)
serializer = URLSafeSerializer(config.encryption.user_session_key.get_secret_value())


def get_current_user(request: Request) -> Optional[SSOUser]:
    """Get current user ID from auth token"""
    auth_token = request.cookies.get("auth_token")
    if not auth_token:
        return None

    try:
        user_id = str(serializer.loads(auth_token))
        db: Session = next(get_db())
        return db.query(SSOUser).filter(SSOUser.id == user_id).first()
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None


async def restrict_access_middleware(request: Request, call_next):
    """Middleware to restrict access to user resources"""
    # Skip if not API v1 users route
    if not request.url.path.startswith("/api/v1/users"):
        return await call_next(request)

    try:
        current_user = get_current_user(request)
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        db: Session = next(get_db())

        # Log the request attempt with username if available
        username = current_user.username if current_user else "anonymous"
        logger.info(
            f'{client_ip} "{method} {path} HTTP/1.1" - Access check by {username}'
        )

        # Block all modification requests (PUT/DELETE) to users
        if method in ("PUT", "DELETE"):
            action = "updates" if method == "PUT" else "deletion"
            logger.warning(
                f'User {username} ({client_ip}) attempted {action} at "{method} {path} HTTP/1.1"'
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": f"User {action} is forbidden"},
            )

        # Block manual user creation (only allow via SSO callback)
        if method == "POST" and path == "/api/v1/users/":
            logger.warning(
                f'User {username} ({client_ip}) attempted manual user creation at "{method} {path} HTTP/1.1"'
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Manual user creation is forbidden"},
            )

        # Special case for GET /api/v1/users/{username}
        if method == "GET" and "/api/v1/users/" in path:
            path_parts = path.split("/")
            if len(path_parts) == 5 and path_parts[4]:  # username is at index 4
                if not current_user:
                    logger.warning(
                        f'Anonymous user ({client_ip}) attempted access to "{path_parts[4]}"'
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Unauthorized"},
                    )

                # Allow access if username matches current user's username
                requested_user = (
                    db.query(SSOUser).filter(SSOUser.username == path_parts[4]).first()
                )
                if requested_user and requested_user.id == current_user.id:
                    return await call_next(request)

                logger.warning(
                    f'User {current_user.username} ({client_ip}) attempted access to "{path_parts[4]}"'
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Access denied"},
                )

        # For other routes that require user ID in path
        if "/api/v1/users/" in path and path != "/api/v1/users/":
            path_parts = path.split("/")
            if len(path_parts) > 4 and path_parts[4]:  # user_id is at index 4
                requested_user_id = path_parts[4]

                # If no current user or IDs don't match
                if not current_user or str(current_user.id) != requested_user_id:
                    requested_user = (
                        db.query(SSOUser)
                        .filter(SSOUser.id == requested_user_id)
                        .first()
                    )
                    requested_username = (
                        requested_user.username if requested_user else "unknown"
                    )

                    logger.warning(
                        f"User '{current_user.username if current_user else 'anonymous'}' ({client_ip}) "
                        f"attempted access to '{requested_username}' account"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Access denied"},
                    )

        return await call_next(request)

    except Exception as e:
        logger.error(f"Error in restrict_access_middleware: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
