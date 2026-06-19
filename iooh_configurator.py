#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - 核心配置器 v4.0（本地变量版）

核心机制：本地选择器变量
- 每个mod声明自己的本地选择器变量 $iooh_s<id>
- 每个mod拥有自己的 VK_LEFT/VK_RIGHT 处理器，同步循环选择器值
  （三方监听同一物理按键、各自相同计数，实现无通信巧合同步）
- Key section 保留原有type，condition 使用本地变量判断
- 3DMigoto Key condition 只能可靠引用同文件变量，跨文件引用无效

四个 IOOH 菜单控制键集中在 IOOHKeyConfig（iooh_keys.py），主 ini 与各 mod
选择器块共用同一份按键，确保巧合同步成立；用户可在 UI 自定义。
"""

import os
import re
import shutil
import json
import stat
import sys
from typing import Dict, List
from datetime import datetime

from iooh_models import ModKeyBinding, ModInfo
from iooh_keys import IOOHKeyConfig


class EFMIKeyConfigurator:
    """EFMI按键配置器"""

    def __init__(self):
        self.mods: List[ModInfo] = []
        self.mods_directory = ""
        self.config_file = os.path.join(self._get_output_dir(), "xxmi_key_config.json")
        # IOOH 菜单四个控制键的单一数据源（持久化在 exe/脚本同级）
        self.iooh_keys = IOOHKeyConfig(self._get_output_dir())

    @staticmethod
    def _get_bundle_dir() -> str:
        """Return the directory containing bundled read-only assets."""
        if getattr(sys, 'frozen', False):
            return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def _get_output_dir() -> str:
        """Return the directory where generated files should be written."""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def _resolve_output_dir(self) -> str:
        """Always write generated files next to the running executable."""
        return self._get_output_dir()

    def _muban_aspect(self) -> float:
        """读取 muban.png 实际尺寸，返回 高/宽 比例（面板等比缩放用）。"""
        from PIL import Image
        muban_path = os.path.join(self._resolve_output_dir(), "resources", "textures", "muban.png")
        with Image.open(muban_path) as im:
            w, h = im.size
        return h / w

    def _ensure_runtime_shader_assets(self):
        """Copy bundled runtime assets (shaders + muban 模板) next to the executable."""
        self._copy_bundled_tree("shaders")
        # muban 模板源在 assets/，复制到运行时渲染目录 resources/textures/
        # （用户头像在 exe 同级 rolepicture/，由纹理生成器按需读取，不在此复制）
        src = os.path.join(self._get_bundle_dir(), "assets", "muban.png")
        dst = os.path.join(self._resolve_output_dir(), "resources", "textures", "muban.png")
        if os.path.isfile(src) and os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dst)):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    def _copy_bundled_tree(self, rel_dir: str):
        """Copy a bundled directory tree to the output dir (skip when identical)."""
        source_dir = os.path.join(self._get_bundle_dir(), rel_dir)
        target_dir = os.path.join(self._resolve_output_dir(), rel_dir)
        if not os.path.isdir(source_dir):
            return

        # 开发环境下 bundle 目录与输出目录相同，源即目标，无需复制
        if os.path.normcase(os.path.abspath(source_dir)) == os.path.normcase(os.path.abspath(target_dir)):
            return

        os.makedirs(target_dir, exist_ok=True)
        for root, _, files in os.walk(source_dir):
            relative_root = os.path.relpath(root, source_dir)
            current_target_dir = target_dir if relative_root == "." else os.path.join(target_dir, relative_root)
            os.makedirs(current_target_dir, exist_ok=True)
            for file in files:
                source_file = os.path.join(root, file)
                target_file = os.path.join(current_target_dir, file)
                shutil.copy2(source_file, target_file)

    @staticmethod
    def _ensure_writable(filepath: str):
        """移除文件只读属性（如有）"""
        if os.path.exists(filepath) and not os.access(filepath, os.W_OK):
            os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)

    @staticmethod
    def _is_disabled_folder(folder_name: str) -> bool:
        """Return True when a folder name marks it as disabled."""
        return "disabled" in os.path.basename(os.path.normpath(folder_name)).lower()

    def restore_backups(self, directory: str):
        """恢复所有备份文件，确保从干净状态开始"""
        print("恢复备份文件...")
        restored_count = 0

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not self._is_disabled_folder(d)]

            for file in files:
                if file.endswith('.backup'):
                    backup_path = os.path.join(root, file)
                    original_path = backup_path[:-7]  # 去掉 .backup

                    try:
                        self._ensure_writable(original_path)
                        shutil.copy2(backup_path, original_path)
                        restored_count += 1
                    except Exception as e:
                        print(f"恢复 {file} 失败: {e}")

        if restored_count > 0:
            print(f"✓ 已恢复 {restored_count} 个备份文件")
        else:
            print("未找到备份文件（首次配置）")

    def backup_mod(self, mod: ModInfo):
        """为指定 mod 的所有 ini 创建 .backup 副本（幂等）"""
        for ini_file in mod.ini_files:
            backup_path = ini_file + '.backup'
            try:
                if not os.path.exists(backup_path):
                    shutil.copy2(ini_file, backup_path)
            except Exception as e:
                print(f"备份 {ini_file} 失败: {e}")

    def save_config(self, output_path: str = None) -> bool:
        """保存扫描结果与按键信息，便于调试/复用"""
        if output_path is None:
            output_path = self.config_file

        data = {
            "mods": [
                {
                    "name": mod.name,
                    "path": mod.path,
                    "character_id": mod.character_id,
                    "ini_files": mod.ini_files,
                    "key_bindings": [
                        {
                            "section": kb.section_name,
                            "key": kb.key,
                            "variable": kb.variable,
                            "description": kb.description,
                        }
                        for kb in mod.key_bindings
                    ],
                }
                for mod in self.mods
            ]
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"配置已保存到: {output_path}")
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def scan_mods(self, directory: str) -> List[ModInfo]:
        """扫描目录下的所有mod，检测所有.ini文件和角色hash"""
        self.mods_directory = directory
        self.config_file = os.path.join(self._resolve_output_dir(), "xxmi_key_config.json")
        self.mods.clear()

        # 扫描是只读操作，不还原真实 ini（还原职责归「保存/自动配置」）。
        # 解析时在内存里剥离上次注入的内容，原始 section 不受影响。

        # 获取工具输出目录，用于跳过工具自身目录
        script_dir = os.path.abspath(self._resolve_output_dir())

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)

            # 跳过隐藏文件夹、EFMI文件夹和脚本自身所在的文件夹
            if item.startswith('.') or item.startswith('EFMI'):
                continue

            if self._is_disabled_folder(item):
                continue

            # 忽略 rabbitFX 相关
            if 'rabbitfx' in item.lower():
                continue

            # 根据用户要求增加跳过的文件夹关键字：UI, 大世界, 功能
            if any(keyword in item.lower() for keyword in ['ui', '大世界', '功能']):
                continue

            # 跳过脚本自身所在的文件夹（IOOH文件夹）
            if os.path.abspath(item_path) == script_dir:
                continue

            if os.path.isdir(item_path):
                # 递归查找该文件夹下所有.ini文件（包括子文件夹）
                ini_files = []
                try:
                    for root, dirs, files in os.walk(item_path):
                        dirs[:] = [d for d in dirs if not self._is_disabled_folder(d)]

                        for file in files:
                            if file.lower().endswith('.ini'):
                                ini_files.append(os.path.join(root, file))
                except PermissionError:
                    continue

                if ini_files:
                    # Skip tool-generated IOOH main UI config to avoid self-scan
                    if any(os.path.basename(f).lower() == 'ioohmod.ini' for f in ini_files):
                        continue
                    mod = ModInfo(item, item_path, ini_files)
                    # 解析所有ini文件
                    for ini_file in ini_files:
                        self._parse_ini_file(mod, ini_file)

                    # 只添加有按键绑定的mod
                    if mod.key_bindings:
                        self.mods.append(mod)

        # 按名称排序
        self.mods.sort(key=lambda m: m.name)

        # 自动分配character ID
        for idx, mod in enumerate(self.mods):
            mod.character_id = idx

        return self.mods

    def _iter_sections(self, content: str):
        """迭代所有 section（更稳健，支持没有换行的 section 间隔）。"""
        matches = list(re.finditer(r'(?m)^[ \t]*\[([^\]\r\n]+)\][ \t]*$', content))
        for idx, match in enumerate(matches):
            name = match.group(1)
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            yield name, start, end, content[start:end]

    def _normalize_section_text(self, section_text: str) -> str:
        """Normalize section text so key fields are on their own lines."""
        text = section_text
        # Ensure a newline right after the [Section] header.
        text = re.sub(r'(\[[^\]]+\])([ \t]*)(?=[^\n])', r'\1\n', text, count=1)
        # If multiple fields are on the same line, split them into lines.
        patterns = [
            r'key\s*=',
            r'condition\s*=',
            r'type\s*=',
            r'run\s*=',
            r'\$[A-Za-z_]\w*\s*=(?!=)',
        ]
        for pattern in patterns:
            text = re.sub(rf'(?i)(?<=[^\n])[ \t]+({pattern})', r'\n\1', text)
        return text

    def _parse_ini_file(self, mod: ModInfo, ini_file_path: str):
        """解析ini文件，提取按键绑定 - 通用检测所有按键section"""
        try:
            with open(ini_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 扫描不还原真实 ini（避免读取操作改写磁盘）；但 ini 可能含上次注入的
            # Key_iooh_s* 块（自带 key 行），故在内存里剥离注入内容再解析，不写回磁盘。
            content = self._strip_local_selector(content)

            # 更通用的模式：查找所有包含 key = 的section（不限于Key开头）
            # 匹配格式：[任意section名] ... key = 某值 ... （可能有其他内容）
            for section_name, _, _, section_text in self._iter_sections(content):
                section_content = section_text.split(']', 1)[-1]

                # 跳过非按键相关的section（如Constants, Present等）
                if section_name in ['Constants', 'Present', 'Resources', 'CommandList', 'TextureOverride']:
                    continue
                if section_name.startswith('CommandList') or section_name.startswith('Resource'):
                    continue

                # 检查是否包含 key = 行
                key = self._extract_key_from_section(section_content)
                if not key:
                    continue

                # 提取变量名和类型
                variable = self._extract_variable_from_section(section_content)
                binding_type = self._extract_type_from_section(section_content)

                # 处理所有包含 key = 的热键绑定（记录来源 ini，避免跨文件同名 section 归错组）
                binding = ModKeyBinding(section_name, key, variable or f"${section_name}", mod.path, ini_file_path)
                binding.description = self._generate_description(section_name, variable, binding_type)
                mod.key_bindings.append(binding)

        except Exception as e:
            ini_filename = os.path.basename(ini_file_path)
            print(f"解析 {mod.name}/{ini_filename} 失败: {e}")

    def _extract_key_from_section(self, section_content: str):
        """Extract the raw ini key value (e.g. 'alt 1'、'vk_up'、'ctrl /')。

        直接返回 ini 原文（去行内注释、压缩空白），与列表改键显示风格统一、
        与 ini 实际内容一致，不转 Alt+1 这类友好格式。
        """
        key_lines = re.findall(
            r'^\s*key\s*=\s*(.+)$',
            section_content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        if not key_lines:
            # Fallback: key and other fields are on the same line
            key_match = re.search(
                r'(?i)\bkey\s*=\s*(.*?)(?=\s+[A-Za-z_][A-Za-z0-9_]*\s*=|\s+\$\w+\s*=|\s+\[|$)',
                section_content,
                flags=re.DOTALL,
            )
            if key_match:
                key_lines = [key_match.group(1)]
        if not key_lines:
            return None

        for line in key_lines:
            # 去行内注释，压缩连续空白为单空格
            cleaned = re.sub(r'\s+', ' ', line.split(';', 1)[0].strip())
            if cleaned:
                return cleaned

        return None


    def _extract_variable_from_section(self, section_content: str):
        """从section内容中提取变量名"""
        var_pattern = r'\$(\w+)\s*=(?!=)'
        match = re.search(var_pattern, section_content)
        if match:
            return f"${match.group(1)}"
        return None

    def _extract_type_from_section(self, section_content: str):
        """从section内容中提取type类型"""
        type_pattern = r'type\s*=\s*(\w+)'
        match = re.search(type_pattern, section_content)
        if match:
            return match.group(1)
        return None

    def _generate_description(self, section_name: str, variable, binding_type) -> str:
        """生成按键绑定的描述"""
        desc_parts = []

        if section_name:
            # 移除Key前缀显示更简洁
            clean_name = re.sub(r'^Key', '', section_name)
            desc_parts.append(clean_name)

        if binding_type:
            desc_parts.append(f"({binding_type})")

        if variable:
            desc_parts.append(f"[{variable}]")

        return " ".join(desc_parts) if desc_parts else section_name

    def generate_main_mod_ini(self, output_path: str = None):
        """生成 IOOH 主UI ini，按扫描结果动态维护角色映射

        布局：左下角统一面板
        - 角色列表（全部显示，选中高亮）
        """
        self._ensure_runtime_shader_assets()

        if output_path is None:
            output_path = os.path.join(self._resolve_output_dir(), "IOOHmod.ini")

        total_chars = len(self.mods)
        max_id = total_chars - 1 if total_chars > 0 else 0

        # IOOH 菜单四个控制键（用户可自定义，主 ini 与各 mod 选择器块共用同一份）
        key_toggle = self.iooh_keys.key_line("toggle_menu")
        key_prev = self.iooh_keys.key_line("prev_char")
        key_next = self.iooh_keys.key_line("next_char")
        key_enable = self.iooh_keys.key_line("enable_toggle")

        # 生成角色映射注释
        char_mapping = "; 角色ID映射:\n"
        for mod in self.mods:
            char_mapping += f"; {mod.character_id} = {mod.name}\n"

        # === 布局参数 ===
        # 一页一个角色：muban 作为背景模板（已内置按键提示与箭头），
        # 其上叠加「头像层」与「文字层」。三层共用同一面板四边形，
        # 对齐由叠加层画布与 muban 等大保证。
        aspect = 16 / 9       # 屏幕宽高比
        left_x = 0.01         # 左侧起始X

        # 面板高度（占屏高比例）；宽度按 muban 宽高比反推为等比方块。
        # 以高度为基准可适配竖版模板，避免竖图按固定宽度撑出屏幕。
        # 调整整体缩放只需改这一个值，宽度自动等比反推、不变形。
        panel_h_val = 0.4                             # 模板高度（占屏高）
        muban_aspect = self._muban_aspect()              # muban 高/宽（实测）
        panel_w = panel_h_val / (aspect * muban_aspect)  # 等比缩放，保持不变形

        # 从底部向上计算起始Y
        bottom_margin = 0.04
        default_start_y = 1.0 - bottom_margin - panel_h_val

        # 每个角色一个启用标志（与各 mod ini 的 $iooh_en<id> 平行），
        # 让菜单侧也能存储并反映每个角色的启用状态
        enable_decls = "".join(
            f"global $iooh_en{mod.character_id} = 0\n" for mod in self.mods
        )

        # 主体内容
        content = f"""; EFMI 主UI管理器 - 自动生成
