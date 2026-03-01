from typing import Dict, Any, Optional
from storage.interface import Document


class TrieNode:
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.documents: list = []


class PrefixTrie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, key: str, document: Dict[str, Any]):
        node = self.root
        for char in key.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        if len(node.documents) < 10:
            node.documents.append(document)

    def search(self, prefix: str) -> list:
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        return self._collect(node)[:10]

    def _collect(self, node: TrieNode) -> list:
        results = list(node.documents)
        for child in node.children.values():
            results.extend(self._collect(child))
        return results


class FastPath:
    def __init__(self):
        self.exact_index: Dict[str, Dict[str, Any]] = {}
        self.prefix_trie = PrefixTrie()

    def index(self, key: str, document: Document, score: float = 1.0):
        doc_dict = {
            'document': document,
            'score': score
        }

        key_lower = key.lower().strip()
        if len(key) < 100 or '@' in key:
            self.exact_index[key_lower] = doc_dict

        for word in key_lower.split():
            word = word.strip('.,!?"\'()')
            if len(word) > 2:
                self.prefix_trie.insert(word, doc_dict)

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        query_lower = query.lower().strip()

        if query_lower in self.exact_index:
            result = self.exact_index[query_lower]
            return {
                'document': result['document'],
                'score': result['score'],
                'confidence': 1.0,
                'type': 'exact'
            }

        if len(query_lower) >= 3:
            results = self.prefix_trie.search(query_lower)
            if results:
                first = results[0]
                doc = first['document']
                if doc.content.lower().startswith(query_lower):
                    return {
                        'document': doc,
                        'score': first['score'],
                        'confidence': 0.9,
                        'type': 'prefix'
                    }

        return None
