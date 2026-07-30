import { expect, test } from "@playwright/test";

test("dashboard renders the ForgeAI control plane", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("ForgeAI")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Start$/i })).toBeVisible();
  await expect(page.getByText("Run Trace")).toBeVisible();
  await expect(page.getByText("Approval", { exact: true })).toBeVisible();
});
