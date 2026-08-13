"""
RAM-optimized VectorStore — smaller batches, gc.collect after heavy ops.
"""
import gc
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VectorStore:
    def __init__(self, persist_dir, collection_name, embedding_model):
        logger.info(f"Loading embedding model: {embedding_model}")
        self._embedder = SentenceTransformer(embedding_model)
        self._embedder.encode(["warmup"], batch_size=1, show_progress_bar=False)
        gc.collect()
        logger.info("Model ready.")

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"ChromaDB ready — {self._collection.count()} chunks.")

    def _encode(self, texts, batch_size=64):
        result = self._embedder.encode(
            texts, batch_size=batch_size, show_progress_bar=False,
            normalize_embeddings=True, convert_to_numpy=True,
        ).tolist()
        gc.collect()
        return result

    def add_chunks(self, chunks, file_hash, source_filename):
        if not chunks: return
        texts     = [c["content"] for c in chunks]
        metadatas = [{**{k:str(v) for k,v in c.get("metadata",{}).items()},
                      "source":source_filename,"file_hash":file_hash} for c in chunks]
        ids       = [f"{file_hash}_{i}" for i in range(len(chunks))]
        embeddings= self._encode(texts)
        for i in range(0, len(ids), 200):
            self._collection.add(
                ids=ids[i:i+200], embeddings=embeddings[i:i+200],
                documents=texts[i:i+200], metadatas=metadatas[i:i+200],
            )
        gc.collect()
        logger.info(f"Stored {len(chunks)} chunks for '{source_filename}'")

    def query(self, question, top_k=8):
        count = self._collection.count()
        if count == 0: return []
        emb  = self._encode([question], batch_size=1)[0]
        res  = self._collection.query(
            query_embeddings=[emb], n_results=min(top_k, count),
            include=["documents","metadatas","distances"],
        )
        return [{"content":d,"metadata":m,"score":max(0.0,1.0-dist)}
                for d,m,dist in zip(res["documents"][0],res["metadatas"][0],res["distances"][0])]

    def query_by_source(self, source_filename, top_k=4):
        if self._collection.count()==0: return []
        try:
            r = self._collection.get(where={"source":source_filename},limit=top_k,include=["documents","metadatas"])
            return [{"content":d,"metadata":m,"score":0.05} for d,m in zip(r["documents"],r["metadatas"])]
        except Exception as e:
            logger.warning(f"query_by_source failed: {e}"); return []

    def is_indexed(self, file_hash):
        r = self._collection.get(where={"file_hash":file_hash},limit=1,include=[])
        return len(r["ids"])>0

    def delete_by_source(self, source_filename):
        self._collection.delete(where={"source":source_filename}); gc.collect()

    def list_sources(self):
        if self._collection.count()==0: return []
        r = self._collection.get(include=["metadatas"])
        return sorted({m.get("source","") for m in r["metadatas"] if m.get("source")})

    def get_stats(self):
        return {"total_chunks":self._collection.count(),"sources":self.list_sources()}
