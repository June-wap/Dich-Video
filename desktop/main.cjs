/* Electron production host for Local AI Voice Studio.
 *
 * It owns every local process: an internal static UI server and the FastAPI
 * backend.  The renderer never receives Node privileges.  Runtime payloads
 * are staged by scripts/stage_release_runtime.ps1 before packaging.
 */
const { app, BrowserWindow, dialog, ipcMain, Menu } = require('electron');
const childProcess = require('node:child_process');
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');

const UI_PORT = 5173;
const API_PORT = 8000;
let backend;
let uiServer;
let mainWindow;

function packagedRoot() {
  return app.isPackaged ? process.resourcesPath : path.resolve(__dirname, '..');
}

function runtimePath(...segments) {
  return path.join(packagedRoot(), 'runtime', ...segments);
}

function appDataPaths() {
  const root = path.join(app.getPath('userData'), 'backend-data');
  return { root, audio: path.join(root, 'audio'), database: path.join(root, 'data', 'metadata.sqlite3'), token: path.join(root, 'runtime', 'session.token') };
}

async function ensureUserData() {
  const data = appDataPaths();
  await Promise.all([fsp.mkdir(data.audio, { recursive: true }), fsp.mkdir(path.dirname(data.database), { recursive: true }), fsp.mkdir(path.dirname(data.token), { recursive: true })]);
  return data;
}

function startStaticServer() {
  const root = path.join(packagedRoot(), 'frontend');
  return new Promise((resolve, reject) => {
    uiServer = http.createServer(async (request, response) => {
      const raw = decodeURIComponent((request.url || '/').split('?')[0]);
      const requested = raw === '/' ? 'index.html' : raw.replace(/^\/+/, '');
      const candidate = path.resolve(root, requested);
      if (!candidate.startsWith(`${path.resolve(root)}${path.sep}`) && candidate !== path.join(root, 'index.html')) {
        response.writeHead(403).end(); return;
      }
      try {
        const file = await fsp.readFile(candidate);
        response.writeHead(200, { 'Cache-Control': 'no-store', 'Content-Type': candidate.endsWith('.js') ? 'text/javascript' : candidate.endsWith('.css') ? 'text/css' : candidate.endsWith('.svg') ? 'image/svg+xml' : 'text/html; charset=utf-8' });
        response.end(file);
      } catch {
        // BrowserRouter routes resolve to the app shell, not a 404.
        response.writeHead(200, { 'Cache-Control': 'no-store', 'Content-Type': 'text/html; charset=utf-8' });
        response.end(await fsp.readFile(path.join(root, 'index.html')));
      }
    });
    uiServer.once('error', reject);
    uiServer.listen(UI_PORT, '127.0.0.1', () => resolve());
  });
}

async function commandExists(command, args = ['-version']) {
  return new Promise((resolve) => {
    const probe = childProcess.spawn(command, args, { windowsHide: true, stdio: 'ignore' });
    probe.once('error', () => resolve(false));
    probe.once('exit', (code) => resolve(code === 0));
  });
}

