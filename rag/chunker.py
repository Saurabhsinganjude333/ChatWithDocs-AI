import re
from typing import List, Dict, Any

_PARA  = re.compile(r'\n{2,}')
_SENT  = re.compile(r'(?<=[.!?])\s+')
_WS    = re.compile(r'[ \t]+')

class TextChunker:
    def __init__(self, chunk_size=800, chunk_overlap=150):
        self.chunk_size    = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunks = []
        for doc in documents:
            content = doc.get("content","").strip()
            if not content: continue
            meta   = doc.get("metadata",{})
            pieces = self._split(content)
            for i, text in enumerate(pieces):
                chunks.append({"content":text,"metadata":{**meta,"chunk_index":i,"total_chunks":len(pieces)}})
        return chunks

    def _split(self, text):
        if len(text) <= self.chunk_size: return [text]
        paras = [p.strip() for p in _PARA.split(text) if p.strip()]
        units = []
        for p in paras:
            if len(p) <= self.chunk_size: units.append(p)
            else: units.extend(s.strip() for s in _SENT.split(p) if s.strip())
        return self._merge(units)

    def _merge(self, units):
        chunks, current, cur_len = [], [], 0
        for unit in units:
            ul = len(unit)
            if cur_len + ul + 1 > self.chunk_size and current:
                chunks.append(" ".join(current))
                keep, kl = [], 0
                for p in reversed(current):
                    kl += len(p)+1
                    keep.insert(0,p)
                    if kl >= self.chunk_overlap: break
                current, cur_len = keep, sum(len(p) for p in keep)+len(keep)
            if ul > self.chunk_size:
                if current: chunks.append(" ".join(current)); current,cur_len=[],0
                for i in range(0,ul,self.chunk_size-self.chunk_overlap):
                    piece=unit[i:i+self.chunk_size].strip()
                    if piece: chunks.append(piece)
                continue
            current.append(unit); cur_len += ul+1
        if current: chunks.append(" ".join(current))
        return [c for c in chunks if c.strip()]
