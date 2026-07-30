from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from forgeai.core.config import get_settings


@dataclass
class VectorHit:
    file_path: str
    content: str
    score: float
    language: str = "text"
    repo_path: str | None = None


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.points: list[tuple[str, list[float], dict]] = []

    def upsert(self, point_id: str, vector: list[float], payload: dict) -> None:
        self.points = [point for point in self.points if point[0] != point_id]
        self.points.append((point_id, vector, payload))

    def delete_by_repo(self, repo_path: str) -> None:
        self.points = [
            point for point in self.points if point[2].get("repo_path") != repo_path
        ]

    def search(
        self, vector: list[float], limit: int = 8, repo_path: str | None = None
    ) -> list[VectorHit]:
        def dot(point: tuple[str, list[float], dict]) -> float:
            return sum(a * b for a, b in zip(vector, point[1], strict=False))

        points = [
            point
            for point in self.points
            if repo_path is None or point[2].get("repo_path") == repo_path
        ]
        ranked = sorted(points, key=dot, reverse=True)[:limit]
        return [
            VectorHit(
                file_path=payload["file_path"],
                content=payload["content"],
                language=payload.get("language", "text"),
                repo_path=payload.get("repo_path"),
                score=float(dot(point)),
            )
            for point_id, point_vector, payload in ranked
            for point in [(point_id, point_vector, payload)]
        ]


class QdrantVectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = QdrantClient(url=self.settings.qdrant_url, timeout=2.0)
        self.collection = self.settings.qdrant_collection
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        if any(collection.name == self.collection for collection in collections):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(
                size=self.settings.embedding_dimensions,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def upsert(self, point_id: str, vector: list[float], payload: dict) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    def delete_by_repo(self, repo_path: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="repo_path",
                            match=qmodels.MatchValue(value=repo_path),
                        )
                    ]
                )
            ),
        )

    def search(
        self, vector: list[float], limit: int = 8, repo_path: str | None = None
    ) -> list[VectorHit]:
        query_filter = None
        if repo_path is not None:
            query_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="repo_path",
                        match=qmodels.MatchValue(value=repo_path),
                    )
                ]
            )
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter,
        )
        return [
            VectorHit(
                file_path=str(hit.payload.get("file_path", "")),
                content=str(hit.payload.get("content", "")),
                language=str(hit.payload.get("language", "text")),
                repo_path=str(hit.payload.get("repo_path", "")),
                score=float(hit.score),
            )
            for hit in hits
        ]


_memory_store = InMemoryVectorStore()


def get_vector_store(prefer_qdrant: bool = True):
    if not prefer_qdrant:
        return _memory_store
    try:
        return QdrantVectorStore()
    except Exception:
        return _memory_store
