/* Electron production host for Voca Basic.
 *
 * It owns every local process: an internal static UI server and the FastAPI
 * backend. The renderer never receives Node privileges. Runtime payloads
 * are staged by scripts/stage_release_runtime.ps1 before packaging.
 */
const { app, BrowserWindow, dialog, ipcMain, Menu } = require('electron');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { resolveFrontendRuntime } = require('./frontend-runtime.cjs');
const { spawnBackendProcess } = require('./backend-launch.cjs');
const { resolveRuntimeLayout } = require('./runtime-paths.cjs');

const UI_PORT = 5173;
const API_PORT = 8000;

const BackendState = {
  STOPPED: 'STOPPED',
  STARTING: 'STARTING',
  READY: 'READY',
  FAILED: 'FAILED',
};

let backend = null;
let backendState = BackendState.STOPPED;
let backendOutputBuffer = '';
let uiServer = null;
let uiServerSockets = new Set();
let actualUiPort = UI_PORT;
let mainWindow = null;
let isAppQuitting = false;

// ============================================================================
// SINGLE INSTANCE LOCK
// ============================================================================
// Establish single-instance lock BEFORE binding port 5173, spawning backend,
// or creating the main window.
const gotTheLock = app ? app.requestSingleInstanceLock() : true;

if (!gotTheLock) {
  console.info('[SingleInstance] Second instance detected. Quitting immediately.');
  app.quit();
} else if (app) {
  app.on('second-instance', () => {
    console.info('[SingleInstance] Second instance attempted to launch. Focusing main window.');
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// ============================================================================
// PATH RESOLUTION
// ============================================================================
function packagedRoot() {
  return app?.isPackaged ? process.resourcesPath : path.resolve(__dirname, '..');
}

function appDataPaths() {
  const localAppData = process.env.LOCALAPPDATA;
  const root = localAppData
    ? path.join(localAppData, 'Voca Basic')
    : (app ? app.getPath('userData') : path.join(process.cwd(), '.user-data'));
  return {
    root,
    audio: path.join(root, 'audio'),
    database: path.join(root, 'data', 'metadata.sqlite3'),
    token: path.join(root, 'runtime', 'session.token'),
  };
}

async function ensureUserData() {
  const data = appDataPaths();
  await Promise.all([
    fsp.mkdir(data.audio, { recursive: true }),
    fsp.mkdir(path.dirname(data.database), { recursive: true }),
    fsp.mkdir(path.dirname(data.token), { recursive: true }),
  ]);
  return data;
}

// ============================================================================
// STATIC UI SERVER (PORT 5173 WITH RESILIENT DYNAMIC FALLBACK)
// ============================================================================
function createStaticHttpServer(rootDirectory, socketsSet) {
  const server = http.createServer(async (request, response) => {
    const raw = decodeURIComponent((request.url || '/').split('?')[0]);
    const requested = raw === '/' ? 'index.html' : raw.replace(/^\/+/, '');
    const candidate = path.resolve(rootDirectory, requested);
    if (
      !candidate.startsWith(`${path.resolve(rootDirectory)}${path.sep}`) &&
      candidate !== path.join(rootDirectory, 'index.html')
    ) {
      response.writeHead(403).end();
      return;
    }
    try {
      const file = await fsp.readFile(candidate);
      response.writeHead(200, {
        'Cache-Control': 'no-store',
        'Content-Type': candidate.endsWith('.js')
          ? 'text/javascript'
          : candidate.endsWith('.css')
          ? 'text/css'
          : candidate.endsWith('.svg')
          ? 'image/svg+xml'
          : 'text/html; charset=utf-8',
      });
      response.end(file);
    } catch {
      // BrowserRouter routes resolve to the app shell, not a 404.
      response.writeHead(200, {
        'Cache-Control': 'no-store',
        'Content-Type': 'text/html; charset=utf-8',
      });
      response.end(await fsp.readFile(path.join(rootDirectory, 'index.html')));
    }
  });

  server.on('connection', (socket) => {
    socketsSet.add(socket);
    socket.once('close', () => socketsSet.delete(socket));
  });

  return server;
}

function startStaticServer(port = 0, rootDir = null) {
  const root = rootDir || path.join(packagedRoot(), 'frontend');
  const sockets = new Set();

  return new Promise((resolve, reject) => {
    const server = createStaticHttpServer(root, sockets);

    const onError = (err) => {
      server.removeListener('error', onError);
      reject(err);
    };

    server.once('error', onError);
    server.listen(port, '127.0.0.1', () => {
      server.removeListener('error', onError);
      uiServer = server;
      uiServerSockets = sockets;
      actualUiPort = server.address().port;
      console.info(`[UI Server] Đang phục vụ giao diện tại http://127.0.0.1:${actualUiPort}`);
      resolve({ server, port: actualUiPort });
    });
  });
}

async function stopStaticServer(serverToClose = uiServer, socketsToDestroy = uiServerSockets) {
  if (!serverToClose) return;
  if (serverToClose === uiServer) {
    uiServer = null;
  }

  if (socketsToDestroy) {
    for (const socket of socketsToDestroy) {
      try {
        socket.destroy();
      } catch {}
    }
    socketsToDestroy.clear();
  }

  if (typeof serverToClose.closeAllConnections === 'function') {
    try {
      serverToClose.closeAllConnections();
    } catch {}
  }

  await new Promise((resolve) => {
    serverToClose.close(() => resolve());
  });
}

// ============================================================================
// PORT 8000 COLLISION AUDIT
// ============================================================================
async function isPortInUse(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const tester = http.createServer();
    tester.once('error', (err) => {
      resolve(err.code === 'EADDRINUSE');
    });
    tester.once('listening', () => {
      tester.close(() => resolve(false));
    });
    tester.listen(port, host);
  });
}

async function assertBackendPortAvailable(port = API_PORT) {
  const inUse = await isPortInUse(port);
  if (!inUse) return;

  backendState = BackendState.FAILED;
  throw new Error(
    `Cổng backend ${port} đang bị chiếm dụng bởi một ứng dụng khác trên máy tính.\n` +
    `Vui lòng đóng ứng dụng đang sử dụng cổng ${port} để Voca Basic có thể khởi chạy.`
  );
}

// ============================================================================
// BACKEND READINESS & DIAGNOSTICS
// ============================================================================
async function waitForHealth(targetProcess = backend, timeoutMs = 45000, port = API_PORT) {
  const deadline = Date.now() + timeoutMs;
  let token = null;

  while (Date.now() < deadline) {
    if (targetProcess?.exitCode !== null && targetProcess?.exitCode !== undefined) {
      backendState = BackendState.FAILED;
      const exitCode = targetProcess.exitCode;
      const recentOutput = backendOutputBuffer.slice(-2500);
      throw new Error(
        `Tiến trình AI backend cục bộ đã dừng đột ngột trước khi sẵn sàng (Mã thoát: ${exitCode}).\n\n` +
        `Nhật ký chẩn đoán:\n${recentOutput || '(Không có nhật ký stderr)'}`
      );
    }

    try {
      if (!token) {
        try {
          const tokenResponse = await fetch(`http://127.0.0.1:${port}/api/auth/token`);
          if (tokenResponse.ok) {
            token = (await tokenResponse.json()).token;
          }
        } catch {
          // Backend chưa sẵn sàng nhận kết nối
        }
      }

      const headers = token ? { 'X-Local-Token': token } : {};
      const response = await fetch(`http://127.0.0.1:${port}/api/health`, { headers });
      if (response.ok) {
        backendState = BackendState.READY;
        return;
      }
    } catch {
      // Đang trong quá trình nạp tiến trình / models
    }

    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  backendState = BackendState.FAILED;
  const recentOutput = backendOutputBuffer.slice(-2500);
  throw new Error(
    `Dịch vụ AI backend cục bộ không phản hồi sau ${Math.round(timeoutMs / 1000)} giây.\n\n` +
    `Nhật ký chẩn đoán:\n${recentOutput || '(Không có nhật ký)'}`
  );
}

// ============================================================================
// BACKEND SPAWN & LIFECYCLE (EXACT CHILD PROCESS OWNERSHIP)
// ============================================================================
async function startBackend({ customLayout = null, customData = null, uiPort = actualUiPort, apiPort = API_PORT } = {}) {
  // Chỉ Electron mới sở hữu tối đa 1 tiến trình con backend
  if (backend && backend.exitCode === null) {
    console.warn('[startBackend] Backend process already exists and is active.');
    return;
  }

  backendState = BackendState.STARTING;
  await assertBackendPortAvailable(apiPort);

  const data = customData || (await ensureUserData());
  const layout =
    customLayout ||
    resolveRuntimeLayout({
      isPackaged: app?.isPackaged ?? false,
      resourcesPath: process.resourcesPath,
      projectRoot: path.resolve(__dirname, '..'),
    });

  backendOutputBuffer = '';
  backend = spawnBackendProcess({ layout, data, uiPort, apiPort });

  const currentBackend = backend;

  currentBackend.stdout?.on('data', (chunk) => {
    backendOutputBuffer = (backendOutputBuffer + chunk).slice(-8000);
    if (!app?.isPackaged) console.info(`[backend stdout] ${chunk}`);
  });

  currentBackend.stderr?.on('data', (chunk) => {
    backendOutputBuffer = (backendOutputBuffer + chunk).slice(-8000);
    if (!app?.isPackaged) console.info(`[backend stderr] ${chunk}`);
  });

  currentBackend.once('error', (error) => {
    backendOutputBuffer = `${backendOutputBuffer}\n${error.message}`;
  });

  // Giám sát tiến trình sau khi đã chạy: cảnh báo nếu backend bị crash đột ngột
  currentBackend.on('exit', (code, signal) => {
    if (!isAppQuitting && currentBackend === backend) {
      backendState = BackendState.FAILED;
      console.error(`[backend exit] Backend exited unexpectedly with code ${code}, signal ${signal}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        try {
          mainWindow.webContents.send('backend:status-changed', {
            state: BackendState.FAILED,
            code,
            signal,
          });
        } catch {}
        dialog.showMessageBox(mainWindow, {
          type: 'error',
          title: 'Lỗi Dịch Vụ AI Cục Bộ',
          message:
            `Dịch vụ AI backend cục bộ đã dừng đột ngột (Mã thoát: ${code}).\n\n` +
            `Vui lòng đóng và mở lại ứng dụng Voca Basic để tiếp tục sử dụng.`,
        });
      }
    }
  });

  try {
    await waitForHealth(currentBackend, 45000, apiPort);
  } catch (error) {
    backendState = BackendState.FAILED;
    await stopBackend(currentBackend);
    throw error;
  }
}

async function stopBackend(processToStop = backend) {
  if (!processToStop || (processToStop.exitCode !== null && processToStop.exitCode !== undefined)) {
    if (processToStop === backend) {
      backend = null;
      backendState = BackendState.STOPPED;
    }
    return;
  }

  if (processToStop === backend) {
    backend = null;
    backendState = BackendState.STOPPED;
  }

  const pid = processToStop.pid;
  if (!pid) return;

  // Trên Windows, kết hợp processToStop.kill() và taskkill /pid /t /f
  // để vừa cập nhật handle Node.js vừa diệt sạch toàn bộ cây tiến trình con
  if (process.platform === 'win32') {
    try {
      if (typeof processToStop.kill === 'function') {
        processToStop.kill();
      }
    } catch {}
    try {
      childProcess.spawnSync('taskkill', ['/pid', String(pid), '/t', '/f'], { windowsHide: true });
    } catch {}
  } else {
    try {
      processToStop.kill('SIGTERM');
    } catch {}
  }

  await Promise.race([
    new Promise((resolve) => processToStop.once('exit', resolve)),
    new Promise((resolve) => setTimeout(resolve, 3000)),
  ]);
}

// ============================================================================
// USER DATA ACTIONS
// ============================================================================
async function backupUserData() {
  const target = await dialog.showOpenDialog(mainWindow, {
    title: 'Chọn thư mục sao lưu',
    properties: ['openDirectory', 'createDirectory'],
  });
  if (target.canceled || !target.filePaths[0]) return false;
  const destination = path.join(
    target.filePaths[0],
    `Voca-Basic-backup-${new Date().toISOString().replace(/[:.]/g, '-')}`
  );
  await fsp.cp(appDataPaths().root, destination, { recursive: true, force: false });
  await dialog.showMessageBox(mainWindow, {
    type: 'info',
    message: `Đã sao lưu dữ liệu vào:\n${destination}`,
  });
  return true;
}

async function eraseUserData() {
  const confirmation = await dialog.showMessageBox(mainWindow, {
    type: 'warning',
    buttons: ['Hủy', 'Xóa toàn bộ'],
    defaultId: 0,
    cancelId: 0,
    message:
      'Xóa toàn bộ audio, profile giọng, lịch sử và cấu hình cục bộ? ' +
      'Hành động này không thể hoàn tác.',
  });
  if (confirmation.response !== 1) return false;
  await stopBackend();
  await fsp.rm(appDataPaths().root, { recursive: true, force: true });
  app.relaunch();
  app.exit(0);
  return true;
}

// ============================================================================
// WINDOW CREATION
// ============================================================================
function createWindow() {
  const frontendConfig = resolveFrontendRuntime({ isPackaged: app.isPackaged });
  // Dùng actualUiPort nếu đang chạy static server được đóng gói
  const frontendUrl = frontendConfig.serveStatic
    ? `http://127.0.0.1:${actualUiPort}`
    : frontendConfig.url;

  const iconPath = path.join(__dirname, 'icon.png');
  mainWindow = new BrowserWindow({
    title: 'Voca Basic',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.loadURL(frontendUrl);
}

// ============================================================================
// ELECTRON APP LIFECYCLE
// ============================================================================
if (gotTheLock && app) {
  app.whenReady().then(async () => {
    ipcMain.handle('app:backup', backupUserData);
    ipcMain.handle('app:erase-data', eraseUserData);
    ipcMain.handle('app:get-backend-status', () => ({
      state: backendState,
      port: API_PORT,
      uiPort: actualUiPort,
    }));

    try {
      const frontendRuntime = resolveFrontendRuntime({ isPackaged: app.isPackaged });
      if (frontendRuntime.serveStatic) {
        // Trong packaged production: luôn bind trực tiếp 127.0.0.1:0 (cổng động)
        // Cổng 5173 chỉ dành riêng cho development / Vite dev server
        await startStaticServer(0);
      }
      await startBackend({ uiPort: actualUiPort, apiPort: API_PORT });
      createWindow();
    } catch (error) {
      await dialog.showMessageBox({
        type: 'error',
        title: 'Không thể khởi động Voca Basic',
        message: String(error.message || error),
      });
      app.quit();
      return;
    }

    Menu.setApplicationMenu(
      Menu.buildFromTemplate([
        {
          label: 'Dữ liệu',
          submenu: [
            { label: 'Sao lưu dữ liệu...', click: () => void backupUserData() },
            { label: 'Xóa toàn bộ dữ liệu cục bộ...', click: () => void eraseUserData() },
          ],
        },
      ])
    );
  });

  app.on('window-all-closed', () => {
    app.quit();
  });

  // Async shutdown pattern: hoãn quit để dừng triệt để backend process tree và UI server
  app.on('before-quit', (event) => {
    if (!isAppQuitting) {
      event.preventDefault();
      isAppQuitting = true;
      (async () => {
        try {
          await stopBackend();
          await stopStaticServer();
        } catch (err) {
          console.error('[before-quit error]', err);
        } finally {
          app.quit();
        }
      })();
    }
  });
}

// Export for unit tests
module.exports = {
  startStaticServer,
  stopStaticServer,
  startBackend,
  stopBackend,
  waitForHealth,
  assertBackendPortAvailable,
  isPortInUse,
  UI_PORT,
  API_PORT,
  BackendState,
  getBackendState: () => backendState,
  setBackendState: (s) => { backendState = s; },
};
