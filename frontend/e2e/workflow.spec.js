import { test, expect } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

test("empty workspace, demo, real training, detail, filters, upload and reload", async ({
  page,
}) => {
  const errors = [];
  await page.emulateMedia({ reducedMotion: "reduce" });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Start with your commit history" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Load synthetic demo" })
    .first()
    .click();
  await expect(
    page.getByLabel("Select dataset").locator("option:checked"),
  ).toHaveText("Synthetic review example");
  await page.getByRole("button", { name: "Train baseline" }).click();
  await expect(
    page.getByRole("table", { name: "Commit risk list" }),
  ).toBeVisible();
  await expect(
    page.getByText("Recall @ 20% effort", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Inspect demo-/ })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Why this score?" }),
  ).toBeVisible();
  await expect(
    page.getByText("Exact linear contributions", { exact: true }),
  ).toBeVisible();
  await fs.mkdir(path.resolve("../runtime/evidence"), { recursive: true });
  await page.screenshot({
    path: path.resolve("../runtime/evidence/review-desktop.png"),
    fullPage: true,
  });
  await page.getByLabel("Search commit ID").fill("does-not-exist");
  await expect(page.getByText("No commits match these filters.")).toBeVisible();
  await page.getByLabel("Search commit ID").fill("");
  await expect(
    page.getByRole("table", { name: "Commit risk list" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("table", { name: "Commit risk list" }),
  ).toBeVisible();
  const beforeModels = await page.request.get("/api/models");
  expect((await beforeModels.json()).length).toBe(1);

  await page.getByRole("button", { name: "Import CSV", exact: true }).click();
  await page.getByLabel("Dataset name").fill("Browser upload");
  await page
    .getByLabel("Data source / provenance")
    .fill("Synthetic browser test");
  await page
    .getByLabel("Label policy")
    .fill("Synthetic labels; software smoke only");
  await page.getByLabel("This is synthetic / demo data").check();
  const sample = await page.request.get("/api/demo.csv");
  await page.getByLabel("Feature CSV", { exact: true }).setInputFiles({
    name: "sample.csv",
    mimeType: "text/csv",
    buffer: await sample.body(),
  });
  await page
    .getByRole("button", { name: "Import dataset", exact: true })
    .click();
  await expect(
    page.getByText("Train the first model for this dataset."),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Why this score?" }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "Train baseline" }).click();
  await expect(
    page.getByRole("table", { name: "Commit risk list" }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  const inspectBounds = await page
    .getByRole("button", { name: /Inspect demo-/ })
    .first()
    .boundingBox();
  expect(inspectBounds.x).toBeGreaterThanOrEqual(0);
  expect(inspectBounds.x + inspectBounds.width).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: path.resolve("../runtime/evidence/review-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("invalid upload preserves the existing dataset and displays the error", async ({
  page,
}) => {
  const demo = await (await page.request.post("/api/demo")).json();
  const existingModels = await (
    await page.request.get(`/api/models?dataset_id=${demo.id}`)
  ).json();
  if (!existingModels.length)
    await page.request.post("/api/models/train", {
      data: { dataset_id: demo.id },
    });
  const before = await (await page.request.get("/api/datasets")).json();
  await page.goto("/");
  await page.getByRole("button", { name: "Import CSV", exact: true }).click();
  await page.getByLabel("Dataset name").fill("Invalid import");
  await page.getByLabel("Data source / provenance").fill("Test");
  await page.getByLabel("Label policy").fill("Test");
  await page.getByLabel("Feature CSV", { exact: true }).setInputFiles({
    name: "bad.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "commit_id,committed_at,label\na,2025-01-01T00:00:00Z,0\n",
    ),
  });
  await page
    .getByRole("button", { name: "Import dataset", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("Missing columns");
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(await (await page.request.get("/api/datasets")).json()).toEqual(
    before,
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("table", { name: "Commit risk list" }),
  ).toBeVisible();
});

test("a delayed previous dataset response cannot replace the current model", async ({
  page,
}) => {
  const demo = await (await page.request.post("/api/demo")).json();
  let demoModels = await (
    await page.request.get(`/api/models?dataset_id=${demo.id}`)
  ).json();
  if (!demoModels.length) {
    await page.request.post("/api/models/train", {
      data: { dataset_id: demo.id },
    });
    demoModels = await (
      await page.request.get(`/api/models?dataset_id=${demo.id}`)
    ).json();
  }
  const sample = await (await page.request.get("/api/demo.csv")).body();
  const alternate = await (
    await page.request.post("/api/datasets/import", {
      multipart: {
        file: { name: "race.csv", mimeType: "text/csv", buffer: sample },
        name: "Selection race fixture",
        provenance: "Synthetic race test",
        label_policy: "Synthetic only",
        is_demo: "true",
      },
    })
  ).json();
  const alternateModel = await (
    await page.request.post("/api/models/train", {
      data: { dataset_id: alternate.id },
    })
  ).json();
  await page.goto("/");
  await expect(page.getByLabel("Select model")).toHaveValue(alternateModel.id);
  await page.getByLabel("Select dataset").selectOption(demo.id);
  await expect(page.getByLabel("Select model")).toHaveValue(demoModels[0].id);
  let signalStarted;
  const started = new Promise((resolve) => {
    signalStarted = resolve;
  });
  await page.route(
    (url) =>
      url.pathname === "/api/models" &&
      url.searchParams.get("dataset_id") === alternate.id,
    async (route) => {
      const response = await route.fetch();
      signalStarted();
      await delay(500);
      await route.fulfill({ response });
    },
  );
  const finished = page.waitForResponse((response) =>
    response.url().includes(`dataset_id=${alternate.id}`),
  );
  await page.getByLabel("Select dataset").selectOption(alternate.id);
  await started;
  await page.getByLabel("Select dataset").selectOption(demo.id);
  await expect(page.getByLabel("Select model")).toHaveValue(demoModels[0].id);
  await (await finished).finished();
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await expect(page.getByLabel("Select dataset")).toHaveValue(demo.id);
  await expect(page.getByLabel("Select model")).toHaveValue(demoModels[0].id);
  await expect(
    page.getByRole("table", { name: "Commit risk list" }),
  ).toBeVisible();
});
