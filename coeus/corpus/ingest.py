from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib
from datetime import datetime
from coeus.artifacts import DocumentArtifact, ChunkArtifact

class CorpusError(Exception):
    pass

@dataclass
class IngestResult:
    documents: List[DocumentArtifact]
    chunks: List[ChunkArtifact]
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

def _generate_doc_id(source: str, content: str) -> str:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    source_hash = hashlib.sha256(source.encode()).hexdigest()[:8]
    return f'doc_{source_hash}_{content_hash}'

def _generate_chunk_id(doc_id: str, index: int, content: str) -> str:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f'{doc_id}_chunk_{index}_{content_hash}'

def _count_lines(content: str) -> int:
    if not content:
        return 0
    return content.count('\n') + (0 if content.endswith('\n') else 1)

def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='latin-1')

def _detect_language(path: Path) -> Optional[str]:
    ext_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript', '.jsx': 'javascript', '.go': 'go', '.rs': 'rust', '.java': 'java', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp', '.md': 'markdown', '.txt': 'text', '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml'}
    return ext_map.get(path.suffix.lower())

def _simple_line_chunk(content: str, chunk_size: int=1000) -> List[str]:
    lines = content.splitlines(keepends=True)
    chunks = []
    current_chunk = []
    current_size = 0
    for line in lines:
        line_size = len(line)
        if current_size + line_size > chunk_size and current_chunk:
            chunks.append(''.join(current_chunk))
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size
    if current_chunk:
        chunks.append(''.join(current_chunk))
    return chunks

def ingest_file(path: Path, chunk_size: int=1000, metadata: Optional[Dict[str, Any]]=None, source_id: Optional[str]=None) -> IngestResult:
    if not path.exists():
        raise CorpusError(f'Path does not exist: {path}')
    if path.is_dir():
        raise CorpusError(f'Path is a directory, use ingest_directory(): {path}')
    errors = []
    try:
        content = _read_file(path)
        doc_id = _generate_doc_id(source_id or path.name, content)
        doc_metadata = {'language': _detect_language(path), 'file_size': path.stat().st_size, 'modified_time': datetime.fromtimestamp(path.stat().st_mtime).isoformat()}
        if metadata:
            doc_metadata.update(metadata)
        document = DocumentArtifact(id=doc_id, source=str(path), content=content, metadata=doc_metadata)
        chunk_texts = _simple_line_chunk(content, chunk_size)
        chunks = []
        next_start_line = 1
        for (i, chunk_text) in enumerate(chunk_texts):
            chunk_id = _generate_chunk_id(doc_id, i, chunk_text)
            line_count = _count_lines(chunk_text)
            start_line = next_start_line if line_count else None
            end_line = start_line + line_count - 1 if start_line is not None else None
            if end_line is not None:
                next_start_line = end_line + 1
            chunk = ChunkArtifact(id=chunk_id, document_id=doc_id, content=chunk_text, start_line=start_line, end_line=end_line, metadata={'chunk_index': i})
            chunks.append(chunk)
        return IngestResult(documents=[document], chunks=chunks, errors=errors)
    except Exception as e:
        errors.append({'file': str(path), 'error': str(e)})
        return IngestResult(documents=[], chunks=[], errors=errors)

def ingest_directory(path: Path, extensions: Optional[List[str]]=None, recursive: bool=True, chunk_size: int=1000) -> IngestResult:
    if not path.exists():
        raise CorpusError(f'Path does not exist: {path}')
    if not path.is_dir():
        raise CorpusError(f'Path is not a directory: {path}')
    all_documents = []
    all_chunks = []
    all_errors = []
    root_path = path.resolve()
    pattern = '**/*' if recursive else '*'
    files = list(path.glob(pattern))
    if extensions:
        ext_set = set((e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions))
        files = [f for f in files if f.suffix.lower() in ext_set]
    ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.claude'}
    files = [f for f in files if f.is_file() and (not any((part.startswith('.') for part in f.parts))) and (not any((part in ignore_dirs for part in f.parts)))]
    for file_path in files:
        source_id = file_path.resolve().relative_to(root_path).as_posix()
        result = ingest_file(file_path, chunk_size, source_id=source_id)
        all_documents.extend(result.documents)
        all_chunks.extend(result.chunks)
        all_errors.extend(result.errors)
    return IngestResult(documents=all_documents, chunks=all_chunks, errors=all_errors)