; 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
; 总角色数: {total_chars}

{char_mapping}

[Constants]
global $show_character_ui = 0
global $total_characters = {total_chars}
global $iooh_sel = 0
{enable_decls}
; 拖拽控制变量
global persist $ui_x = {left_x:.4f}
global persist $ui_y = {default_start_y:.4f}
global $mouse_clicked = 0
global $is_dragging = 0
global $drag_start_x = 0
global $drag_start_y = 0

; 鼠标拖拽检测 (仅当UI显示时)
[KeyMouseDrag]
condition = $show_character_ui == 1
key = VK_LBUTTON
type = hold
$mouse_clicked = 1

[CommandList_UpdateDrag]
if $mouse_clicked
    if cursor_x > $ui_x && cursor_x < $ui_x + {panel_w:.4f} && cursor_y > $ui_y && cursor_y < $ui_y + {panel_h_val:.4f}
        if $is_dragging == 0
            $drag_start_x = cursor_x - $ui_x
            $drag_start_y = cursor_y - $ui_y
            $is_dragging = 1
        endif
    endif
else
    $is_dragging = 0
endif

if $is_dragging
    $ui_x = cursor_x - $drag_start_x
    $ui_y = cursor_y - $drag_start_y
endif

; UI复位快捷键
[KeyEFMI_ResetUIPosition]
condition = $show_character_ui == 1
key = ctrl no_alt /
type = cycle
$ui_x = {left_x:.4f}
$ui_y = {default_start_y:.4f}

