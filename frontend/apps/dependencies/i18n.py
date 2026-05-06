from fastapi import Header

def get_user_language(accept_language: str | None = Header(default="en")) -> str:
    """
    Extracts the preferred language from the frontend headers.
    Example: If header is 'es-ES,es;q=0.9', it returns 'es'.
    """
    if accept_language and "," in accept_language:
        return accept_language.split(",")[0].split("-")[0]
    return accept_language or "en"