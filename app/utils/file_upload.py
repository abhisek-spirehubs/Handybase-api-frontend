import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile

# BULLETPROOF PATH: Resolves to the absolute path of your project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent # Adjust .parent based on folder depth
MEDIA_ROOT = os.path.abspath(os.path.join(os.getcwd(), "media"))


async def save_file(file: UploadFile, folder: str) -> str:
    """
    Generic file saver.
    Saves file to /media/{folder}/ and returns URL.
    """
    if not file:
        return None

    # Use the absolute MEDIA_ROOT
    folder_path = os.path.join(MEDIA_ROOT, folder)
    os.makedirs(folder_path, exist_ok=True)

    filename_parts = file.filename.split(".")
    ext = filename_parts[-1] if len(filename_parts) > 1 else "bin"
    
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(folder_path, filename)

    # 1. Reset file pointer to ensure we don't save an empty file
    await file.seek(0) 
    
    # 2. Read and write the file
    content = await file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    return f"/media/{folder}/{filename}"


async def save_category_icon(file: UploadFile) -> str:
    return await save_file(file, "categories")


async def save_provider_profile_image(file: UploadFile) -> str:
    return await save_file(file, "providers/profile")


async def save_provider_portfolio_image(file: UploadFile) -> str:
    return await save_file(file, "providers/portfolio")


def delete_file(file_url: str):
    if not file_url:
        return
    file_path = file_url.lstrip("/")
    if os.path.exists(file_path):
        os.remove(file_path)

async def save_service_image(file: UploadFile) -> str:
    return await save_file(file, "services")