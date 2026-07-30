from typing import Any, TypedDict


class ForgeState(TypedDict, total=False):
    run_id: str
    task: str
    repo_path: str | None
    model_profile: str
    plan: list[str]
    retrieved_chunks: list[dict[str, Any]]
    verified_patch_id: str
    halted: bool
    summary: str
