import re
import os
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from storage.interface import StorageInterface, SearchResult
from embedders import Embedder
from core.fastpath import FastPath


class QueryType(Enum):
    LOOKUP = "lookup"
    SEMANTIC = "semantic"
    AGGREGATION = "aggregation"


@dataclass
class Pointer:
    file_path: str
    line_start: int
    line_end: int
    section: str
    keywords: List[str]
    confidence: float


@dataclass
class QueryResult:
    query: str
    query_type: QueryType
    chunks: List[SearchResult] = field(default_factory=list)
    pointers: List[Pointer] = field(default_factory=list)
    entities: List = field(default_factory=list)
    method: str = "hybrid"
    savings: Dict[str, Any] = field(default_factory=dict)


class Oracle:
    def __init__(
        self,
        storage: StorageInterface,
        embedder: Embedder,
        fastpath: Optional[FastPath] = None
    ):
        self.storage = storage
        self.embedder = embedder
        self.fastpath = fastpath or FastPath()
        self._lock = threading.Lock()
        self._warmup_fastpath()

        self.pricing = {
            "claude-3.5-sonnet": 3.0,
            "claude-3-opus": 15.0,
            "gemini-3-flash": 0.10,
            "default": 3.0
        }

    def _warmup_fastpath(self):
        from storage.interface import Document
        try:
            entities = self.storage.get_entities()
            for entity in entities:
                doc = Document(
                    id=str(entity.id),
                    content=entity.content,
                    source=entity.file_path,
                    project=entity.project
                )
                self.fastpath.index(entity.content, doc)
        except Exception:
            pass

    def ask(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 10,
        hyde: bool = True
    ) -> QueryResult:
        with self._lock:
            query_type = self._detect_query_type(query)
            is_temporal = self._is_temporal_query(query)

            fast_result = self.fastpath.search(query)
            if fast_result and fast_result.get('confidence', 0) > 0.9:
                doc = fast_result.get('document')
                if doc:
                    return QueryResult(
                        query=query,
                        query_type=query_type,
                        chunks=[SearchResult(doc, 1.0, 'fastpath')],
                        pointers=[],
                        entities=[],
                        method="fastpath"
                    )

            vector_query = self._expand_query(query) if hyde else query
            query_embedding = self.embedder.embed_query(vector_query)

            results = self.storage.search_hybrid(
                query_embedding=query_embedding,
                query_text=query,
                limit=limit * 4,
                project=project
            )

            candidates = []
            for r in results:
                candidates.append({
                    'score': r.score,
                    'document': r.document,
                    'method': r.method
                })

            fts_results = self.storage.search_fts(query, limit * 2, project)
            for r in fts_results:
                candidates.append({
                    'score': r.score,
                    'document': r.document,
                    'method': 'fts'
                })

            unique_candidates = self._deduplicate(candidates)
            sorted_candidates = self._rank_candidates(unique_candidates, is_temporal)

            chunks = []
            pointers = []

            top_score = sorted_candidates[0]['boosted_score'] if sorted_candidates else 1.0
            chunk_threshold = top_score * 0.3
            pointer_threshold = top_score * 0.05

            for i, cand in enumerate(sorted_candidates):
                score = cand['boosted_score']
                doc = cand['document']

                if score >= chunk_threshold or (is_temporal and i < 5):
                    chunks.append(SearchResult(doc, score, cand['method']))
                elif score >= pointer_threshold:
                    pointers.append(Pointer(
                        file_path=doc.source,
                        line_start=doc.start_line,
                        line_end=doc.end_line,
                        section=self._extract_section(doc.content),
                        keywords=self._extract_keywords(query),
                        confidence=score
                    ))

            entities = self.storage.get_entities(project=project)[:5]

            potential_tokens = sum(len(c['document'].content) for c in sorted_candidates) // 4
            actual_tokens = sum(len(c.document.content) for c in chunks) // 4

            model = os.getenv("COEUS_LLM_MODEL", "claude-3.5-sonnet")
            price_per_million = self.pricing.get(model, self.pricing["default"])
            usd_saved = ((potential_tokens - actual_tokens) / 1_000_000) * price_per_million

            if hasattr(self.storage, 'record_savings'):
                self.storage.record_savings(query, model, potential_tokens, actual_tokens, usd_saved)

            return QueryResult(
                query=query,
                query_type=query_type,
                chunks=chunks[:limit],
                pointers=pointers[:limit],
                entities=entities,
                method="hybrid-zvec",
                savings={
                    "potential_tokens": potential_tokens,
                    "actual_tokens": actual_tokens,
                    "usd_saved": round(usd_saved, 6)
                }
            )

    def _detect_query_type(self, query: str) -> QueryType:
        q = query.lower()

        aggregation_markers = [
            "list", "all", "every", "count", "how many", "sum", "total",
            "summary", "show me", "get all"
        ]
        if any(w in q for w in aggregation_markers):
            return QueryType.AGGREGATION

        semantic_markers = [
            "how", "why", "explain", "what is", "how does", "overview",
            "architecture", "design", "concept", "principle"
        ]
        if any(w in q for w in semantic_markers):
            return QueryType.SEMANTIC

        return QueryType.LOOKUP

    def _is_temporal_query(self, query: str) -> bool:
        temporal_keywords = [
            "latest", "recent", "new", "update", "changed", "today",
            "yesterday", "last", "v0.", "v1.", "v2.", "current", "status"
        ]
        return any(k in query.lower() for k in temporal_keywords)

    def _expand_query(self, query: str) -> str:
        return query

    def _deduplicate(self, candidates: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for cand in candidates:
            doc_id = f"{cand['document'].source}:{cand['document'].start_line}"
            if doc_id not in seen:
                seen.add(doc_id)
                unique.append(cand)
        return unique

    def _rank_candidates(self, candidates: List[Dict], is_temporal: bool) -> List[Dict]:
        for cand in candidates:
            base_score = cand['score']
            if is_temporal:
                cand['boosted_score'] = base_score * 1.2
            else:
                cand['boosted_score'] = base_score

        return sorted(candidates, key=lambda x: x['boosted_score'], reverse=True)

    def _extract_section(self, content: str) -> str:
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                return line.lstrip('#').strip()[:60]
            if line and len(line) < 100:
                return line[:60]
        return "Untitled"

    def _extract_keywords(self, query: str) -> List[str]:
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'how', 'what', 'where', 'when',
            'why', 'to', 'for', 'with', 'from', 'and', 'or', 'but'
        }
        words = re.findall(r'\w+', query.lower())
        return [w for w in words if w not in stopwords and len(w) > 2][:5]

