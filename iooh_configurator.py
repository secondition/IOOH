#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - 核心配置器 v5.0（全局热键开关版）

核心机制：全局热键开关
- 每个含热键的 mod ini 各自声明自己的 $iooh_en（global $iooh_en = 0）
- 每个含热键的 mod ini 拥有自己的开关处理器，监听同一物理键、各自翻转
  （三方监听同一物理按键、各自相同计数，实现无通信巧合同步）
- Key section 保留原有 type，condition 使用本地变量 $iooh_en 判断
- 3DMigoto Key condition 只能可靠引用同文件变量，跨文件引用无效
- 主 ini 同样持有一份 $iooh_en；每次按下开关键时走 XXMI ShaderFixes\\help.ini
  通知（与 credits 同一套黄绿字），约 5 秒后消失。每次触发都显示，不是首次才显示

IOOH 全局开关键集中在 IOOHKeyConfig（iooh_keys.py），主 ini 与各 mod
开关块共用同一份按键，确保巧合同步成立；用户可在 UI 自定义。
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
        # IOOH 全局开关键的单一数据源（持久化在 exe/脚本同级）
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
        """扫描目录下的所有mod，检测所有含按键绑定的ini文件"""
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
            # IOOH 全局开关块（自带 key 行），故在内存里剥离注入内容再解析，不写回磁盘。
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

                # 鼠标键 section 不是角色功能热键，一律不纳入注入：
                # 给 type=hold 的 VK_LBUTTON 追加门控会破坏按下/释放配对，
                # 导致拖拽检测不到鼠标抬起、点击区域检测失败。
                if re.search(r'(?i)VK_[LMR]BUTTON|VK_XBUTTON', key):
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

        先把字段规整到各自行（处理多字段同行的写法），再按行提取 key 值。
        key = 后为空时，键值可能续行到下一行（部分 mod 这样写）：仅当下一行不是
        字段赋值（A = B / $var = ...）且非 section 头时才当作续行键值；若下一行是
        type = cycle 这类字段赋值，说明 key 本就为空，返回 None。判别口径与
        _modify_key_section_with_context 处理 condition 空值续行保持一致。
        """
        normalized = self._normalize_section_text(section_content)
        lines = normalized.split('\n')
        for idx, line in enumerate(lines):
            match = re.match(r'(?i)^[ \t]*key[ \t]*=[ \t]*(.*)$', line)
            if not match:
                continue
            value = match.group(1).split(';', 1)[0].strip()
            if not value and idx + 1 < len(lines):
                next_line = lines[idx + 1]
                next_stripped = next_line.split(';', 1)[0].strip()
                is_field_line = re.match(
                    r'(?i)^\s*(?:[A-Za-z_]\w*|\$[A-Za-z_]\w*)\s*=(?!=)',
                    next_line,
                )
                if next_stripped and not next_stripped.startswith('[') and not is_field_line:
                    value = next_stripped
            return re.sub(r'\s+', ' ', value) or None
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
        """生成 IOOH 主 ini：全局热键开关 + help.ini 通知

        主 ini 持有一份 $iooh_en，与各 mod ini 的 $iooh_en 监听同一物理键、
        各自翻转（巧合同步）。每次按下开关键都把状态字符串交给
        ShaderFixes\\help.ini 的 FormatText，约 5 秒后消失。
        """
        if output_path is None:
            output_path = os.path.join(self._resolve_output_dir(), "IOOHmod.ini")

        total_chars = len(self.mods)

        # IOOH 全局开关键（用户可自定义，主 ini 与各 mod 开关块共用同一份）
        key_enable = self.iooh_keys.key_line("enable_toggle")

        # 角色/mod 列表注释（id = name，便于核对扫描结果）
        char_mapping = "; 角色/mod 列表 (id = name):\n"
        for mod in self.mods:
            char_mapping += f"; {mod.character_id} = {mod.name}\n"

        content = f"""; IOOH 全局热键开关 - 自动生成
; 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
; 已扫描 mod 数: {total_chars}
{char_mapping}
[Constants]
global $iooh_en = 0

[KeyIOOH_Toggle]
key = {key_enable}
run = CommandList_Toggle

