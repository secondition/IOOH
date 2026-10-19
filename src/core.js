import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const covers = new URL("../assets/covers/", import.meta.url);
const knownCharacters = new Set(directories(covers).map((item) => item.name));
const otherNames = new Set(["NPC", "UI", "功能", "大世界", "主角"]);
const marker = "; ===== IOOH 全局开关 =====";
const markerEnd = "; ===== IOOH 全局开关结束 =====";

function directories(folder) {
	return fs.existsSync(folder)
		? fs
				.readdirSync(folder, { withFileTypes: true })
				.filter((item) => item.isDirectory())
		: [];
}

function safeName(name) {
	if (
		typeof name !== "string" ||
		!name.trim() ||
		name === "." ||
		name === ".." ||
		/[\\/:*?"<>|]/.test(name)
	) {
		throw new Error("文件夹名称无效");
	}
	return name;
}

function isDisabled(name) {
	return /^DISABLED[_ ]/i.test(name);
}

function modName(name) {
	return isDisabled(name) ? name.slice(9) : name;
}

function walkIni(folder) {
	const result = [];
	if (!fs.existsSync(folder)) return result;
	for (const item of fs.readdirSync(folder, { withFileTypes: true })) {
		const filename = path.join(folder, item.name);
		if (item.isDirectory()) result.push(...walkIni(filename));
		if (
			item.isFile() &&
			item.name.toLowerCase().endsWith(".ini") &&
			item.name.toLowerCase() !== "ioohmod.ini"
		)
			result.push(filename);
	}
	return result;
}

function sections(text) {
	const headers = [...text.matchAll(/^[ \t]*\[([^\]\r\n]+)\][ \t]*\r?$/gm)];
	return headers.map((match, index) => ({
		name: match[1],
		start: match.index,
		end: headers[index + 1]?.index ?? text.length,
		text: text.slice(match.index, headers[index + 1]?.index ?? text.length),
	}));
}

function normalizeSection(text) {
	let normalized = text.replace(/(\[[^\]]+\])([ \t]*)(?=[^\n])/i, "$1\n");
	for (const field of [
		/key\s*=/i,
		/condition\s*=/i,
		/type\s*=/i,
		/run\s*=/i,
		/\$[A-Za-z_]\w*\s*=(?!=)/i,
	]) {
		normalized = normalized.replace(
			new RegExp(`(?<=[^\\n])[ \\t]+(${field.source})`, "gi"),
			"\n$1",
		);
	}
	return normalized;
}

function fieldValue(text, field) {
	const lines = normalizeSection(text).split("\n");
	const index = lines.findIndex((line) =>
		new RegExp(`^[ \\t]*${field}[ \\t]*=`, "i").test(line),
	);
	if (index < 0) return null;
	let value = lines[index].split("=").slice(1).join("=").split(";")[0].trim();
	if (
		!value &&
		lines[index + 1] &&
		!/^\s*(?:\[|[A-Za-z_]\w*\s*=|\$[A-Za-z_]\w*\s*=)/.test(lines[index + 1])
	) {
		value = lines[index + 1].split(";")[0].trim();
	}
	return value.replace(/\s+/g, " ") || null;
}

const oldGates =
	/\s*&&\s*\$iooh_(?:en\d*|s\d*|sel)\s*==\s*\d+|\$iooh_(?:en\d*|s\d*|sel)\s*==\s*\d+\s*&&\s*|\$iooh_(?:en\d*|s\d*|sel)\s*==\s*\d+|\s*&&\s*\$\w+_sel\s*==\s*\d+|\$\w+_sel\s*==\s*\d+\s*&&\s*|\$\w+_sel\s*==\s*\d+/gi;

function stripInjection(text) {
	return text
		.replace(/^.*\$selected_character.*\r?\n/gm, "")
		.replace(/^global \$iooh_(?:s\d+|en\d*|ui\d+)\s*=\s*-?\d+\s*\r?\n/gm, "")
		.replace(
			/;\s*=====\s*IOOH (?:全局开关|本地选择器)\s*=====[\s\S]*?;\s*=====\s*IOOH (?:全局开关|本地选择器)结束\s*=====\s*\r?\n?/g,
			"",
		)
		.replace(
			/\[(?:KeySelect(?:Up|Down)|CommandListSelect(?:Up|Down)|CommandList_IOOH_\w+|Key_\w+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)|CommandList_\w+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible))\][\s\S]*?(?=\r?\n\[|$)/g,
			"",
		)
		.replace(/^global \$\w+_sel\s*=\s*\d+\s*\r?\n/gm, "")
		.replace(
			/;\s*=====\s*角色选择器控制[\s\S]*?;\s*=====\s*选择器控制结束\s*=====\s*\r?\n?/g,
			"",
		)
		.replace(/;\s*=====\s*IOOH 角色选择器 CommandList\s*=====\s*\r?\n?/g, "")
		.replace(/^[ \t]*condition\s*=.*$/gim, (line) => {
			const [head, ...rest] = line.split("=");
			const condition = rest.join("=").replace(oldGates, "").trim();
			return condition ? `${head}= ${condition}` : "";
		})
		.replace(/\n{4,}/g, "\n\n\n");
}