; 显示/隐藏菜单
[KeyEFMI_ToggleMenu]
key = {key_toggle}
run = CommandList_ToggleMenu

[CommandList_ToggleMenu]
if $show_character_ui == 1
    $show_character_ui = 0
else
    $show_character_ui = 1
endif

; 上一个角色（仅菜单显示时响应，隐藏时保留当前选择）
[KeyEFMI_PrevChar]
condition = $show_character_ui == 1
key = {key_prev}
run = CommandList_PrevChar

[CommandList_PrevChar]
"""
        # 上一个角色：自减并回绕（O(1)，不随角色数膨胀）
        if total_chars > 0:
            content += f"$iooh_sel = $iooh_sel - 1\nif $iooh_sel < 0\n    $iooh_sel = {max_id}\nendif\n"

        content += f"""
; 下一个角色（仅菜单显示时响应，隐藏时保留当前选择）
[KeyEFMI_NextChar]
condition = $show_character_ui == 1
key = {key_next}
run = CommandList_NextChar

[CommandList_NextChar]
"""
        # 下一个角色：自增并回绕（O(1)，不随角色数膨胀）
        if total_chars > 0:
            content += f"$iooh_sel = $iooh_sel + 1\nif $iooh_sel > {max_id}\n    $iooh_sel = 0\nendif\n"

        content += f"""
