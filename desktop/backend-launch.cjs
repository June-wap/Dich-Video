const childProcess = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function spawnBackendProcess({ layout, data, uiPort, apiPort, spawn = childProcess.spawn, baseEnvironment = process.env }) {
  const { python, backend: sourceRoot, modelStore, chatterbox } = layout;
  const moduleRoot = fs.existsSync(path.join(sourceRoot, 'backend'))
    ? sourceRoot
    : path.dirname(sourceRoot);
  const environment = {
    ...baseEnvironment,
    LOCAL_AI_APP_DATA_DIR: data.root,
    LOCAL_AI_DATA_ROOT: data.root,
    LOCAL_AI_OUTPUT_DIR: data.audio,
    LOCAL_AI_DATABASE_PATH: data.database,
    LOCAL_AI_REFERENCE_AUDIO_DIR: path.join(data.root, 'voice-profiles', 'references'),
    LOCAL_AI_TEMP_DIR: path.join(data.root, 'temp'),
    LOCAL_AI_TOKEN_PATH: data.token,
    LOCAL_AI_CHATTERBOX_PYTHON: chatterbox,
    LOCAL_AI_REQUIRE_LOCAL_TOKEN: '1',
    LOCAL_AI_WARM_UP_ON_START: '1',
    LOCAL_AI_CORS_ORIGINS: `http://127.0.0.1:${uiPort}`,
    LOCAL_AI_HOST: '127.0.0.1', LOCAL_AI_PORT: String(apiPort),
    PYTHONPATH: `${moduleRoot}${path.delimiter}${sourceRoot}`,
    HF_HOME: modelStore,
    HF_HUB_CACHE: path.join(modelStore, 'hub'),
    HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1',
  };
  delete environment.HF_TOKEN;
  return spawn(python, ['-m', 'backend.main'], {
    cwd: moduleRoot,
    env: environment,
    windowsHide: true,
    stdio: 'pipe',
  });
}

module.exports = { spawnBackendProcess };
