#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - EFMI按键上下文配置工具 v3.0（重构版）

核心机制：选择器伪共享
- 所有mod同步计算$selected_character变量
- 通过↑↓键全局输入实现变量同步
- 双重condition判断：角色在场 && 选中匹配
"""

import os
import re
import shutil
import json
from typing import Dict, List, Optional
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
        
    def scan_mods(self, directory: str) -> List[ModInfo]:
        """扫描目录下的所有mod，检测所有.ini文件和角色hash"""
        self.mods_directory = directory
        self.mods.clear()
        
        # 获取当前脚本所在目录名，用于跳过自身
        current_dir_name = os.path.basename(directory)
        
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            
            # 跳过隐藏文件夹
            if item.startswith('.') or item.startswith('EFMI'):
                continue
            
            if os.path.isdir(item_path):
                # 查找该文件夹下所有.ini文件
                ini_files = []
                try:
                    for file in os.listdir(item_path):
                        if file.lower().endswith('.ini'):
                            ini_files.append(os.path.join(item_path, file))
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
                    
                    # 只添加有type=cycle按键绑定的mod（模型切换功能）
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
                
                # 只处理 type = cycle 的按键（模型切换功能）
                if binding_type and binding_type.lower() == 'cycle':
                    binding = ModKeyBinding(section_name, key, variable or f"${section_name}", mod.path)
                    # 使用section名称作为描述，保持原样
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
    
    def backup_mod(self, mod: ModInfo):
        """备份所有ini文件"""
        for ini_file in mod.ini_files:
            if ini_file not in mod.ini_file_backups or not mod.ini_file_backups[ini_file]:
                backup_path = ini_file + ".backup"
                if not os.path.exists(backup_path):
                    try:
                        shutil.copy2(ini_file, backup_path)
                        mod.ini_file_backups[ini_file] = True
                    except Exception as e:
                        print(f"备份 {os.path.basename(ini_file)} 失败: {e}")
        mod.has_backup = True
    
    def save_config(self, output_path: str = None):
        """保存配置到JSON文件"""
        if output_path is None:
            output_path = self.config_file
        
        config = {
            "version": "3.0",
            "generated_at": datetime.now().isoformat(),
            "mods_directory": self.mods_directory,
            "total_characters": len(self.mods),
            "mods": []
        }
        
        for mod in self.mods:
            mod_data = {
                "name": mod.name,
                "path": mod.path,
                "character_id": mod.character_id,
                "has_character_detection": mod.has_character_detection,
                "key_bindings": [
                    {
                        "section": binding.section_name,
                        "key": binding.key,
                        "original_key": binding.original_key,
                        "variable": binding.variable,
                        "description": binding.description
                    }
                    for binding in mod.key_bindings
                ]
            }
            config["mods"].append(mod_data)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"配置已保存到: {output_path}")
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def insert_selector_control_to_mod(self, mod: ModInfo) -> bool:
        """为mod的ini文件插入选择器控制代码"""
        try:
            # 获取主ini文件（通常是第一个或最大的）
            main_ini = mod.ini_files[0] if mod.ini_files else None
            if not main_ini:
                return False
            
            with open(main_ini, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 生成选择器控制代码
            selector_code = f"""\n; ===== 角色选择器控制（由EFMI工具自动生成）=====
[Constants]
global persist $selected_character = 0  ; 当前选中的角色ID (0-{len(self.mods)-1})

[KeySelectUp]
key = VK_UP
type = standard
run = CommandListSelectUp

[CommandListSelectUp]
if $selected_character > 0
    $selected_character = $selected_character - 1
else
    $selected_character = {len(self.mods) - 1}
endif

[KeySelectDown]
key = VK_DOWN
type = standard
run = CommandListSelectDown

[CommandListSelectDown]
if $selected_character < {len(self.mods) - 1}
    $selected_character = $selected_character + 1
else
    $selected_character = 0
