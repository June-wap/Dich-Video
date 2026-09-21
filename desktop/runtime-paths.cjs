const fs = require('node:fs');
const path = require('node:path');

function requireFile(candidate, label) {
  if (!fs.statSync(candidate, { throwIfNoEntry: false })?.isFile()) {
    throw new Error(`Missing ${label}: ${candidate}`);
  }
  return candidate;
}

function resolveRuntimeRoot({ isPackaged, resourcesPath, projectRoot }) {
  if (!isPackaged) {
    return path.join(projectRoot, 'release', 'staged-runtime');
  }

  // 1. Check for ai-package-config.json in resourcesPath or next to executable
  const configCandidates = [
    path.join(resourcesPath, 'ai-package-config.json'),
    path.join(resourcesPath, '..', 'ai-package-config.json'),
  ];
  for (const configPath of configCandidates) {
    if (fs.statSync(configPath, { throwIfNoEntry: false })?.isFile()) {
      try {
        const raw = fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, '');
        const parsed = JSON.parse(raw);
        if (parsed.ai_packages_dir) {
          const resolved = path.isAbsolute(parsed.ai_packages_dir)
            ? parsed.ai_packages_dir
            : path.resolve(path.dirname(configPath), parsed.ai_packages_dir);
          if (fs.statSync(resolved, { throwIfNoEntry: false })?.isDirectory()) {
            return resolved;
          }
        }
      } catch {
        // Fall through on malformed config
      }
    }
  }

  // 2. Check for sibling 'ai-packages' folder next to the app executable
  const siblingAiPackages = path.join(resourcesPath, '..', 'ai-packages');
  if (fs.statSync(siblingAiPackages, { throwIfNoEntry: false })?.isDirectory()) {
    return siblingAiPackages;
  }

  // 3. Fall back to standard resources/runtime (bundled or legacy layout)
  return path.join(resourcesPath, 'runtime');
}

function resolveRuntimeLayout({ isPackaged, resourcesPath, projectRoot }) {
  const root = resolveRuntimeRoot({ isPackaged, resourcesPath, projectRoot });
  const main = path.join(root, 'runtime-main');
  const chatterbox = path.join(root, 'runtime-chatterbox', 'python.exe');
  
  // Backend can be in resources/backend (Core App) or runtime-main/app (bundled package)
  let backend = path.join(main, 'app');
  if (isPackaged) {
    const coreBackend = path.join(resourcesPath, 'backend');
    if (fs.statSync(coreBackend, { throwIfNoEntry: false })?.isDirectory()) {
      backend = coreBackend;
    }
  }

  const layout = {
    root,
    python: path.join(main, 'python.exe'),
    backend,
    chatterbox,
    modelStore: path.join(root, 'models', 'huggingface'),
    development: !isPackaged,
  };

  const mode = isPackaged ? 'packaged' : 'development staged';
  requireFile(layout.python, `${mode} runtime-main Python (kiểm tra thư mục runtime-main/python.exe)`);
  requireFile(layout.chatterbox, `${mode} runtime-chatterbox Python (kiểm tra thư mục runtime-chatterbox/python.exe)`);
  if (!fs.statSync(layout.backend, { throwIfNoEntry: false })?.isDirectory()) {
    throw new Error(`Missing ${mode} backend: ${layout.backend}`);
  }
  if (!fs.statSync(path.join(layout.modelStore, 'hub'), { throwIfNoEntry: false })?.isDirectory()) {
    throw new Error(`Missing ${mode} model store: ${layout.modelStore} (kiểm tra thư mục models/huggingface/hub)`);
  }
  return layout;
}

module.exports = { resolveRuntimeLayout, resolveRuntimeRoot };

