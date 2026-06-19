#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - EFMI按键上下文配置工具 v4.0（本地变量版）

核心机制：本地选择器变量
- 每个mod声明自己的本地选择器变量 $iooh_s<id>
- 每个mod拥有自己的 VK_LEFT/VK_RIGHT 处理器，同步循环选择器值
  （三方监听同一物理按键、各自相同计数，实现无通信巧合同步）
- Key section 保留原有type，condition 使用本地变量判断
- 3DMigoto Key condition 只能可靠引用同文件变量，跨文件引用无效
"""

import os
import re
import shutil
import json
import stat
import subprocess
import sys
from typing import Dict, List
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


class ModKeyBinding:
    """mod按键绑定信息"""
    def __init__(self, section_name: str, key: str, variable: str, mod_path: str, ini_file: str = ""):
        self.section_name = section_name
        self.key = key
        self.variable = variable
        self.mod_path = mod_path
        self.ini_file = ini_file  # 该绑定所属的 ini 文件（解析时记录，分组时直接使用）
        self.description = ""


class ModInfo:
    """mod信息"""
    def __init__(self, name: str, path: str, ini_files: List[str] = None):
        self.name = name
        self.path = path
        self.ini_files = ini_files or []
        self.character_id = 0  # 角色ID（用于选择器变量）
        self.key_bindings: List[ModKeyBinding] = []
        self.has_backup = False
        self.ini_file_backups: Dict[str, bool] = {}


class EFMIKeyConfigurator:
    """EFMI按键配置器"""
    
    def __init__(self):
        self.mods: List[ModInfo] = []
        self.mods_directory = ""
        self.config_file = os.path.join(self._get_output_dir(), "efmi_key_config.json")

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
        self.config_file = os.path.join(self._resolve_output_dir(), "efmi_key_config.json")
        self.mods.clear()
        
        # 先恢复备份文件，确保从干净状态开始
        self.restore_backups(directory)
        
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
        """Extract a display-friendly key string (e.g., Alt+1)."""
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

        skip_tokens = {
            'no_modifiers',
            'any_modifiers',
            'allow_modifiers',
            'no_ctrl',
            'no_alt',
            'no_shift',
            'no_lctrl',
            'no_rctrl',
            'no_lalt',
            'no_ralt',
            'no_lshift',
            'no_rshift',
        }
        modifier_map = {
            'ctrl': 'Ctrl',
            'lctrl': 'LCtrl',
            'rctrl': 'RCtrl',
            'shift': 'Shift',
            'lshift': 'LShift',
            'rshift': 'RShift',
            'alt': 'Alt',
            'lalt': 'LAlt',
            'ralt': 'RAlt',
        }

        for line in key_lines:
            cleaned_line = line.split(';', 1)[0].strip()
            tokens = [p for p in re.split(r'[\s,]+', cleaned_line) if p]
            if not tokens:
                continue

            mods = []
            main_keys = []
            for token in tokens:
                lowered = token.lower()
                if lowered in skip_tokens:
                    continue
                if lowered in modifier_map:
                    mods.append(modifier_map[lowered])
                    continue
                main_keys.append(token)

            if not main_keys:
                continue

            if mods:
                return "+".join(mods + [main_keys[0]])
            return main_keys[0]

        return key_lines[0].strip()

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

; NUMPAD0: 呼出/隐藏菜单
[KeyEFMI_ToggleMenu]
key = no_ctrl no_alt VK_NUMPAD0
run = CommandList_ToggleMenu

[CommandList_ToggleMenu]
if $show_character_ui == 1
    $show_character_ui = 0
else
    $show_character_ui = 1
endif

; PageUp: 上一个角色（仅菜单显示时响应，隐藏时保留当前选择）
[KeyEFMI_PrevChar]
condition = $show_character_ui == 1
key = no_ctrl no_alt VK_PRIOR
run = CommandList_PrevChar

[CommandList_PrevChar]
"""
        # 上一个角色：自减并回绕（O(1)，不随角色数膨胀）
        if total_chars > 0:
            content += f"$iooh_sel = $iooh_sel - 1\nif $iooh_sel < 0\n    $iooh_sel = {max_id}\nendif\n"

        content += """
; PageDown: 下一个角色（仅菜单显示时响应，隐藏时保留当前选择）
[KeyEFMI_NextChar]
condition = $show_character_ui == 1
key = no_ctrl no_alt VK_NEXT
run = CommandList_NextChar

[CommandList_NextChar]
"""
        # 下一个角色：自增并回绕（O(1)，不随角色数膨胀）
        if total_chars > 0:
            content += f"$iooh_sel = $iooh_sel + 1\nif $iooh_sel > {max_id}\n    $iooh_sel = 0\nendif\n"

        content += """
; NUMPAD2: 启用/禁用当前聚焦的角色（翻转该 id 对应的 $iooh_en<id>，仅菜单显示时响应）
[KeyEFMI_EnableToggle]
condition = $show_character_ui == 1
key = no_ctrl no_alt VK_NUMPAD2
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
; NUMPAD0: 菜单显隐镜像（仅同步本地门控变量，不负责实际显示；
;          与菜单侧 $show_character_ui 监听同一物理键、各自相同计数实现巧合同步）
[Key_{local_var}_ToggleVisible]
key = no_ctrl no_alt VK_NUMPAD0
run = CommandList_{local_var}_ToggleVisible

[CommandList_{local_var}_ToggleVisible]
if ${ui_var} == 1
    ${ui_var} = 0
else
    ${ui_var} = 1
endif

[Key_{local_var}_SelectUp]
key = no_ctrl no_alt VK_PRIOR
run = CommandList_{local_var}_SelectUp

[CommandList_{local_var}_SelectUp]
{cmd_up_block}

[Key_{local_var}_SelectDown]
key = no_ctrl no_alt VK_NEXT
run = CommandList_{local_var}_SelectDown

[CommandList_{local_var}_SelectDown]
{cmd_down_block}

[Key_{local_var}_ToggleUI]
key = no_ctrl no_alt VK_NUMPAD2
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
            # （NUMPAD0/2/PageUp/PageDown 处理器）。
            # 不依赖跨 ini 共享变量——3DMigoto 的 Key condition 只能可靠引用同文件变量，
            # `global` 并不会按同名跨 ini 合并成一份共享存储（实测：只在宿主 ini 注入处理器时，
            # 仅宿主 ini 生效，其余只声明+引用 $iooh_en 的文件因自己那份永远为 0 而失效）。
            # 因此沿用与「跨 mod 巧合同步」一致的方案：每个文件各持一份 $iooh_s/$iooh_en/$iooh_ui，
            # 各自监听同一物理键、做相同计数，天然保持数值同步；多份 NUMPAD2 处理器分别翻转
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
                # $iooh_s<id>：聚焦角色（初始 0，让 PageUp/PageDown 立即可循环切换）
                # $iooh_en<id>：启用标志（初始 0，NUMPAD2 对当前聚焦角色翻转）
                # $iooh_ui<id>：菜单显隐镜像（初始 0，NUMPAD0 与菜单侧 $show_character_ui 巧合同步；
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
    
    def _modify_key_section_with_context(self, section_content: str, character_id: int, local_var: str, enable_var: str) -> str:
        """Modify one key section, inject enable condition without changing the key.

        门控条件用启用标志 ${enable_var} == 1：角色被 VK_DOWN 启用后键才生效，
        切换聚焦不影响已启用角色的键继续工作。
        """
        section_content = self._normalize_section_text(section_content)
        lines = section_content.split('\n')
        modified_lines = []
        has_condition = False
        index = 0

        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

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

        # 移除新版本地选择器 Key 和 CommandList sections（SelectUp/Down + ToggleUI + ToggleVisible）
        content = re.sub(r'\[Key_iooh_s\d+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandList_iooh_s\d+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 移除旧的 IOOH CommandList sections（上次脚本生成的）
        content = re.sub(r'\[CommandList_IOOH_\w+\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 移除标记块
        content = re.sub(r';\s*=====\s*角色选择器控制.*?;\s*=====\s*选择器控制结束\s*=====?\n?', '', content, flags=re.MULTILINE | re.DOTALL)
        content = re.sub(r';\s*=====\s*IOOH 角色选择器 CommandList\s*=====\s*\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r';\s*=====\s*IOOH 本地选择器\s*=====\s*\n?', '', content, flags=re.MULTILINE)
        content = re.sub(r';\s*=====\s*IOOH 本地选择器结束\s*=====\s*\n?', '', content, flags=re.MULTILINE)

        # 移除测试用的本地选择变量（如 $perlica_sel）和相关sections
        content = re.sub(r'^;.*测试用.*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^global \$\w+_sel\s*=\s*\d+\s*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[Key_\w+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandList_\w+_(?:Select(?:Up|Down)|ToggleUI|ToggleVisible)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 清理多余空行（3个以上连续空行压缩为2个）
        content = re.sub(r'\n{4,}', '\n\n\n', content)

        return content


GUI_TRANSLATIONS = {
    "title": {"zh": "EFMI IOOH v1.4", "en": "EFMI IOOH v1.4"},
    "mod_dir": {"zh": "Mods目录:", "en": "Mods Directory:"},
    "browse": {"zh": "打开文件夹", "en": "open folder"},
    "scan": {"zh": "自动配置并保存", "en": "Auto Config & Save"},
    "lang_btn": {"zh": "🌐 English", "en": "🌐 中文"},
    "col_mod_name": {"zh": "Mod名称", "en": "Mod Name"},
    "col_char_id": {"zh": "角色ID", "en": "Char ID"},
    "col_function": {"zh": "功能说明", "en": "Function"},
    "col_key": {"zh": "按键", "en": "Key"},
    "col_status": {"zh": "状态", "en": "Status"},
    "status_configured": {"zh": "✓ 已配置", "en": "✓ Configured"},
    "log_frame": {"zh": "操作日志", "en": "Operation Log"}
}

class KeyConfiguratorGUI:
    """图形界面"""
    
    def __init__(self):
        self.configurator = EFMIKeyConfigurator()
        self.lang = "zh"
        
        self.root = tk.Tk()
        
        # 隐藏窗口避免闪烁
        self.root.withdraw()
        
        # 尝试加载自定义图标
        try:
            icon_path = os.path.join(self.configurator._get_bundle_dir(), "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            elif os.path.exists("icon.ico"):
                self.root.iconbitmap("icon.ico")
        except Exception:
            pass  # 如果图标加载失败，静默忽略，继续使用默认图标
            
        self.root.geometry("1400x800")
        self.root.minsize(1000, 600)
        
        # ttk 样式优化
        style = ttk.Style()
        style.configure("TButton", padding=5)
        style.configure("TLabel", padding=2)
        
        self._create_widgets()
        self._update_texts()
        
        # 居中并显示窗口
        self.root.update_idletasks()
        self.root.deiconify()
        
    def _tr(self, key: str) -> str:
        """获取翻译文本"""
        return GUI_TRANSLATIONS.get(key, {}).get(self.lang, key)

    def _toggle_lang(self):
        """切换中英文"""
        self.lang = "en" if self.lang == "zh" else "zh"
        self._update_texts()
        
    def _update_texts(self):
        """刷新UI文本"""
        self.root.title(self._tr("title"))
        self.lbl_mod_dir.config(text=self._tr("mod_dir"))
        self.btn_browse.config(text=self._tr("browse"))
        self.btn_scan.config(text=self._tr("scan"))
        self.btn_lang.config(text=self._tr("lang_btn"))
        
        self.tree.heading("mod_name", text=self._tr("col_mod_name"))
        self.tree.heading("char_id", text=self._tr("col_char_id"))
        self.tree.heading("function", text=self._tr("col_function"))
        self.tree.heading("key", text=self._tr("col_key"))
        self.tree.heading("status", text=self._tr("col_status"))
        
        # 刷新所有行的状态文本
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, 'values'))
            if vals:
                # 状态位于第5列（索引4）
                vals[4] = self._tr("status_configured")
                self.tree.item(item, values=vals)
        
        self.log_frame.config(text=self._tr("log_frame"))
        
    def _create_widgets(self):
        """创建界面组件"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        self.lbl_mod_dir = ttk.Label(toolbar)
        self.lbl_mod_dir.pack(side=tk.LEFT, padx=(0, 5))
        
        self.dir_entry = ttk.Entry(toolbar, width=60)
        self.dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.dir_entry.insert(0, r"d:\ikun\Downloads\endfield")
        
        self.btn_browse = ttk.Button(toolbar, command=self._browse_directory)
        self.btn_browse.pack(side=tk.LEFT, padx=2)
        self.btn_scan = ttk.Button(toolbar, command=self._scan_mods)
        self.btn_scan.pack(side=tk.LEFT, padx=2)
        
        # 语言切换按钮靠右
        self.btn_lang = ttk.Button(toolbar, command=self._toggle_lang)
        self.btn_lang.pack(side=tk.RIGHT, padx=5)
        
        # 主要内容区域
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建表格
        columns = ("mod_name", "char_id", "function", "key", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        self.tree.column("mod_name", width=250, anchor=tk.W)
        self.tree.column("char_id", width=80, anchor=tk.CENTER)
        self.tree.column("function", width=200, anchor=tk.W)
        self.tree.column("key", width=150, anchor=tk.W)
        self.tree.column("status", width=120, anchor=tk.CENTER)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部日志区域
        self.log_frame = ttk.LabelFrame(self.root)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _browse_directory(self):
        """浏览目录"""
        directory = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
    
    def _scan_mods(self):
        """扫描mods"""
        directory = self.dir_entry.get()
        if not os.path.exists(directory):
            messagebox.showerror("错误", "目录不存在！")
            return
        
        self.log(f"开始扫描目录: {directory}")
        self.log("检测所有热键绑定...")
        mods = self.configurator.scan_mods(directory)
        self.log(f"扫描完成，发现 {len(mods)} 个包含热键绑定的mod")
        
        # 显示检测到的ini文件详情
        for mod in mods:
            ini_names = [os.path.basename(f) for f in mod.ini_files]
            key_count = len(mod.key_bindings)
            self.log(f"  ✓ {mod.name}: {', '.join(ini_names)} ({key_count}个按键绑定)")

        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not mods:
            self.log("未检测到包含热键绑定的mod")
            messagebox.showwarning("提示", "未检测到包含热键绑定的mod\n\n请确保mod文件夹中包含 key = 的按键配置")
            return
        
        # 立即执行备份和修改
        self.log("开始自动备份并注入选择器上下文...")
        success_count = 0
        for mod in mods:
            if self.configurator.modify_mod_ini(mod):
                success_count += 1
                self.log(f"  ✓ {mod.name} 按键已配置 (ID={mod.character_id}, {len(mod.key_bindings)}个按键)")
            else:
                self.log(f"  ✗ {mod.name} 配置失败")
        
        self.log(f"自动配置完成: {success_count}/{len(mods)}")

        # 填充表格
        for mod in mods:
            for binding in mod.key_bindings:
                self.tree.insert("", tk.END, values=(
                    mod.name,
                    mod.character_id,
                    binding.description,
                    binding.key,
                    self._tr("status_configured")
                ))
        
        total_bindings = sum(len(m.key_bindings) for m in mods)
        total_ini_files = sum(len(m.ini_files) for m in mods)
        self.log(f"表格更新完成，共扫描 {total_ini_files} 个ini文件，{total_bindings} 个按键绑定")
        
        # 保存配置文件
        if self.configurator.save_config():
            self.log(f"✓ 配置已保存到 {self.configurator.config_file}")
        
        # 生成主 IOOHmod.ini 配置文件（动态角色列表）
        if self.configurator.generate_main_mod_ini():
            self.log(f"✓ 主UI配置已生成: IOOHmod.ini (角色数:{len(mods)})")

        # 自动生成UI纹理
        self.log("正在生成UI纹理...")
        try:
            from generate_ui_textures import UITextureGenerator
            generator = UITextureGenerator(base_output_dir=self.configurator._resolve_output_dir())
            generator.generate_all()
            self.log("✓ UI纹理已自动生成")
        except Exception as e:
            self.log(f"✗ UI纹理生成异常: {e}")

        # 删除中间文件
        try:
            config_path = self.configurator.config_file
            if os.path.exists(config_path):
                os.remove(config_path)
                self.log("✓ 已清理中间文件 efmi_key_config.json")
        except Exception as e:
            self.log(f"✗ 清理中间文件失败: {e}")

        # 显示完成信息
        self.log("")
        self.log("=" * 60)
        self.log("配置完成！使用说明：")
        self.log("1. 小键盘0 显示/隐藏UI，PageUp/PageDown 切换角色，小键盘2 启用/禁用")
        self.log("2. 热键仅在对应角色被选中时生效，实现热键复用")
        self.log("3. 无需修改 d3dx.ini")
        self.log("")
        self.log("=" * 60)
    
    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()




def main():
    app = KeyConfiguratorGUI()
    app.run()


if __name__ == "__main__":
    main()
