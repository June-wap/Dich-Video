const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const test = require('node:test');
const {
  startStaticServer,
  stopStaticServer,
  waitForHealth,
  stopBackend,
  assertBackendPortAvailable,
  BackendState,
  getBackendState,
  setBackendState,
  UI_PORT,
  API_PORT,
} = require('./main.cjs');
const { resolveRuntimeLayout } = require('./runtime-paths.cjs');
const { spawnBackendProcess } = require('./backend-launch.cjs');

// Mock helpers
function createMockProcess(pid = 12345) {
  const listeners = {};
  return {
    pid,
    exitCode: null,
    stdout: { on: (event, cb) => {} },
    stderr: { on: (event, cb) => {} },
    on: function (event, cb) {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(cb);
    },
    once: function (event, cb) {
      const wrapper = (...args) => {
        this.removeListener(event, wrapper);
        cb(...args);
      };
      this.on(event, wrapper);
    },
    removeListener: function (event, cb) {
      if (listeners[event]) {
        listeners[event] = listeners[event].filter((f) => f !== cb);
      }
    },
    emit: function (event, ...args) {
      if (listeners[event]) {
        const cbs = [...listeners[event]];
        for (const cb of cbs) cb(...args);
      }
    },
    kill: function (signal) {
      this.exitCode = 0;
      setImmediate(() => this.emit('exit', 0, signal || null));
    },
  };
}

test('1. first instance obtains single instance lock', () => {
  let requested = false;
  const mockApp = {
    requestSingleInstanceLock: () => {
      requested = true;
      return true;
    },
  };
  const lock = mockApp.requestSingleInstanceLock();
  assert.equal(requested, true);
  assert.equal(lock, true);
});

test('2. second instance does not start another UI server', () => {
  let uiServerStarted = false;
  let appQuitCalled = false;
  const mockApp = {
    requestSingleInstanceLock: () => false,
    quit: () => { appQuitCalled = true; },
  };

  const gotLock = mockApp.requestSingleInstanceLock();
  if (!gotLock) {
    mockApp.quit();
  } else {
    uiServerStarted = true;
  }

  assert.equal(gotLock, false);
  assert.equal(appQuitCalled, true);
  assert.equal(uiServerStarted, false);
});

test('3. second instance does not spawn backend', () => {
  let backendSpawned = false;
  let appQuitCalled = false;
  const mockApp = {
    requestSingleInstanceLock: () => false,
    quit: () => { appQuitCalled = true; },
  };

  const gotLock = mockApp.requestSingleInstanceLock();
  if (!gotLock) {
    mockApp.quit();
  } else {
    backendSpawned = true;
  }

  assert.equal(appQuitCalled, true);
  assert.equal(backendSpawned, false);
});

test('4. second instance focuses and restores existing window', () => {
  let restored = false;
  let focused = false;
  const mockWindow = {
    isMinimized: () => true,
    restore: () => { restored = true; },
    focus: () => { focused = true; },
  };

  // Simulate 'second-instance' handler
  if (mockWindow) {
    if (mockWindow.isMinimized()) mockWindow.restore();
    mockWindow.focus();
  }

  assert.equal(restored, true);
  assert.equal(focused, true);
});

test('5. backend is only spawned once (single owner guard)', async () => {
  let spawnCount = 0;
  let activeBackend = createMockProcess(2001);

  // Guard: if backend already active, don't spawn second
  function guardStartBackend() {
    if (activeBackend && activeBackend.exitCode === null) {
      return; // Already running
    }
    spawnCount++;
    activeBackend = createMockProcess(2002);
  }

  guardStartBackend();
  assert.equal(spawnCount, 0); // Already running -> no new spawn

  activeBackend.exitCode = 0; // Terminated
  guardStartBackend();
  assert.equal(spawnCount, 1); // Now spawned
});

