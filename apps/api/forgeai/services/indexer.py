import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from forgeai.db.tables import RepoChunk
from forgeai.services.embeddings import get_embedding_provider
from forgeai.services.security import (
    contains_secret,
    detect_suspicious_content,
    is_sensitive_path,
    redact_secrets,
)
from forgeai.services.vector_store import get_vector_store

TEXT_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".css": "css",
    ".html": "html",
    ".sql": "sql",
}

IGNORED_PARTS = {
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "node_modules",
    ".forgeai",
    "dist",
    "coverage",
    "playwright-report",
    "test-results",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}

MAX_INDEXABLE_BYTES = 500_000
SYMBOL_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<kind>class|def|async def|function|export function|"
    r"export default function|interface|type)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
IMPORT_PATTERN = re.compile(
    r"^\s*(?:from\s+[\w.]+\s+import\s+.+|import\s+.+|import\s+.+\s+from\s+['\"][^'\"]+['\"])",
)


@dataclass(frozen=True)
class IndexedChunk:
    content: str
    language: str
    symbol_path: str | None
    kind: str
    start_line: int
    end_line: int
    signature: str | None
    docstring: str | None
    imports: list[str]


def _load_forgeignore(root: Path) -> list[str]:
    ignore_file = root / ".forgeignore"
    if not ignore_file.exists():
        return []
    try:
        return [
            line.strip()
            for line in ignore_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except UnicodeDecodeError:
        return []


def _matches_glob(relative: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def is_indexable(
    path: Path, root: Path | None = None, ignore_globs: list[str] | None = None
) -> bool:
    relative = str(path.relative_to(root)) if root else str(path)
    return (
        path.is_file()
        and path.suffix in TEXT_EXTENSIONS
        and not any(part in IGNORED_PARTS for part in path.parts)
        and not is_sensitive_path(relative)
        and not _matches_glob(relative, ignore_globs or [])
        and path.stat().st_size <= MAX_INDEXABLE_BYTES
    )


def chunk_text(text: str, *, max_chars: int = 1600) -> list[str]:
    paragraphs = text.splitlines()
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in paragraphs:
        line_size = len(line) + 1
        if current and current_size + line_size > max_chars:
            chunks.append("\n".join(current).strip())
            current = []
            current_size = 0
        current.append(line)
        current_size += line_size
    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _extract_imports(lines: list[str]) -> list[str]:
    imports: list[str] = []
    for line in lines:
        if IMPORT_PATTERN.match(line):
            imports.append(line.strip())
    return imports[:40]


def _extract_docstring(lines: list[str]) -> str | None:
    joined = "\n".join(line.strip() for line in lines[:12])
    match = re.search(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', joined, flags=re.DOTALL)
    if not match:
        return None
    return redact_secrets((match.group(1) or match.group(2) or "").strip())[:400]


def _symbol_boundaries(lines: list[str]) -> list[tuple[int, str, str, str]]:
    boundaries: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(lines, start=1):
        match = SYMBOL_PATTERN.match(line)
        if not match:
            continue
        if match.group("indent") and not line.startswith("export "):
            continue
        kind = match.group("kind").replace("export default ", "").replace("export ", "")
        boundaries.append((index, kind, match.group("name"), line.strip()))
    return boundaries


def chunk_code(text: str, language: str, *, max_chars: int = 2600) -> list[IndexedChunk]:
    lines = text.splitlines()
    imports = _extract_imports(lines)
    boundaries = _symbol_boundaries(lines)
    if language not in {"python", "typescript", "javascript"} or not boundaries:
        return [
            IndexedChunk(
                content=chunk,
                language=language,
                symbol_path=None,
                kind="file",
                start_line=1,
                end_line=max(1, len(chunk.splitlines())),
                signature=None,
                docstring=_extract_docstring(chunk.splitlines()),
                imports=imports,
            )
            for chunk in chunk_text(text, max_chars=max_chars)
        ]

    chunks: list[IndexedChunk] = []
    for boundary_index, (start, kind, name, signature) in enumerate(boundaries):
        next_start = (
            boundaries[boundary_index + 1][0]
            if boundary_index + 1 < len(boundaries)
            else len(lines) + 1
        )
        segment_lines = lines[start - 1 : next_start - 1]
        if len("\n".join(segment_lines)) <= max_chars:
            chunks.append(
                IndexedChunk(
                    content="\n".join(segment_lines).strip(),
                    language=language,
                    symbol_path=name,
                    kind=kind,
                    start_line=start,
                    end_line=next_start - 1,
                    signature=signature,
                    docstring=_extract_docstring(segment_lines),
                    imports=imports,
                )
            )
            continue
        offset = start
        for chunk in chunk_text("\n".join(segment_lines), max_chars=max_chars):
            line_count = max(1, len(chunk.splitlines()))
            chunks.append(
                IndexedChunk(
                    content=chunk,
                    language=language,
                    symbol_path=name,
                    kind=kind,
                    start_line=offset,
                    end_line=offset + line_count - 1,
                    signature=signature,
                    docstring=_extract_docstring(chunk.splitlines()),
                    imports=imports,
                )
            )
            offset += line_count
    return [chunk for chunk in chunks if chunk.content]


def index_repository(db: Session, repo_path: str) -> int:
    root = Path(repo_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    embedder = get_embedding_provider()
    vector_store = get_vector_store()
    ignore_globs = _load_forgeignore(root)
    db.execute(delete(RepoChunk).where(RepoChunk.repo_path == str(root)))
    delete_by_repo = getattr(vector_store, "delete_by_repo", None)
    if callable(delete_by_repo):
        delete_by_repo(str(root))
    indexed = 0
    for file_path in root.rglob("*"):
        if not is_indexable(file_path, root, ignore_globs):
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if contains_secret(text):
            continue
        relative = str(file_path.relative_to(root))
        suspicious = detect_suspicious_content(relative, text)
        language = TEXT_EXTENSIONS.get(file_path.suffix, "text")
        for chunk in chunk_code(text, language):
            chunk_id = str(uuid4())
            vector = embedder.embed(f"{relative}\n{chunk.symbol_path or ''}\n{chunk.content}")
            db_chunk = RepoChunk(
                id=chunk_id,
                repo_path=str(root),
                file_path=relative,
                language=language,
                symbol_path=chunk.symbol_path,
                kind=chunk.kind,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                signature=chunk.signature,
                docstring=chunk.docstring,
                imports=chunk.imports,
                content=chunk.content,
                token_estimate=max(1, len(chunk.content) // 4),
                embedding_ref=chunk_id,
            )
            db.add(db_chunk)
            vector_store.upsert(
                chunk_id,
                vector,
                {
                    "repo_path": str(root),
                    "file_path": relative,
                    "language": language,
                    "symbol_path": chunk.symbol_path,
                    "kind": chunk.kind,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                    "suspicious_findings": suspicious,
                },
            )
            indexed += 1
    db.commit()
    return indexed


def semantic_search(query: str, limit: int = 8, repo_path: str | None = None):
    embedder = get_embedding_provider()
    vector_store = get_vector_store()
    return vector_store.search(embedder.embed(query), limit=limit, repo_path=repo_path)


def search_repository_context(
    db: Session, repo_path: str | None, query: str, limit: int = 8
) -> list[dict[str, object]]:
    root = str(Path(repo_path).expanduser().resolve()) if repo_path else None
    terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_]{3,}", query)[:12]]
    rows = db.execute(
        select(RepoChunk).where(RepoChunk.repo_path == root) if root else select(RepoChunk)
    ).scalars()

    scored: list[tuple[int, RepoChunk]] = []
    for chunk in rows:
        haystack = " ".join(
            part
            for part in [
                chunk.file_path,
                chunk.symbol_path or "",
                chunk.signature or "",
                chunk.content,
            ]
        ).lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, chunk))

    ranked = sorted(
        scored,
        key=lambda item: (item[0], item[1].file_path, item[1].start_line),
        reverse=True,
    )[:limit]
    if ranked:
        return [_chunk_payload(chunk, score=float(score)) for score, chunk in ranked]

    return [
        {
            "file_path": hit.file_path,
            "score": round(hit.score, 4),
            "language": hit.language,
            "preview": hit.content[:360],
            "content": hit.content,
            "retrieval_mode": "vector",
        }
        for hit in semantic_search(query, limit=limit, repo_path=root)
    ]


def _chunk_payload(chunk: RepoChunk, *, score: float) -> dict[str, object]:
    return {
        "file_path": chunk.file_path,
        "score": score,
        "language": chunk.language,
        "symbol_path": chunk.symbol_path,
        "kind": chunk.kind,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "preview": chunk.content[:360],
        "content": chunk.content,
        "retrieval_mode": "keyword-symbol",
    }
