import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow, dialog, ipcMain } from "electron";
import {
	applyPreset,
	configure,
	coverPath,
	createPreset,
	moveMod,
	restore,
	scan,
	toggleMod,
} from "./core.js";

const appDir = path.dirname(fileURLToPath(import.meta.url));
let settingsPath;
let settings;

function save() {
	fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
	fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
}

function root() {
	if (!settings.modsPath || !fs.existsSync(settings.modsPath))
		throw new Error("请选择有效的 Mods 目录");
	return settings.modsPath;
}

function state() {
	const data =
		settings.modsPath && fs.existsSync(settings.modsPath)
			? scan(settings.modsPath, settings.roles)
			: { characters: [], loose: [] };
	return {
		...data,
		modsPath: settings.modsPath,
		key: settings.key,
		presets: settings.presets,
		activePresetId: settings.activePresetId,
	};
}

function result(handler) {
	return async (_event, ...args) => {
		try {
			return { success: true, data: await handler(...args) };
		} catch (error) {
			return { success: false, error: error.message };
		}
	};
}

app.whenReady().then(() => {
	settingsPath = path.join(app.getPath("userData"), "settings.json");
	try {
		settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
	} catch {
		settings = {};
	}
	settings.presets ??= [];
	settings.roles ??= [];
	settings.key ??= "VK_NUMPAD2";

	ipcMain.handle("state", result(state));
	ipcMain.handle(
		"choose-directory",
		result(async () => {
			const { canceled, filePaths } = await dialog.showOpenDialog({
				properties: ["openDirectory"],
				defaultPath: settings.modsPath || app.getPath("home"),
			});
			if (!canceled) {
				settings.modsPath = filePaths[0];
				settings.activePresetId = null;
				save();
			}
			return state();
		}),
	);
	ipcMain.handle(
		"cover",
		result((character) => coverPath(character)?.toString() || null),
	);
	ipcMain.handle(
		"add-role",
		result((name) => {
			if (
				typeof name !== "string" ||
				!name.trim() ||
				/[\\/:*?"<>|]/.test(name) ||
				[".", ".."].includes(name)
			)
				throw new Error("角色名称无效");
			const role = name.trim();
			if (
				state().characters.some((character) => character.name === role) ||
				fs.existsSync(path.join(root(), role))
			)
				throw new Error("角色已存在");
			fs.mkdirSync(path.join(root(), role));
			settings.roles.push(role);
			save();
			return state();
		}),
	);
	ipcMain.handle(
		"move-mod",
		result((name, character) => {
			moveMod(root(), name, character);
			settings.activePresetId = null;
			save();
			return state();
		}),
	);
	ipcMain.handle(
		"toggle-mod",
		result((character, mod, enabled) => {
			toggleMod(root(), character, mod, enabled);
			settings.activePresetId = null;
			save();
			configure(root(), settings.key, [], settings.roles);
			return state();
		}),
	);
	ipcMain.handle(
		"configure",
		result((key, edits) => {
			if (!/^(?:VK_[A-Z0-9_]+|[a-z0-9])$/i.test(key))
				throw new Error("开关键无效");
			settings.key = key;
			save();
			const count = configure(root(), key, edits, settings.roles);
			return { count, state: state() };
		}),
	);
	ipcMain.handle(
		"restore",
		result(() => ({ count: restore(root()), state: state() })),
	);
	ipcMain.handle(
		"preset-create",
		result((name, description) => {
			createPreset(settings, name, description, state().characters);
			save();
			return state();
		}),
	);
	ipcMain.handle(
		"preset-update",
		result((id, name, description, snapshot = false) => {
			const preset = settings.presets.find((item) => item.id === id);
			if (!preset) throw new Error("预设不存在");
			if (
				!name?.trim() ||
				settings.presets.some(
					(item) => item.id !== id && item.name === name.trim(),
				)
			)
				throw new Error("预设名称为空或已存在");
			preset.name = name.trim();
			preset.description = description.trim();
			if (snapshot)
				preset.mods = state().characters.flatMap((character) =>
					character.mods
						.filter((mod) => mod.enabled)
						.map((mod) => ({ character: character.name, mod: mod.name })),
				);
			save();
			return state();
		}),
	);
	ipcMain.handle(
		"preset-delete",
		result((id) => {
			const index = settings.presets.findIndex((item) => item.id === id);
			if (index === -1) throw new Error("预设不存在");
			settings.presets.splice(index, 1);
			if (settings.activePresetId === id) settings.activePresetId = null;
			save();
			return state();
		}),
	);
	ipcMain.handle(
		"preset-apply",
		result((id) => {
			const preset =
				id === "all-off"
					? { mods: [] }
					: settings.presets.find((item) => item.id === id);
			if (!preset) throw new Error("预设不存在");
			const changed = applyPreset(root(), preset, state().characters);
			configure(root(), settings.key, [], settings.roles);
			settings.activePresetId = id;
			save();
			return { changed, state: state() };
		}),
	);

	const window = new BrowserWindow({
		width: 1280,
		height: 820,
		minWidth: 920,
		minHeight: 620,
		icon: path.join(appDir, "../icon.ico"),
		webPreferences: {
			preload: path.join(appDir, "preload.cjs"),
			contextIsolation: true,
			nodeIntegration: false,
		},
	});
	window.loadFile(path.join(appDir, "../index.html"));
	window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
});

app.on("window-all-closed", () => {
	app.quit();
});