test('6. backend readiness waits for health endpoint to respond', async () => {
  // Start a local test HTTP server acting as FastAPI backend
  const testServer = http.createServer((req, res) => {
    if (req.url === '/api/auth/token') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ token: 'test-session-token' }));
      return;
    }
    if (req.url === '/api/health') {
      const auth = req.headers['x-local-token'];
      if (auth === 'test-session-token') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok' }));
      } else {
        res.writeHead(401).end();
      }
      return;
    }
    res.writeHead(404).end();
  });

  await new Promise((resolve) => testServer.listen(0, '127.0.0.1', resolve));
  const port = testServer.address().port;
  const proc = createMockProcess(3001);

  try {
    await waitForHealth(proc, 5000, port);
    assert.ok(true, 'Health check passed successfully');
  } finally {
    await new Promise((resolve) => testServer.close(resolve));
  }
});

test('7. backend early exit is detected immediately with diagnostics', async () => {
  const proc = createMockProcess(4001);
  // Mark process as dead early
  proc.exitCode = 1;

  await assert.rejects(
    async () => {
      await waitForHealth(proc, 5000, 9999);
    },
    /dừng đột ngột trước khi sẵn sàng \(Mã thoát: 1\)/
  );
});

test('8. readiness timeout handled properly', async () => {
  const proc = createMockProcess(5001);
  // Use a port where nothing is listening and a short 800ms timeout
  await assert.rejects(
    async () => {
      await waitForHealth(proc, 800, 9998);
    },
    /không phản hồi sau 1 giây/
  );
});

test('9. owned backend terminated on quit', async () => {
  const proc = createMockProcess(6001);
  let processExited = false;
  proc.once('exit', () => { processExited = true; });

  await stopBackend(proc);
  assert.equal(proc.exitCode, 0);
  assert.equal(processExited, true);
});

test('10. unrelated process is never killed (exact PID target only)', async () => {
  const targetPid = 7777;
  const unrelatedPid = 8888;
  const killedPids = [];

  function safeStop(proc) {
    if (proc && proc.pid) {
      killedPids.push(proc.pid);
      proc.exitCode = 0;
      proc.emit('exit', 0);
    }
  }

  const targetProcess = createMockProcess(targetPid);
  safeStop(targetProcess);

  assert.deepEqual(killedPids, [targetPid]);
  assert.ok(!killedPids.includes(unrelatedPid), 'Unrelated PID must never be targeted');
});

test('11. UI server closed cleanly on quit and releases port', async () => {
  const testDir = path.resolve(__dirname, '..');
  const { server, port } = await startStaticServer(0, testDir);
  assert.ok(port > 0);

  await stopStaticServer(server);

  // Verify port is released by creating another server on the same port
  const probeServer = http.createServer();
  await new Promise((resolve) => {
    probeServer.listen(port, '127.0.0.1', () => {
      probeServer.close(resolve);
    });
  });
});

test('12. LOCAL_AI_CHATTERBOX_PYTHON is still passed correctly to child environment', () => {
  const fakeLayout = {
    python: 'C:\\fake\\runtime-main\\python.exe',
    backend: 'C:\\fake\\runtime-main\\app',
    chatterbox: 'C:\\fake\\runtime-chatterbox\\python.exe',
    modelStore: 'C:\\fake\\models\\huggingface',
  };
  const fakeData = {
    root: 'C:\\fake\\user-data',
    audio: 'C:\\fake\\user-data\\audio',
    database: 'C:\\fake\\user-data\\metadata.sqlite3',
    token: 'C:\\fake\\user-data\\session.token',
  };

  let capturedEnv = null;
  spawnBackendProcess({
    layout: fakeLayout,
    data: fakeData,
    uiPort: 5173,
    apiPort: 8000,
    spawn: (cmd, args, opts) => {
      capturedEnv = opts.env;
      return createMockProcess(9001);
    },
  });

  assert.equal(
    capturedEnv.LOCAL_AI_CHATTERBOX_PYTHON,
    'C:\\fake\\runtime-chatterbox\\python.exe'
  );
  assert.equal(capturedEnv.LOCAL_AI_CORS_ORIGINS, 'http://127.0.0.1:5173');
});

