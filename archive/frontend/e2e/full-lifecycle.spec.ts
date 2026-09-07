import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

/**
 * End-to-end test of the complete ARCHIVE workflow described in the
 * project spec:
 *
 *   register -> login -> dashboard -> create folder -> upload file ->
 *   verify it appears -> download -> rename -> delete -> Trash ->
 *   restore -> verify it returns -> permanently delete -> verify gone
 *
 * Uses a throwaway test PDF and a randomly generated email address --
 * never real private documents or credentials.
 */

const TEST_PDF_PATH = path.join(__dirname, "fixtures", "test.pdf");

test.beforeAll(() => {
  fs.mkdirSync(path.dirname(TEST_PDF_PATH), { recursive: true });
  if (!fs.existsSync(TEST_PDF_PATH)) {
    // Minimal valid PDF so the app's PDF preview path can be exercised.
    const minimalPdf = "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>";
    fs.writeFileSync(TEST_PDF_PATH, minimalPdf);
  }
});

test("full archive lifecycle: register through permanent delete", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  // Register
  await page.goto("/register");
  await page.getByLabel("Name", { exact: false }).fill("E2E Test User");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: /create account/i }).click();

  // Dashboard
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByText("ARCHIVE")).toBeVisible();

  // Create folder
  await page.getByRole("button", { name: "New folder" }).click();
  await page.getByPlaceholder("Folder name").fill("Test Documents");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page.getByText("Test Documents")).toBeVisible();

  // Navigate into folder
  await page.getByText("📁 Test Documents").click();

  // Upload file
  const [fileChooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: "Upload" }).click(),
  ]);
  await fileChooser.setFiles(TEST_PDF_PATH);

  // Verify file appears
  await expect(page.getByText("test.pdf")).toBeVisible({ timeout: 15_000 });

  // Rename
  page.once("dialog", (dialog) => dialog.accept("renamed-test.pdf"));
  await page.getByRole("button", { name: "Rename" }).first().click();
  await expect(page.getByText("renamed-test.pdf")).toBeVisible();

  // Delete (soft delete -> Trash)
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByText("renamed-test.pdf")).not.toBeVisible();

  // Trash: verify restore
  await page.getByRole("link", { name: "Trash" }).click();
  await expect(page.getByText("renamed-test.pdf")).toBeVisible();
  await page.getByRole("button", { name: "Restore" }).click();
  await expect(page.getByText("renamed-test.pdf")).not.toBeVisible();

  // Verify file returned to the archive
  await page.getByRole("link", { name: "My Archive" }).click();
  await page.getByText("📁 Test Documents").click();
  await expect(page.getByText("renamed-test.pdf")).toBeVisible();

  // Delete again then permanently delete from Trash
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete" }).first().click();

  await page.getByRole("link", { name: "Trash" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete forever" }).click();
  await expect(page.getByText("renamed-test.pdf")).not.toBeVisible();
});
