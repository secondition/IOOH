#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IOOH 菜单按键配置：四个菜单控制键的单一数据源。

IOOH 菜单依赖四个物理键（默认：小键盘0 显隐、PageUp/PageDown 切换、小键盘2 启用）。
这些键原先硬编码在主 ini 生成、各 mod 选择器块注入、以及按键提示纹理三处，
必须保持完全一致才能实现「三方监听同一物理键、各自相同计数」的巧合同步。

本模块把这四个键集中到 IOOHKeyConfig 一处：
- 持久化到 exe/脚本同级的 iooh_keys_config.json（用户可在 UI 自定义）
- 统一产出 ini 用的 key 行（key_line）
- 统一产出按键提示纹理用的多行文案（hint_lines）

对没有小键盘的用户，可在 UI 把默认的小键盘键改为 PageUp/Home/功能键等。
"""

import json
import os
from typing import Dict, List, Tuple

# 配置文件名（位于 exe/脚本同级，用户自定义后持久保存，不随包分发）
IOOH_KEYS_FILENAME = "iooh_keys_config.json"

# 四个菜单动作的标识与默认按键 token（token 为 3DMigoto 主键名）。
# key 行统一加 `no_ctrl no_alt` 前缀，避免与游戏内修饰键组合冲突。
ACTIONS: List[str] = ["toggle_menu", "prev_char", "next_char", "enable_toggle"]

DEFAULT_KEYS: Dict[str, str] = {
    "toggle_menu": "VK_NUMPAD0",
    "prev_char": "VK_PRIOR",
    "next_char": "VK_NEXT",
    "enable_toggle": "VK_NUMPAD2",
}

# 动作的中英文说明（用于 UI 标签与提示纹理文案）
ACTION_LABELS: Dict[str, Dict[str, str]] = {
    "toggle_menu": {"zh": "显示 / 隐藏菜单", "en": "Show / Hide Menu"},
    "prev_char": {"zh": "上一个角色", "en": "Previous Character"},
    "next_char": {"zh": "下一个角色", "en": "Next Character"},
    "enable_toggle": {"zh": "启用 / 禁用角色", "en": "Enable / Disable Character"},
}

# ===== 物理按键捕获 =====
# UI 点击动作按钮后，直接按下键盘上的目标键即可绑定。
# tkinter 在 Windows 上 event.keycode 即为 Windows 虚拟键码(VK)，据此映射为
# 3DMigoto ini 可用的按键名(token)，并附中英文显示名。仅接受下表中的按键，
# 其余键（修饰键、回车空格等）在捕获时忽略、继续等待。
# 注：NumLock 关闭时按下小键盘键，系统发出的是导航键 VK（与游戏内 3DMigoto
# 收到的一致），捕获结果因此天然与实际行为对齐。
_CAPTURE_TABLE: List[Tuple[int, str, str, str]] = [
    # 小键盘（NumLock 开启）
    (96, "VK_NUMPAD0", "小键盘 0", "Numpad 0"),
    (97, "VK_NUMPAD1", "小键盘 1", "Numpad 1"),
    (98, "VK_NUMPAD2", "小键盘 2", "Numpad 2"),
    (99, "VK_NUMPAD3", "小键盘 3", "Numpad 3"),
    (100, "VK_NUMPAD4", "小键盘 4", "Numpad 4"),
    (101, "VK_NUMPAD5", "小键盘 5", "Numpad 5"),
    (102, "VK_NUMPAD6", "小键盘 6", "Numpad 6"),
    (103, "VK_NUMPAD7", "小键盘 7", "Numpad 7"),
    (104, "VK_NUMPAD8", "小键盘 8", "Numpad 8"),
    (105, "VK_NUMPAD9", "小键盘 9", "Numpad 9"),
    # 导航键
    (33, "VK_PRIOR", "PageUp", "PageUp"),
    (34, "VK_NEXT", "PageDown", "PageDown"),
    (36, "VK_HOME", "Home", "Home"),
    (35, "VK_END", "End", "End"),
    (45, "VK_INSERT", "Insert", "Insert"),
    (46, "VK_DELETE", "Delete", "Delete"),
    # 方向键
    (37, "VK_LEFT", "← 左", "Left"),
    (38, "VK_UP", "↑ 上", "Up"),
    (39, "VK_RIGHT", "→ 右", "Right"),
    (40, "VK_DOWN", "↓ 下", "Down"),
    # 功能键
    (112, "VK_F1", "F1", "F1"),
    (113, "VK_F2", "F2", "F2"),
    (114, "VK_F3", "F3", "F3"),
    (115, "VK_F4", "F4", "F4"),
    (116, "VK_F5", "F5", "F5"),
    (117, "VK_F6", "F6", "F6"),
    (118, "VK_F7", "F7", "F7"),
    (119, "VK_F8", "F8", "F8"),
    (120, "VK_F9", "F9", "F9"),
    (121, "VK_F10", "F10", "F10"),
    (122, "VK_F11", "F11", "F11"),
    (123, "VK_F12", "F12", "F12"),
]
# 字母 A-Z（VK 65-90）：token 用裸字符小写，3DMigoto 直接识别
_CAPTURE_TABLE += [(code, chr(code).lower(), chr(code), chr(code)) for code in range(65, 91)]
# 主键盘数字 0-9（VK 48-57）：token 用裸字符
_CAPTURE_TABLE += [(code, chr(code), chr(code), chr(code)) for code in range(48, 58)]

VK_TO_TOKEN: Dict[int, str] = {vk: tok for vk, tok, _, _ in _CAPTURE_TABLE}
_TOKEN_TO_ZH = {tok: zh for _, tok, zh, _ in _CAPTURE_TABLE}
_TOKEN_TO_EN = {tok: en for _, tok, _, en in _CAPTURE_TABLE}


def key_display(token: str, lang: str = "zh") -> str:
    """返回某个 token 的友好名称（中/英）。"""
    table = _TOKEN_TO_EN if lang == "en" else _TOKEN_TO_ZH
    return table.get(token, token)


def token_for_keycode(keycode: int):
    """把 tkinter 捕获的 Windows 虚拟键码映射为 ini 可用 token；不支持则返回 None。"""
    return VK_TO_TOKEN.get(keycode)


# ===== mod 列表按键捕获（支持修饰键组合）=====
# 与 IOOH 菜单键不同：mod 原始热键常带修饰键（Alt+1、Ctrl+/、vk_left），
# 因此捕获时读取 event.state 的 Alt/Ctrl/Shift 位 + 主键，产出 ini 形式键值
# （如 "alt 1"、"ctrl VK_LEFT"、"VK_NUMPAD0"），直接写入 ini，列表也按此原文显示
# （不转友好符号，保持与 ini 一致）。
# tkinter event.state 修饰键位（Windows）：Shift=0x1, Control=0x4, Alt=0x20000。
_STATE_SHIFT = 0x0001
_STATE_CTRL = 0x0004
_STATE_ALT = 0x20000

# 这些键单独按下时只是修饰键，不作为主键采纳（等待主键到来）。
_MODIFIER_KEYCODES = {16, 17, 18, 91, 92}  # Shift/Ctrl/Alt/Win


def capture_with_modifiers(keycode: int, state: int):
    """从一次按键事件解析「修饰键 + 主键」组合，返回 ini 形式键值。

    主键不可识别或按下的是纯修饰键时返回 None。
    """
    if keycode in _MODIFIER_KEYCODES:
        return None
    token = token_for_keycode(keycode)
    if token is None:
        return None

    mods = []
    if state & _STATE_CTRL:
        mods.append("ctrl")
    if state & _STATE_ALT:
        mods.append("alt")
    if state & _STATE_SHIFT:
        mods.append("shift")

    return " ".join(mods + [token])



class IOOHKeyConfig:
    """IOOH 菜单四个控制键的单一数据源（含持久化、ini key 行、提示文案）。"""

    def __init__(self, output_dir: str):
        # 配置写到 exe/脚本同级，自定义后持久保存
        self.config_path = os.path.join(output_dir, IOOH_KEYS_FILENAME)
        self.keys: Dict[str, str] = dict(DEFAULT_KEYS)
        self.load()

    def load(self):
        """从磁盘读取自定义按键；缺失或损坏则用默认值并忽略未知动作。"""
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"读取 IOOH 按键配置失败，使用默认值: {e}")
            return
        stored = data.get("keys", {})
        for action in ACTIONS:
            token = stored.get(action)
            if token:
                self.keys[action] = token

    def save(self) -> bool:
        """保存当前按键配置到磁盘。"""
        data = {"keys": {action: self.keys[action] for action in ACTIONS}}
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存 IOOH 按键配置失败: {e}")
            return False

    def set_key(self, action: str, token: str):
        """更新单个动作的按键 token。"""
        if action in self.keys:
            self.keys[action] = token

    def token(self, action: str) -> str:
        """返回某动作的按键 token。"""
        return self.keys[action]

    def key_line(self, action: str) -> str:
        """返回写入 ini 的 key 行值（含 no_ctrl no_alt 前缀）。"""
        return f"no_ctrl no_alt {self.keys[action]}"

    def hint_lines(self, lang: str = "zh") -> List[str]:
        """返回按键提示纹理用的多行文案（依据当前按键动态生成）。"""
        if lang == "en":
            return [
                f"{key_display(self.keys['toggle_menu'], 'en')} : {ACTION_LABELS['toggle_menu']['en']}",
                f"{key_display(self.keys['prev_char'], 'en')} / {key_display(self.keys['next_char'], 'en')} : Switch Character",
                f"{key_display(self.keys['enable_toggle'], 'en')} : {ACTION_LABELS['enable_toggle']['en']}",
            ]
        return [
            f"{key_display(self.keys['toggle_menu'], 'zh')} : {ACTION_LABELS['toggle_menu']['zh']}",
            f"{key_display(self.keys['prev_char'], 'zh')} / {key_display(self.keys['next_char'], 'zh')} : 切换角色",
            f"{key_display(self.keys['enable_toggle'], 'zh')} : {ACTION_LABELS['enable_toggle']['zh']}",
        ]