; 启用/禁用当前聚焦的角色（翻转该 id 对应的 $iooh_en<id>，仅菜单显示时响应）
[KeyEFMI_EnableToggle]
condition = $show_character_ui == 1
key = {key_enable}
run = CommandList_EnableToggle

[CommandList_EnableToggle]
"""
        for i in range(total_chars):
            keyword = "if" if i == 0 else "elif"
            content += f"{keyword} $iooh_sel == {i}\n"
            content += f"    if $iooh_en{i} == 1\n        $iooh_en{i} = 0\n    else\n        $iooh_en{i} = 1\n    endif\n"
        if total_chars > 0:
            content += "endif\n"

        content += """
[Present]
if $show_character_ui == 1
    run = CommandList_UpdateDrag
    run = CustomShaderDrawUI
endif

[CustomShaderDrawUI]
vs = shaders\\draw_2d_ui.hlsl
ps = shaders\\draw_2d_ui.hlsl
run = BuiltInCommandListUnbindAllRenderTargets
blend = ADD SRC_ALPHA INV_SRC_ALPHA
cull = none
topology = triangle_strip
o0 = set_viewport bb
"""
        # 三层叠加：muban 背景 → 头像层 → 文字层，共用同一面板四边形
        content += f"""
; ===== 面板四边形（三层共用） =====
x87 = {panel_w:.4f}
y87 = {panel_h_val:.4f}
z87 = $ui_x
w87 = $ui_y

