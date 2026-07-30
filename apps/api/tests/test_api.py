import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./.forgeai/test.db")
os.environ.setdefault("RUNNER_MODE", "inline")
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:1")

from fastapi.testclient import TestClient  # noqa: E402

from forgeai.api import app  # noqa: E402
from forgeai.db.session import init_db  # noqa: E402


def client() -> TestClient:
    init_db()
    return TestClient(app)


def wait_for_status(test_client: TestClient, run_id: str, status: str) -> dict:
    deadline = time.time() + 5
    latest: dict | None = None
    while time.time() < deadline:
        latest = test_client.get(f"/api/runs/{run_id}").json()
        if latest["status"] == status:
            return latest
        time.sleep(0.1)
    assert latest is not None
    raise AssertionError(f"Expected status {status}, got {latest['status']}")


def create_temp_repo(path: Path) -> Path:
    path.mkdir()
    (path / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "pytest",
            "GIT_AUTHOR_EMAIL": "pytest@example.com",
            "GIT_COMMITTER_NAME": "pytest",
            "GIT_COMMITTER_EMAIL": "pytest@example.com",
        },
    )
    return path


def test_run_pauses_for_approval_then_applies_verified_patch(tmp_path: Path) -> None:
    test_client = client()
    repo_path = create_temp_repo(tmp_path / "repo")
    response = test_client.post(
        "/api/runs",
        json={
            "task": "Prepare a safe README improvement",
            "model_profile": "balanced",
            "repo_path": str(repo_path),
        },
    )
    assert response.status_code == 200
    created = response.json()
    run = wait_for_status(test_client, created["id"], "awaiting_approval")
    assert run["approvals"][0]["status"] == "pending"
    assert run["verified_patches"]
    assert run["verified_patches"][0]["applies_cleanly"] is True

    approval_id = run["approvals"][0]["id"]
    response = test_client.post(
        f"/api/runs/{run['id']}/approvals/{approval_id}",
        json={"decision": "approved", "actor": "pytest"},
    )
    assert response.status_code == 200
    completed = wait_for_status(test_client, run["id"], "completed")
    assert completed["verified_patches"][0]["applied_at"] is not None
    assert any(artifact["kind"] == "review" for artifact in completed["artifacts"])
    assert any(step["agent"] == "documenter" for step in completed["steps"])
    assert "ForgeAI Verified Run" in (repo_path / "README.md").read_text(encoding="utf-8")


def test_repository_index_and_search() -> None:
    test_client = client()
    repo_path = Path(__file__).resolve().parents[3] / "examples" / "sample-repo"
    response = test_client.post("/api/repos/index", json={"path": str(repo_path)})
    assert response.status_code == 200
    assert response.json()["indexed_chunks"] > 0

    response = test_client.get("/api/search", params={"q": "task board completion rate"})
    assert response.status_code == 200
    results = response.json()
    assert results
    assert any("taskBoard" in item["file_path"] for item in results)
