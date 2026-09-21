const assert = require('node:assert/strict');
const test = require('node:test');
const { DEV_FRONTEND_URL, resolveFrontendRuntime } = require('./frontend-runtime.cjs');

test('development frontend is served by Vite, never Electron static file serving', () => {
  const frontend = resolveFrontendRuntime({ isPackaged: false });

  assert.equal(frontend.url, DEV_FRONTEND_URL);
  assert.equal(frontend.serveStatic, false);
});

test('packaged frontend retains Electron static file serving', () => {
  const frontend = resolveFrontendRuntime({ isPackaged: true });

  assert.equal(frontend.serveStatic, true);
});
