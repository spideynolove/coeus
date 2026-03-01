from pathlib import Path
from typing import List, Iterator, Dict, Any, Optional
import hashlib

from storage.interface import StorageInterface, Document
from embedders import Embedder
from core.extractor import Extractor


class Chunk:
    def __init__(self, content: str, start_line: int, end_line: int,
                 section: Optional[str] = None):
        self.content = content
        self.start_line = start_line
        self.end_line = end_line
        self.section = section


class Ingestor:
    def __init__(
        self,
        storage: StorageInterface,
        embedder: Embedder,
        chunk_size: int = 1000,
        chunk_overlap: int = 100
    ):
        self.storage = storage
        self.embedder = embedder
        self.extractor = Extractor()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def ingest_file(self, file_path: Path, project: str = "default") -> Dict[str, Any]:
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Path does not exist: {file_path}")

        mtime = file_path.stat().st_mtime
        if self.storage.is_file_indexed(str(file_path), mtime):
            return {'chunks': 0, 'entities': 0, 'status': 'unchanged'}

        content = self._read_file(file_path)
        chunks = self._choose_chunker(file_path.suffix, content)
        extracted = self.extractor.extract(content)

        self.storage.delete_documents_by_source(str(file_path))

        documents = []
        for i, chunk in enumerate(chunks):
            doc_id = f"{file_path.stem}_{i}_{hashlib.md5(chunk.content.encode()).hexdigest()[:8]}"

            documents.append(Document(
                id=doc_id,
                content=chunk.content,
                source=str(file_path),
                project=project,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                metadata={"section": chunk.section} if chunk.section else None,
            ))

        if documents:
            texts = [doc.content for doc in documents]
            embeddings = self.embedder.embed(texts)

            for doc, emb in zip(documents, embeddings):
                doc.embedding = emb

            self.storage.insert_documents(documents)

        if extracted.has_data():
            entities = extracted.to_entities(str(file_path), project)
            self.storage.insert_entities(entities)

        self.storage.mark_file_indexed(str(file_path), project, mtime)

        return {
            'chunks': len(documents),
            'entities': extracted.count(),
            'status': 'indexed'
        }

    def ingest_directory(
        self,
        dir_path: Path,
        project: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> Iterator[Dict[str, Any]]:
        dir_path = Path(dir_path)
        project = project or dir_path.name
        extensions = extensions or ['.py', '.md', '.js', '.ts', '.tsx', '.json', '.txt']

        extensions = [e if e.startswith('.') else f'.{e}' for e in extensions]

        pattern = '**/*' if recursive else '*'

        def should_include(f: Path) -> bool:
            if not f.is_file():
                return False
            if f.suffix not in extensions:
                return False
            parts = f.parts
            if any(p.startswith('.') for p in parts):
                return False
            ignore_dirs = {'node_modules', '__pycache__', 'venv', '.git', 'dist', 'build'}
            if any(p in ignore_dirs for p in parts):
                return False
            return True

        files = [f for f in dir_path.glob(pattern) if should_include(f)]

        for file_path in files:
            try:
                stats = self.ingest_file(file_path, project)
                stats['file'] = str(file_path)
                yield stats
            except Exception as e:
                yield {'file': str(file_path), 'error': str(e)}

    def _choose_chunker(self, suffix: str, text: str) -> List[Chunk]:
        try:
            from core.ast_chunker import chunk_by_ast
            ast_chunks = chunk_by_ast(text, suffix, self.chunk_size)
            if ast_chunks:
                return [
                    Chunk(c.content, c.start_line, c.end_line, c.section)
                    for c in ast_chunks
                ]
        except Exception:
            pass
        return self._chunk_content(text)

    def _read_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return path.read_text(encoding='latin-1')

    def _chunk_content(self, text: str) -> List[Chunk]:
        lines = text.split('\n')
        chunks = []

        current_lines = []
        current_size = 0
        start_line = 1

        for i, line in enumerate(lines, 1):
            line_len = len(line) + 1

            if current_size + line_len > self.chunk_size and current_lines:
                chunks.append(Chunk(
                    content='\n'.join(current_lines),
                    start_line=start_line,
                    end_line=i - 1
                ))

                overlap_line_count = max(1, self.chunk_overlap // 80) if self.chunk_overlap else 0
                overlap_lines = current_lines[-overlap_line_count:] if overlap_line_count else []
                current_lines = overlap_lines + [line]
                current_size = sum(len(l) + 1 for l in current_lines)
                start_line = i - len(overlap_lines)
            else:
                current_lines.append(line)
                current_size += line_len

        if current_lines:
            chunks.append(Chunk(
                content='\n'.join(current_lines),
                start_line=start_line,
                end_line=len(lines)
            ))

        return chunks
