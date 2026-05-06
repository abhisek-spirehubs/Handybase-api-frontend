import firebase_admin
from firebase_admin import credentials
from app.utils.logger import app_logger

_initialized = False


def init_firebase(credentials_path: str) -> None:
    """
    Initialize Firebase Admin SDK once on startup.
    Called from main.py lifespan.
    """
    global _initialized
    if _initialized:
        return
    try:
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred)
        _initialized = True
        app_logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        app_logger.error("Firebase initialization failed: %s", e)