endif
; ===== 选择器控制结束 =====\n\n"""
            
            # 查找Constants section，在其后插入
            constants_pattern = r'\[Constants\].*?(?=\n\[|$)'
            constants_match = re.search(constants_pattern, content, re.DOTALL)
            
            if constants_match:
                # 在Constants section后插入
                insert_pos = constants_match.end()
                content = content[:insert_pos] + selector_code + content[insert_pos:]
            else:
                # 如果没有Constants，在文件开头插入
                content = selector_code + content
            
            # 写回文件
            with open(main_ini, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"插入选择器控制到 {mod.name} 失败: {e}")
            return False
    
    def modify_mod_ini(self, mod: ModInfo, key_mapping: Dict[str, str] = None, create_backup: bool = True) -> bool:
        """修改所有ini文件，添加选择器判断并统一按键"""
        try:
            # 备份所有ini文件（仅在需要时）
            if create_backup:
                self.backup_mod(mod)
            
            # 按ini文件分组处理按键绑定
            bindings_by_file: Dict[str, List[ModKeyBinding]] = {}
            for binding in mod.key_bindings:
                # 需要找到这个binding来自哪个ini文件
                # 通过在每个ini文件中查找section来确定
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
                
                # 修改该文件中的所有按键绑定
                for binding in bindings:
                    section_pattern = rf'\[{re.escape(binding.section_name)}\](.*?)(?=\n\[|$)'
                    match = re.search(section_pattern, content, re.DOTALL)
                    
                    if match:
                        old_section = match.group(0)
                        # 获取原始condition（如果有）
                        original_condition = None
                        condition_match = re.search(r'condition\s*=\s*(.+)', old_section)
                        if condition_match:
                            original_condition = condition_match.group(1).strip()
                        
                        new_section = self._modify_key_section_with_context(
                            old_section, 
                            mod.character_id,
                            binding.key,
                            original_condition
                        )
                        content = content.replace(old_section, new_section, 1)
                
                # 写回文件
                with open(ini_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return True
            
        except Exception as e:
            print(f"修改 {mod.name} 失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _modify_key_section_with_context(self, section_content: str, character_id: int, new_key: str, original_condition: str = None) -> str:
        """修改单个按键section，添加选择器判断和新按键"""
        lines = section_content.split('\n')
        modified_lines = []
        has_condition = False
        key_line_index = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 找到key行
            if stripped.startswith('key =') or stripped.startswith('key='):
                key_line_index = i
                # 替换为新按键
                indent = line[:len(line) - len(line.lstrip())]
                modified_lines.append(f'{indent}key = {new_key}')
            # 找到condition行
            elif stripped.startswith('condition =') or stripped.startswith('condition='):
                has_condition = True
                # 提取现有条件
                condition_match = re.search(r'condition\s*=\s*(.+)', line)
                if condition_match:
                    existing_condition = condition_match.group(1).strip()
                    # 添加选择器判断
                    indent = line[:len(line) - len(line.lstrip())]
                    modified_lines.append(f'{indent}condition = {existing_condition} && $selected_character == {character_id}')
                else:
                    modified_lines.append(line)
            else:
                modified_lines.append(line)
        
        # 如果没有condition，在key行后添加一个
        if not has_condition and key_line_index >= 0:
            key_line = modified_lines[key_line_index]
            indent = key_line[:len(key_line) - len(key_line.lstrip())]
            # 如果有原始condition（从扫描时保存），使用它
            if original_condition:
                modified_lines.insert(key_line_index + 1, f'{indent}condition = {original_condition} && $selected_character == {character_id}')
            else:
                # 否则只判断选择器
                modified_lines.insert(key_line_index + 1, f'{indent}condition = $selected_character == {character_id}')
        
        return '\n'.join(modified_lines)


class KeyConfiguratorGUI:
    """图形界面"""
    
    def __init__(self):
        self.configurator = EFMIKeyConfigurator()
        self.key_mapping: Dict[str, str] = {}  # variable -> new_key
        
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
        self.log("只检测包含 type=cycle 的按键（模型切换功能）...")
        mods = self.configurator.scan_mods(directory)
        self.log(f"扫描完成，发现 {len(mods)} 个支持模型切换的mod")
        
        # 显示检测到的ini文件详情
        for mod in mods:
            ini_names = [os.path.basename(f) for f in mod.ini_files]
            key_count = len(mod.key_bindings)
            detection_info = "有检测" if mod.has_character_detection else "无检测"
            if key_count > 15:
                self.log(f"  ⚠ {mod.name}: {', '.join(ini_names)} ({key_count}个cycle按键，超过15个) [{detection_info}]")
            else:
                self.log(f"  ✓ {mod.name}: {', '.join(ini_names)} ({key_count}个cycle按键) [{detection_info}]")
        
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not mods:
            self.log("未检测到支持模型切换的mod（需要有 type=cycle 的按键）")
            messagebox.showwarning("提示", "未检测到支持模型切换的mod\n\n请确保mod文件夹中包含 type=cycle 的按键配置")
            return
        
        # 自动按顺序分配按键
        self.configurator.auto_assign_keys_sequential()
        self.log("已自动分配小键盘按键（0-9 + */+-.，共15个）")
        
        # 立即执行备份和修改
        self.log("开始自动备份并修改配置文件...")
        self.log("步骤1：为每个mod插入选择器控制代码...")
        selector_count = 0
        for mod in mods:
            if self.configurator.insert_selector_control_to_mod(mod):
                selector_count += 1
                self.log(f"  ✓ {mod.name} 已插入选择器控制（ID={mod.character_id}）")
            else:
                self.log(f"  ✗ {mod.name} 插入选择器失败")
        
        self.log(f"步骤2：修改按键绑定为双重condition...")
        success_count = 0
        for mod in mods:
            if self.configurator.modify_mod_ini(mod):
                success_count += 1
                self.log(f"  ✓ {mod.name} 按键已配置 (ID={mod.character_id}, {len(mod.key_bindings)}个按键)")
            else:
                self.log(f"  ✗ {mod.name} 配置失败")
        
        self.log(f"自动配置完成: 选择器{selector_count}/{len(mods)}, 按键{success_count}/{len(mods)}")
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
        self.log(f"表格更新完成，共扫描 {total_ini_files} 个ini文件，{total_bindings} 个cycle按键绑定")
        
        # 保存配置文件
        if self.configurator.save_config():
            self.log(f"✓ 配置已保存到 {self.configurator.config_file}")
        
        # 生成角色显示配置（游戏内UI）
        self.log("")
        self.log("步骤3：生成游戏内显示配置...")
        try:
            from generate_character_display import CharacterDisplayGenerator
            display_gen = CharacterDisplayGenerator()
            if display_gen.generate_display_config():
                self.log("✓ 已生成角色显示配置 (character_display.json)")
                if display_gen.update_main_ini():
                    self.log("✓ 已添加游戏内文本显示功能到 mod.ini")
                else:
                    self.log("⚠ 更新显示代码失败，请手动运行 generate_character_display.py")
            else:
                self.log("⚠ 生成显示配置失败")
        except Exception as e:
            self.log(f"⚠ 无法生成显示配置: {e}")
            self.log("提示：可手动运行 generate_character_display.py 生成")
        
        # 显示完成信息
        self.log("")
        self.log("=" * 60)
        self.log("配置完成！使用说明：")
        self.log(f"1. 每个mod已添加选择器控制（↑↓键切换角色0-{len(mods)-1}）")
        self.log("2. 小键盘按键只在对应角色ID被选中时生效")
        self.log("3. 所有mod同步计算$selected_character变量")
        self.log("4. 游戏内按Enter键切换UI显示/隐藏")
        self.log("5. 编辑 character_name_mapping.json 可自定义角色名称")
        self.log("")
        self.log("提示：运行 python generate_character_display.py 可单独更新UI")
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
