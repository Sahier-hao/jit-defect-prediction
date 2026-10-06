import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: {
    baseURL: process.env.JIT_E2E_BASE_URL || "http://127.0.0.1:8765",
    browserName: "chromium",
    channel: process.env.JIT_BROWSER_CHANNEL || "msedge",
    trace: "retain-on-failure",
  },
});
