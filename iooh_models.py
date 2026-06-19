#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI 数据模型：mod 信息与按键绑定。"""

from typing import Dict, List


class ModKeyBinding:
    """mod按键绑定信息"""
    def __init__(self, section_name: str, key: str, variable: str, mod_path: str, ini_file: str = ""):
        self.section_name = section_name
        self.key = key
        self.variable = variable
        self.mod_path = mod_path
        self.ini_file = ini_file  # 该绑定所属的 ini 文件（解析时记录，分组时直接使用）
        self.description = ""
        # 用户在 UI 改键后的 ini 形式覆盖值（如 "alt 1"、"ctrl VK_LEFT"）。
        # 为空表示沿用原始键；注入时若非空则重写该 section 的 key 行。
        self.key_override = ""


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
