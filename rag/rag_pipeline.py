"""RAG Pipeline — multi-doc, query expansion, guaranteed coverage."""
import re
from typing import List, Dict, Any, Generator
from groq import Groq
from utils.logger import setup_logger

logger = setup_logger(__name__)

SYS = """You are DocMind AI — an expert document analyst.

RULES:
1. Answer ONLY from the document context below.
2. For multi-part questions, answer EACH part with a ## heading.
3. Cite sources: "According to [filename]..."
4. Never say "not found" for info that IS in the context.
5. Only say "I could not find information about X" if that topic is truly absent.
6. Use rich markdown: ## headings, bullets, **bold**, tables, code blocks.
7. Be thorough — cover every part of the question.

KNOWLEDGE BASE:
{context}"""


class RAGPipeline:
    def __init__(self, vector_store, config, groq_client=None):
        self.vs           = vector_store
        self.config       = config
        self.groq_client  = groq_client or Groq(api_key=config.GROQ_API_KEY)

    def expand(self, q):
        queries = [q]
        parts   = re.split(r'\?\s*(?:and|also|aur|or)\s*|\?\s+(?=[A-ZIWH])', q, flags=re.IGNORECASE)
        parts   = [p.strip().rstrip('?').strip() for p in parts if len(p.strip())>4]
        if len(parts)>1: queries.extend(parts)
        stop = r'\b(what|is|are|how|to|do|the|a|an|tell|me|about|explain|give|list|please|i|want|know|for|in|on|at|kya|hai|batao)\b'
        kw   = ' '.join(re.sub(stop,' ',q,flags=re.IGNORECASE).split()).strip()
        if kw and len(kw)>3 and kw.lower()!=q.lower(): queries.append(kw)
        seen,uniq=[],[]
        for x in queries:
            k=x.lower().strip()
            if k not in seen and len(k)>3: seen.append(k); uniq.append(x)
        logger.info(f"Queries: {uniq}")
        return uniq

    def retrieve(self, q):
        sources = self.vs.list_sources()
        if not sources: return []
        per_q   = max(10, len(sources)*5)
        queries = self.expand(q)
        seen,all_c = set(),[]
        for query in queries:
            for c in self.vs.query(query, top_k=per_q):
                cid = c["content"][:120]
                if cid not in seen:
                    seen.add(cid); c["mq"]=query; all_c.append(c)
        all_c.sort(key=lambda x:x["score"],reverse=True)
        MIN_PER  = 3
        MAX_TOT  = max(24, len(sources)*6)
        by_src   = {}
        for c in all_c:
            s=c["metadata"].get("source","")
            by_src.setdefault(s,[]).append(c)
        result,in_r=[],set()
        for src in sources:
            avail = by_src.get(src,[])
            if len(avail)<MIN_PER:
                for c in self.vs.query_by_source(src, top_k=MIN_PER):
                    if c["content"][:120] not in seen:
                        seen.add(c["content"][:120]); avail.append(c)
            for c in avail[:MIN_PER]:
                cid=c["content"][:120]
                if cid not in in_r: in_r.add(cid); result.append(c)
        budget=MAX_TOT-len(result)
        for c in all_c:
            if budget<=0: break
            cid=c["content"][:120]
            if cid not in in_r: in_r.add(cid); result.append(c); budget-=1
        result.sort(key=lambda x:x["score"],reverse=True)
        covered={c["metadata"].get("source") for c in result}
        logger.info(f"Context: {len(result)} chunks from {len(covered)}/{len(sources)} docs → {covered}")
        return result[:MAX_TOT]

    def build_context(self, chunks):
        if not chunks: return "No documents available."
        by_src={}
        for c in chunks:
            s=c["metadata"].get("source","Unknown")
            by_src.setdefault(s,[]).append(c)
        sections=[]
        for src,cs in by_src.items():
            parts=[]
            for i,c in enumerate(cs,1):
                pg=c["metadata"].get("page",""); sl=c["metadata"].get("slide",""); sh=c["metadata"].get("sheet","")
                loc=f" | Page {pg}" if pg else f" | Slide {sl}" if sl else f" | Sheet {sh}" if sh else ""
                sc=int(c["score"]*100)
                parts.append(f"[Excerpt {i}{loc} | relevance {sc}%]\n{c['content'].strip()}")
            sections.append(f"{'━'*50}\nDOCUMENT: {src}\n{'━'*50}\n\n"+"\n\n".join(parts))
        return "\n\n".join(sections)

    def generate_stream(self, q, history=None) -> Generator:
        if history is None: history=[]
        chunks  = self.retrieve(q)
        context = self.build_context(chunks)
        sources = list({c["metadata"].get("source","") for c in chunks if c["metadata"].get("source")})
        msgs    = [{"role":"system","content":SYS.format(context=context)}]
        for t in history[-8:]: msgs.append({"role":t["role"],"content":t["content"]})
        msgs.append({"role":"user","content":q})
        if sources: yield f"__SOURCES__:{','.join(sources)}__END_SOURCES__"
        try:
            stream = self.groq_client.chat.completions.create(
                model=self.config.GROQ_MODEL, messages=msgs,
                max_tokens=self.config.GROQ_MAX_TOKENS,
                temperature=self.config.GROQ_TEMPERATURE, stream=True,
            )
            for chunk in stream:
                delta=chunk.choices[0].delta.content
                if delta: yield delta
        except Exception as e:
            logger.error(f"Groq error: {e}"); yield f"\n\n❌ **Error:** {str(e)}"
