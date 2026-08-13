import os, threading, gc
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List
from rag.document_loader import DocumentLoader
from rag.chunker import TextChunker
from utils.file_utils import get_file_hash
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DocumentService:
    def __init__(self, vector_store, config, groq_client=None):
        self.vs      = vector_store
        self.config  = config
        self.loader  = DocumentLoader(config=config, groq_client=groq_client)
        self.chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
        self._status: Dict[str,Dict[str,Any]] = {}
        self._lock   = threading.Lock()
        self._pool   = ThreadPoolExecutor(max_workers=2, thread_name_prefix="idx")

    def index_file_async(self, filepath, filename):
        self._set(filename,"pending"); self._pool.submit(self._run,filepath,filename)

    def index_files_async(self, pairs: List):
        for _,n in pairs: self._set(n,"pending")
        for fp,fn in pairs: self._pool.submit(self._run,fp,fn)

    def _run(self, fp, fn):
        self._set(fn,"processing")
        try:
            fh=get_file_hash(fp)
            if self.vs.is_indexed(fh): logger.info(f"[SKIP] {fn}"); self._set(fn,"done",chunks=-1); return
            logger.info(f"[LOAD] {fn}")
            docs=self.loader.load(fp)
            if not docs: raise ValueError("No content extracted.")
            chunks=self.chunker.chunk_documents(docs)
            if not chunks: raise ValueError("No chunks produced.")
            logger.info(f"[EMBED] {fn} — {len(chunks)} chunks")
            self.vs.add_chunks(chunks,fh,fn)
            gc.collect()
            self._set(fn,"done",chunks=len(chunks))
            logger.info(f"[DONE] {fn} ({len(chunks)} chunks)")
        except Exception as e:
            logger.error(f"[ERROR] {fn}: {e}"); self._set(fn,"error",error=str(e))

    def _set(self,fn,status,chunks=0,error=None):
        with self._lock: self._status[fn]={"status":status,"error":error,"chunks":chunks}

    def get_status(self,fn):
        with self._lock: return self._status.get(fn,{"status":"unknown","error":None,"chunks":0})

    def get_all_status(self):
        with self._lock: return dict(self._status)

    def delete_file(self,fn,fp=None):
        self.vs.delete_by_source(fn)
        if fp and os.path.exists(fp): os.remove(fp)
        with self._lock: self._status.pop(fn,None)

    def reindex_file(self,fp,fn):
        self.vs.delete_by_source(fn); self.index_file_async(fp,fn)

    def list_indexed_files(self): return self.vs.list_sources()
