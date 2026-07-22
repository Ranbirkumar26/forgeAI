import { expect, test } from "@playwright/test";

test("dashboard can submit a run against a mocked API", async ({ page }) => {
  await page.route("**/api/runs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "run-demo",
        task: "Demo task",
        repo_path: null,
        status: "awaiting_approval",
        model_profile: "balanced",
        metadata_json: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        completed_at: null,
        events: [
          {
            id: "event-1",
            run_id: "run-demo",
            sequence: 1,
            level: "warning",
            agent: "approval-gate",
            event_type: "approval_requested",
            message: "Approve the prepared code patch before ForgeAI proceeds.",
            payload: {},
            created_at: new Date().toISOString()
          }
        ],
        steps: [{ id: "step-1", run_id: "run-demo", agent: "planner", status: "completed", summary: "ok", token_input: 1, token_output: 1, payload: {}, started_at: new Date().toISOString(), completed_at: new Date().toISOString() }],
        approvals: [
          {
            id: "approval-1",
            run_id: "run-demo",
            action_type: "file_write",
            status: "pending",
            prompt: "Approve patch.",
            risk_level: "medium",
            payload: {},
            created_at: new Date().toISOString(),
            resolved_at: null
          }
        ],
        artifacts: []
      })
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Start Run/i }).click();
  await expect(page.getByText("Approve patch.")).toBeVisible();
});

