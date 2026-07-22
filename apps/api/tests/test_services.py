from pathlib import Path

from forgeai.services.indexer import chunk_text
from forgeai.services.security import ApprovalPolicy, redact_secrets
from forgeai.services.vision import create_demo_visual_diff


def test_chunk_text_splits_large_content() -> None:
    chunks = chunk_text("\n".join(f"line {index}" for index in range(200)), max_chars=120)
    assert len(chunks) > 1
    assert all(len(chunk) <= 180 for chunk in chunks)


def test_approval_policy_guards_mutations() -> None:
    policy = ApprovalPolicy()
    assert policy.requires_approval("file_write")
    assert policy.requires_approval("shell", "rm -rf dist")
    assert not policy.requires_approval("shell", "pytest apps/api/tests")


def test_secret_redaction() -> None:
    redacted = redact_secrets("OPENAI_API_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz")
    assert "sk-123" not in redacted
    assert "[REDACTED]" in redacted


def test_visual_diff_fixture(tmp_path: Path) -> None:
    output = tmp_path / "diff.png"
    stats = create_demo_visual_diff(output)
    assert output.exists()
    assert stats["changed_pixels"] > 0
