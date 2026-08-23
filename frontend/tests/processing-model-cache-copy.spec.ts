import { expect, test } from "@playwright/test";

test("Processing explains where managed transcription models are kept", async ({ page }) => {
  await page.goto("/?e2e=1");
  await page.getByRole("button", { name: "Processing" }).click();
  await expect(
    page.getByRole("heading", { name: "Transcribe recordings." }),
  ).toBeVisible();

  await expect(
    page.getByText(/Scholion keeps installed models in its private model cache/),
  ).toBeVisible();
});
