const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { resolveRuntimeLayout } = require('./runtime-paths.cjs');

function createRuntimeLayout(root) {
  fs.mkdirSync(path.join(root, 'runtime-main', 'app'), { recursive: true });
  fs.mkdirSync(path.join(root, 'runtime-chatterbox'), { recursive: true });
  fs.mkdirSync(path.join(root, 'models', 'huggingface', 'hub'), { recursive: true });
  fs.closeSync(fs.openSync(path.join(root, 'runtime-main', 'python.exe'), 'w'));
  fs.closeSync(fs.openSync(path.join(root, 'runtime-chatterbox', 'python.exe'), 'w'));
}

test('packaged layout uses resources runtime and rejects missing payload', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-runtime-'));
  const runtime = path.join(root, 'runtime');
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  createRuntimeLayout(runtime);
  const layout = resolveRuntimeLayout({ isPackaged: true, resourcesPath: root, projectRoot: 'ignored' });
  assert.equal(layout.python, path.join(runtime, 'runtime-main', 'python.exe'));
  assert.equal(layout.backend, path.join(runtime, 'runtime-main', 'app'));
  assert.equal(layout.modelStore, path.join(runtime, 'models', 'huggingface'));
  assert.equal(layout.development, false);
  fs.rmSync(path.join(runtime, 'runtime-chatterbox', 'python.exe'));
  assert.throws(() => resolveRuntimeLayout({ isPackaged: true, resourcesPath: root, projectRoot: 'ignored' }), /runtime-chatterbox/);
});

test('development layout uses the absolute CP8.3 staged runtime, never cwd or obsolete python/', (t) => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-project-'));
  t.after(() => fs.rmSync(projectRoot, { recursive: true, force: true }));
  const stagedRuntime = path.join(projectRoot, 'release', 'staged-runtime');
  createRuntimeLayout(stagedRuntime);

  const layout = resolveRuntimeLayout({
    isPackaged: false,
    resourcesPath: 'ignored',
    projectRoot,
  });

  assert.equal(layout.root, stagedRuntime);
  assert.equal(layout.python, path.join(stagedRuntime, 'runtime-main', 'python.exe'));
  assert.equal(layout.chatterbox, path.join(stagedRuntime, 'runtime-chatterbox', 'python.exe'));
  assert.equal(layout.backend, path.join(stagedRuntime, 'runtime-main', 'app'));
  assert.equal(layout.modelStore, path.join(stagedRuntime, 'models', 'huggingface'));
  assert.equal(layout.development, true);
  assert.notEqual(layout.python, path.join(stagedRuntime, 'python', 'python.exe'));
});

test('packaged layout discovers sibling ai-packages folder', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-app-'));
  const resourcesPath = path.join(root, 'resources');
  const aiPackages = path.join(root, 'ai-packages');
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(resourcesPath, { recursive: true });
  createRuntimeLayout(aiPackages);

  const layout = resolveRuntimeLayout({ isPackaged: true, resourcesPath, projectRoot: 'ignored' });
  assert.equal(layout.root, aiPackages);
  assert.equal(layout.python, path.join(aiPackages, 'runtime-main', 'python.exe'));
  assert.equal(layout.chatterbox, path.join(aiPackages, 'runtime-chatterbox', 'python.exe'));
});

test('packaged layout discovers external packages via ai-package-config.json', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-app-'));
  const externalDir = fs.mkdtempSync(path.join(os.tmpdir(), 'voca-external-'));
  const resourcesPath = path.join(root, 'resources');
  t.after(() => {
    fs.rmSync(root, { recursive: true, force: true });
    fs.rmSync(externalDir, { recursive: true, force: true });
  });
  fs.mkdirSync(resourcesPath, { recursive: true });
  createRuntimeLayout(externalDir);
  fs.writeFileSync(
    path.join(resourcesPath, 'ai-package-config.json'),
    JSON.stringify({ ai_packages_dir: externalDir }),
    'utf8'
  );

  const layout = resolveRuntimeLayout({ isPackaged: true, resourcesPath, projectRoot: 'ignored' });
  assert.equal(layout.root, externalDir);
  assert.equal(layout.python, path.join(externalDir, 'runtime-main', 'python.exe'));
});

