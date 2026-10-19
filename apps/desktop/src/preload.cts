const { contextBridge, ipcRenderer } = require('electron') as typeof import('electron');

contextBridge.exposeInMainWorld('openspriteDesktop', Object.freeze({
  getAppInfo: () => ipcRenderer.invoke('opensprite:app-info'),
}));
