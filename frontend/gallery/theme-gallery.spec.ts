import { mkdir } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { THEMES } from "../src/themes";

const OUTPUT_DIR = path.resolve(process.cwd(), "../docs/images/themes");

test.beforeAll(async () => {
  await mkdir(OUTPUT_DIR, { recursive: true });
});

for (const theme of THEMES) {
  test(`capture ${theme.label} theme`, async ({ page }) => {
    await page.goto("/?e2e=1");
    await page.getByLabel("Theme").selectOption(theme.id);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme.id);

    await page.getByRole("button", { name: "Research" }).click();
    const panel = page.getByRole("region", { name: "What are you looking for?" });
    await expect(panel).toBeVisible();
    await panel.getByText("Search options", { exact: true }).click();
    await expect(panel.getByLabel("Search by")).toBeVisible();

    await page.screenshot({
      path: path.join(OUTPUT_DIR, `${theme.id}.png`),
      fullPage: true,
      animations: "disabled",
      caret: "hide",
    });
  });
}
