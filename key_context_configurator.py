#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - EFMI按键上下文配置工具 v4.0（本地变量版）

核心机制：本地选择器变量
- 每个mod声明自己的本地选择器变量 $iooh_s<id>
- 每个mod拥有自己的 VK_UP/VK_DOWN 处理器，同步循环选择器值
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
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog


class ModKeyBinding:
    """mod按键绑定信息"""
    def __init__(self, section_name: str, key: str, variable: str, mod_path: str):
        self.section_name = section_name
        self.key = key
        self.original_key = key
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
        self.config_file = "efmi_key_config.json"

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
                            "original_key": kb.original_key,
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
        self.mods.clear()
        
        # 先恢复备份文件，确保从干净状态开始
        self.restore_backups(directory)
        
        # 获取当前脚本所在目录的绝对路径，用于跳过自身
        script_dir = os.path.abspath(os.path.dirname(__file__))
        
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            
            # 跳过隐藏文件夹、EFMI文件夹和脚本自身所在的文件夹
            if item.startswith('.') or item.startswith('EFMI'):
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
    
    def _parse_ini_file(self, mod: ModInfo, ini_file_path: str):
        """解析ini文件，提取按键绑定 - 通用检测所有按键section"""
        try:
            with open(ini_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更通用的模式：查找所有包含 key = 的section（不限于Key开头）
            # 匹配格式：[任意section名] ... key = 某值 ... （可能有其他内容）
            section_pattern = r'\[([^\]]+)\]\s*\n((?:.*\n)*?)(?=\n\[|$)'
            sections = re.finditer(section_pattern, content, re.MULTILINE)
            
            for section_match in sections:
                section_name = section_match.group(1)
                section_content = section_match.group(2)
                
                # 跳过非按键相关的section（如Constants, Present等）
                if section_name in ['Constants', 'Present', 'Resources', 'CommandList', 'TextureOverride']:
                    continue
                if section_name.startswith('CommandList') or section_name.startswith('Resource'):
                    continue
                
                # 检查是否包含 key = 行
                key_match = re.search(r'key\s*=\s*(\S+)', section_content)
                if not key_match:
                    continue
                
                key = key_match.group(1)
                
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
    
    def _extract_variable_from_section(self, section_content: str):
        """从section内容中提取变量名"""
        var_pattern = r'\$(\w+)\s*='
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
        - 帮助文本（3行）
        - 角色列表（全部显示，选中高亮）
        - 选中角色的按键绑定（右侧）
        """
        if output_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = os.path.join(script_dir, "IOOHmod.ini")

        total_chars = len(self.mods)
        max_id = total_chars - 1 if total_chars > 0 else 0

        # 生成角色映射注释
        char_mapping = "; 角色ID映射:\n"
        for mod in self.mods:
            char_mapping += f"; {mod.character_id} = {mod.name}\n"

        # === 布局参数（基于16:9屏幕等比例缩放） ===
        aspect = 16 / 9       # 屏幕宽高比
        left_x = 0.01         # 左侧起始X
        help_w = 0.28         # 帮助文本宽度
        help_h = help_w * aspect * (60 / 500)   # 纹理500x60，等比缩放
        char_w = 0.15         # 角色项宽度
        char_h = char_w * aspect * (100 / 500)  # 纹理500x100，等比缩放
        gap = 0.006           # 行间距
        section_gap = 0.012   # 帮助文本与角色列表间距
        # === 按键图标网格参数 ===
        icon_w = 0.028        # 图标宽度
        icon_h = icon_w * aspect * (55 / 70)    # 纹理70x55，等比缩放
        icon_gap = 0.004      # 图标间距
        grid_cols = 5         # 5列
        kb_x = left_x + char_w + 0.015  # 按键图标区X起始

        # 从底部向上计算起始Y
        bottom_margin = 0.02
        total_height = (3 * help_h + 2 * gap +
                        section_gap +
                        total_chars * char_h + max(0, total_chars - 1) * gap)
        start_y = 1.0 - bottom_margin - total_height

        # 主体内容
        content = f"""; EFMI 主UI管理器 - 自动生成
; 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
; 总角色数: {total_chars}

{char_mapping}

[Constants]
global $show_character_ui = 1
global $total_characters = {total_chars}
global $iooh_sel = 0

; 上键: 反向循环（$iooh_sel == -1 时不响应）
[KeyEFMI_SelectUp]
key = VK_UP
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
; 下键: 正向循环（$iooh_sel == -1 时不响应）
[KeyEFMI_SelectDown]
key = VK_DOWN
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
; Enter: 切换UI显示，同时切换 $iooh_sel（-1=禁用小键盘）
[KeyEFMI_ToggleUI]
key = VK_RETURN
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
        content += f"""
; ===== 帮助文本（左下角顶部） =====
x87 = {help_w:.4f}
y87 = {help_h:.4f}
z87 = {left_x:.4f}
"""
        # 帮助文本3行
        y = start_y
        for i in range(1, 4):
            content += f"w87 = {y:.4f}\n"
            content += f"ps-t100 = ResourceHelpText{i}\n"
            content += "Draw = 4,0\n"
            y += help_h + gap

        # 角色列表
        y += section_gap - gap  # 额外间距
        content += f"""
; ===== 角色列表（全部显示，选中高亮） =====
x87 = {char_w:.4f}
y87 = {char_h:.4f}
z87 = {left_x:.4f}
"""
        char_start_y = y
        for i, mod in enumerate(self.mods):
            content += f"w87 = {y:.4f}\n"
            content += f"if $iooh_sel == {mod.character_id}\n"
            content += f"    ps-t100 = ResourceCharacter{mod.character_id}Selected\n"
            content += f"else\n"
            content += f"    ps-t100 = ResourceCharacter{mod.character_id}Normal\n"
            content += f"endif\n"
            content += "Draw = 4,0\n"
            y += char_h + gap

        # === 按键图标网格（角色列表右侧） ===
        # 15个小键盘按键: (VK名, 资源后缀, 文件名后缀)
        numpad_keys = [
            ("VK_NUMPAD0", "Num0", "num0"), ("VK_NUMPAD1", "Num1", "num1"),
            ("VK_NUMPAD2", "Num2", "num2"), ("VK_NUMPAD3", "Num3", "num3"),
            ("VK_NUMPAD4", "Num4", "num4"), ("VK_NUMPAD5", "Num5", "num5"),
            ("VK_NUMPAD6", "Num6", "num6"), ("VK_NUMPAD7", "Num7", "num7"),
            ("VK_NUMPAD8", "Num8", "num8"), ("VK_NUMPAD9", "Num9", "num9"),
            ("VK_ADD", "Add", "add"), ("VK_SUBTRACT", "Subtract", "subtract"),
            ("VK_MULTIPLY", "Multiply", "multiply"), ("VK_DIVIDE", "Divide", "divide"),
            ("VK_DECIMAL", "Decimal", "decimal"),
        ]

        # 构建每个VK键被哪些角色使用的映射
        key_to_chars = {}
        for mod in self.mods:
            used_keys = set()
            for binding in mod.key_bindings:
                used_keys.add(binding.key)
            for vk in used_keys:
                if vk not in key_to_chars:
                    key_to_chars[vk] = []
                key_to_chars[vk].append(mod.character_id)

        content += f"""
; ===== 按键图标网格（角色列表右侧，5列x3行） =====
; 仅绘制选中角色实际使用的按键图标
"""
        for idx, (vk_name, res_suffix, _) in enumerate(numpad_keys):
            col = idx % grid_cols
            row = idx // grid_cols
            ix = kb_x + col * (icon_w + icon_gap)
            iy = char_start_y + row * (icon_h + icon_gap)

            char_ids = key_to_chars.get(vk_name, [])
            if not char_ids:
                continue  # 没有角色使用这个键，跳过

            content += f"x87 = {icon_w:.4f}\ny87 = {icon_h:.4f}\n"
            content += f"z87 = {ix:.4f}\nw87 = {iy:.4f}\n"

            if len(char_ids) == total_chars:
                # 所有角色都用这个键，无条件绘制
                content += f"ps-t100 = ResourceKey{res_suffix}\nDraw = 4,0\n"
            else:
                for j, cid in enumerate(char_ids):
                    keyword = "if" if j == 0 else "elif"
                    content += f"{keyword} $iooh_sel == {cid}\n"
                    content += f"    ps-t100 = ResourceKey{res_suffix}\n"
                    content += f"    Draw = 4,0\n"
                content += "endif\n"

        # ===== 资源定义 =====
        content += """
; ===== 资源定义 =====
[ResourceUIBackground]
filename = resources\\textures\\ui_background.png

"""
        # 角色纹理（normal + selected）
        for mod in self.mods:
            content += f"""[ResourceCharacter{mod.character_id}Normal]
filename = resources\\textures\\character_{mod.character_id}_normal.png

[ResourceCharacter{mod.character_id}Selected]
filename = resources\\textures\\character_{mod.character_id}_selected.png

"""

        # 按键图标纹理（15个固定图标）
        for vk_name, res_suffix, file_suffix in numpad_keys:
            content += f"""[ResourceKey{res_suffix}]
filename = resources\\textures\\key_{file_suffix}.png

"""

        # 帮助文本资源
        content += """[ResourceHelpText1]
filename = resources\\textures\\help_↑↓__切换角色.png

[ResourceHelpText2]
filename = resources\\textures\\help_数字键__控制功能.png

[ResourceHelpText3]
filename = resources\\textures\\help_Enter__显示_隐藏UI.png
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
    
    def auto_assign_keys_sequential(self):
        """按检测顺序自动分配小键盘按键（0-9，加减乘除，小数点，共15个）
        单个mod内相同的原始键位将分配相同的新键位"""
        numpad_keys = [
            # 数字键 0-9 (10个)
            "VK_NUMPAD0", "VK_NUMPAD1", "VK_NUMPAD2", "VK_NUMPAD3", "VK_NUMPAD4",
            "VK_NUMPAD5", "VK_NUMPAD6", "VK_NUMPAD7", "VK_NUMPAD8", "VK_NUMPAD9",
            # 运算符键 (4个)
            "VK_ADD",       # + 加号
            "VK_SUBTRACT",  # - 减号
            "VK_MULTIPLY",  # * 乘号
            "VK_DIVIDE",    # / 除号
            # 小数点 (1个)
            "VK_DECIMAL"    # . 小数点
        ]
        
        # 对每个mod单独处理
        for mod in self.mods:
            # 为当前mod建立原始键位到新键位的映射表
            mod_key_mapping = {}
            available_keys = list(numpad_keys)
            
            # 记录原始按键并分配新键位
            for binding in mod.key_bindings:
                binding.original_key = binding.key
                
                # 如果这个原始键位在当前mod中还没有分配过
                if binding.original_key not in mod_key_mapping:
                    if available_keys:
                        # 为这个原始键位分配一个新键位
                        new_key = available_keys.pop(0)
                        mod_key_mapping[binding.original_key] = new_key
                    else:
                        # 如果小键盘按键用完了，保持原按键
                        mod_key_mapping[binding.original_key] = binding.original_key
                        print(f"警告: {mod.name} 的小键盘按键已用完，{binding.original_key} 保持不变")
                
                # 应用映射（相同原始键位会得到相同的新键位）
                binding.key = mod_key_mapping[binding.original_key]
            
            # 输出当前mod的映射情况
            if len(mod_key_mapping) < len(mod.key_bindings):
                print(f"{mod.name}: {len(mod.key_bindings)}个按键绑定 -> {len(mod_key_mapping)}个不同键位")
    
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
key = VK_UP
run = CommandList_{local_var}_SelectUp

[CommandList_{local_var}_SelectUp]
{chr(10).join(cmd_up_lines)}

[Key_{local_var}_SelectDown]
key = VK_DOWN
run = CommandList_{local_var}_SelectDown

[CommandList_{local_var}_SelectDown]
{chr(10).join(cmd_down_lines)}

[Key_{local_var}_ToggleUI]
key = VK_RETURN
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
                for binding in bindings:
                    section_pattern = rf'\[{re.escape(binding.section_name)}\](.*?)(?=\n\[|$)'
                    match = re.search(section_pattern, content, re.DOTALL)

                    if match:
                        old_section = match.group(0)
                        new_section = self._modify_key_section_with_context(
                            old_section,
                            mod.character_id,
                            binding.key,
                            local_var,
                        )
                        content = content.replace(old_section, new_section, 1)

                # 在 [Constants] 之后、第一个Key section之前插入选择器块
                # 找到第一个非Constants的section位置
                first_key_match = re.search(r'\n(\[Key\w+\])', content)
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
    
    def _modify_key_section_with_context(self, section_content: str, character_id: int, new_key: str, local_var: str) -> str:
        """修改单个按键section，保留原有type，添加本地选择器变量条件。
        返回修改后的Key section字符串"""
        lines = section_content.split('\n')
        modified_lines = []
        has_condition = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('key =') or stripped.startswith('key='):
                indent = line[:len(line) - len(line.lstrip())]
                modified_lines.append(f'{indent}key = {new_key}')
            elif stripped.startswith('condition =') or stripped.startswith('condition='):
                has_condition = True
                cond_match = re.search(r'condition\s*=\s*(.+)', line)
                if cond_match:
                    cond_text = cond_match.group(1).strip()
                    # 清理旧的 iooh_sel / iooh_s\d+ / *_sel 条件
                    cond_clean = re.sub(r'\s*&&\s*\$iooh_s\d*\s*==\s*\d+', '', cond_text)
                    cond_clean = re.sub(r'\$iooh_s\d*\s*==\s*\d+\s*&&\s*', '', cond_clean)
                    cond_clean = re.sub(r'\$iooh_s\d*\s*==\s*\d+', '', cond_clean)
                    cond_clean = re.sub(r'\s*&&\s*\$iooh_sel\s*==\s*\d+', '', cond_clean)
                    cond_clean = re.sub(r'\$iooh_sel\s*==\s*\d+\s*&&\s*', '', cond_clean)
                    cond_clean = re.sub(r'\$iooh_sel\s*==\s*\d+', '', cond_clean)
                    # 清理测试用的 *_sel 变量条件（如 $perlica_sel）
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
            else:
                modified_lines.append(line)

        # 如果原来没有condition行，在key行后面插入一行
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


class KeyConfiguratorGUI:
    """图形界面"""
    
    def __init__(self):
        self.configurator = EFMIKeyConfigurator()
        
        self.root = tk.Tk()
        self.root.title("EFMI 按键上下文配置器 v1.0")
        self.root.geometry("1200x700")
        
        self._create_widgets()
        
    def _create_widgets(self):
        """创建界面组件"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(toolbar, text="Mods目录:").pack(side=tk.LEFT, padx=5)
        
        self.dir_entry = ttk.Entry(toolbar, width=50)
        self.dir_entry.pack(side=tk.LEFT, padx=5)
        self.dir_entry.insert(0, r"d:\ikun\Downloads\endfield")
        
        ttk.Button(toolbar, text="浏览...", command=self._browse_directory).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="扫描并自动配置", command=self._scan_mods).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="保存", command=self._apply_changes).pack(side=tk.LEFT, padx=5)
        
        # 主要内容区域
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建表格
        columns = ("mod_name", "char_id", "detection", "function", "current_key", "new_key", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
        
        self.tree.heading("mod_name", text="Mod名称")
        self.tree.heading("char_id", text="角色ID")
        self.tree.heading("detection", text="检测变量")
        self.tree.heading("function", text="功能说明")
        self.tree.heading("current_key", text="原始按键")
        self.tree.heading("new_key", text="新按键（当前配置）- 双击修改")
        self.tree.heading("status", text="状态")
        
        self.tree.column("mod_name", width=180)
        self.tree.column("char_id", width=60)
        self.tree.column("detection", width=80)
        self.tree.column("function", width=120)
        self.tree.column("current_key", width=100)
        self.tree.column("new_key", width=100)
        self.tree.column("status", width=120)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部日志区域
        log_frame = ttk.LabelFrame(self.root, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 绑定双击事件
        self.tree.bind("<Double-1>", self._on_double_click)
    
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
            if key_count > 15:
                self.log(f"  ⚠ {mod.name}: {', '.join(ini_names)} ({key_count}个按键绑定，超过15个) [{detection_info}]")
            else:
                self.log(f"  ✓ {mod.name}: {', '.join(ini_names)} ({key_count}个按键绑定) [{detection_info}]")
        
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not mods:
            self.log("未检测到包含热键绑定的mod")
            messagebox.showwarning("提示", "未检测到包含热键绑定的mod\n\n请确保mod文件夹中包含 key = 的按键配置")
            return
        
        # 自动按顺序分配按键
        self.configurator.auto_assign_keys_sequential()
        self.log("已自动分配小键盘按键（0-9 + */+-.，共15个）")
        
        # 立即执行备份和修改
        self.log("开始自动备份并修改配置文件...")
        self.log("步骤：注入本地选择器变量 + 上下键处理器 + condition条件")
        success_count = 0
        for mod in mods:
            if self.configurator.modify_mod_ini(mod):
                success_count += 1
                self.log(f"  ✓ {mod.name} 按键已配置 (ID={mod.character_id}, {len(mod.key_bindings)}个按键)")
            else:
                self.log(f"  ✗ {mod.name} 配置失败")
        
        self.log(f"自动配置完成: 按键{success_count}/{len(mods)}")
        self.log('提示：双击"新按键"列可以手动修改，然后点击"保存"按钮更新配置')
        
        # 填充表格
        for mod in mods:
            for binding in mod.key_bindings:
                self.tree.insert("", tk.END, values=(
                    mod.name,
                    mod.character_id,
                    "✓" if mod.has_character_detection else "✗",
                    binding.description,
                    binding.original_key,  # 显示修改前的原始按键
                    binding.key,           # 显示当前配置的新按键
                    "✓ 已自动配置"
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
            script_dir = os.path.dirname(os.path.abspath(__file__))
            result = subprocess.run(
                [sys.executable, os.path.join(script_dir, "generate_ui_textures.py")],
                cwd=script_dir, capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                self.log("✓ UI纹理已自动生成")
                for line in result.stdout.strip().splitlines():
                    self.log(f"  {line}")
            else:
                self.log(f"✗ UI纹理生成失败: {result.stderr.strip()}")
        except Exception as e:
            self.log(f"✗ UI纹理生成异常: {e}")

        # 显示完成信息
        self.log("")
        self.log("=" * 60)
        self.log("配置完成！使用说明：")
        self.log(f"1. 每个mod拥有本地选择器变量 $iooh_s<id>")
        self.log(f"2. 每个mod拥有自己的 VK_UP/VK_DOWN 处理器，保持同步")
        self.log("3. 各mod的按键 condition 使用本地变量判断 $iooh_s<id> == <角色ID>")
        self.log("4. 小键盘按键只在对应角色ID被选中时生效")
        self.log("5. 游戏内按Enter键切换UI显示/隐藏，↑↓切换角色")
        self.log("6. 无需修改 d3dx.ini")
        self.log("")
        self.log("=" * 60)
    
    
    def _apply_changes(self):
        """保存并应用修改到所有mod"""
        if not self.configurator.mods:
            messagebox.showwarning("警告", "请先扫描mods！")
            return
            
        if not messagebox.askyesno("确认保存", 
            "确定要保存在GUI中修改的按键配置吗？\n\n"
            "此操作将：\n"
            "1. 将修改后的按键写入配置文件\n"
            "2. 确保按键仅在对应角色激活时生效\n\n"
            "注意：不会重新备份文件。"):
            return
        
        self.log("开始保存修改...")
        success_count = 0
        
        # 从表格更新binding的按键（用户可能已修改）
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            mod_name = values[0]
            function_desc = values[2]
            new_key = values[4]
            
            # 查找对应的binding并更新
            for mod in self.configurator.mods:
                if mod.name == mod_name:
                    for binding in mod.key_bindings:
                        if binding.description == function_desc:
                            binding.key = new_key
                            break
        
        # 修改所有mod（不再次备份）
        for mod in self.configurator.mods:
            if self.configurator.modify_mod_ini(mod, create_backup=False):
                success_count += 1
                self.log(f"✓ {mod.name} 已保存 (ID={mod.character_id}, {len(mod.key_bindings)}个按键)")
                
                # 更新表格状态
                for item in self.tree.get_children():
                    values = self.tree.item(item, 'values')
                    if values[0] == mod.name:
                        self.tree.item(item, values=(
                            values[0], values[1], values[2], values[3], values[4], "✓ 已保存"
                        ))
            else:
                self.log(f"✗ {mod.name} 保存失败")
        
        self.log(f"保存完成: {success_count}/{len(self.configurator.mods)} 个mod成功")
        
        # 统计信息
        total_bindings = sum(len(m.key_bindings) for m in self.configurator.mods)
        
        messagebox.showinfo("完成", 
            f"已成功修改 {success_count} 个mod\n"
            f"共处理 {total_bindings} 个按键绑定\n\n"
            f"使用说明：\n"
            f"- Tab: 打开/关闭角色选择GUI\n"
            f"- ↑/↓: 在GUI中切换角色\n"
            f"- Enter: 确认选择角色\n"
            f"- ESC: 关闭GUI并重置角色\n"
            f"- 小键盘: 控制当前激活的角色\n"
            f"  · 0-9: 前10个按键\n"
            f"  · * + - / .: 第11-15个按键\n\n"
            f"每个mod最多支持15个按键")
    
    def _on_double_click(self, event):
        """双击编辑按键"""
        item = self.tree.selection()[0]
        column = self.tree.identify_column(event.x)
        
        if column == "#5":  # new_key列
            values = self.tree.item(item, 'values')
            current_value = values[4]
            
            # 弹出编辑对话框
            new_value = simpledialog.askstring("修改按键", f"输入新按键 (当前: {current_value}):", initialvalue=current_value)
            if new_value:
                self.tree.item(item, values=(
                    values[0], values[1], values[2], values[3], new_value, "待保存"
                ))
    
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
