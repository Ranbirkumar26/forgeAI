import difflib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from forgeai.db.tables import VerifiedPatch
from forgeai.services.security import contains_secret, redact_secrets


@dataclass(frozen=True)
class CommandCheck:
    name: str
    command: str
    exit_code: int
    duration_ms: int
    output_tail: str

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "output_tail": redact_secrets(self.output_tail)[-1200:],
        }


def build_readme_note_patch(repo_root: Path, task: str) -> str:
    readme = repo_root / "README.md"
    before = readme.read_text(encoding="utf-8") if readme.exists() else ""
    clean_task = " ".join(redact_secrets(task).split())[:180]
    note = (
        "\n\n## ForgeAI Verified Run\n\n"
        f"- Task: {clean_task}\n"
        "- Patch prepared with approval-gated execution evidence.\n"
    )
    after = before.rstrip() + note + "\n"
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="a/README.md",
            tofile="b/README.md",
            lineterm="",
        )
    ) + "\n"


def summarize_diff(diff: str) -> dict[str, object]:
    files: list[str] = []
    added = 0
    removed = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line.removeprefix("+++ b/"))
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {"files_changed": files, "lines_added": added, "lines_removed": removed}


def get_base_sha(repo_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def verify_patch(repo_root: Path, diff: str) -> tuple[bool, list[dict[str, object]]]:
    checks = [_git_apply_check(repo_root, diff).as_payload(), _secret_scan_check(diff).as_payload()]
    return all(int(check["exit_code"]) == 0 for check in checks), checks


def create_verified_patch(
    db: Session,
    *,
    run_id: str,
    repo_root: Path,
    diff: str,
    context_files_read: list[dict[str, object]],
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> VerifiedPatch:
    stats = summarize_diff(diff)
    applies_cleanly, checks = verify_patch(repo_root, diff)
    patch = VerifiedPatch(
        run_id=run_id,
        base_sha=get_base_sha(repo_root),
        diff=diff,
        files_changed=stats["files_changed"],
        lines_added=int(stats["lines_added"]),
        lines_removed=int(stats["lines_removed"]),
        applies_cleanly=applies_cleanly,
        checks=checks,
        attempts=1,
        context_files_read=context_files_read,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=0.0,
        sandbox_image="local-verifier:no-container",
        provenance={
            "verification": "local git apply check plus diff secret scan",
            "sandbox": "container sandbox deferred",
        },
    )
    db.add(patch)
    db.commit()
    db.refresh(patch)
    return patch


def apply_verified_patch(db: Session, patch: VerifiedPatch, repo_root: Path) -> VerifiedPatch:
    if patch.applied_at:
        return patch
    result = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=repo_root,
        input=patch.diff,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    patch.apply_output = redact_secrets((result.stdout + result.stderr).strip())
    if result.returncode != 0:
        db.add(patch)
        db.commit()
        raise RuntimeError(f"Patch apply failed: {patch.apply_output}")
    patch.applied_at = datetime.utcnow()
    db.add(patch)
    db.commit()
    db.refresh(patch)
    return patch


def _git_apply_check(repo_root: Path, diff: str) -> CommandCheck:
    started = datetime.utcnow()
    result = subprocess.run(
        ["git", "apply", "--check", "--whitespace=nowarn", "-"],
        cwd=repo_root,
        input=diff,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    output = (result.stdout + result.stderr).strip() or "patch applies cleanly"
    return CommandCheck(
        name="patch_applies",
        command="git apply --check --whitespace=nowarn -",
        exit_code=result.returncode,
        duration_ms=duration_ms,
        output_tail=output,
    )


def _secret_scan_check(diff: str) -> CommandCheck:
    exit_code = 1 if contains_secret(diff) else 0
    output = "diff secret scan passed" if exit_code == 0 else "diff contains likely secret"
    return CommandCheck(
        name="diff_secret_scan",
        command="internal secret scan",
        exit_code=exit_code,
        duration_ms=0,
        output_tail=output,
    )
