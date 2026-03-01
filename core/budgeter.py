from typing import List
from dataclasses import dataclass

from core.oracle import QueryResult, Pointer
from storage.interface import SearchResult

PRICING = {
    "claude-3.5-sonnet": 3.0,
    "claude-3-opus": 15.0,
    "gemini-3-flash": 0.10,
    "default": 3.0
}


@dataclass
class ContextItem:
    content: str
    source: str
    item_type: str
    tokens: int
    priority: float


class ContextBudgeter:
    def __init__(self, budget: int = 4000):
        self.budget = budget
        self.char_per_token = 4
        self.model_name = "claude-3.5-sonnet"
        self.potential_tokens = 0
        self.current_tokens = 0

    def assemble(self, result: QueryResult) -> str:
        items = []

        self.potential_tokens = 0

        for entity in result.entities:
            content = f"[{entity.type.upper()}] {entity.content}"
            items.append(ContextItem(
                content=content,
                source=entity.file_path,
                item_type='entity',
                tokens=self._estimate_tokens(content),
                priority=0.9
            ))

        for chunk in result.chunks:
            self.potential_tokens += len(chunk.document.content)
            content = f"--- {chunk.document.source} (lines {chunk.document.start_line}-{chunk.document.end_line}) ---\n{chunk.document.content}"
            items.append(ContextItem(
                content=content,
                source=chunk.document.source,
                item_type='chunk',
                tokens=self._estimate_tokens(content),
                priority=chunk.score
            ))

        for pointer in result.pointers:
            content = f"📍 {pointer.file_path}:{pointer.line_start}-{pointer.line_end} ({pointer.section})"
            items.append(ContextItem(
                content=content,
                source=pointer.file_path,
                item_type='pointer',
                tokens=self._estimate_tokens(content),
                priority=pointer.confidence
            ))

        self.potential_tokens = self.potential_tokens // self.char_per_token

        items.sort(key=lambda x: x.priority, reverse=True)

        selected = []
        total_tokens = 0

        for item in items:
            if total_tokens + item.tokens > self.budget:
                continue

            file_count = sum(1 for s in selected if s.source == item.source)
            if file_count >= 3 and item.item_type != 'entity':
                continue

            selected.append(item)
            total_tokens += item.tokens

        selected.sort(key=lambda x: (0 if x.item_type == 'entity' else 1, x.source))

        parts = [item.content for item in selected]
        context = "\n\n".join(parts)

        self.current_tokens = total_tokens

        savings = self._calculate_savings(result, selected)
        context += f"\n\n[Context: {total_tokens} tokens used, {savings}% reduction]"

        return context

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // self.char_per_token

    def _calculate_savings(self, result: QueryResult, selected: List[ContextItem]) -> int:
        raw_size = sum(len(c.document.content) for c in result.chunks)
        raw_tokens = raw_size // self.char_per_token
        used_tokens = sum(i.tokens for i in selected)

        if raw_tokens == 0:
            return 0

        return int((1 - used_tokens / raw_tokens) * 100)
