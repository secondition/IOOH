let data = { characters: [], loose: [], presets: [], key: "VK_NUMPAD2" };
let page = "mods";
let selectedCharacter = null;
let expandedPreset = null;
let editingPreset = null;
let deletingPreset = null;
let search = "";
let populatedOnly = false;
let capture = null;
let busy = false;
const edits = new Map();
const covers = new Map();
const content = document.querySelector("#content");
const feedback = document.querySelector("#feedback");

function escapeHtml(value) {
	return String(value ?? "").replace(
		/[&<>"']/g,
		(char) =>
			({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
				char
			],
	);
}

function notify(message, error = false) {
	feedback.textContent = message;
	feedback.classList.toggle("error", error);
	clearTimeout(notify.timer);
	notify.timer = setTimeout(() => {
		feedback.textContent = "";
	}, 5000);
}

async function request(task) {
	if (busy) return null;
	busy = true;
	try {
		const response = await task();
		if (!response.success) throw new Error(response.error);
		return response.data;
	} catch (error) {
		notify(error.message, true);
		return null;
	} finally {
		busy = false;
	}
}

function accept(state) {
	if (!state) return;
	data = state;
	render();
}

function render() {
	document.querySelector("#path-label").textContent =
		data.modsPath || "尚未选择 Mods 目录";
	document.querySelector("#global-key").textContent = capture?.global
		? "请按下目标键 · Esc 取消"
		: data.key;
	for (const button of document.querySelectorAll(".nav"))
		button.classList.toggle("active", button.dataset.page === page);
	document.querySelector("#page-title").textContent =
		document.querySelector(".nav.active span").textContent;
	if (page === "presets") renderPresets();
	else renderMods();
}

function renderMods() {
	if (selectedCharacter) {
		const character = data.characters.find(
			(item) => item.name === selectedCharacter,
		);
		if (!character) {
			selectedCharacter = null;
			renderMods();
			return;
		}
		content.innerHTML = `<button class="back" data-action="back">← 返回模组列表</button><div class="page-head"><div><h1>${escapeHtml(character.name)}</h1><p class="subtitle">${character.mods.filter((mod) => mod.enabled).length} 个已启用 · 共 ${character.mods.length} 个 Mod</p></div></div><div class="mod-list">${character.mods.length ? character.mods.map((mod) => `<section class="mod-row ${mod.enabled ? "enabled" : ""}"><div><div class="mod-name">${escapeHtml(mod.name)}</div><div class="mod-status">${mod.enabled ? "已启用" : "已禁用"} · ${mod.files.length} 个 INI · ${mod.bindings.length} 个热键</div></div><div class="mod-actions"><button class="toggle ${mod.enabled ? "on" : ""}" role="switch" aria-label="${escapeHtml(mod.name)}" aria-checked="${mod.enabled}" data-action="toggle" data-mod="${escapeHtml(mod.name)}"></button></div>${!character.other && mod.bindings.length ? `<div class="bindings">${mod.bindings.map((binding) => `<div class="binding"><span title="${escapeHtml(binding.file)}">${escapeHtml(binding.description)}</span><button title="点击后按下目标键" data-action="capture" data-file="${escapeHtml(binding.file)}" data-section="${escapeHtml(binding.section)}">${escapeHtml(edits.get(`${binding.file}\u0000${binding.section}`) || binding.key)}</button></div>`).join("")}</div>` : ""}</section>`).join("") : `<div class="empty">暂无 Mod</div>`}</div>`;
		return;
	}
	const other = data.characters.filter((character) => character.other);
	const roles = data.characters.filter((character) => !character.other);
	const visible = roles.filter(
		(character) =>
			(!populatedOnly || character.mods.length) &&
			character.name.toLowerCase().includes(search.toLowerCase()),
	);
	const cards = (characters) =>
		`<div class="grid">${characters.map((character) => `<button class="character-card${character.other ? "" : " portrait"}" data-action="character" data-character="${escapeHtml(character.name)}"><div class="card-image" data-cover="${escapeHtml(character.name)}">${escapeHtml(character.name[0])}</div><div class="card-name">${escapeHtml(character.name)}<span class="card-count">${character.mods.filter((mod) => mod.enabled).length}/${character.mods.length} 个 Mod</span></div></button>`).join("")}</div>`;
	const loosePanel = data.loose.length
		? `<section class="panel"><h2 class="panel-title">待归类的 Mod · ${data.loose.length}</h2>${data.loose.map((mod) => `<div class="inline"><strong>${escapeHtml(mod.name)}</strong><select aria-label="${escapeHtml(mod.name)}的目标分类" data-loose="${escapeHtml(mod.name)}"><option value="">选择分类</option>${data.characters.map((character) => `<option value="${escapeHtml(character.name)}">${escapeHtml(character.name)}</option>`).join("")}</select><button class="secondary" data-action="move" data-loose="${escapeHtml(mod.name)}">归类</button></div>`).join("")}</section>`
		: "";
	content.innerHTML = `<div class="page-head"><div><h1>模组列表</h1><p class="subtitle">${data.characters.reduce((sum, character) => sum + character.mods.length, data.loose.length)} 个 Mod</p></div></div><section class="category-section"><div class="page-head"><h2 class="section-title">其他模组</h2></div>${loosePanel}${cards(other)}</section><section class="category-section"><div class="page-head"><h2 class="section-title">角色列表</h2><div class="inline role-filters"><label class="checkbox"><input type="checkbox" id="populated-only" ${populatedOnly ? "checked" : ""} />仅显示有 Mod 的角色</label><input id="search" class="search" aria-label="搜索角色" placeholder="搜索角色…" value="${escapeHtml(search)}" /></div></div><form id="add-role" class="inline add-role"><input class="field" name="name" placeholder="新建角色分类" required /><button class="secondary">添加角色</button></form>${visible.length ? cards(visible) : '<div class="empty">暂无符合条件的角色</div>'}</section>`;
	for (const element of content.querySelectorAll("[data-cover]")) {
		const name = element.dataset.cover;
		if (!covers.has(name)) covers.set(name, window.iooh.cover(name));
		covers.get(name).then((response) => {
			if (!response.success || !response.data || !element.isConnected) return;
			const image = document.createElement("img");
			image.src = response.data;
			image.alt = "";
			element.replaceChildren(image);
		});
	}
}

function renderPresets() {
	const allPresets = [
		{
			id: "all-off",
			name: "无 Mod",
			description: "关闭所有 Mod",
			mods: [],
			builtin: true,
		},
		...data.presets,
	];
	content.innerHTML = `<div class="page-head"><div><h1>预设配置</h1><p class="subtitle">保存已启用的 Mod 组合，一键切换</p></div></div><section class="panel"><h2 class="panel-title">创建预设</h2><p class="muted">保存当前启用的 Mod 状态</p><form id="create-preset" class="inline"><input class="field" name="name" placeholder="预设名称" required /><input class="field" name="description" placeholder="备注（可选）" /><button class="primary">保存当前状态</button></form></section><div class="preset-list">${allPresets
		.map((preset) => {
			const expanded = expandedPreset === preset.id;
			const editing = editingPreset === preset.id;
			const groups = Object.groupBy(preset.mods, (mod) => mod.character);
			return `<section class="preset ${data.activePresetId === preset.id ? "active" : ""}"><div class="preset-head"><div><div class="preset-name">${data.activePresetId === preset.id ? "● " : ""}${escapeHtml(preset.name)}</div><div class="preset-meta">${preset.mods.length} 个 Mod · ${Object.keys(groups).length} 个分类${preset.description ? ` · ${escapeHtml(preset.description)}` : ""}</div></div><div class="inline"><button class="secondary" data-action="expand" data-id="${preset.id}">${expanded ? "收起" : "查看"}</button><button class="primary" data-action="apply" data-id="${preset.id}">应用</button></div></div>${
				expanded
					? `<div class="preset-body">${preset.builtin ? "" : `<div class="inline"><button class="secondary" data-action="snapshot" data-id="${preset.id}">更新为当前状态</button><button class="secondary" data-action="edit" data-id="${preset.id}">编辑信息</button><button class="danger" data-action="delete" data-id="${preset.id}">${deletingPreset === preset.id ? "确认删除" : "删除"}</button></div>`}${editing ? `<form id="edit-preset" class="inline" data-id="${preset.id}"><input class="field" name="name" value="${escapeHtml(preset.name)}" required /><input class="field" name="description" value="${escapeHtml(preset.description)}" /><button class="primary">保存</button></form>` : ""}<p class="muted">${preset.mods.length ? "包含的 Mod" : "该预设没有 Mod"}</p><div class="preset-tags">${Object.entries(
							groups,
						)
							.flatMap(([character, mods]) =>
								mods.map(
									(mod) =>
										`<span>${escapeHtml(character)} / ${escapeHtml(mod.mod)}</span>`,
								),
							)
							.join("")}</div></div>`
					: ""
			}</section>`;
		})
		.join("")}</div>`;
}

function keyToken(code, key) {
	const navigation = {
		ArrowUp: "VK_UP",
		ArrowDown: "VK_DOWN",
		ArrowLeft: "VK_LEFT",
		ArrowRight: "VK_RIGHT",
		Home: "VK_HOME",
		End: "VK_END",
		PageUp: "VK_PRIOR",
		PageDown: "VK_NEXT",
		Insert: "VK_INSERT",
		Delete: "VK_DELETE",
	};
	if (/^Numpad[0-9]$/.test(code))
		return navigation[key] || `VK_NUMPAD${code.slice(-1)}`;
	if (/^Key[A-Z]$/.test(code)) return code.slice(-1).toLowerCase();
	if (/^Digit[0-9]$/.test(code)) return code.slice(-1);
	if (/^F(?:[1-9]|1[0-2])$/.test(code)) return `VK_${code}`;
	return navigation[code] || null;
}

document.addEventListener("keydown", (event) => {
	if (!capture) return;
	event.preventDefault();
	if (event.code === "Escape") {
		capture = null;
		render();
		return;
	}
	const token = keyToken(event.code, event.key);
	if (!token) return;
	if (capture.global) data.key = token;
	else
		edits.set(
			`${capture.file}\u0000${capture.section}`,
			[
				event.ctrlKey && "ctrl",
				event.altKey && "alt",
				event.shiftKey && "shift",
				token,
			]
				.filter(Boolean)
				.join(" "),
		);
	capture = null;
	render();
});

document.querySelector("#global-key").addEventListener("click", () => {
	capture = { global: true };
	render();
});
document
	.querySelector("#choose-directory")
	.addEventListener("click", async () =>
		accept(await request(() => window.iooh.chooseDirectory())),
	);
document.querySelector("#configure").addEventListener("click", async () => {
	const changed = [...edits].map(([identity, key]) => {
		const [file, section] = identity.split("\u0000");
		return { file, section, key };
	});
	const response = await request(() =>
		window.iooh.configure(data.key, changed),
	);
	if (response) {
		edits.clear();
		accept(response.state);
		notify(`已注入 ${response.count} 个 INI 文件`);
	}
});
document.querySelector("#restore").addEventListener("click", async () => {
	const response = await request(() => window.iooh.restore());
	if (response) {
		accept(response.state);
		notify(`已恢复 ${response.count} 个 INI 备份`);
	}
});
for (const button of document.querySelectorAll(".nav"))
	button.addEventListener("click", () => {
		page = button.dataset.page;
		selectedCharacter = null;
		capture = null;
		render();
	});

content.addEventListener("input", (event) => {
	if (event.target.id === "populated-only") {
		populatedOnly = event.target.checked;
		renderMods();
		return;
	}
	if (event.target.id !== "search") return;
	search = event.target.value;
	const position = event.target.selectionStart;
	renderMods();
	const input = document.querySelector("#search");
	input.focus();
	input.setSelectionRange(position, position);
});
content.addEventListener("submit", async (event) => {
	event.preventDefault();
	const form = event.target;
	if (form.id === "add-role") {
		const response = await request(() =>
			window.iooh.addRole(form.elements.name.value),
		);
		if (response) {
			accept(response);
			notify("角色已添加");
		}
		return;
	}
	const response =
		form.id === "create-preset"
			? await request(() =>
					window.iooh.presetCreate(
						form.elements.name.value,
						form.elements.description.value,
					),
				)
			: await request(() =>
					window.iooh.presetUpdate(
						form.dataset.id,
						form.elements.name.value,
						form.elements.description.value,
						false,
					),
				);
	if (response) {
		editingPreset = null;
		accept(response);
		notify("预设已保存");
	}
});
content.addEventListener("click", async (event) => {
	const button = event.target.closest("[data-action]");
	if (!button) return;
	const { action, character, mod, loose, id, file, section } = button.dataset;
	if (action === "character") {
		selectedCharacter = character;
		render();
	}
	if (action === "back") {
		selectedCharacter = null;
		render();
	}
	if (action === "capture") {
		capture = { file, section };
		button.textContent = "请按键 · Esc 取消";
	}
	if (action === "expand") {
		expandedPreset = expandedPreset === id ? null : id;
		render();
	}
	if (action === "edit") {
		editingPreset = editingPreset === id ? null : id;
		render();
	}
	if (action === "delete") {
		if (deletingPreset !== id) {
			deletingPreset = id;
			render();
			return;
		}
		const response = await request(() => window.iooh.presetDelete(id));
		if (response) {
			deletingPreset = null;
			accept(response);
			notify("预设已删除");
		}
	}
	if (action === "move") {
		const target = [...content.querySelectorAll("select[data-loose]")].find(
			(select) => select.dataset.loose === loose,
		)?.value;
		if (!target) {
			notify("请选择目标分类", true);
			return;
		}
		const response = await request(() => window.iooh.moveMod(loose, target));
		if (response) {
			accept(response);
			notify(`${loose} 已归入 ${target}`);
		}
	}
	if (action === "toggle") {
		const response = await request(() =>
			window.iooh.toggleMod(
				selectedCharacter,
				mod,
				button.getAttribute("aria-checked") !== "true",
			),
		);
		if (response) {
			accept(response);
			notify(`${mod} 状态已更新`);
		}
	}
	if (action === "apply") {
		const response = await request(() => window.iooh.presetApply(id));
		if (response) {
			accept(response.state);
			notify(`已应用预设，切换 ${response.changed} 个 Mod`);
		}
	}
	if (action === "snapshot") {
		const preset = data.presets.find((item) => item.id === id);
		const response = await request(() =>
			window.iooh.presetUpdate(id, preset.name, preset.description, true),
		);
		if (response) {
			accept(response);
			notify("预设已更新为当前 Mod 状态");
		}
	}
});

accept(await request(() => window.iooh.state()));