function bindingsFromIni(filename) {
	const text = stripInjection(
		fs.readFileSync(filename, "utf8").replace(/\r\n/g, "\n"),
	);
	return sections(text).flatMap(({ name, text: section }) => {
		if (
			[
				"Constants",
				"Present",
				"Resources",
				"CommandList",
				"TextureOverride",
			].includes(name) ||
			/^(?:CommandList|Resource)/.test(name)
		)
			return [];
		const key = fieldValue(section, "key");
		if (!key || /VK_[LMR]BUTTON|VK_XBUTTON/i.test(key)) return [];
		const type = fieldValue(section, "type");
		const variable = section.match(/\$(\w+)\s*=(?!=)/)?.[1];
		return [
			{
				section: name,
				key,
				description: `${name.replace(/^Key/, "")}${type ? ` (${type})` : ""}${variable ? ` [$${variable}]` : ""}`,
				file: filename,
			},
		];
	});
}

function gateSection(text, key) {
	const lines = normalizeSection(text).split("\n");
	const hasCondition = lines.some((line) => /^\s*condition\s*=/i.test(line));
	const updated = [];
	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		if (/^\s*key\s*=/i.test(line)) {
			updated.push(
				line.replace(
					/^(\s*key\s*=\s*)[^;]*(;.*)?$/i,
					(_, head, comment = "") =>
						`${head}${key}${comment ? ` ${comment}` : ""}`,
				),
			);
			if (!hasCondition)
				updated.push(`${line.match(/^\s*/)[0]}condition = $iooh_en == 1`);
			continue;
		}
		if (/^\s*condition\s*=/i.test(line)) {
			let condition = line.split("=").slice(1).join("=").trim();
			if (
				!condition &&
				lines[i + 1] &&
				!/^\s*(?:\[|[A-Za-z_]\w*\s*=|\$[A-Za-z_]\w*\s*=)/.test(lines[i + 1])
			)
				condition = lines[++i].trim();
			condition = condition.replace(oldGates, "").trim();
			updated.push(
				`${line.match(/^\s*/)[0]}condition = ${condition ? `${condition} && ` : ""}$iooh_en == 1`,
			);
			continue;
		}
		updated.push(line);
	}
	return updated.join("\n");
}

function writeText(filename, text) {
	if (fs.existsSync(filename)) fs.chmodSync(filename, 0o666);
	fs.writeFileSync(filename, text, "utf8");
}

