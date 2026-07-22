from sqlalchemy.orm import Session

from forgeai.db.tables import MemoryRecord


def remember_run_summary(db: Session, run_id: str, task: str, summary: str) -> MemoryRecord:
    record = MemoryRecord(
        scope="project",
        key=f"run:{run_id}:summary",
        value=f"Task: {task}\nSummary: {summary}",
        confidence=0.92,
        source_run_id=run_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
