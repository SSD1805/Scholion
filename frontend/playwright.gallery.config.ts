import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./gallery",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:4173/?e2e=1",
    reducedMotion: "reduce",
  },
  projects: [
    {
      name: "chromium-theme-gallery",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173/?e2e=1",
    reuseExistingServer: false,
  },
});
