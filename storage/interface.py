from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Document:
    id: str
    content: str
    embedding: Optional[list[float]] = None
    metadata: Optional[dict] = None
    source: str = ""
    project: str = "default"
    start_line: int = 1
    end_line: int = 1
    created_at: Optional[datetime] = None


@dataclass
class Entity:
    id: Optional[int]
    type: str
    content: str
    file_path: str
    project: str
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    superseded_by: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class SearchResult:
    document: Document
    score: float
    method: str


class StorageInterface(ABC):
    @abstractmethod
    def insert_documents(self, docs: List[Document]) -> None:
        pass

    @abstractmethod
    def delete_documents_by_source(self, source: str) -> None:
        pass

    @abstractmethod
    def search_vector(
        self,
        query_embedding: list[float],
        limit: int = 10,
        project: Optional[str] = None
    ) -> List[SearchResult]:
        pass

    @abstractmethod
    def search_fts(
        self,
        query: str,
        limit: int = 10,
        project: Optional[str] = None
    ) -> List[SearchResult]:
        pass

    @abstractmethod
    def search_hybrid(
        self,
        query_embedding: list[float],
        query_text: str,
        limit: int = 10,
        project: Optional[str] = None
    ) -> List[SearchResult]:
        pass

    @abstractmethod
    def insert_entities(self, entities: List[Entity]) -> None:
        pass

    @abstractmethod
    def get_entities(
        self,
        entity_type: Optional[str] = None,
        project: Optional[str] = None,
        date: Optional[str] = None
    ) -> List[Entity]:
        pass

    @abstractmethod
    def is_file_indexed(self, path: str, mtime: float) -> bool:
        pass

    @abstractmethod
    def mark_file_indexed(self, path: str, project: str, mtime: float) -> None:
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
