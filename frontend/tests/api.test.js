import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { request } from "../src/api.js";

let server, base;
before(async () => {
  server = createServer((req, res) => {
    res.setHeader("Content-Type", "application/json");
    if (req.url === "/ok") return res.end(JSON.stringify({ ready: true }));
    if (req.url === "/invalid") {
      res.statusCode = 422;
      return res.end(JSON.stringify({ detail: "Row 2: invalid nf" }));
    }
    if (req.url === "/fields") {
      res.statusCode = 422;
      return res.end(
        JSON.stringify({
          detail: [{ loc: ["body", "provenance"], msg: "Field required" }],
        }),
      );
    }
    res.statusCode = 503;
    res.end("Unavailable");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => new Promise((resolve) => server.close(resolve)));

test("reads a successful API response", async () => {
  assert.deepEqual(await request(`${base}/ok`), { ready: true });
});
test("preserves readable validation error from API", async () => {
  await assert.rejects(request(`${base}/invalid`), /Row 2: invalid nf/);
});
test("formats framework field errors for the user", async () => {
  await assert.rejects(request(`${base}/fields`), /provenance.*Field required/);
});
test("reports non-JSON service failure without a parsing error", async () => {
  await assert.rejects(request(`${base}/unavailable`), /503/);
});