export function scan(root, roleNames = []) {
	const characters = [];
	const roles = new Set([...knownCharacters, ...roleNames]);
	const loose = [];
	for (const item of directories(root)) {
		if (
			item.name.startsWith(".") ||
			item.name.startsWith("EFMI") ||
			item.name.toLowerCase() === "rabbitfx"
		)
			continue;
		const folder = path.join(root, item.name);
		const children = directories(folder);
		const hasOwnIni = fs
			.readdirSync(folder, { withFileTypes: true })
			.some(
				(child) => child.isFile() && child.name.toLowerCase().endsWith(".ini"),
			);
		if (!roles.has(item.name) && (!children.length || hasOwnIni)) {
			loose.push({ name: item.name, path: folder });
			continue;
		}
		characters.push({
			name: item.name,
			other: otherNames.has(item.name),
			mods: children
				.filter(
					(child) =>
						!child.name.startsWith(".") &&
						!fs.existsSync(path.join(folder, child.name, "IOOHmod.ini")),
				)
				.map((child) => {
					const files = walkIni(path.join(folder, child.name));
					return {
						name: modName(child.name),
						enabled: !isDisabled(child.name),
						path: path.join(folder, child.name),
						bindings: files.flatMap(bindingsFromIni),
						files,
					};
				}),
		});
	}
	const byName = new Map(
		characters.map((character) => [character.name, character]),
	);
	for (const name of knownCharacters)
		if (!byName.has(name))
			byName.set(name, { name, other: otherNames.has(name), mods: [] });
	return { characters: [...byName.values()], loose };
}

export function moveMod(root, folderName, character) {
	safeName(folderName);
	safeName(character);
	const source = path.join(root, folderName);
	const destination = path.join(root, character, folderName);
	if (!directories(root).some((entry) => entry.name === folderName))
		throw new Error("待归类的 Mod 不存在");
	if (fs.existsSync(destination)) throw new Error("目标角色下已有同名 Mod");
	fs.mkdirSync(path.dirname(destination), { recursive: true });
	fs.renameSync(source, destination);
}

export function toggleMod(root, character, mod, enable) {
	safeName(character);
	safeName(mod);
	const folder = path.join(root, character);
	const current = enable
		? directories(folder).find(
				(entry) => isDisabled(entry.name) && modName(entry.name) === mod,
			)?.name
		: mod;
	if (!current) throw new Error("Mod 不存在或已经切换状态");
	const source = path.join(folder, current);
	const destination = path.join(folder, enable ? mod : `DISABLED_${mod}`);
	if (!fs.existsSync(source)) throw new Error("Mod 不存在或已经切换状态");
	if (fs.existsSync(destination)) throw new Error("目标目录已存在");
	fs.renameSync(source, destination);
}

function toggleBlock(key) {
	return `${marker}\n[Key_iooh_Toggle]\nkey = no_ctrl no_alt ${key}\nrun = CommandList_iooh_Toggle\n\n[CommandList_iooh_Toggle]\nif $iooh_en == 1\n    $iooh_en = 0\nelse\n    $iooh_en = 1\nendif\n${markerEnd}`;
}