; ===== 第1层：muban 背景模板（已内置按键提示与箭头） =====
ps-t100 = ResourceMuban
Draw = 4,0

; ===== 第2层：当前角色头像（白框位置；无头像则为问号） =====
"""
        for i, mod in enumerate(self.mods):
            keyword = "if" if i == 0 else "elif"
            content += f"{keyword} $iooh_sel == {mod.character_id}\n"
            content += f"    ps-t100 = ResourceAvatar{mod.character_id}\n"
        if total_chars > 0:
            content += "endif\n"
        content += "Draw = 4,0\n"

        content += """
; ===== 第3层：当前角色文字（白框右侧） =====
"""
        for i, mod in enumerate(self.mods):
            keyword = "if" if i == 0 else "elif"
            content += f"{keyword} $iooh_sel == {mod.character_id}\n"
            content += f"    ps-t100 = ResourceText{mod.character_id}\n"
        if total_chars > 0:
            content += "endif\n"
        content += "Draw = 4,0\n"

        content += """
; ===== 第4层：当前角色启用/禁用状态图案（头像与名称下方空白区） =====
"""
        for i, mod in enumerate(self.mods):
            keyword = "if" if i == 0 else "elif"
            content += f"{keyword} $iooh_sel == {mod.character_id}\n"
            content += f"    if $iooh_en{mod.character_id} == 1\n"
            content += f"        ps-t100 = ResourceStatusEnabled\n"
            content += f"    else\n"
            content += f"        ps-t100 = ResourceStatusDisabled\n"
            content += f"    endif\n"
        if total_chars > 0:
            content += "endif\n"
        content += "Draw = 4,0\n"

        content += """
; ===== 第5层：按键提示（全局静态，状态图案下方） =====
ps-t100 = ResourceHintKeys
Draw = 4,0
"""

        # ===== 资源定义 =====
        content += """
; ===== 资源定义 =====
[ResourceMuban]
filename = resources\\textures\\muban.png

[ResourceHintKeys]
filename = resources\\textures\\hint_keys.png

[ResourceStatusEnabled]
filename = resources\\textures\\status_enabled.png

[ResourceStatusDisabled]
filename = resources\\textures\\status_disabled.png

"""
        # 角色头像层与文字层（一页一个）
        for mod in self.mods:
            content += f"""[ResourceAvatar{mod.character_id}]
filename = resources\\textures\\character_{mod.character_id}_avatar.png

[ResourceText{mod.character_id}]
filename = resources\\textures\\character_{mod.character_id}_text.png


