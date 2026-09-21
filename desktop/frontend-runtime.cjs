const DEV_FRONTEND_URL = 'http://127.0.0.1:5173';
const PACKAGED_FRONTEND_URL = 'http://127.0.0.1:5173';

function resolveFrontendRuntime({ isPackaged }) {
  return {
    // In development Vite owns this URL and transforms /src/*.tsx. Packaged
    // builds use Electron's static server on the same loopback URL.
    url: isPackaged ? PACKAGED_FRONTEND_URL : DEV_FRONTEND_URL,
    serveStatic: isPackaged,
  };
}

module.exports = { DEV_FRONTEND_URL, resolveFrontendRuntime };
