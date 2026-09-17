const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('localVoiceApp', {
  backup: () => ipcRenderer.invoke('app:backup'),
  eraseData: () => ipcRenderer.invoke('app:erase-data'),
});
