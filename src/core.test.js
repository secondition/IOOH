import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import {
	applyPreset,
	configure,
	coverPath,
	createPreset,
	moveMod,
	scan,
} from "./core.js";

test("角色归类、预设切换与全局热键注入", () => {
	using temp = fs.mkdtempDisposableSync(path.join(os.tmpdir(), "iooh-"));
	const root = temp.path;
	const loose = path.join(root, "外观 Mod");
	fs.mkdirSync(loose);
	const ini = path.join(loose, "mod.ini");
	fs.writeFileSync(
		ini,
		"[KeySwap]\nkey = alt 1\ntype = cycle\ncondition = $ready == 1\n",
	);
	fs.writeFileSync(
		path.join(loose, "other.ini"),
		"[KeyOne]\r\nkey=2\r\n[KeyMouse]\r\nkey=VK_LBUTTON\r\n",
	);
	assert.equal(scan(root).loose[0].name, "外观 Mod");
	moveMod(root, "外观 Mod", "安比");
	assert.equal(
		scan(root).characters.find((char) => char.name === "安比").mods.length,
		1,
	);
	assert.equal(
		scan(root).characters.some((char) => char.name === "零号·安比"),
		true,
	);
	assert.match(coverPath("安比").pathname, /AnbyM6\.png$/);
	assert.match(coverPath("主角").pathname, /_cover\.webp$/);
	assert.equal(
		scan(root).characters.find((char) => char.name === "主角").other,
		true,
	);
	const toolIni = path.join(root, "功能", "iooh", "IOOHmod.ini");
	fs.mkdirSync(path.dirname(toolIni), { recursive: true });
	fs.writeFileSync(toolIni, "; IOOH");
	const otherIni = path.join(root, "功能", "辅助 Mod", "mod.ini");
	fs.mkdirSync(path.dirname(otherIni));
	fs.writeFileSync(otherIni, "[KeyOther]\nkey=4\n");
	const disabledIni = path.join(
		root,
		"安比",
		"DISABLED 备用 Mod",
		"DISABLED_资源",
		"mod.ini",
	);
	fs.mkdirSync(path.dirname(disabledIni), { recursive: true });
	fs.writeFileSync(disabledIni, "[KeyAlt]\nkey=3\n");
	assert.equal(
		scan(root).characters.find((char) => char.name === "功能").other,
		true,
	);
	assert.equal(configure(root, "VK_NUMPAD2"), 3);
	assert.equal(configure(root, "VK_NUMPAD2"), 3);
	assert.match(
		fs.readFileSync(disabledIni, "utf8"),
		/condition = \$iooh_en == 1/,
	);
	assert.equal(fs.readFileSync(otherIni, "utf8"), "[KeyOther]\nkey=4\n");
	const text = fs.readFileSync(
		path.join(root, "安比", "外观 Mod", "mod.ini"),
		"utf8",
	);
	assert.equal(
		text.match(/condition = \$ready == 1 && \$iooh_en == 1/g).length,
		1,
	);
	assert.equal(text.match(/\[Key_iooh_Toggle\]/g).length, 1);
	const other = fs.readFileSync(
		path.join(root, "安比", "外观 Mod", "other.ini"),
		"utf8",
	);
	assert.equal(other.match(/condition = \$iooh_en == 1/g).length, 1);
	assert.match(other, /\[KeyMouse\]\nkey=VK_LBUTTON/);
	const main = fs.readFileSync(toolIni, "utf8");
	assert.equal(fs.existsSync(path.join(root, "IOOHmod.ini")), false);
	assert.ok(main.includes("VK_NUMPAD2"));
	assert.ok(main.includes("run = CommandList\\ZZMIv1\\PrintText"));
	const store = { presets: [] };
	const preset = createPreset(store, "外观", "", scan(root).characters);
	applyPreset(root, { mods: [] }, scan(root).characters);
	assert.equal(
		fs.existsSync(path.join(root, "安比", "DISABLED_外观 Mod")),
		true,
	);
	applyPreset(root, preset, scan(root).characters);
	assert.equal(fs.existsSync(path.join(root, "安比", "外观 Mod")), true);
	assert.equal(
		scan(root)
			.characters.find((char) => char.name === "安比")
			.mods.find((mod) => mod.name === "备用 Mod").enabled,
		false,
	);
	applyPreset(
		root,
		{ mods: [{ character: "安比", mod: "备用 Mod" }] },
		scan(root).characters,
	);
	assert.equal(fs.existsSync(path.join(root, "安比", "备用 Mod")), true);
	fs.mkdirSync(path.join(root, "自定义分类", "另一 Mod"), { recursive: true });
	assert.equal(
		scan(root).characters.find((char) => char.name === "自定义分类").mods
			.length,
		1,
	);
});
