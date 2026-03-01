import uuid
import threading
import time
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from storage.zvec_store import ZvecStore


class JobManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.storage = ZvecStore(db_path)
        self.worker_running = False
        self.worker_thread = None
        self.job_handlers = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        from core.ingestor import Ingestor
        from config import get_config
        from embedders import create_embedder

        config = get_config()
        embedder = create_embedder(
            provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
            model=config.embedding_model
        )
        ingestor = Ingestor(self.storage, embedder)

        async def handle_ingest(job_id: str, payload: dict):
            path = payload.get('path')
            recursive = payload.get('recursive', True)
            project = payload.get('project', Path(path).name if path else 'default')

            full_path = Path(path).expanduser().resolve()
            if not full_path.exists():
                return {'error': f'Path does not exist: {full_path}'}

            if full_path.is_file():
                result = ingestor.ingest_file(full_path, project)
                return {
                    'status': 'completed',
                    'chunks': result['chunks'],
                    'entities': result['entities']
                }
            else:
                total_chunks = 0
                total_entities = 0
                files_processed = 0

                for result in ingestor.ingest_directory(full_path, project, None, recursive):
                    if 'error' not in result:
                        total_chunks += result.get('chunks', 0)
                        total_entities += result.get('entities', 0)
                        files_processed += 1
                    self.storage.update_job(job_id, progress=int((files_processed / 10) * 100))

            return {
                'status': 'completed',
                'total_chunks': total_chunks,
                'total_entities': total_entities,
                'files_processed': files_processed
            }

        self.job_handlers['ingest'] = handle_ingest
        self.job_handlers['ingest_batch'] = handle_ingest

    def submit_job(
        self,
        job_type: str,
        params: Dict[str, Any],
        priority: int = 5
    ) -> str:
        job_id = str(uuid.uuid4())

        if job_type not in self.job_handlers:
            raise ValueError(f"Unknown job type: {job_type}")

        self.storage.add_job(
            job_id=job_id,
            job_type=job_type,
            payload=json.dumps(params),
            priority=priority
        )

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_job(job_id)

    def list_jobs(self, limit: int = 10, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_jobs(limit, status)

    def get_job_stats(self) -> Dict[str, Any]:
        return self.storage.get_job_stats()

    def _process_job(self, job_id: str, job_type: str, payload: str):
        import asyncio

        async def process():
            try:
                handler = self.job_handlers.get(job_type)
                if not handler:
                    self.storage.update_job(job_id, status='failed', error=f'No handler for type: {job_type}')
                    return

                self.storage.update_job(job_id, status='running', progress=0)

                params = json.loads(payload)
                result = await handler(job_id, params)

                if 'error' in result:
                    self.storage.update_job(job_id, status='failed', error=result['error'])
                else:
                    self.storage.update_job(
                        job_id,
                        status='completed',
                        progress=100,
                        result=json.dumps(result)
                    )
            except Exception as e:
                self.storage.update_job(job_id, status='failed', error=str(e))

        asyncio.run(process())

    def start_worker(self):
        if self.worker_running:
            return

        self.worker_running = True

        def worker_loop():
            while self.worker_running:
                try:
                    jobs = self.storage.list_jobs(limit=10, status='pending')

                    if not jobs:
                        time.sleep(1)
                        continue

                    jobs.sort(key=lambda j: j['priority'], reverse=True)

                    for job in jobs:
                        if not self.worker_running:
                            break

                        self._process_job(job['id'], job['type'], job['payload'])

                except Exception as e:
                    print(f"Worker error: {e}")
                    time.sleep(1)

        self.worker_thread = threading.Thread(target=worker_loop, daemon=True)
        self.worker_thread.start()

    def stop_worker(self):
        self.worker_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
