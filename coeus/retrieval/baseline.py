import time
from typing import List, Dict, Any
from pathlib import Path
from coeus.artifacts import ChunkArtifact, CandidateArtifact
from coeus.retrieval.stages import CandidateGenerator, ContextAssembler, StageFactory, StageContext, StageResult, CandidateGenerationResult, AssemblyResult
from coeus.experiment import StageConfig

class LexicalCandidateGenerator(CandidateGenerator):

    def __init__(self, limit: int=10):
        self.limit = limit

    def _extract_terms(self, text: str) -> set:
        import re
        words = re.findall('\\b\\w+\\b', text.lower())
        return set(words)

    def generate(self, query: str, chunks: List[ChunkArtifact], context: StageContext) -> List[CandidateArtifact]:
        query_terms = self._extract_terms(query)
        if not query_terms:
            return []
        candidates = []
        for chunk in chunks:
            chunk_terms = self._extract_terms(chunk.content)
            overlap = query_terms & chunk_terms
            if not overlap:
                continue
            score = len(overlap) / len(query_terms)
            candidate = CandidateArtifact(chunk_id=chunk.id, score=score, method='lexical', stage='candidate_gen', metadata={'overlap_count': len(overlap), 'matched_terms': sorted(overlap)})
            candidates.append(candidate)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:self.limit]

    def stage_type(self) -> str:
        return 'lexical'

class SimpleContextAssembler(ContextAssembler):

    def __init__(self, max_chunks: int=5, score_threshold: float=0.0):
        self.max_chunks = max_chunks
        self.score_threshold = score_threshold

    def assemble(self, candidates: List[CandidateArtifact], chunks: Dict[str, ChunkArtifact], query: str, context: StageContext) -> AssemblyResult:
        filtered = [c for c in candidates if c.score >= self.score_threshold]
        selected = filtered[:self.max_chunks]
        chunk_ids = [c.chunk_id for c in selected]
        total_chars = sum((len(chunks[cid].content) for cid in chunk_ids if cid in chunks))
        total_tokens = total_chars // 4
        return AssemblyResult(query=query, chunk_ids=chunk_ids, total_chunks=len(chunk_ids), total_tokens_estimate=total_tokens, assembly_method='top_k_threshold')

    def stage_type(self) -> str:
        return 'simple'

def estimate_tokens(text: str) -> int:
    return len(text) // 4
StageFactory.register('lexical', LexicalCandidateGenerator)
StageFactory.register('simple', SimpleContextAssembler)

class BaselineRetriever:

    def __init__(self, generator_config: StageConfig, assembler_config: StageConfig):
        self.generator = StageFactory.create(generator_config)
        self.assembler = StageFactory.create(assembler_config)

    def retrieve(self, query: str, chunks: List[ChunkArtifact], context: StageContext) -> Dict[str, Any]:
        start = time.perf_counter()
        results = {}
        gen_start = time.perf_counter()
        candidates = self.generator.generate(query, chunks, context)
        gen_duration = time.perf_counter() - gen_start
        candidates_serialized = [{'chunk_id': c.chunk_id, 'score': c.score, 'method': c.method, 'stage': c.stage, 'metadata': c.metadata} for c in candidates]
        results['candidates'] = candidates_serialized
        results['candidate_generation_time'] = gen_duration
        results['candidate_count'] = len(candidates)
        chunk_lookup = {c.id: c for c in chunks}
        asm_start = time.perf_counter()
        assembly = self.assembler.assemble(candidates, chunk_lookup, query, context)
        asm_duration = time.perf_counter() - asm_start
        results['assembly'] = {'query': assembly.query, 'chunk_ids': assembly.chunk_ids, 'total_chunks': assembly.total_chunks, 'total_tokens_estimate': assembly.total_tokens_estimate, 'assembly_method': assembly.assembly_method}
        results['assembly_time'] = asm_duration
        results['total_time'] = time.perf_counter() - start
        return results