"""

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"主配置已生成: {output_path}")
            print(f"  - 角色数量: {total_chars}")
            print(f"  - 角色ID范围: 0-{max_id}")
            return True
        except Exception as e:
            print(f"生成主配置失败: {e}")
            return False

    def modify_mod_ini(self, mod: ModInfo, create_backup: bool = True) -> bool:
        """修改所有ini文件，注入本地选择器变量和上下键处理器，添加选择器条件"""
        try:
            if create_backup:
                self.backup_mod(mod)

            total_chars = len(self.mods)
            max_id = total_chars - 1 if total_chars > 0 else 0
            local_var = f'iooh_s{mod.character_id}'
            enable_var = f'iooh_en{mod.character_id}'
            ui_var = f'iooh_ui{mod.character_id}'

            # IOOH 菜单四个控制键（与主 ini 共用同一份，确保巧合同步成立）
            key_toggle = self.iooh_keys.key_line("toggle_menu")
            key_prev = self.iooh_keys.key_line("prev_char")
            key_next = self.iooh_keys.key_line("next_char")
            key_enable = self.iooh_keys.key_line("enable_toggle")

            # 上下键循环：自减/自增 + 回绕（O(1)，不随角色数膨胀）。
            # 仅菜单可见（$iooh_ui<id> == 1）时才执行切换。
            if total_chars > 0:
                cmd_up_block = (
                    f'if ${ui_var} == 1\n'
                    f'    ${local_var} = ${local_var} - 1\n'
                    f'    if ${local_var} < 0\n'
                    f'        ${local_var} = {max_id}\n'
                    f'    endif\n'
                    f'endif'
                )
                cmd_down_block = (
                    f'if ${ui_var} == 1\n'
                    f'    ${local_var} = ${local_var} + 1\n'
                    f'    if ${local_var} > {max_id}\n'
                    f'        ${local_var} = 0\n'
                    f'    endif\n'
                    f'endif'
                )
            else:
                cmd_up_block = ''
                cmd_down_block = ''

            selector_block = f"""; ===== IOOH 本地选择器 =====
; 显隐镜像（仅同步本地门控变量，不负责实际显示；
;          与菜单侧 $show_character_ui 监听同一物理键、各自相同计数实现巧合同步）
[Key_{local_var}_ToggleVisible]
key = {key_toggle}
run = CommandList_{local_var}_ToggleVisible

[CommandList_{local_var}_ToggleVisible]
if ${ui_var} == 1
    ${ui_var} = 0
else
    ${ui_var} = 1
endif

[Key_{local_var}_SelectUp]
key = {key_prev}
run = CommandList_{local_var}_SelectUp

[CommandList_{local_var}_SelectUp]
{cmd_up_block}

[Key_{local_var}_SelectDown]
key = {key_next}
run = CommandList_{local_var}_SelectDown

[CommandList_{local_var}_SelectDown]
{cmd_down_block}

[Key_{local_var}_ToggleUI]
key = {key_enable}
run = CommandList_{local_var}_ToggleUI

[CommandList_{local_var}_ToggleUI]
if ${ui_var} == 1
    if ${local_var} == {mod.character_id}
        if ${enable_var} == 1
            ${enable_var} = 0
        else
            ${enable_var} = 1
        endif
    endif
