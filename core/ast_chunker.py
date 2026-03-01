import importlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class AstChunk:
    content: str
    start_line: int
    end_line: int
    section: Optional[str] = None


_GRAMMAR_MODULES = {
    '.py':  'tree_sitter_python',
    '.go':  'tree_sitter_go',
    '.js':  'tree_sitter_javascript',
    '.ts':  'tree_sitter_typescript',
    '.tsx': 'tree_sitter_typescript',
    '.rs':  'tree_sitter_rust',
}

_TOP_LEVEL_TYPES = {
    '.py':  {'function_definition', 'class_definition', 'decorated_definition'},
    '.go':  {'function_declaration', 'method_declaration', 'type_declaration'},
    '.js':  {'function_declaration', 'class_declaration', 'export_statement'},
    '.ts':  {'function_declaration', 'class_declaration', 'export_statement',
             'interface_declaration', 'type_alias_declaration'},
    '.tsx': {'function_declaration', 'class_declaration', 'export_statement',
             'interface_declaration'},
    '.rs':  {'function_item', 'struct_item', 'impl_item', 'enum_item', 'trait_item'},
}

_LANGUAGE_CACHE: dict = {}


def _get_language(suffix: str):
    if suffix in _LANGUAGE_CACHE:
        return _LANGUAGE_CACHE[suffix]
    module_name = _GRAMMAR_MODULES.get(suffix)
    if not module_name:
        _LANGUAGE_CACHE[suffix] = None
        return None
    try:
        from tree_sitter import Language
        mod = importlib.import_module(module_name)
        if suffix == '.tsx':
            lang = Language(mod.language_tsx())
        else:
            lang = Language(mod.language())
        _LANGUAGE_CACHE[suffix] = lang
        return lang
    except (ImportError, AttributeError):
        _LANGUAGE_CACHE[suffix] = None
        return None


def _node_name(node) -> Optional[str]:
    name_node = node.child_by_field_name('name')
    if name_node:
        return name_node.text.decode('utf-8', errors='replace')
    for child in node.children:
        if child.type in ('function_definition', 'class_definition',
                          'function_declaration', 'class_declaration',
                          'function_item', 'struct_item', 'impl_item',
                          'interface_declaration', 'type_alias_declaration'):
            return _node_name(child)
    return None


def chunk_by_ast(text: str, suffix: str, chunk_size: int) -> list:
    lang = _get_language(suffix)
    if lang is None:
        return []

    try:
        from tree_sitter import Parser
    except ImportError:
        return []

    node_types = _TOP_LEVEL_TYPES.get(suffix, set())
    parser = Parser(lang)
    tree = parser.parse(text.encode('utf-8', errors='replace'))
    lines = text.split('\n')

    segments = []
    for node in tree.root_node.children:
        if node.type in node_types:
            start = node.start_point[0]
            end = node.end_point[0]
            segments.append((start, end, _node_name(node)))

    if not segments:
        return []

    chunks = []
    pack_lines = []
    pack_start = segments[0][0]
    pack_end = segments[0][0]
    pack_section = segments[0][2]

    for start, end, name in segments:
        seg_lines = lines[start:end + 1]
        seg_text = '\n'.join(seg_lines)

        if pack_lines:
            combined = '\n'.join(pack_lines) + '\n' + seg_text
            if len(combined) > chunk_size:
                chunks.append(AstChunk(
                    content='\n'.join(pack_lines),
                    start_line=pack_start + 1,
                    end_line=pack_end + 1,
                    section=pack_section,
                ))
                pack_lines = seg_lines
                pack_start = start
                pack_end = end
                pack_section = name
            else:
                pack_lines.extend(seg_lines)
                pack_end = end
        else:
            pack_lines = seg_lines
            pack_start = start
            pack_end = end
            pack_section = name

    if pack_lines:
        chunks.append(AstChunk(
            content='\n'.join(pack_lines),
            start_line=pack_start + 1,
            end_line=pack_end + 1,
            section=pack_section,
        ))

    return chunks
