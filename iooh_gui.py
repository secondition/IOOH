#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - 图形界面。"""

import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from iooh_configurator import EFMIKeyConfigurator
from iooh_keys import ACTIONS, ACTION_LABELS, key_display, token_for_keycode, capture_with_modifiers


GUI_TRANSLATIONS = {
    "title": {"zh": "EFMI IOOH v1.4", "en": "EFMI IOOH v1.4"},
    "mod_dir": {"zh": "Mods目录:", "en": "Mods Directory:"},
    "browse": {"zh": "打开文件夹", "en": "open folder"},
    "config": {"zh": "自动配置并保存", "en": "Auto Config & Save"},
    "restore": {"zh": "恢复备份", "en": "Restore Backup"},
    "lang_btn": {"zh": "🌐 English", "en": "🌐 中文"},
    "col_mod_name": {"zh": "Mod名称", "en": "Mod Name"},
    "col_char_id": {"zh": "角色ID", "en": "Char ID"},
    "col_function": {"zh": "功能说明", "en": "Function"},
    "col_key": {"zh": "按键（双击修改）", "en": "Key (double-click to edit)"},
    "col_status": {"zh": "状态", "en": "Status"},
    "status_configured": {"zh": "✓ 已配置", "en": "✓ Configured"},
    "log_frame": {"zh": "操作日志", "en": "Operation Log"},
    "keys_frame": {"zh": "IOOH 菜单按键自定义（点击按钮后按下目标键即可绑定）",
                   "en": "IOOH Menu Key Customization (click a button, then press the target key)"},
    "key_capturing": {"zh": "请按下按键…（Esc 取消）", "en": "Press a key…  (Esc to cancel)"},
    "row_capturing": {"zh": "按下按键…(Esc取消)", "en": "Press key… (Esc)"},
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

        # IOOH 按键自定义控件状态
        self._key_action_labels = {}   # action -> ttk.Label（动作说明）
        self._key_buttons = {}         # action -> ttk.Button（显示当前键/捕获中提示）
        self._capturing_action = None  # 当前正在捕获按键的动作（None 表示空闲）

        # mod 列表内改键状态
        self._row_capture = None       # 正在捕获的 (tree_item, binding) 或 None
        self._tree_bindings = {}       # tree_item -> ModKeyBinding（用于改键写回）

        self._create_widgets()
        # 全局监听键盘：仅在捕获态生效，空闲时直接放行不干扰其他输入
        self.root.bind("<KeyPress>", self._on_key_capture)
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
        self.btn_config.config(text=self._tr("config"))
        self.btn_restore.config(text=self._tr("restore"))
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

        # IOOH 按键自定义区：刷新分组标题、动作标签与按键按钮文本（按语言）
        self.keys_frame.config(text=self._tr("keys_frame"))
        for action in ACTIONS:
            self._key_action_labels[action].config(text=ACTION_LABELS[action][self.lang] + ":")
            self._refresh_key_button(action)

    def _refresh_key_button(self, action: str):
        """按当前状态刷新某动作按钮文本：捕获中显示提示，否则显示当前绑定键。"""
        btn = self._key_buttons[action]
        if self._capturing_action == action:
            btn.config(text=self._tr("key_capturing"))
        else:
            token = self.configurator.iooh_keys.token(action)
            btn.config(text=key_display(token, self.lang))

    def _create_widgets(self):
        """创建界面组件"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.lbl_mod_dir = ttk.Label(toolbar)
        self.lbl_mod_dir.pack(side=tk.LEFT, padx=(0, 5))

        self.dir_entry = ttk.Entry(toolbar, width=50)
        self.dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.dir_entry.insert(0, r"d:\ikun\Downloads\endfield")
        # 路径输入框回车即扫描
        self.dir_entry.bind("<Return>", lambda _e: self._scan_mods())

        self.btn_browse = ttk.Button(toolbar, command=self._browse_directory)
        self.btn_browse.pack(side=tk.LEFT, padx=2)
        self.btn_config = ttk.Button(toolbar, command=self._auto_config)
        self.btn_config.pack(side=tk.LEFT, padx=2)
        self.btn_restore = ttk.Button(toolbar, command=self._restore_backup)
        self.btn_restore.pack(side=tk.LEFT, padx=2)

        # 语言切换按钮靠右
        self.btn_lang = ttk.Button(toolbar, command=self._toggle_lang)
        self.btn_lang.pack(side=tk.RIGHT, padx=5)

        # IOOH 菜单按键自定义区（四个动作各一个下拉框）
        self._create_keys_panel()

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
        # 双击「按键」列进入改键捕获态
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # 底部日志区域
        self.log_frame = ttk.LabelFrame(self.root)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_keys_panel(self):
        """创建 IOOH 菜单按键自定义面板：每个动作一个按钮，点击后按下目标键完成绑定。"""
        self.keys_frame = ttk.LabelFrame(self.root)
        self.keys_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))

        row = ttk.Frame(self.keys_frame)
        row.pack(fill=tk.X, padx=5, pady=5)

        for action in ACTIONS:
            cell = ttk.Frame(row)
            cell.pack(side=tk.LEFT, padx=(0, 18))

            lbl = ttk.Label(cell)
            lbl.pack(side=tk.LEFT, padx=(0, 4))
            self._key_action_labels[action] = lbl

            btn = ttk.Button(cell, width=18,
                             command=lambda a=action: self._start_key_capture(a))
            btn.pack(side=tk.LEFT)
            self._key_buttons[action] = btn

    def _start_key_capture(self, action: str):
        """进入捕获态：把焦点收到主窗口，等待用户按下目标键。"""
        previous = self._capturing_action
        self._capturing_action = action
        # 刷新上一个按钮（若之前正在捕获其它动作）与当前按钮
        if previous is not None and previous != action:
            self._refresh_key_button(previous)
        self._refresh_key_button(action)
        self.root.focus_set()

    def _on_key_capture(self, event):
        """全局键盘回调：菜单键捕获 / mod 列表改键捕获，二者互斥；空闲时放行。"""
        if self._row_capture is not None:
            return self._handle_row_capture(event)
        if self._capturing_action is None:
            return
        action = self._capturing_action

        # Esc 取消捕获
        if event.keysym == "Escape":
            self._capturing_action = None
            self._refresh_key_button(action)
            return

        token = token_for_keycode(event.keycode)
        if token is None:
            # 不支持的键（修饰键、回车空格等）：忽略，保持捕获态继续等待
            return "break"

        self.configurator.iooh_keys.set_key(action, token)
        self.configurator.iooh_keys.save()
        self._capturing_action = None
        self._refresh_key_button(action)
        return "break"

    def _on_tree_double_click(self, event):
        """双击「按键」列：对该行绑定进入改键捕获态。"""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#4":  # 第4列 = key
            return
        item = self.tree.identify_row(event.y)
        if not item or item not in self._tree_bindings:
            return
        self._start_row_capture(item)

    def _start_row_capture(self, item):
        """进入 mod 改键捕获态：该行按键列显示提示，等待按下组合键。"""
        # 若正在捕获其它来源，先取消
        if self._capturing_action is not None:
            prev = self._capturing_action
            self._capturing_action = None
            self._refresh_key_button(prev)
        binding = self._tree_bindings[item]
        self._row_capture = (item, binding)
        self._set_row_key_text(item, self._tr("row_capturing"))
        self.root.focus_set()

    def _handle_row_capture(self, event):
        """mod 改键捕获：Esc 取消；组合键解析成功则写回覆盖并持久化。"""
        item, binding = self._row_capture

        if event.keysym == "Escape":
            self._row_capture = None
            self._set_row_key_text(item, binding.key)
            return "break"

        ini_form = capture_with_modifiers(event.keycode, event.state)
        if ini_form is None:
            # 纯修饰键或不支持的主键：继续等待
            return "break"

        # 列表显示与 ini 原文一致（不转友好符号）。改键只更新内存 binding，
        # 注入时写进 ini —— ini 即改键的唯一真实来源，无需另存快照。
        binding.key = ini_form
        self._row_capture = None
        self._set_row_key_text(item, ini_form)
        self.log(f"✎ {binding.section_name} 按键改为 {ini_form} — 需点「自动配置并保存」生效")
        return "break"

    def _set_row_key_text(self, item, text):
        """更新某行「按键」列（索引3）的显示文本。"""
        vals = list(self.tree.item(item, 'values'))
        if vals:
            vals[3] = text
            self.tree.item(item, values=vals)

    def _browse_directory(self):
        """浏览目录：选定后自动扫描。"""
        directory = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
            self._scan_mods()

    def _scan_mods(self, quiet: bool = False):
        """扫描 mods 并填充列表（只读，不改 ini）。

        quiet=True 时静默刷新列表（不打扫描日志），供操作收尾的自动重扫使用。
        """
        directory = self.dir_entry.get()
        if not os.path.exists(directory):
            if not quiet:
                messagebox.showerror("错误", "目录不存在！")
            return

        if not quiet:
            self.log(f"开始扫描目录: {directory}")
            self.log("检测所有热键绑定...")
        mods = self.configurator.scan_mods(directory)
        if not quiet:
            self.log(f"扫描完成，发现 {len(mods)} 个包含热键绑定的mod")
            for mod in mods:
                ini_names = [os.path.basename(f) for f in mod.ini_files]
                self.log(f"  ✓ {mod.name}: {', '.join(ini_names)} ({len(mod.key_bindings)}个按键绑定)")

        self._populate_tree(mods)

        if not mods:
            if not quiet:
                self.log("未检测到包含热键绑定的mod")
                messagebox.showwarning("提示", "未检测到包含热键绑定的mod\n\n请确保mod文件夹中包含 key = 的按键配置")
            return

        if not quiet:
            total_bindings = sum(len(m.key_bindings) for m in mods)
            total_ini_files = sum(len(m.ini_files) for m in mods)
            self.log(f"列表已更新，共 {total_ini_files} 个ini文件，{total_bindings} 个按键绑定")
            self.log("提示：双击「按键」列可改键；改完点「自动配置并保存」生效。")

    def _populate_tree(self, mods):
        """清空并重建列表，记录每行对应的 binding 以支持改键。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._tree_bindings.clear()
        for mod in mods:
            for binding in mod.key_bindings:
                item = self.tree.insert("", tk.END, values=(
                    mod.name,
                    mod.character_id,
                    binding.description,
                    binding.key,
                    self._tr("status_configured"),
                ))
                self._tree_bindings[item] = binding

    def _auto_config(self):
        """自动配置：增量清理旧注入 → 注入选择器 → 生成主 ini/配置/纹理。"""
        if not self.configurator.mods:
            messagebox.showwarning("提示", "请先扫描 Mods 目录")
            return
        self._run_pipeline()

    def _run_pipeline(self):
        """完整流程：注入选择器 → 生成主 ini → 保存配置 → 生成纹理 → 打印说明。

        注入靠 _strip_local_selector 增量清理上次注入内容（不还原备份），改键由
        内存 binding.key 承载、注入时写进 ini，故 ini 自身即改键的真实来源、天然跨启动持久。
        恢复原始 ini 是独立操作（「恢复备份」按钮），不混入注入流程。
        """
        mods = self.configurator.mods

        self.log("开始备份并注入选择器上下文...")
        success_count = 0
        for mod in mods:
            if self.configurator.modify_mod_ini(mod):
                success_count += 1
                self.log(f"  ✓ {mod.name} 按键已配置 (ID={mod.character_id}, {len(mod.key_bindings)}个按键)")
            else:
                self.log(f"  ✗ {mod.name} 配置失败")
        self.log(f"注入完成: {success_count}/{len(mods)}")

        # 生成主 IOOHmod.ini（动态角色列表）
        if self.configurator.generate_main_mod_ini():
            self.log(f"✓ 主UI配置已生成: IOOHmod.ini (角色数:{len(mods)})")

        # 主 ini 引用 xxmi_key_config.json 派生的纹理；生成纹理前确保中间配置就位
        if self.configurator.save_config():
            self.log(f"✓ 配置已保存到 {self.configurator.config_file}")

        # 生成UI纹理（按键提示文案随当前自定义按键动态生成）
        self.log("正在生成UI纹理...")
        try:
            from generate_ui_textures import UITextureGenerator
            generator = UITextureGenerator(base_output_dir=self.configurator._resolve_output_dir())
            generator.generate_all(hint_lines=self.configurator.iooh_keys.hint_lines(self.lang))
            self.log("✓ UI纹理已自动生成")
        except Exception as e:
            self.log(f"✗ UI纹理生成异常: {e}")

        # 完成信息（按键说明随当前自定义按键动态显示）
        ioohk = self.configurator.iooh_keys
        toggle_name = key_display(ioohk.token("toggle_menu"), "zh")
        prev_name = key_display(ioohk.token("prev_char"), "zh")
        next_name = key_display(ioohk.token("next_char"), "zh")
        enable_name = key_display(ioohk.token("enable_toggle"), "zh")
        self.log("")
        self.log("=" * 60)
        self.log("配置完成！使用说明：")
        self.log(f"1. {toggle_name} 显示/隐藏UI，{prev_name}/{next_name} 切换角色，{enable_name} 启用/禁用")
        self.log("2. 热键仅在对应角色被选中时生效，实现热键复用")
        self.log("3. 无需修改 d3dx.ini")
        self.log("=" * 60)

        # 流程完成后重新扫描刷新列表（静默：不刷扫描日志；扫描只读、剥离注入、套用改键）
        if self.configurator.mods_directory:
            self._scan_mods(quiet=True)

    def _restore_backup(self):
        """恢复所有 mod 的 .backup，完全还原到原始状态。"""
        directory = self.dir_entry.get()
        if not os.path.exists(directory):
            messagebox.showerror("错误", "目录不存在！")
            return
        self.log("开始恢复备份...")
        self.configurator.restore_backups(directory)
        # 重新扫描刷新列表（静默：恢复备份已自带完成日志）
        if self.configurator.mods_directory:
            self._scan_mods(quiet=True)
        self.log("✓ 恢复备份完成（已还原原始按键）")

    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def run(self):
        """运行GUI"""
        self.root.mainloop()
