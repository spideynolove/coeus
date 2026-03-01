import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from storage.interface import Entity


@dataclass
class ExtractedData:
    problems: List[str] = field(default_factory=list)
    solutions: List[str] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, str]] = field(default_factory=list)
    code_snippets: List[Dict[str, str]] = field(default_factory=list)

    def has_data(self) -> bool:
        return any([
            self.problems,
            self.solutions,
            self.decisions,
            self.tasks
        ])

    def count(self) -> int:
        return (
            len(self.problems) +
            len(self.solutions) +
            len(self.decisions) +
            len(self.tasks) +
            len(self.code_snippets)
        )

    def to_entities(self, file_path: str, project: str) -> List[Entity]:
        entities = []

        for problem in self.problems:
            entities.append(Entity(
                id=None,
                type='problem',
                content=problem,
                file_path=file_path,
                project=project
            ))

        for solution in self.solutions:
            entities.append(Entity(
                id=None,
                type='solution',
                content=solution,
                file_path=file_path,
                project=project
            ))

        for decision in self.decisions:
            entities.append(Entity(
                id=None,
                type='decision',
                content=decision.get('content', ''),
                file_path=file_path,
                project=project,
                valid_from=decision.get('valid_from'),
                valid_to=decision.get('valid_to'),
                superseded_by=decision.get('superseded_by')
            ))

        for task in self.tasks:
            status = "✓" if task.get('status') == 'done' else "○"
            entities.append(Entity(
                id=None,
                type='task',
                content=f"[{status}] {task.get('content', '')}",
                file_path=file_path,
                project=project
            ))

        return entities


class Extractor:
    def __init__(self):
        self.patterns = {
            'problem': re.compile(r'(?:^|\n)(?:[-*]\s+)?\*?Problem[:?]?\*?\s*(.+?)(?=\n|$)', re.IGNORECASE),
            'solution': re.compile(r'(?:^|\n)(?:[-*]\s+)?\*?Solution[:?]?\*?\s*(.+?)(?=\n|$)', re.IGNORECASE),
            'decision': re.compile(r'(?:^|\n)(?:[-*]\s+)?\*?Decision[:?]?\*?\s*(.+?)(?=\n|$)', re.IGNORECASE),
            'task': re.compile(r'(?:^|\n)(?:[-*]\s+)?\[([ x])\]\s*(.+?)(?=\n|$)', re.IGNORECASE),
            'code_block': re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)
        }

    def extract(self, text: str) -> ExtractedData:
        data = ExtractedData()

        for match in self.patterns['problem'].finditer(text):
            data.problems.append(match.group(1).strip())

        for match in self.patterns['solution'].finditer(text):
            data.solutions.append(match.group(1).strip())

        for match in self.patterns['task'].finditer(text):
            data.tasks.append({
                'status': 'done' if match.group(1).lower() == 'x' else 'todo',
                'content': match.group(2).strip()
            })

        for match in self.patterns['code_block'].finditer(text):
            data.code_snippets.append({
                'language': match.group(1) or 'text',
                'code': match.group(2).strip()[:200]
            })

        data.decisions = self._extract_decisions(text)

        return data

    def _extract_decisions(self, text: str) -> List[Dict[str, Any]]:
        decisions = []
        lines = text.split('\n')
        current_decision = None

        for line in lines:
            stripped = line.strip()

            if not current_decision:
                match = re.search(r'(?:^|\s)\*?Decision[:?]?\*?\s*(.+)', stripped, re.IGNORECASE)
                if match and not stripped.startswith('<!--'):
                    content = match.group(1).strip()

                    v_from, v_to = None, None
                    date_match = re.search(r'\[(\d{4}-\d{2}-\d{2})\s*->\s*(\d{4}-\d{2}-\d{2})\]', content)
                    if date_match:
                        v_from, v_to = date_match.groups()
                        content = content.replace(date_match.group(0), "").strip()

                    current_decision = {
                        'content': content,
                        'valid_from': v_from,
                        'valid_to': v_to,
                        'superseded_by': None
                    }
                continue

            if current_decision:
                lower = stripped.lower()

                if lower.startswith('valid from:'):
                    current_decision['valid_from'] = stripped.split(':', 1)[1].strip()
                elif lower.startswith('valid to:'):
                    current_decision['valid_to'] = stripped.split(':', 1)[1].strip()
                elif lower.startswith('superseded by:'):
                    current_decision['superseded_by'] = stripped.split(':', 1)[1].strip()

                elif stripped == "" or (
                    stripped.startswith(('*', '-', '#')) and
                    not any(x in lower for x in ['valid', 'superseded'])
                ):
                    decisions.append(current_decision)
                    current_decision = None

        if current_decision:
            decisions.append(current_decision)

        return decisions