export function configure(root, key, edits = [], roleNames = []) {
	const existing = [
		path.join(root, "IOOHmod.ini"),
		...directories(root).flatMap((role) =>
			directories(path.join(root, role.name)).map((mod) =>
				path.join(root, role.name, mod.name, "IOOHmod.ini"),
			),
		),
	].filter((filename) => fs.existsSync(filename));
	if (existing.length > 1) throw new Error("发现多个 IOOHmod.ini");
	const { characters } = scan(root, roleNames);
	const results = [];
	for (const character of characters.filter((character) => !character.other))
		for (const mod of character.mods) {
			for (const filename of mod.files) {
				const bindings = mod.bindings.filter(
					(binding) => binding.file === filename,
				);
				if (!bindings.length) continue;
				const backup = `${filename}.backup`;
				if (!fs.existsSync(backup)) fs.copyFileSync(filename, backup);
				let text = stripInjection(
					fs.readFileSync(filename, "utf8").replace(/\r\n/g, "\n"),
				);
				const bindingKeys = new Map(
					bindings.map((binding) => [
						binding.section,
						edits.find(
							(edit) =>
								edit.file === filename && edit.section === binding.section,
						)?.key || binding.key,
					]),
				);
				const parts = [];
				let cursor = 0;
				for (const section of sections(text)) {
					parts.push(
						text.slice(cursor, section.start),
						bindingKeys.has(section.name)
							? gateSection(section.text, bindingKeys.get(section.name))
							: section.text,
					);
					cursor = section.end;
				}
				parts.push(text.slice(cursor));
				text = parts.join("");
				if (/\[Constants\]\s*\r?\n/i.test(text))
					text = text.replace(
						/(\[Constants\]\s*\r?\n)/i,
						"$1global $iooh_en = 0\n",
					);
				else text = `[Constants]\nglobal $iooh_en = 0\n\n${text}`;
				const firstKey = text.search(/\[Key\w+\]/);
				text =
					firstKey < 0
						? `${text.trimEnd()}\n\n${toggleBlock(key)}\n`
						: `${text.slice(0, firstKey)}\n\n${toggleBlock(key)}\n${text.slice(firstKey)}`;
				writeText(filename, text);
				results.push(filename);
			}
		}
	const main = `; IOOH 全局热键开关
[Constants]
global $iooh_en = 0
global $iooh_notification_timeout = 0

[KeyIOOH_Toggle]
key = no_ctrl no_alt ${key}
run = CommandList_Toggle

[CommandList_Toggle]
if $iooh_en == 1
    $iooh_en = 0
else
    $iooh_en = 1
endif
$iooh_notification_timeout = time + 5

[Present]
if time < $iooh_notification_timeout
    if $iooh_en == 1
        Resource\\ZZMIv1\\Text = ref ResourceIOOHOn
    else
        Resource\\ZZMIv1\\Text = ref ResourceIOOHOff
    endif
    Resource\\ZZMIv1\\TextParams = ref Resource\\ZZMIv1\\UserNotificationParams
    run = CommandList\\ZZMIv1\\PrintText
endif

[ResourceIOOHOn]
type = Buffer
data = "IOOH hotkeys ON"

[ResourceIOOHOff]
type = Buffer
data = "IOOH hotkeys OFF"
`;
	writeText(existing[0] || path.join(root, "IOOHmod.ini"), main);
	return results.length;
}

export function restore(root) {
	let count = 0;
	function visit(folder) {
		for (const item of fs.readdirSync(folder, { withFileTypes: true })) {
			const filename = path.join(folder, item.name);
			if (item.isDirectory()) visit(filename);
			else if (item.name.endsWith(".ini.backup")) {
				const original = filename.slice(0, -7);
				if (fs.existsSync(original)) fs.chmodSync(original, 0o666);
				fs.copyFileSync(filename, original);
				count++;
			}
		}
	}
	visit(root);
	return count;
}

export function createPreset(store, name, description, characters) {
	const trimmed = name.trim();
	if (!trimmed || store.presets.some((preset) => preset.name === trimmed))
		throw new Error("预设名称为空或已存在");
	const preset = {
		id: randomUUID(),
		name: trimmed,
		description: description.trim(),
		mods: characters.flatMap((character) =>
			character.mods
				.filter((mod) => mod.enabled)
				.map((mod) => ({ character: character.name, mod: mod.name })),
		),
	};
	store.presets.push(preset);
	return preset;
}

export function applyPreset(root, preset, characters) {
	const enabled = new Set(
		preset.mods.map(({ character, mod }) => `${character}/${mod}`),
	);
	const changes = [];
	for (const character of characters)
		for (const mod of character.mods) {
			const shouldEnable = enabled.has(`${character.name}/${mod.name}`);
			if (mod.enabled !== shouldEnable) {
				try {
					toggleMod(root, character.name, mod.name, shouldEnable);
					changes.push(`${character.name}/${mod.name}`);
				} catch (error) {
					throw new Error(
						`已切换 ${changes.length} 个 Mod；${character.name}/${mod.name}：${error.message}`,
					);
				}
			}
		}
	return changes.length;
}

export function coverPath(character) {
	safeName(character);
	const folder = new URL(`${encodeURIComponent(character)}/`, covers);
	if (!fs.existsSync(folder)) return null;
	const mindscape = fs
		.readdirSync(folder)
		.find((name) => name.endsWith("M6.png"));
	if (mindscape) return new URL(encodeURIComponent(mindscape), folder);
	for (const extension of ["png", "jpg", "jpeg", "webp"]) {
		const file = new URL(`_cover.${extension}`, folder);
		if (fs.existsSync(file)) return file;
	}
	return null;
}
