import sqlite3
import json
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import zvec

from .interface import StorageInterface, Document, Entity, SearchResult


class ZvecStore(StorageInterface):
    def __init__(self, db_path: str, vector_path: Optional[str] = None, vector_dimension: int = 1024):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if vector_path is None:
            self.vector_path = self.db_path.parent / "vectors"
        else:
            self.vector_path = Path(vector_path)
        self.vector_path.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")

        self._vector_dimension_param = vector_dimension
        self._init_schema()
        self._init_vector_store()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                project TEXT DEFAULT 'default',
                start_line INTEGER DEFAULT 1,
                end_line INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                content,
                content='documents',
                content_rowid='rowid'
            )
        """)

        self.conn.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON documents BEGIN
                INSERT INTO docs_fts(rowid, content) VALUES (new.rowid, new.content);
            END
        """)
        self.conn.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON documents BEGIN
                INSERT INTO docs_fts(docs_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
            END
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                file_path TEXT NOT NULL,
                project TEXT DEFAULT 'default',
                valid_from TEXT,
                valid_to TEXT,
                superseded_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                project TEXT,
                last_modified REAL,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_project ON documents(project)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project)")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                payload TEXT,
                priority INTEGER DEFAULT 5,
                progress INTEGER DEFAULT 0,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                model TEXT,
                potential_tokens INTEGER,
                actual_tokens INTEGER,
                usd_saved REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def _init_vector_store(self):
        self._vector_collections = {}
        docs_path = self.vector_path / "docs"

        if docs_path.exists():
            row = self.conn.execute("SELECT value FROM settings WHERE key='vector_dimension'").fetchone()
            self.vector_dimension = int(row["value"]) if row else self._vector_dimension_param
            self._schema = zvec.CollectionSchema(
                name="docs",
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, self.vector_dimension),
            )
            self._vector_store = zvec.open(path=str(docs_path))
        else:
            self.vector_dimension = self._vector_dimension_param
            self._schema = zvec.CollectionSchema(
                name="docs",
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, self.vector_dimension),
            )
            self._vector_store = zvec.create_and_open(
                path=str(docs_path),
                schema=self._schema,
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('vector_dimension', ?)",
                (str(self.vector_dimension),)
            )
            self.conn.commit()

    def insert_documents(self, docs: List[Document]) -> None:
        if not docs:
            return

        doc_ids = []
        for doc in docs:
            self.conn.execute("""
                INSERT OR REPLACE INTO documents
                (id, content, source, project, start_line, end_line)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                doc.id, doc.content, doc.source, doc.project,
                doc.start_line, doc.end_line
            ))
            doc_ids.append(doc.id)

        self.conn.commit()

        zvec_docs = []
        for doc in docs:
            if doc.embedding:
                zvec_docs.append(
                    zvec.Doc(id=doc.id, vectors={"embedding": doc.embedding})
                )

        if zvec_docs:
            self._vector_store.insert(zvec_docs)

    def delete_documents_by_source(self, source: str) -> None:
        cursor = self.conn.execute("SELECT id FROM documents WHERE source = ?", (source,))
        doc_ids = [row[0] for row in cursor]

        self.conn.execute("DELETE FROM documents WHERE source = ?", (source,))
        self.conn.execute("DELETE FROM entities WHERE file_path = ?", (source,))
        self.conn.commit()

        for doc_id in doc_ids:
            self._vector_store.delete(doc_id)

    def search_vector(
        self,
        query_embedding: list[float],
        limit: int = 10,
        project: Optional[str] = None
    ) -> List[SearchResult]:
        if len(query_embedding) != self.vector_dimension:
            raise ValueError(f"Expected {self.vector_dimension} dims, got {len(query_embedding)}")

        results = self._vector_store.query(
            zvec.VectorQuery("embedding", vector=query_embedding),
            topk=limit * 5
        )

        doc_ids = [r.id for r in results]
        if not doc_ids:
            return []

        placeholders = ','.join('?' * len(doc_ids))
        project_filter = ""
        params = list(doc_ids)

        if project:
            project_filter = f" AND project = ?"
            params.append(project)

        cursor = self.conn.execute(f"""
            SELECT * FROM documents
            WHERE id IN ({placeholders}){project_filter}
        """, params)

        id_to_score = {r.id: r.score for r in results}

        output = []
        for row in cursor:
            doc = Document(
                id=row['id'],
                content=row['content'],
                source=row['source'],
                project=row['project'],
                start_line=row['start_line'],
                end_line=row['end_line']
            )
            score = id_to_score.get(row['id'], 0.0)
            output.append(SearchResult(doc, score, 'vector'))

        output.sort(key=lambda x: x.score, reverse=True)
        return output[:limit]

    def search_fts(
        self,
        query: str,
        limit: int = 10,
        project: Optional[str] = None
    ) -> List[SearchResult]:
        safe_query = ' '.join(
            f'"{w.replace(chr(34), "")}"' for w in query.split() if w.strip()
        )

        cursor = self.conn.execute("""
            SELECT d.*, rank
            FROM docs_fts
            JOIN documents d ON d.rowid = docs_fts.rowid
            WHERE docs_fts MATCH ? AND (d.project = ? OR ? IS NULL)
            ORDER BY rank
            LIMIT ?
        """, (safe_query, project, project, limit))

        output = []
        for row in cursor:
            doc = Document(
                id=row['id'],
                content=row['content'],
                source=row['source'],
                project=row['project'],
                start_line=row['start_line'],
                end_line=row['end_line']
            )
            score = 1.0 / (1.0 + abs(row['rank']))
            output.append(SearchResult(doc, score, 'fts'))

        return output

    def search_hybrid(
        self,
        query_embedding: list[float],
        query_text: str,
        limit: int = 10,
        project: Optional[str] = None
    ) -> List[SearchResult]:
        vector_results = self.search_vector(query_embedding, limit * 2, project)
        fts_results = self.search_fts(query_text, limit * 2, project)

        k = 60
        scores = {}

        for rank, result in enumerate(vector_results):
            doc_id = result.document.id
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            scores[doc_id + '_doc'] = result.document
            scores[doc_id + '_methods'] = scores.get(doc_id + '_methods', []) + ['vector']

        for rank, result in enumerate(fts_results):
            doc_id = result.document.id
            scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
            scores[doc_id + '_doc'] = result.document
            scores[doc_id + '_methods'] = scores.get(doc_id + '_methods', []) + ['fts']

        doc_ids = [k for k in scores.keys()
                   if not k.endswith('_doc') and not k.endswith('_methods')]
        doc_ids.sort(key=lambda x: scores[x], reverse=True)

        output = []
        for doc_id in doc_ids[:limit]:
            doc = scores[doc_id + '_doc']
            method = '+'.join(scores.get(doc_id + '_methods', ['unknown']))
            output.append(SearchResult(doc, scores[doc_id], method))

        return output

    def insert_entities(self, entities: List[Entity]) -> None:
        for entity in entities:
            self.conn.execute("""
                INSERT INTO entities
                (type, content, file_path, project, valid_from, valid_to, superseded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                entity.type, entity.content, entity.file_path,
                entity.project, entity.valid_from, entity.valid_to, entity.superseded_by
            ))
        self.conn.commit()

    def get_entities(
        self,
        entity_type: Optional[str] = None,
        project: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[Entity]:
        query = "SELECT * FROM entities WHERE 1=1"
        params = []

        if entity_type:
            query += " AND type = ?"
            params.append(entity_type)
        if project:
            query += " AND project = ?"
            params.append(project)

        cursor = self.conn.execute(query, params)

        output = []
        for row in cursor:
            output.append(Entity(
                id=row['id'],
                type=row['type'],
                content=row['content'],
                file_path=row['file_path'],
                project=row['project'],
                valid_from=row['valid_from'],
                valid_to=row['valid_to'],
                superseded_by=row['superseded_by']
            ))
        return output

    def is_file_indexed(self, path: str, mtime: float) -> bool:
        cursor = self.conn.execute(
            "SELECT last_modified FROM files WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        return row is not None and row['last_modified'] == mtime

    def mark_file_indexed(self, path: str, project: str, mtime: float) -> None:
        self.conn.execute("""
            INSERT OR REPLACE INTO files (path, project, last_modified)
            VALUES (?, ?, ?)
        """, (path, project, mtime))
        self.conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        cursor = self.conn.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM entities")
        entity_count = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT project) FROM files")
        project_count = cursor.fetchone()[0]

        db_size = self.db_path.stat().st_size / (1024 * 1024)

        return {
            'total_documents': doc_count,
            'total_entities': entity_count,
            'project_count': project_count,
            'db_size_mb': db_size,
            'db_path': str(self.db_path)
        }

    def add_job(
        self,
        job_id: str,
        job_type: str,
        payload: str,
        priority: int = 5
    ) -> None:
        self.conn.execute("""
            INSERT INTO jobs (id, type, payload, priority, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (job_id, job_type, payload, priority))
        self.conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'type': row['type'],
                'status': row['status'],
                'payload': row['payload'],
                'priority': row['priority'],
                'progress': row['progress'],
                'result': row['result'],
                'error': row['error'],
                'created_at': row['created_at'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at']
            }
        return None

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        updates = []
        params = []

        if status is not None:
            if status == 'running' and not self._get_job_started_at(job_id):
                updates.append("started_at = CURRENT_TIMESTAMP")
            elif status in ('completed', 'failed'):
                updates.append("completed_at = CURRENT_TIMESTAMP")
            updates.append("status = ?")
            params.append(status)

        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)

        if result is not None:
            updates.append("result = ?")
            params.append(result)

        if error is not None:
            updates.append("error = ?")
            params.append(error)

        if updates:
            params.append(job_id)
            self.conn.execute(f"""
                UPDATE jobs SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            self.conn.commit()

    def _get_job_started_at(self, job_id: str) -> bool:
        cursor = self.conn.execute("SELECT started_at FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return row and row['started_at'] is not None

    def list_jobs(self, limit: int = 10, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM jobs"
        params = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)

        jobs = []
        for row in cursor:
            jobs.append({
                'id': row['id'],
                'type': row['type'],
                'status': row['status'],
                'payload': row['payload'],
                'priority': row['priority'],
                'progress': row['progress'],
                'result': row['result'],
                'error': row['error'],
                'created_at': row['created_at'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at']
            })
        return jobs

    def get_job_stats(self) -> Dict[str, Any]:
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'running' THEN 1 END) as running
            FROM jobs
        """)
        row = cursor.fetchone()

        total = row['total']
        if total == 0:
            return {
                'total': 0,
                'counts': {},
                'success_rate': '0%',
                'avg_latency_sec': 0
            }

        success_count = row['completed']
        success_rate = (success_count / total) * 100

        counts = {
            'completed': row['completed'],
            'failed': row['failed'],
            'pending': row['pending'],
            'running': row['running']
        }

        cursor = self.conn.execute("""
            SELECT AVG(JULIANDAY(completed_at) - JULIANDAY(created_at)) * 86400 as avg_latency
            FROM jobs
            WHERE completed_at IS NOT NULL
        """)
        latency_row = cursor.fetchone()
        avg_latency = latency_row['avg_latency'] if latency_row['avg_latency'] else 0

        return {
            'total': total,
            'counts': counts,
            'success_rate': f"{success_rate:.1f}%",
            'avg_latency_sec': f"{avg_latency:.1f}"
        }

    def record_savings(
        self,
        query: str,
        model: str,
        potential_tokens: int,
        actual_tokens: int,
        usd_saved: float
    ) -> None:
        self.conn.execute("""
            INSERT INTO ledger (query, model, potential_tokens, actual_tokens, usd_saved)
            VALUES (?, ?, ?, ?, ?)
        """, (query, model, potential_tokens, actual_tokens, usd_saved))
        self.conn.commit()

    def get_savings_summary(self, days: int = 30) -> Dict[str, Any]:
        cursor = self.conn.execute("""
            SELECT
                SUM(actual_tokens) as total_actual,
                SUM(potential_tokens) as total_potential,
                SUM(usd_saved) as total_saved,
                SUM(CASE WHEN created_at >= datetime('now', '-' || ? || ' days') THEN usd_saved ELSE 0 END) as recent_saved
            FROM ledger
        """, (days,))
        row = cursor.fetchone()

        recent_saved = row['recent_saved'] or 0
        total_saved = row['total_saved'] or 0
        saved_tokens = (row['total_potential'] or 0) - (row['total_actual'] or 0)

        return {
            'recent_saved_tokens': max(0, saved_tokens),
            'recent_usd_saved': recent_saved,
            'total_usd_saved': total_saved
        }

    def get_active_decisions(
        self,
        project: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM entities WHERE type = 'decision'"
        params = []

        if project:
            query += " AND project = ?"
            params.append(project)

        if date:
            query += " AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)"
            params.extend([date, date])

        query += " ORDER BY created_at DESC"

        cursor = self.conn.execute(query, params)

        decisions = []
        for row in cursor:
            decisions.append({
                'content': row['content'],
                'valid_from': row['valid_from'],
                'valid_to': row['valid_to'],
                'file_path': row['file_path']
            })
        return decisions

    def close(self) -> None:
        self.conn.close()
