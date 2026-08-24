import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

async function openUpdates(
  page: import("@playwright/test").Page,
  querySuffix = "",
) {
  await page.goto(`/?e2e=1${querySuffix}`);
  await page.getByRole("button", { name: "Updates" }).click();
  await expect(
    page.getByRole("heading", { name: "Keep Scholion trustworthy." }),
  ).toBeVisible();
}

test("manual update check explains privacy boundaries and stays accessible", async ({ page }) => {
  await openUpdates(page);

  await expect(page.getByRole("heading", { name: "Never checked" })).toBeVisible();
  await expect(page.getByText(/does not send an installation ID/)).toBeVisible();
  await expect(page.getByText(/IP address and request time/)).toBeVisible();
  await expect(page.getByText(/Existing local work remains available/)).toBeVisible();

  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(page.getByRole("heading", { name: "Checking for updates" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Checking…" })).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Up to date" })).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});

test("trusted update can be downloaded verified and staged without claiming installation", async ({
  page,
}) => {
  await openUpdates(page, "&update-mode=available");

  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(
    page.getByRole("heading", { name: "Trusted update available" }),
  ).toBeVisible();
  await expect(page.getByText("0.2.0", { exact: true })).toBeVisible();
  await expect(page.getByText(/46.0 MB/)).toBeVisible();

  await page.getByRole("button", { name: "Download and verify" }).click();
  await expect(
    page.getByRole("heading", { name: "Verifying update package" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Verifying…" })).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Trusted update staged" })).toBeVisible();
  await expect(page.getByText(/Installation is deliberately separate/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Install/ })).toHaveCount(0);
});

test("source build without production update key remains offline and explicit", async ({ page }) => {
  await openUpdates(page, "&update-mode=off");

  await expect(
    page.getByRole("heading", { name: "Update checking is off" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Check for updates" })).toBeDisabled();
  await expect(page.getByText(/does not contain a production update trust key/)).toBeVisible();
});

test("update failure is bounded and does not expose implementation details", async ({ page }) => {
  await openUpdates(page, "&update-mode=failure");

  await page.getByRole("button", { name: "Check for updates" }).click();
  await expect(
    page.getByRole("heading", { name: "Update check could not finish" }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText(
    "Scholion could not complete the trusted update request",
  );
  await expect(page.getByText(/traceback|home\/|cache\/updates|signature bytes/i)).toHaveCount(0);
});
