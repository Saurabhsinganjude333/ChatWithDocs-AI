"""
DocMind AI — Config with latest Groq models (August 2026).
RAM-optimized for Render free tier (512MB).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)


class Config:
    SECRET_KEY         = os.getenv("FLASK_SECRET_KEY", "change-this-in-production")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 52428800))  # 50MB

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    # ── UPDATED MODELS (old ones deprecated Aug 2026) ──────────────
    # Text model: llama-3.3-70b-versatile → qwen/qwen3.6-27b
    GROQ_MODEL        = os.getenv("GROQ_MODEL",        "qwen/qwen3.6-27b")
    # Vision model: meta-llama/llama-4-scout → qwen/qwen3.6-27b (same model, supports vision!)
    GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")

    GROQ_MAX_TOKENS  = 2500
    GROQ_TEMPERATURE = 0.1

    UPLOAD_FOLDER     = os.getenv("UPLOAD_FOLDER",      str(BASE_DIR / "uploads"))
    CHROMA_PERSIST_DIR= os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_db"))

    ALLOWED_EXTENSIONS = {
        "pdf","txt","docx","doc","csv","xlsx","xls",
        "ppt","pptx","json","xml","html","htm",
        "md","markdown","log","png","jpg","jpeg","bmp","tiff","webp",
    }

    # RAM-OPTIMIZED: all-MiniLM-L6-v2 = ~90MB RAM (free tier safe)
    # multilingual = ~280MB (too heavy for 512MB free tier)
    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "600"))  # Smaller = less RAM
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
    TOP_K_RESULTS = int(os.getenv("TOP_K",         "6"))    # Fewer chunks = less RAM
    COLLECTION_NAME = "rag_documents"

    VISION_ENABLED      = os.getenv("VISION_ENABLED", "true").lower() == "true"
    PII_MASKING_ENABLED = os.getenv("PII_MASKING",    "true").lower() == "true"

    SESSION_TYPE               = "filesystem"
    PERMANENT_SESSION_LIFETIME = 3600

    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")
    LOG_FILE  = str(BASE_DIR / "app.log")


class DevelopmentConfig(Config):
    DEBUG     = True
    LOG_LEVEL = "INFO"


class ProductionConfig(Config):
    DEBUG     = False
    LOG_LEVEL = "WARNING"


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return ProductionConfig() if env == "production" else DevelopmentConfig()