endif
; ===== IOOH 本地选择器结束 ====="""

            # 按来源 ini 分组（解析时已记录 binding.ini_file），
            # 直接归组而非靠 section 名反查文件——后者在跨 ini 同名 section 时会把
            # 所有同名绑定都归到第一个匹配文件，导致其余文件漏注入。
            bindings_by_file: Dict[str, List[ModKeyBinding]] = {}
            for binding in mod.key_bindings:
                bindings_by_file.setdefault(binding.ini_file, []).append(binding)

            # 每个含按键的 ini 都是自洽单元：自带 [Constants] 变量声明 + 完整选择器块
            # （显隐/上一个/下一个/启用 处理器）。
            # 不依赖跨 ini 共享变量——3DMigoto 的 Key condition 只能可靠引用同文件变量，
            # `global` 并不会按同名跨 ini 合并成一份共享存储（实测：只在宿主 ini 注入处理器时，
            # 仅宿主 ini 生效，其余只声明+引用 $iooh_en 的文件因自己那份永远为 0 而失效）。
            # 因此沿用与「跨 mod 巧合同步」一致的方案：每个文件各持一份 $iooh_s/$iooh_en/$iooh_ui，
            # 各自监听同一物理键、做相同计数，天然保持数值同步；多份启用键处理器分别翻转
            # 各自文件的 $iooh_en（互不共享，不会相互抵消）。
            # 无按键绑定的 ini 不引用任何 iooh 变量，无需注入（仅清理旧注入）。
            for ini_file in mod.ini_files:
                with open(ini_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 清理旧的IOOH注入内容
                content = self._strip_local_selector(content)

                bindings = bindings_by_file.get(ini_file, [])

                # 无按键绑定：写回清理后的内容即可，不注入变量与选择器块。
                if not bindings:
                    self._ensure_writable(ini_file)
                    with open(ini_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    continue

                # 在本 ini 的 [Constants] 声明这些变量（无则新建 [Constants]）：
                # $iooh_s<id>：聚焦角色（初始 0，让上一个/下一个立即可循环切换）
                # $iooh_en<id>：启用标志（初始 0，启用键对当前聚焦角色翻转）
                # $iooh_ui<id>：菜单显隐镜像（初始 0，显隐键与菜单侧 $show_character_ui 巧合同步；
                #               仅作门控，菜单隐藏时切换/启用键不生效）
                decls = f'global ${local_var} = 0\nglobal ${enable_var} = 0\nglobal ${ui_var} = 0\n'
                constants_match = re.search(r'(\[Constants\]\s*\n)', content)
                if constants_match:
                    insert_pos = constants_match.end()
                    content = content[:insert_pos] + decls + content[insert_pos:]
                else:
                    content = f'[Constants]\n{decls}\n' + content

                # 给本 ini 内的按键 section 补 condition 门控
                binding_map = {b.section_name: b for b in bindings}
                sections = list(self._iter_sections(content))
                if sections:
                    new_parts = []
                    last_idx = 0
                    for section_name, start, end, section_text in sections:
                        new_parts.append(content[last_idx:start])
                        if section_name in binding_map:
                            new_section = self._modify_key_section_with_context(
                                section_text,
                                mod.character_id,
                                local_var,
                                enable_var,
                                binding_map[section_name].key,
                            )
                            new_parts.append(new_section)
                        else:
                            new_parts.append(section_text)
                        last_idx = end
                    new_parts.append(content[last_idx:])
                    content = ''.join(new_parts)

                # 注入完整选择器块：每个含按键的 ini 各注入一份，互不共享、靠相同计数巧合同步
                first_key_match = re.search(r'\[Key\w+\]', content)
                if first_key_match:
                    insert_pos = first_key_match.start()
                    content = content[:insert_pos] + '\n\n' + selector_block + '\n' + content[insert_pos:]
                else:
                    # 没有Key section，追加到文件末尾
                    content = content.rstrip('\n') + '\n\n' + selector_block + '\n'

                self._ensure_writable(ini_file)
                with open(ini_file, 'w', encoding='utf-8') as f:
                    f.write(content)

            return True

        except Exception as e:
            print(f"修改 {mod.name} 失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _modify_key_section_with_context(self, section_content: str, character_id: int, local_var: str, enable_var: str, key_value: str = "") -> str:
        """Modify one key section, inject enable condition without changing the key.

        门控条件用启用标志 ${enable_var} == 1：角色被 VK_DOWN 启用后键才生效，
        切换聚焦不影响已启用角色的键继续工作。

        key_value 非空时，把该 section 的 key 行重写为该值（承载 UI 改键，
        也是改键落盘到 ini 的唯一途径——ini 自身即改键的真实来源）。
        """
        section_content = self._normalize_section_text(section_content)
        lines = section_content.split('\n')
        modified_lines = []
        has_condition = False
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            # 重写 key 行为 key_value（保留缩进与行内注释）
            if key_value and re.match(r'(?i)^key\s*=', stripped):
                indent = line[:len(line) - len(line.lstrip())]
                comment = ''
                value_part = line.split('=', 1)[1]
                if ';' in value_part:
                    comment = ' ;' + value_part.split(';', 1)[1]
                modified_lines.append(f'{indent}key = {key_value}{comment}')
                index += 1
                continue

            if re.match(r'(?i)^condition\s*=', stripped):
                has_condition = True
                cond_match = re.match(r'(?i)^(\s*condition\s*=\s*)(.*)$', line)
                if not cond_match:
                    modified_lines.append(line)
                    index += 1
                    continue

                cond_text = cond_match.group(2).strip()
                if not cond_text and index + 1 < len(lines):
                    next_line = lines[index + 1]
                    next_stripped = next_line.strip()
                    is_field_line = re.match(
                        r'(?i)^\s*(?:[A-Za-z_]\w*|\$[A-Za-z_]\w*)\s*=(?!=)',
                        next_line,
                    )
                    if next_stripped and not next_stripped.startswith('[') and not is_field_line:
                        cond_text = next_stripped
                        index += 1

                # remove old iooh selectors
                cond_clean = re.sub(r'\s*&&\s*\$iooh_en\d*\s*==\s*\d+', '', cond_text)
                cond_clean = re.sub(r'\$iooh_en\d*\s*==\s*\d+\s*&&\s*', '', cond_clean)
                cond_clean = re.sub(r'\$iooh_en\d*\s*==\s*\d+', '', cond_clean)
                cond_clean = re.sub(r'\s*&&\s*\$iooh_s\d*\s*==\s*\d+', '', cond_clean)
                cond_clean = re.sub(r'\$iooh_s\d*\s*==\s*\d+\s*&&\s*', '', cond_clean)
                cond_clean = re.sub(r'\$iooh_s\d*\s*==\s*\d+', '', cond_clean)
                cond_clean = re.sub(r'\s*&&\s*\$iooh_sel\s*==\s*\d+', '', cond_clean)
                cond_clean = re.sub(r'\$iooh_sel\s*==\s*\d+\s*&&\s*', '', cond_clean)
                cond_clean = re.sub(r'\$iooh_sel\s*==\s*\d+', '', cond_clean)
                cond_clean = re.sub(r'\s*&&\s*\$\w+_sel\s*==\s*\d+', '', cond_clean)
                cond_clean = re.sub(r'\$\w+_sel\s*==\s*\d+\s*&&\s*', '', cond_clean)
                cond_clean = re.sub(r'\$\w+_sel\s*==\s*\d+', '', cond_clean)
                cond_clean = cond_clean.strip()
                indent = line[:len(line) - len(line.lstrip())]
                if cond_clean:
                    modified_lines.append(f'{indent}condition = {cond_clean} && ${enable_var} == 1')
                else:
                    modified_lines.append(f'{indent}condition = ${enable_var} == 1')
            else:
                modified_lines.append(line)
            index += 1

        if not has_condition:
            new_lines = []
            for line in modified_lines:
                new_lines.append(line)
                stripped = line.strip()
                if stripped.startswith('key =') or stripped.startswith('key='):
                    indent = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f'{indent}condition = ${enable_var} == 1')
            modified_lines = new_lines

        return '\n'.join(modified_lines)

    def _strip_local_selector(self, content: str) -> str:
        """移除各mod ini中的IOOH注入内容（本地选择器变量、上下键、旧CommandList）"""
        # 移除 global persist $selected_character 行
        content = re.sub(r'^.*\$selected_character.*\n', '', content, flags=re.MULTILINE)

        # 移除本地选择器变量声明 global $iooh_s<N> / $iooh_en<N> / $iooh_ui<N> = 0 或 -1
        content = re.sub(r'^global \$iooh_s\d+\s*=\s*-?\d+\s*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^global \$iooh_en\d+\s*=\s*-?\d+\s*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^global \$iooh_ui\d+\s*=\s*-?\d+\s*\n', '', content, flags=re.MULTILINE)

        # 移除旧版 [KeySelectUp]/[KeySelectDown] 及其 CommandList
        content = re.sub(r'\[KeySelectUp\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[KeySelectDown\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandListSelectUp\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandListSelectDown\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 移除新版本地选择器：起止标记之间整块删除（标记、夹缝注释、全部 Key/CommandList
        # section 一次清掉）。起止标记由注入时同一字符串原子写入，不会只剩半边；
        # 按块删可避免夹在标记与首个 section 之间的说明注释逐次累积。
        content = re.sub(
            r';\s*=====\s*IOOH 本地选择器\s*=====[\s\S]*?;\s*=====\s*IOOH 本地选择器结束\s*=====\s*\n?',
            '', content, flags=re.MULTILINE,
        )

        # 移除旧的 IOOH CommandList sections（上次脚本生成的）
        content = re.sub(r'\[CommandList_IOOH_\w+\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 移除标记块
        content = re.sub(r';\s*=====\s*角色选择器控制.*?;\s*=====\s*选择器控制结束\s*=====?\n?', '', content, flags=re.MULTILINE | re.DOTALL)
        content = re.sub(r';\s*=====\s*IOOH 角色选择器 CommandList\s*=====\s*\n?', '', content, flags=re.MULTILINE)

        # 移除测试用的本地选择变量（如 $perlica_sel）和相关sections
        content = re.sub(r'^;.*测试用.*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^global \$\w+_sel\s*=\s*\d+\s*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[Key_\w+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandList_\w+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 清理多余空行（3个以上连续空行压缩为2个）
        content = re.sub(r'\n{4,}', '\n\n\n', content)

        return content
