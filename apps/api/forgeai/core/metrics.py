from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from starlette.responses import Response

RUNS_CREATED = Counter("forgeai_runs_created_total", "Total ForgeAI task runs created")
APPROVALS_RESOLVED = Counter(
    "forgeai_approvals_resolved_total",
    "Total approval decisions resolved",
    ["decision"],
)
ACTIVE_RUNS = Gauge("forgeai_active_runs", "Runs currently marked running or awaiting approval")


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
