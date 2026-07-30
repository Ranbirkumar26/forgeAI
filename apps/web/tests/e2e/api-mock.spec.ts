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
            message: "Approve and apply verified patch.",
            payload: {},
            created_at: new Date().toISOString()
          }
        ],
        steps: [{ id: "step-1", run_id: "run-demo", agent: "planner", status: "completed", summary: "ok", token_input: 1, token_output: 1, payload: {}, started_at: new Date().toISOString(), completed_at: new Date().toISOString() }],
        approvals: [
          {
            id: "approval-1",
            run_id: "run-demo",
            action_type: "apply_patch",
            status: "pending",
            prompt: "Approve and apply verified patch.",
            risk_level: "medium",
            payload: {},
            created_at: new Date().toISOString(),
            resolved_at: null
          }
        ],
        artifacts: [],
        verified_patches: [
          {
            id: "patch-1",
            run_id: "run-demo",
            base_sha: "abc123",
            diff: "diff --git a/README.md b/README.md\n",
            files_changed: ["README.md"],
            lines_added: 2,
            lines_removed: 0,
            applies_cleanly: true,
            applied_at: null,
            apply_output: null,
            checks: [
              {
                name: "patch_applies",
                command: "git apply --check --whitespace=nowarn -",
                exit_code: 0,
                output_tail: "patch applies cleanly"
              }
            ],
            attempts: 1,
            context_files_read: [],
            tokens_in: 1,
            tokens_out: 1,
            cost_usd: 0,
            sandbox_image: "local-verifier:no-container",
            provenance: {}
          }
        ],
        llm_calls: []
      })
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /^Start$/i }).click();
  await expect(
    page.locator(".approval-panel").getByText("Approve and apply verified patch.", { exact: true })
  ).toBeVisible();
});
