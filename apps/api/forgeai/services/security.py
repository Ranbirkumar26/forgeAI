import re
from dataclasses import dataclass

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{8,})"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]

SAFE_SHELL_PREFIXES = (
    "pytest",
    "python -m pytest",
    "npm test",
    "pnpm test",
    "pnpm lint",
    "pnpm build",
    "playwright test",
)

MUTATING_TOOLS = {
    "file_write",
    "apply_patch",
    "shell_mutation",
    "git_push",
    "github_pr",
    "deploy",
    "browser_form",
}


@dataclass(frozen=True)
class ApprovalPolicy:
    mode: str = "required"

    def requires_approval(self, tool_name: str, command: str | None = None) -> bool:
        if self.mode == "disabled":
            return False
        if tool_name in MUTATING_TOOLS:
            return True
        if tool_name == "shell":
            command_text = (command or "").strip()
            return not command_text.startswith(SAFE_SHELL_PREFIXES)
        return False


def redact_secrets(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda m: m.group(0).replace(m.group(m.lastindex), "[REDACTED]"), redacted
        )
    return redacted


def summarize_risk(tool_name: str, command: str | None = None) -> str:
    if tool_name in {"deploy", "git_push", "github_pr"}:
        return "high"
    if tool_name in {"file_write", "apply_patch", "shell_mutation", "browser_form"}:
        return "medium"
    if tool_name == "shell" and ApprovalPolicy().requires_approval(tool_name, command):
        return "medium"
    return "low"