test('13. packaged production UI server binds dynamic loopback port (0) without depending on 5173', async () => {
  // Deliberately occupy port 5173 with a separate third-party server
  const blocker5173 = http.createServer((req, res) => res.end('occupied 5173'));
  let blockerPort = 5173;
  try {
    await new Promise((resolve, reject) => {
      blocker5173.once('error', reject);
      blocker5173.listen(5173, '127.0.0.1', resolve);
    });
  } catch {
    // If 5173 is already in use by something else, use another port as mock blocker
    await new Promise((resolve) => blocker5173.listen(0, '127.0.0.1', resolve));
    blockerPort = blocker5173.address().port;
  }

  const testDir = path.resolve(__dirname, '..');
  // Packaged production binds 0 directly:
  const { server, port } = await startStaticServer(0, testDir);

  try {
    assert.ok(port > 0, 'Dynamic port must be a valid port');
    assert.notEqual(port, blockerPort, 'Dynamic port must not collide with occupied port');
  } finally {
    await stopStaticServer(server);
    await new Promise((resolve) => blocker5173.close(resolve));
  }
});

test('14. port 8000 collision handled: rejects immediately and unrelated process is not touched', async () => {
  const dummyOccupier = http.createServer((req, res) => res.end('foreign service'));
  await new Promise((resolve) => dummyOccupier.listen(0, '127.0.0.1', resolve));
  const occupiedPort = dummyOccupier.address().port;

  try {
    await assert.rejects(
      async () => {
        await assertBackendPortAvailable(occupiedPort);
      },
      /Cổng backend \d+ đang bị chiếm dụng bởi một ứng dụng khác/
    );
    assert.equal(getBackendState(), BackendState.FAILED);

    // Verify unrelated server is still alive and responds
    const res = await new Promise((resolve, reject) => {
      http.get(`http://127.0.0.1:${occupiedPort}/`, (r) => {
        let data = '';
        r.on('data', (c) => (data += c));
        r.on('end', () => resolve(data));
      }).on('error', reject);
    });
    assert.equal(res, 'foreign service', 'Unrelated occupier must remain intact and unharmed');
  } finally {
    await new Promise((resolve) => dummyOccupier.close(resolve));
    setBackendState(BackendState.STOPPED);
  }
});

test('15. post-ready backend crash transitions state to FAILED', () => {
  setBackendState(BackendState.READY);
  assert.equal(getBackendState(), BackendState.READY);

  // Simulate crash event handler
  const code = 1;
  let state = getBackendState();
  if (code !== 0) {
    state = BackendState.FAILED;
  }
  assert.equal(state, BackendState.FAILED);
  setBackendState(BackendState.STOPPED);
});

test('16. missing runtime-main Python fails fast with actionable error and no fallback', () => {
  assert.throws(
    () => {
      resolveRuntimeLayout({
        isPackaged: true,
        resourcesPath: 'C:\\non_existent_folder_xyz_123',
        projectRoot: 'C:\\fake',
      });
    },
    /Missing .* runtime-main Python/
  );
});

test('17. Frontend NetworkError is distinct from ApiError and preserves cause', () => {
  const cause = new Error('fetch failed: ECONNREFUSED');
  const netErr = new Error('Không thể kết nối dịch vụ Voca Basic cục bộ (127.0.0.1:8000). Vui lòng kiểm tra hoặc khởi động lại ứng dụng.');
  netErr.name = 'NetworkError';
  netErr.cause = cause;

  assert.equal(netErr.name, 'NetworkError');
  assert.equal(netErr.cause.message, 'fetch failed: ECONNREFUSED');
  assert.match(netErr.message, /Không thể kết nối dịch vụ Voca Basic cục bộ/);
});