async function waitForHealth(timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${API_PORT}/api/health`);
      if (response.ok) return;
    } catch { /* process may still be loading */ }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error('Backend did not become healthy within 45 seconds.');
}

async function startBackend() {
  const data = await ensureUserData();
  const python = runtimePath('python', 'python.exe');
  const ffmpegDir = runtimePath('ffmpeg');
  const sourceRoot = runtimePath('backend');
  if (!fs.existsSync(python) || !fs.existsSync(sourceRoot)) throw new Error('Runtime Python/backend chưa được stage vào installer.');
  if (!await commandExists(path.join(ffmpegDir, 'ffmpeg.exe'))) throw new Error('FFmpeg trong runtime bị thiếu hoặc không thể chạy.');
  const environment = {
    ...process.env,
    PYTHONPATH: `${sourceRoot}${path.delimiter}${path.join(sourceRoot, 'prototype')}`,
    PATH: `${ffmpegDir}${path.delimiter}${process.env.PATH || ''}`,
    LOCAL_AI_APP_DATA_DIR: data.root,
    LOCAL_AI_OUTPUT_DIR: data.audio,
    LOCAL_AI_DATABASE_PATH: data.database,
    LOCAL_AI_TOKEN_PATH: data.token,
    LOCAL_AI_REQUIRE_LOCAL_TOKEN: '1',
    LOCAL_AI_WARM_UP_ON_START: '1',
    LOCAL_AI_CORS_ORIGINS: `http://127.0.0.1:${UI_PORT}`,
    LOCAL_AI_HOST: '127.0.0.1', LOCAL_AI_PORT: String(API_PORT),
    HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1',
  };
  backend = childProcess.spawn(python, ['-m', 'backend.main'], { cwd: sourceRoot, env: environment, windowsHide: true, stdio: 'pipe' });
  let output = '';
  backend.stderr.on('data', (chunk) => { output = (output + chunk).slice(-4000); });
  backend.once('error', (error) => { output = `${output}\n${error.message}`; });
  try { await waitForHealth(); } catch (error) { await stopBackend(); throw new Error(`${error.message}\n${output}`); }
}

async function stopBackend() {
  if (!backend || backend.exitCode !== null) return;
  const processToStop = backend;
  backend = undefined;
  processToStop.kill();
  await Promise.race([new Promise((resolve) => processToStop.once('exit', resolve)), new Promise((resolve) => setTimeout(resolve, 5000))]);
  if (processToStop.exitCode === null) childProcess.spawn('taskkill', ['/pid', String(processToStop.pid), '/t', '/f'], { windowsHide: true });
}

async function backupUserData() {
  const target = await dialog.showOpenDialog(mainWindow, { title: 'Chọn thư mục sao lưu', properties: ['openDirectory', 'createDirectory'] });
  if (target.canceled || !target.filePaths[0]) return false;
  const destination = path.join(target.filePaths[0], `Local-AI-Voice-Studio-backup-${new Date().toISOString().replace(/[:.]/g, '-')}`);
  await fsp.cp(appDataPaths().root, destination, { recursive: true, force: false });
  await dialog.showMessageBox(mainWindow, { type: 'info', message: `Đã sao lưu dữ liệu vào:\n${destination}` });
  return true;
}

async function eraseUserData() {
  const confirmation = await dialog.showMessageBox(mainWindow, { type: 'warning', buttons: ['Hủy', 'Xóa toàn bộ'], defaultId: 0, cancelId: 0, message: 'Xóa toàn bộ audio, profile giọng, lịch sử và cấu hình cục bộ? Hành động này không thể hoàn tác.' });
  if (confirmation.response !== 1) return false;
  await stopBackend();
  await fsp.rm(appDataPaths().root, { recursive: true, force: true });
  app.relaunch(); app.exit(0); return true;
}

function createWindow() {
  mainWindow = new BrowserWindow({ width: 1440, height: 920, minWidth: 1024, minHeight: 700, show: false, webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, sandbox: true, nodeIntegration: false } });
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.loadURL(`http://127.0.0.1:${UI_PORT}`);
}

app.whenReady().then(async () => {
  ipcMain.handle('app:backup', backupUserData);
  ipcMain.handle('app:erase-data', eraseUserData);
  try { await startStaticServer(); await startBackend(); createWindow(); }
  catch (error) { await dialog.showMessageBox({ type: 'error', title: 'Không thể khởi động Local AI Voice Studio', message: String(error.message || error) }); app.quit(); return; }
  Menu.setApplicationMenu(Menu.buildFromTemplate([{ label: 'Dữ liệu', submenu: [{ label: 'Sao lưu dữ liệu...', click: () => void backupUserData() }, { label: 'Xóa toàn bộ dữ liệu cục bộ...', click: () => void eraseUserData() }] }]));
});
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { void stopBackend(); if (uiServer) uiServer.close(); });
