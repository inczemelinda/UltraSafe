import { defineConfig, devices } from "playwright/test";

const baseURL = process.env.DEMO_BASE_URL ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: ".",
  timeout: 120_000,
  expect: {
    timeout: 10_000
  },
  outputDir: "test-results/demo",
  reporter: [["list"]],
  use: {
    baseURL,
    browserName: "chromium",
    launchOptions: {
      slowMo: Number(process.env.DEMO_SLOW_MO_MS ?? 0)
    },
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 960 }
  },
  webServer: {
    command: "npm run dev -- --port 5173",
    env: {
      VITE_USE_MOCK_API: "true",
      VITE_BACKEND_PRICING: "false"
    },
    reuseExistingServer: true,
    timeout: 120_000,
    url: baseURL
  },
  projects: [
    {
      name: "demo",
      use: {
        ...devices["Desktop Chrome"],
        headless: false,
        viewport: { width: 1440, height: 960 }
      }
    },
    {
      name: "demo-recording",
      use: {
        ...devices["Desktop Chrome"],
        headless: false,
        viewport: { width: 1440, height: 960 },
        video: {
          mode: "on",
          size: { width: 1440, height: 960 }
        }
      }
    }
  ]
});