[CommandList_Toggle]
if $iooh_en == 1
    $iooh_en = 0
    pre Resource\\ShaderFixes\\help.ini\\Notification = ResourceIOOHOff
    pre run = CustomShader\\ShaderFixes\\help.ini\\FormatText
    pre $\\ShaderFixes\\help.ini\\notification_timeout = time + 5.0
else
    $iooh_en = 1
    pre Resource\\ShaderFixes\\help.ini\\Notification = ResourceIOOHOn
    pre run = CustomShader\\ShaderFixes\\help.ini\\FormatText
    pre $\\ShaderFixes\\help.ini\\notification_timeout = time + 5.0
endif

[ResourceIOOHOn]
type = Buffer
data = "IOOH hotkeys ON"

[ResourceIOOHOff]
type = Buffer
data = "IOOH hotkeys OFF"
"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"主配置已生成: {output_path}")
            print(f"  - 已扫描 mod 数: {total_chars}")
            return True
        except Exception as e:
            print(f"生成主配置失败: {e}")
            return False

    def modify_mod_ini(self, mod: ModInfo, create_backup: bool = True) -> bool:
        """修改所有ini文件，注入全局开关变量和开关处理器，添加开关条件"""
        try:
            if create_backup:
                self.backup_mod(mod)

            # IOOH 全局开关键（与主 ini 共用同一份，确保巧合同步成立）
            key_enable = self.iooh_keys.key_line("enable_toggle")

            toggle_block = f"""; ===== IOOH 全局开关 =====
[Key_iooh_Toggle]
key = {key_enable}
run = CommandList_iooh_Toggle

[CommandList_iooh_Toggle]
if $iooh_en == 1
    $iooh_en = 0
else
    $iooh_en = 1
endif
; ===== IOOH 全局开关结束 ====="""

            # 按来源 ini 分组（解析时已记录 binding.ini_file），
            # 直接归组而非靠 section 名反查文件——后者在跨 ini 同名 section 时会把
            # 所有同名绑定都归到第一个匹配文件，导致其余文件漏注入。
            bindings_by_file: Dict[str, List[ModKeyBinding]] = {}
            for binding in mod.key_bindings:
                bindings_by_file.setdefault(binding.ini_file, []).append(binding)

            # 每个含按键的 ini 都是自洽单元：自带 [Constants] 变量声明 + 完整开关块。
            # 不依赖跨 ini 共享变量——3DMigoto 的 Key condition 只能可靠引用同文件变量，
            # `global` 并不会按同名跨 ini 合并成一份共享存储（实测：只在宿主 ini 注入处理器时，
            # 仅宿主 ini 生效，其余只声明+引用 $iooh_en 的文件因自己那份永远为 0 而失效）。
            # 因此沿用与「跨 mod 巧合同步」一致的方案：每个文件各持一份 $iooh_en，
            # 各自监听同一物理键、做相同翻转，天然保持数值同步。
            # 无按键绑定的 ini 不引用任何 iooh 变量，无需注入（仅清理旧注入）。
            for ini_file in mod.ini_files:
                with open(ini_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 清理旧的IOOH注入内容
                content = self._strip_local_selector(content)

                bindings = bindings_by_file.get(ini_file, [])

                # 无按键绑定：写回清理后的内容即可，不注入变量与开关块。
                if not bindings:
                    self._ensure_writable(ini_file)
                    with open(ini_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    continue

                # 在本 ini 的 [Constants] 声明 $iooh_en（无则新建 [Constants]）：
                # 全局开关标志（初始 0，开关键翻转）
                decls = 'global $iooh_en = 0\n'
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
                                "iooh_en",
                                binding_map[section_name].key,
                            )
                            new_parts.append(new_section)
                        else:
                            new_parts.append(section_text)
                        last_idx = end
                    new_parts.append(content[last_idx:])
                    content = ''.join(new_parts)

                # 注入全局开关块：每个含按键的 ini 各注入一份，互不共享、靠相同计数巧合同步
                first_key_match = re.search(r'\[Key\w+\]', content)
                if first_key_match:
                    insert_pos = first_key_match.start()
                    content = content[:insert_pos] + '\n\n' + toggle_block + '\n' + content[insert_pos:]
                else:
                    # 没有Key section，追加到文件末尾
                    content = content.rstrip('\n') + '\n\n' + toggle_block + '\n'

                self._ensure_writable(ini_file)
                with open(ini_file, 'w', encoding='utf-8') as f:
                    f.write(content)

            return True

        except Exception as e:
            print(f"修改 {mod.name} 失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _modify_key_section_with_context(self, section_content: str, enable_var: str, key_value: str = "") -> str:
        """Modify one key section, inject enable condition without changing the key.

        门控条件用全局开关标志 ${enable_var} == 1：开关打开后键才生效，
        关闭后所有已注入热键一起失效。

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

    @staticmethod
    def _strip_condition_gates(match) -> str:
        """从单行 condition 中移除 IOOH 门控项；条件清空则删除整行。

        令牌集合与 _modify_key_section_with_context 追加时一致，确保注入可逆。
        """
        line = match.group(1)
        head, cond_text = line.split('=', 1)
        cond = cond_text
        cond = re.sub(r'\s*&&\s*\$iooh_en\d*\s*==\s*\d+', '', cond)
        cond = re.sub(r'\$iooh_en\d*\s*==\s*\d+\s*&&\s*', '', cond)
        cond = re.sub(r'\$iooh_en\d*\s*==\s*\d+', '', cond)
        cond = re.sub(r'\s*&&\s*\$iooh_s\d*\s*==\s*\d+', '', cond)
        cond = re.sub(r'\$iooh_s\d*\s*==\s*\d+\s*&&\s*', '', cond)
        cond = re.sub(r'\$iooh_s\d*\s*==\s*\d+', '', cond)
        cond = re.sub(r'\s*&&\s*\$iooh_sel\s*==\s*\d+', '', cond)
        cond = re.sub(r'\$iooh_sel\s*==\s*\d+\s*&&\s*', '', cond)
        cond = re.sub(r'\$iooh_sel\s*==\s*\d+', '', cond)
        cond = re.sub(r'\s*&&\s*\$\w+_sel\s*==\s*\d+', '', cond)
        cond = re.sub(r'\$\w+_sel\s*==\s*\d+\s*&&\s*', '', cond)
        cond = re.sub(r'\$\w+_sel\s*==\s*\d+', '', cond)
        cond = cond.strip()
        # 条件被清空：原本无 condition，删除整行（返回哨兵，随后压缩空行清理）
        if not cond:
            return ''
        return f'{head}= {cond}'

    def _strip_local_selector(self, content: str) -> str:
        """移除各mod ini中的IOOH注入内容（新老两代注入：全局开关块/本地选择器变量）"""
        # 移除 global persist $selected_character 行
        content = re.sub(r'^.*\$selected_character.*\n', '', content, flags=re.MULTILINE)

        # 移除本地选择器变量声明 global $iooh_s<N> / $iooh_en<N> / $iooh_ui<N> = 0 或 -1；
        # $iooh_en 同时覆盖新版的 global $iooh_en = 0（无数字后缀）
        content = re.sub(r'^global \$iooh_s\d+\s*=\s*-?\d+\s*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^global \$iooh_en\d*\s*=\s*-?\d+\s*\n', '', content, flags=re.MULTILINE)
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

        # 移除新版全局开关块：起止标记之间整块删除（同上，标记由注入时同一字符串原子写入）。
        content = re.sub(
            r';\s*=====\s*IOOH 全局开关\s*=====[\s\S]*?;\s*=====\s*IOOH 全局开关结束\s*=====\s*\n?',
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

        # 剥离历史注入残留在 condition 行里的门控项（$iooh_en/$iooh_s/$iooh_sel/$*_sel）。
        # 早期版本会对鼠标键 section 也注入门控；如今这些 section 不再纳入注入、不走
        # _modify_key_section_with_context 的清理，故在此统一还原任意 condition 行：
        # 去掉门控项后若 condition 为空则整行删除（原本无 condition 的 section 复原）。
        content = re.sub(r'(?im)^([ \t]*condition\s*=.*)$', self._strip_condition_gates, content)

        # 清理多余空行（3个以上连续空行压缩为2个）
        content = re.sub(r'\n{4,}', '\n\n\n', content)

        return content
