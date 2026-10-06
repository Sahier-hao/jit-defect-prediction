// Manage a direct Python child: shell process-tree teardown can hang on Windows.
import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const port = await new Promise((resolve, reject) => {
  const socket = net.createServer();
  socket.once("error", reject);
  socket.listen(0, "127.0.0.1", () => {
    const selected = socket.address().port;
    socket.close(() => resolve(selected));
  });
});
const baseURL = `http://127.0.0.1:${port}`;
const environment = {
  ...process.env,
  JIT_E2E_BASE_URL: baseURL,
  JIT_DATA_DIR: path.resolve(`../runtime/e2e-${process.pid}`),
  PYTHONIOENCODING: "utf-8",
};
delete environment.FORCE_COLOR;
delete environment.NO_COLOR;
let launchError;
const server = spawn(
  "python",
  [
    "-m",
    "uvicorn",
    "jit_defect.api:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
    "--log-level",
    "warning",
  ],
  {
    cwd: "..",
    env: environment,
    stdio: ["ignore", "ignore", "inherit"],
    shell: false,
  },
);
server.once("error", (error) => {
  launchError = error;
});
try {
  let ready = false;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (launchError) throw launchError;
    if (server.exitCode !== null)
      throw new Error(`Test API exited with code ${server.exitCode}`);
    try {
      const response = await fetch(`${baseURL}/api/health`, {
        signal: AbortSignal.timeout(1000),
      });
      if (response.ok && (await response.json()).status === "ok") {
        ready = true;
        break;
      }
    } catch {
      /* Poll the owned server until ready. */
    }
    await delay(200);
  }
  if (!ready)
    throw new Error("Test API did not become ready within 30 seconds");
  const tests = spawn(
    process.execPath,
    [
      path.resolve("node_modules/@playwright/test/cli.js"),
      "test",
      ...process.argv.slice(2),
    ],
    { env: environment, stdio: "inherit", shell: false },
  );
  process.exitCode = await new Promise((resolve, reject) => {
    tests.once("error", reject);
    tests.once("exit", (code) => resolve(code ?? 1));
  });
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  await new Promise((resolve) => {
    if (server.exitCode !== null || server.signalCode !== null)
      return resolve();
    server.once("exit", resolve);
    server.kill();
    setTimeout(resolve, 3000).unref();
  });
}
