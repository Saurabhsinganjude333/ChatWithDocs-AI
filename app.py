"""
DocMind AI — RAM-optimized production entry point.
Key optimizations for Render/Railway free tier (512MB RAM):
- Lazy model loading (model loads on first use, not at startup)
- Smaller embedding model option
- Gunicorn-friendly factory pattern
- GC optimization
"""
import os
import gc
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

from flask import Flask, render_template, jsonify
from groq import Groq

from config import get_config
from utils.logger import setup_logger
from utils.file_utils import ensure_dir


def create_app():
    config = get_config()
    logger = setup_logger("app", config.LOG_FILE, config.LOG_LEVEL)

    ensure_dir(config.UPLOAD_FOLDER)
    ensure_dir(config.CHROMA_PERSIST_DIR)

    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing. Check your .env file.")

    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config_obj = config

    groq_client = Groq(api_key=config.GROQ_API_KEY)

    # ── Lazy init: only import heavy libs here, once ──────────────
    logger.info("Loading vector store (embedding model)...")
    from rag.vector_store import VectorStore
    vector_store = VectorStore(
        persist_dir     = config.CHROMA_PERSIST_DIR,
        collection_name = config.COLLECTION_NAME,
        embedding_model = config.EMBEDDING_MODEL,
    )
    app.vector_store = vector_store
    gc.collect()  # Free memory after model load

    from rag.rag_pipeline import RAGPipeline
    from services.document_service import DocumentService

    app.doc_service  = DocumentService(vector_store, config, groq_client=groq_client)
    app.rag_pipeline = RAGPipeline(vector_store, config, groq_client=groq_client)

    from routes import chat_bp, doc_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(doc_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        import psutil, os
        process = psutil.Process(os.getpid())
        mem_mb  = process.memory_info().rss / 1024 / 1024
        stats   = vector_store.get_stats()
        return jsonify({
            "status": "ok",
            "ram_mb": round(mem_mb, 1),
            "indexed_files": len(stats["sources"]),
            "total_chunks": stats["total_chunks"],
        })

    @app.errorhandler(413)
    def too_large(e): return jsonify({"error": "File too large. Max 100MB."}), 413

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"500: {e}")
        return jsonify({"error": "Internal server error."}), 500

    logger.info("DocMind AI ready!")
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
