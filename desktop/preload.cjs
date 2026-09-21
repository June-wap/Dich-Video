const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('localVoiceApp', {
  backup: () => ipcRenderer.invoke('app:backup'),
  eraseData: () => ipcRenderer.invoke('app:erase-data'),
  getBackendStatus: () => ipcRenderer.invoke('app:get-backend-status'),
  onBackendStatus: (callback) => {
    if (typeof callback !== 'function') return () => {};
    const listener = (_event, data) => callback(data);
    ipcRenderer.on('backend:status-changed', listener);
    return () => ipcRenderer.removeListener('backend:status-changed', listener);
  },
});
