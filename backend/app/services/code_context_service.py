"""
Code Context Service — deterministic, no LLM.

Responsibilities:
1. Parse import dependencies from Python files using AST
2. Resolve transitive dependencies (files that depend on other files)
3. Combine planned files + their deps + vector search results
   into a deduplicated context for the code writer agent.
"""
import ast
from typing import List, Dict, Set


def _parse_local_imports(file_content: str, all_paths: Set[str]) -> List[str]:
    """
    Parse a Python file's imports using AST and return
    only the ones that exist in the repo (local imports).
    Ignores stdlib and third-party packages.
    """
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return []

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name.replace(".", "/"))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module.replace(".", "/"))

    # Match against actual repo file paths
    resolved = []
    for module_path in imported_modules:
        # Try exact match and with .py extension
        candidates = [
            f"{module_path}.py",
            f"{module_path}/__init__.py",
        ]
        for candidate in candidates:
            # Check if any repo file ends with this path
            matches = [p for p in all_paths if p.endswith(candidate) or p == candidate]
            resolved.extend(matches)

    return list(set(resolved))


def resolve_dependencies(
    seed_paths: List[str],
    all_files: List[dict],
    max_depth: int = 3,
) -> List[dict]:
    """
    Given a list of seed file paths, recursively resolve
    all local import dependencies up to max_depth levels.

    Returns list of {path, content} dicts including seeds + all deps.
    """
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}
    all_paths: Set[str] = set(file_map.keys())

    visited: Set[str] = set()
    queue: List[str] = list(seed_paths)
    depth = 0

    while queue and depth < max_depth:
        next_queue = []
        for path in queue:
            if path in visited or path not in file_map:
                continue
            visited.add(path)
            deps = _parse_local_imports(file_map[path], all_paths)
            for dep in deps:
                if dep not in visited:
                    next_queue.append(dep)
        queue = next_queue
        depth += 1

    return [
        {"path": p, "content": file_map[p]}
        for p in visited
        if p in file_map
    ]


def build_context(
    planned_paths: List[str],
    vector_chunks: List[dict],
    all_files: List[dict],
) -> List[dict]:
    """
    Build complete, deduplicated context for the code writer:

    1. Start with files the planner explicitly identified
    2. Resolve all their import dependencies (AST, deterministic)
    3. Add files referenced in vector search results
    4. Deduplicate by path — planned files take priority

    Returns list of {path, chunk} dicts ready for the LLM prompt.
    """
    file_map: Dict[str, str] = {f["path"]: f["content"] for f in all_files}

    # Step 1+2: planned files + their transitive deps
    dep_files = resolve_dependencies(planned_paths, all_files)
    dep_paths = {f["path"] for f in dep_files}

    # Step 3: add paths from vector search not already covered
    vector_paths = [
        c["path"] for c in vector_chunks
        if c["path"] not in dep_paths and c["path"] in file_map
    ]
    extra_files = resolve_dependencies(vector_paths, all_files)

    # Step 4: merge, deduplicate, planned files first
    seen: Set[str] = set()
    result: List[dict] = []

    for f in dep_files + extra_files:
        if f["path"] not in seen:
            seen.add(f["path"])
            result.append({"path": f["path"], "chunk": f["content"]})

    return result
