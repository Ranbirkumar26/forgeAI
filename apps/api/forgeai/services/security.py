import re
from dataclasses import dataclass
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{8,})"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
]

SENSITIVE_NAME_PATTERNS = (
    re.compile(r"(^|/)\.env(\.|$|/)?", re.IGNORECASE),
    re.compile(r"(^|/)(id_rsa|id_dsa|id_ecdsa|id_ed25519)$", re.IGNORECASE),
    re.compile(r"\.(pem|p12|pfx|key|keystore|jks)$", re.IGNORECASE),
    re.compile(r"(credentials|secrets?|token|password).*\.(json|ya?ml|txt|env)$", re.IGNORECASE),
    re.compile(r"\.tfstate(\.backup)?$", re.IGNORECASE),
)

SUSPICIOUS_CONTENT_PATTERNS = [
    re.compile(
        r"ignore (?:all )?(?:previous|prior|above) (?:instructions|messages)",
        re.IGNORECASE,
    ),
    re.compile(r"reveal (?:the )?(?:system|developer) (?:prompt|message)", re.IGNORECASE),
    re.compile(r"print (?:the )?(?:contents of )?\.env", re.IGNORECASE),
    re.compile(r"disable (?:approval|safety|security) checks?", re.IGNORECASE),
    re.compile(r"exfiltrate|data exfiltration", re.IGNORECASE),
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


def contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def is_sensitive_path(path: Path | str) -> bool:
    normalized = str(path).replace("\\", "/")
    return any(pattern.search(normalized) for pattern in SENSITIVE_NAME_PATTERNS)


def detect_suspicious_content(file_path: str, content: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for pattern in SUSPICIOUS_CONTENT_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "file_path": file_path,
                        "line": line_number,
                        "pattern": pattern.pattern,
                        "preview": redact_secrets(line.strip())[:220],
                    }
                )
    return findings


def summarize_risk(tool_name: str, command: str | None = None) -> str:
    if tool_name in {"deploy", "git_push", "github_pr"}:
        return "high"
    if tool_name in {"file_write", "apply_patch", "shell_mutation", "browser_form"}:
        return "medium"
    if tool_name == "shell" and ApprovalPolicy().requires_approval(tool_name, command):
        return "medium"
    return "low"
