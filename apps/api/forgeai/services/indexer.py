from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from forgeai.db.tables import RepoChunk
from forgeai.services.embeddings import get_embedding_provider
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
}


def is_indexable(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix in TEXT_EXTENSIONS
        and not any(part in IGNORED_PARTS for part in path.parts)
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


def index_repository(db: Session, repo_path: str) -> int:
    root = Path(repo_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    embedder = get_embedding_provider()
    vector_store = get_vector_store()
    indexed = 0
    for file_path in root.rglob("*"):
        if not is_indexable(file_path):
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(file_path.relative_to(root))
        for chunk in chunk_text(text):
            chunk_id = str(uuid4())
            language = TEXT_EXTENSIONS.get(file_path.suffix, "text")
            vector = embedder.embed(f"{relative}\n{chunk}")
            db_chunk = RepoChunk(
                id=chunk_id,
                repo_path=str(root),
                file_path=relative,
                language=language,
                content=chunk,
                token_estimate=max(1, len(chunk) // 4),
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
                    "content": chunk,
                },
            )
            indexed += 1
    db.commit()
    return indexed


def semantic_search(query: str, limit: int = 8):
    embedder = get_embedding_provider()
    vector_store = get_vector_store()
    return vector_store.search(embedder.embed(query), limit=limit)
