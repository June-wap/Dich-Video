const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { spawnBackendProcess } = require('./backend-launch.cjs');
const { resolveRuntimeLayout } = require('./runtime-paths.cjs');

test('spawns backend with the resolved packaged Chatterbox interpreter', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-app-'));
  const resourcesPath = path.join(root, 'resources');
  const packages = path.join(root, 'ai-packages');
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(resourcesPath, { recursive: true });
  fs.mkdirSync(path.join(packages, 'runtime-main', 'app'), { recursive: true });
  fs.mkdirSync(path.join(packages, 'runtime-chatterbox'), { recursive: true });
  fs.mkdirSync(path.join(packages, 'models', 'huggingface', 'hub'), { recursive: true });
  fs.closeSync(fs.openSync(path.join(packages, 'runtime-main', 'python.exe'), 'w'));
  fs.closeSync(fs.openSync(path.join(packages, 'runtime-chatterbox', 'python.exe'), 'w'));
  const layout = resolveRuntimeLayout({ isPackaged: true, resourcesPath, projectRoot: 'ignored' });
  const data = {
    root: path.join(root, 'user-data'),
    audio: path.join(root, 'user-data', 'audio'),
    database: path.join(root, 'user-data', 'data', 'metadata.sqlite3'),
    token: path.join(root, 'user-data', 'runtime', 'session.token'),
  };
  let received;
  const spawned = { marker: 'child' };

  const result = spawnBackendProcess({
    layout,
    data,
    uiPort: 5173,
    apiPort: 8000,
    baseEnvironment: { HF_TOKEN: 'must-not-leak' },
    spawn: (command, args, options) => {
      received = { command, args, options };
      return spawned;
    },
  });

  assert.equal(result, spawned);
  assert.equal(received.command, layout.python);
  assert.deepEqual(received.args, ['-m', 'backend.main']);
  assert.equal(received.options.env.LOCAL_AI_CHATTERBOX_PYTHON, layout.chatterbox);
  assert.equal(received.options.env.HF_TOKEN, undefined);
});
