import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180000,
  expect: { timeout: 20000 },
  use: {
    baseURL: process.env.KOMBOE_WEB || "http://127.0.0.1:4173",
    viewport: { width: 1280, height: 800 },
  },
  reporter: [["list"]],
});
