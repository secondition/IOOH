#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - EFMI按键上下文配置工具 v4.0（本地变量版）

核心机制：本地选择器变量
- 每个mod声明自己的本地选择器变量 $iooh_s<id>
- 每个mod拥有自己的 VK_PRIOR/VK_NEXT 处理器，同步循环选择器值
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
    def __init__(self, section_name: str, key: str, variable: str, mod_path: str):
        self.section_name = section_name
        self.key = key
        self.variable = variable
        self.mod_path = mod_path
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
        self.has_character_detection = False  # 是否已有角色检测变量


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

    def _ensure_runtime_shader_assets(self):
        """Copy bundled shader files next to the executable for 3DMigoto to read."""
        source_dir = os.path.join(self._get_bundle_dir(), "shaders")
        target_dir = os.path.join(self._resolve_output_dir(), "shaders")
        if not os.path.isdir(source_dir):
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
        
    def restore_backups(self, directory: str):
        """恢复所有备份文件，确保从干净状态开始"""
        print("恢复备份文件...")
        restored_count = 0
        
        for root, dirs, files in os.walk(directory):
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
                    "has_character_detection": mod.has_character_detection,
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
                    for root, _, files in os.walk(item_path):
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
                        # 检查是否已有角色检测变量
                        if self._check_has_character_detection(ini_file):
                            mod.has_character_detection = True
                    
                    # 只添加有按键绑定的mod
                    if mod.key_bindings:
                        self.mods.append(mod)
        
        # 按名称排序
        self.mods.sort(key=lambda m: m.name)
        
        # 自动分配character ID
        for idx, mod in enumerate(self.mods):
            mod.character_id = idx
            
        return self.mods
    
    def _check_has_character_detection(self, ini_file: str) -> bool:
        """检查ini文件是否已有角色检测变量（如$active, $object_detected等）"""
        try:
            with open(ini_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找常见的角色检测变量
            detection_patterns = [
                r'\$active\d*\s*=\s*[01]',
                r'\$object_detected\s*=\s*[01]',
                r'\$mod_enabled\s*=\s*[01]'
            ]
            
            for pattern in detection_patterns:
                if re.search(pattern, content):
                    return True
            return False
            
        except Exception:
            return False

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
                
                # 处理所有包含 key = 的热键绑定
                binding = ModKeyBinding(section_name, key, variable or f"${section_name}", mod.path)
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

        # === 布局参数（基于16:9屏幕等比例缩放） ===
        aspect = 16 / 9       # 屏幕宽高比
        left_x = 0.01         # 左侧起始X
        char_w = 0.15         # 角色项宽度
        char_h = char_w * aspect * (100 / 500)  # 纹理500x100，等比缩放
        gap = 0.006           # 行间距
        
        help_w = char_w
        help_h = help_w * aspect * (60 / 500)   # 帮助纹理500x60
        
        # 从底部向上计算起始Y
        bottom_margin = 0.02
        total_height = total_chars * char_h + max(0, total_chars - 1) * gap
        total_ui_height = total_height + 2 * help_h + 3 * gap
        default_start_y = 1.0 - bottom_margin - total_ui_height

        # 面板背景大小
        panel_w = char_w + 0.02
        panel_h_val = total_ui_height + 0.02

        # 主体内容
        content = f"""; EFMI 主UI管理器 - 自动生成
; 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
; 总角色数: {total_chars}

{char_mapping}

[Constants]
global $show_character_ui = 1
global $total_characters = {total_chars}
global $iooh_sel = 0

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

; PageUp: 反向循环（$iooh_sel == -1 时不响应）
[KeyEFMI_SelectUp]
key = VK_PRIOR
run = CommandList_SelectUp

[CommandList_SelectUp]
"""
        # 生成上键循环逻辑，-1不在条件中所以自动跳过
        for i in range(total_chars):
            keyword = "if" if i == 0 else "elif"
            prev_val = (i - 1) % total_chars
            content += f"{keyword} $iooh_sel == {i}\n    $iooh_sel = {prev_val}\n"
        if total_chars > 0:
            content += "endif\n"

        content += """
; PageDown: 正向循环（$iooh_sel == -1 时不响应）
[KeyEFMI_SelectDown]
key = VK_NEXT
run = CommandList_SelectDown

[CommandList_SelectDown]
"""
        for i in range(total_chars):
            keyword = "if" if i == 0 else "elif"
            next_val = (i + 1) % total_chars
            content += f"{keyword} $iooh_sel == {i}\n    $iooh_sel = {next_val}\n"
        if total_chars > 0:
            content += "endif\n"

        content += """
; Enter: 切换UI显示，同时切换 $iooh_sel（-1=禁用选择器）
[KeyEFMI_ToggleUI]
key = no_ctrl no_alt VK_RETURN
run = CommandList_ToggleUI

[CommandList_ToggleUI]
if $show_character_ui == 1
    $show_character_ui = 0
    $iooh_sel = -1
else
    $show_character_ui = 1
    $iooh_sel = 0
endif

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
        # 背景和帮助提示图层
        content += f"""
; ===== 背景面板 =====
x87 = {panel_w:.4f}
y87 = {panel_h_val:.4f}
z87 = $ui_x - 0.01
w87 = $ui_y - 0.01
ps-t100 = ResourcePanelBackground
Draw = 4,0

; ===== 帮助提示 =====
x87 = {help_w:.4f}
y87 = {help_h:.4f}
z87 = $ui_x
w87 = $ui_y + {total_height + gap:.4f}
ps-t100 = ResourceHelpPgUpDn
Draw = 4,0

w87 = $ui_y + {total_height + gap + help_h + gap:.4f}
ps-t100 = ResourceHelpEnter
Draw = 4,0

; ===== 角色列表（全部显示，选中高亮） =====
x87 = {char_w:.4f}
y87 = {char_h:.4f}
z87 = $ui_x
"""
        for i, mod in enumerate(self.mods):
            offset_y = i * (char_h + gap)
            content += f"w87 = $ui_y + {offset_y:.4f}\n"
            content += f"if $iooh_sel == {mod.character_id}\n"
            content += f"    ps-t100 = ResourceCharacter{mod.character_id}Selected\n"
            content += f"else\n"
            content += f"    ps-t100 = ResourceCharacter{mod.character_id}Normal\n"
            content += f"endif\n"
            content += "Draw = 4,0\n"

        # ===== 资源定义 =====
        content += """
; ===== 资源定义 =====
[ResourcePanelBackground]
filename = resources\\textures\\panel_background.png

[ResourceUIBackground]
filename = resources\\textures\\ui_background.png

[ResourceHelpPgUpDn]
filename = resources\\textures\\help_PgUp_PgDn__切换角色.png

[ResourceHelpEnter]
filename = resources\\textures\\help_Enter__显示_隐藏UI.png

"""
        # 角色纹理（normal + selected）
        for mod in self.mods:
            content += f"""[ResourceCharacter{mod.character_id}Normal]
filename = resources\\textures\\character_{mod.character_id}_normal.png

[ResourceCharacter{mod.character_id}Selected]
filename = resources\\textures\\character_{mod.character_id}_selected.png

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
            local_var = f'iooh_s{mod.character_id}'

            # 生成上下键 CommandList 循环逻辑
            cmd_up_lines = []
            cmd_down_lines = []
            for i in range(total_chars):
                keyword = "if" if i == 0 else "elif"
                next_up = (i - 1) % total_chars
                next_down = (i + 1) % total_chars
                cmd_up_lines.append(f'{keyword} ${local_var} == {i}\n    ${local_var} = {next_up}')
                cmd_down_lines.append(f'{keyword} ${local_var} == {i}\n    ${local_var} = {next_down}')
            if total_chars > 0:
                cmd_up_lines.append('endif')
                cmd_down_lines.append('endif')

            selector_block = f"""; ===== IOOH 本地选择器 =====
[Key_{local_var}_SelectUp]
key = VK_PRIOR
run = CommandList_{local_var}_SelectUp

[CommandList_{local_var}_SelectUp]
{chr(10).join(cmd_up_lines)}

[Key_{local_var}_SelectDown]
key = VK_NEXT
run = CommandList_{local_var}_SelectDown

[CommandList_{local_var}_SelectDown]
{chr(10).join(cmd_down_lines)}

[Key_{local_var}_ToggleUI]
key = no_ctrl no_alt VK_RETURN
run = CommandList_{local_var}_ToggleUI

[CommandList_{local_var}_ToggleUI]
if ${local_var} == -1
    ${local_var} = 0
else
    ${local_var} = -1
endif
; ===== IOOH 本地选择器结束 ====="""

            # 按ini文件分组处理按键绑定
            bindings_by_file: Dict[str, List[ModKeyBinding]] = {}
            for binding in mod.key_bindings:
                for ini_file in mod.ini_files:
                    try:
                        with open(ini_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if f'[{binding.section_name}]' in content:
                            if ini_file not in bindings_by_file:
                                bindings_by_file[ini_file] = []
                            bindings_by_file[ini_file].append(binding)
                            break
                    except:
                        continue

            # 修改每个ini文件
            for ini_file, bindings in bindings_by_file.items():
                with open(ini_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 清理旧的IOOH注入内容
                content = self._strip_local_selector(content)

                # 注入本地选择器变量到 [Constants] section
                constants_match = re.search(r'(\[Constants\]\s*\n)', content)
                if constants_match:
                    insert_pos = constants_match.end()
                    content = content[:insert_pos] + f'global ${local_var} = 0\n' + content[insert_pos:]

                # 修改每个按键绑定的Key section
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
                            )
                            new_parts.append(new_section)
                        else:
                            new_parts.append(section_text)
                        last_idx = end
                    new_parts.append(content[last_idx:])
                    content = ''.join(new_parts)

                # ?????? Key section ???????
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
    
    def _modify_key_section_with_context(self, section_content: str, character_id: int, local_var: str) -> str:
        """Modify one key section, inject selector condition without changing the key."""
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
                cond_clean = re.sub(r'\s*&&\s*\$iooh_s\d*\s*==\s*\d+', '', cond_text)
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
                    modified_lines.append(f'{indent}condition = {cond_clean} && ${local_var} == {character_id}')
                else:
                    modified_lines.append(f'{indent}condition = ${local_var} == {character_id}')
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
                    new_lines.append(f'{indent}condition = ${local_var} == {character_id}')
            modified_lines = new_lines

        return '\n'.join(modified_lines)

    def _strip_local_selector(self, content: str) -> str:
        """移除各mod ini中的IOOH注入内容（本地选择器变量、上下键、旧CommandList）"""
        # 移除 global persist $selected_character 行
        content = re.sub(r'^.*\$selected_character.*\n', '', content, flags=re.MULTILINE)

        # 移除本地选择器变量声明 global $iooh_s<N> = 0 或 -1
        content = re.sub(r'^global \$iooh_s\d+\s*=\s*-?\d+\s*\n', '', content, flags=re.MULTILINE)

        # 移除旧版 [KeySelectUp]/[KeySelectDown] 及其 CommandList
        content = re.sub(r'\[KeySelectUp\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[KeySelectDown\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandListSelectUp\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandListSelectDown\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

        # 移除新版本地选择器 Key 和 CommandList sections（SelectUp/Down + ToggleUI）
        content = re.sub(r'\[Key_iooh_s\d+_(?:Select(?:Up|Down)|ToggleUI)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandList_iooh_s\d+_(?:Select(?:Up|Down)|ToggleUI)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

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
        content = re.sub(r'\[Key_\w+_(?:Select(?:Up|Down)|ToggleUI)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)
        content = re.sub(r'\[CommandList_\w+_(?:Select(?:Up|Down)|ToggleUI)\][\s\S]*?(?=\n\[|\Z)', '', content, flags=re.MULTILINE)

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
    "col_detection": {"zh": "检测变量", "en": "Detection"},
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
        self.tree.heading("detection", text=self._tr("col_detection"))
        self.tree.heading("function", text=self._tr("col_function"))
        self.tree.heading("key", text=self._tr("col_key"))
        self.tree.heading("status", text=self._tr("col_status"))
        
        # 刷新所有行的状态文本
        for item in self.tree.get_children():
            vals = list(self.tree.item(item, 'values'))
            if vals:
                # 状态位于第6列（索引5）
                vals[5] = self._tr("status_configured")
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
        columns = ("mod_name", "char_id", "detection", "function", "key", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        self.tree.column("mod_name", width=250, anchor=tk.W)
        self.tree.column("char_id", width=80, anchor=tk.CENTER)
        self.tree.column("detection", width=100, anchor=tk.CENTER)
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
            detection_info = "有检测" if mod.has_character_detection else "无检测"
            self.log(f"  ✓ {mod.name}: {', '.join(ini_names)} ({key_count}个按键绑定) [{detection_info}]")

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
                    "✓" if mod.has_character_detection else "✗",
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
        self.log("1. PageUp/PageDown 切换角色，Enter 显示/隐藏UI")
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
