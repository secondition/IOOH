#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EFMI Key Context Configurator - 入口

功能已按职责拆分到独立模块：
- iooh_models.py      数据模型（ModKeyBinding / ModInfo）
- iooh_keys.py        IOOH 菜单四个控制键的单一数据源（含持久化、ini key 行、提示文案）
- iooh_configurator.py 核心配置器（扫描/解析/备份/生成/注入）
- iooh_gui.py         图形界面（含 IOOH 按键自定义面板）
- generate_ui_textures.py UI 纹理生成（按键提示文案由 IOOHKeyConfig 提供）
"""

from iooh_gui import KeyConfiguratorGUI


def main():
    app = KeyConfiguratorGUI()
    app.run()


if __name__ == "__main__":
    main()
