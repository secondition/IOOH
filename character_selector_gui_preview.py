#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EFMI 角色选择GUI预览
用于预览角色选择GUI的外观和交互

作者: EFMI Community
版本: 1.0
"""

import tkinter as tk
from tkinter import ttk, font
import json
import os


class CharacterSelectorGUIPreview:
    """角色选择GUI预览窗口"""
    
    def __init__(self, character_list=None):
        self.root = tk.Tk()
        self.root.title("角色选择器")
        self.root.geometry("400x600")
        self.root.configure(bg="#1e1e1e")
        
        # 设置窗口始终在最前
        self.root.attributes('-topmost', True)
        
        # 角色列表
        self.characters = character_list or self._load_default_characters()
        self.current_index = 0
        
        self._create_widgets()
        self._bind_keys()
        self._update_display()
    
    def _load_default_characters(self):
        """加载默认角色列表（从配置文件或使用示例数据）"""
        config_file = "efmi_key_config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return [{"id": mod["character_id"], "name": mod["name"]} 
                            for mod in config.get("mods", [])]
            except Exception as e:
                print(f"加载配置失败: {e}")
        
        # 默认示例数据
        return [
            {"id": 1, "name": "角色1"},
            {"id": 2, "name": "角色2"},
            {"id": 3, "name": "角色3"},
            {"id": 4, "name": "角色4"},
            {"id": 5, "name": "角色5"},
        ]
    
    def _create_widgets(self):
        """创建界面组件"""
        # 标题
        title_frame = tk.Frame(self.root, bg="#2d2d2d", height=60)
        title_frame.pack(fill=tk.X, pady=0)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame, 
            text="角色选择器", 
            font=("Microsoft YaHei UI", 16, "bold"),
            bg="#2d2d2d",
            fg="#ffffff"
        )
        title_label.pack(pady=15)
        
        # 角色列表容器
        self.list_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建可滚动的角色列表
        self.canvas = tk.Canvas(self.list_frame, bg="#1e1e1e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#1e1e1e")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=360)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建角色卡片
        self.character_frames = []
        for i, char in enumerate(self.characters):
            frame = self._create_character_card(i, char)
            self.character_frames.append(frame)
        
        # 底部提示
        hint_frame = tk.Frame(self.root, bg="#2d2d2d", height=80)
        hint_frame.pack(fill=tk.X, pady=0)
        hint_frame.pack_propagate(False)
        
        hint_label = tk.Label(
            hint_frame,
            text="↑/↓ 切换角色 | Enter 确认 | ESC 关闭",
            font=("Microsoft YaHei UI", 10),
            bg="#2d2d2d",
            fg="#888888"
        )
        hint_label.pack(pady=10)
        
        # 当前选择信息
        self.info_label = tk.Label(
            hint_frame,
            text="",
            font=("Microsoft YaHei UI", 9),
            bg="#2d2d2d",
            fg="#00ff00"
        )
        self.info_label.pack()
    
    def _create_character_card(self, index, character):
        """创建角色卡片"""
        frame = tk.Frame(
            self.scrollable_frame,
            bg="#2d2d2d",
            relief=tk.FLAT,
            bd=2
        )
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # 角色ID标签
        id_label = tk.Label(
            frame,
            text=f"ID: {character['id']}",
            font=("Microsoft YaHei UI", 9),
            bg="#2d2d2d",
            fg="#888888",
            width=8,
            anchor=tk.W
        )
        id_label.pack(side=tk.LEFT, padx=10, pady=10)
        
        # 角色名称
        name_label = tk.Label(
            frame,
            text=character['name'],
            font=("Microsoft YaHei UI", 11),
            bg="#2d2d2d",
            fg="#ffffff",
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=10)
        
        # 选中指示器
        indicator = tk.Label(
            frame,
            text="▶",
            font=("Arial", 14, "bold"),
            bg="#2d2d2d",
            fg="#00ff00"
        )
        indicator.pack(side=tk.RIGHT, padx=10)
        indicator.pack_forget()  # 初始隐藏
        
        # 存储组件引用
        frame.indicator = indicator
        frame.id_label = id_label
        frame.name_label = name_label
        
        # 绑定点击事件
        for widget in [frame, id_label, name_label]:
            widget.bind("<Button-1>", lambda e, idx=index: self._select_character(idx))
        
        return frame
    
    def _bind_keys(self):
        """绑定按键"""
        self.root.bind("<Up>", lambda e: self._previous_character())
        self.root.bind("<Down>", lambda e: self._next_character())
        self.root.bind("<Return>", lambda e: self._confirm_selection())
        self.root.bind("<Escape>", lambda e: self.root.quit())
        self.root.bind("<Tab>", lambda e: self.root.quit())
    
    def _previous_character(self):
        """选择上一个角色"""
        self.current_index = (self.current_index - 1) % len(self.characters)
        self._update_display()
    
    def _next_character(self):
        """选择下一个角色"""
        self.current_index = (self.current_index + 1) % len(self.characters)
        self._update_display()
    
    def _select_character(self, index):
        """直接选择角色"""
        self.current_index = index
        self._update_display()
    
    def _confirm_selection(self):
        """确认选择"""
        selected = self.characters[self.current_index]
        print(f"已选择角色: {selected['name']} (ID: {selected['id']})")
        self.info_label.config(text=f"已激活: {selected['name']}")
        # 在实际应用中，这里会设置 $active_character 变量
    
    def _update_display(self):
        """更新显示"""
        # 更新所有卡片状态
        for i, frame in enumerate(self.character_frames):
            if i == self.current_index:
                # 高亮当前选择
                frame.config(bg="#3d5afe", relief=tk.RAISED, bd=2)
                frame.id_label.config(bg="#3d5afe", fg="#ffffff")
                frame.name_label.config(bg="#3d5afe", fg="#ffffff", font=("Microsoft YaHei UI", 12, "bold"))
                frame.indicator.pack(side=tk.RIGHT, padx=10)
            else:
                # 普通状态
                frame.config(bg="#2d2d2d", relief=tk.FLAT, bd=2)
                frame.id_label.config(bg="#2d2d2d", fg="#888888")
                frame.name_label.config(bg="#2d2d2d", fg="#ffffff", font=("Microsoft YaHei UI", 11))
                frame.indicator.pack_forget()
        
        # 滚动到当前选择
        if self.character_frames:
            # 计算卡片位置
            card_height = 60  # 估计的卡片高度
            scroll_position = self.current_index * card_height
            total_height = len(self.characters) * card_height
            
            if total_height > 0:
                scroll_fraction = scroll_position / total_height
                self.canvas.yview_moveto(max(0, scroll_fraction - 0.1))
        
        # 更新信息标签
        current_char = self.characters[self.current_index]
        self.info_label.config(text=f"当前: {current_char['name']} ({self.current_index + 1}/{len(self.characters)})")
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()


def main():
    """主函数"""
    print("EFMI 角色选择GUI预览")
    print("=" * 50)
    print("使用方法:")
    print("  - 上/下箭头: 切换角色")
    print("  - Enter: 确认选择")
    print("  - ESC/Tab: 关闭GUI")
    print("=" * 50)
    
    # 尝试从配置文件加载角色列表
    config_file = "efmi_key_config.json"
    characters = None
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                characters = [{"id": mod["character_id"], "name": mod["name"]} 
                            for mod in config.get("mods", [])]
            print(f"已从 {config_file} 加载 {len(characters)} 个角色")
        except Exception as e:
            print(f"加载配置失败: {e}，使用示例数据")
    else:
        print(f"未找到 {config_file}，使用示例数据")
    
    app = CharacterSelectorGUIPreview(characters)
    app.run()


if __name__ == "__main__":
    main()
