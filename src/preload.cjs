const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("iooh", {
	state: () => ipcRenderer.invoke("state"),
	chooseDirectory: () => ipcRenderer.invoke("choose-directory"),
	cover: (character) => ipcRenderer.invoke("cover", character),
	addRole: (name) => ipcRenderer.invoke("add-role", name),
	moveMod: (name, character) => ipcRenderer.invoke("move-mod", name, character),
	toggleMod: (character, mod, enabled) =>
		ipcRenderer.invoke("toggle-mod", character, mod, enabled),
	configure: (key, edits) => ipcRenderer.invoke("configure", key, edits),
	restore: () => ipcRenderer.invoke("restore"),
	presetCreate: (name, description) =>
		ipcRenderer.invoke("preset-create", name, description),
	presetUpdate: (id, name, description, snapshot) =>
		ipcRenderer.invoke("preset-update", id, name, description, snapshot),
	presetDelete: (id) => ipcRenderer.invoke("preset-delete", id),
	presetApply: (id) => ipcRenderer.invoke("preset-apply", id),
});
