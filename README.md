# IOOH — I'm out of hotkeys

IOOH 是一个 3DMigoto mod 的小工具，用于解决多角色 mod 之间的按键冲突问题。它能自动扫描 mod 目录、重新分配小键盘按键，并生成游戏内 UI 覆盖层，让你在游戏中直观地切换角色和控制 mod 功能。

ui相当简陋，因为我要拉电线去了。

ps：只测试了终末地模组，并且只对绑定了 `type=cycle` 的按键进行重分配，其他类型的按键（如 `type=hold`）暂不支持。



## 功能

- 自动扫描 mod 目录，检测 `type=cycle` 按键绑定
- 将冲突按键自动重分配到小键盘（0-9、+-*/. 共 15 键）
- 为每个 mod 注入本地选择器变量 `$iooh_s<id>`，无需修改 `d3dx.ini`
- 生成游戏内 UI 配置（`IOOHmod.ini`），显示角色列表和按键图标
- 生成 UI 纹理资源（角色名称标签、按键图标、帮助文本）

## 使用方法

### 1. 安装依赖

```bash
pip install Pillow
```

### 2. 运行配置工具

```bash
python key_context_configurator.py
```

在弹出的 GUI 中：
1. 选择你的 mod 目录（包含各角色 mod 子文件夹的路径）
2. 点击「扫描并自动配置」
3. 工具会自动完成按键分配、mod 注入、配置生成和 UI 纹理生成

### 3. 部署到游戏

将以下文件复制到游戏的 3DMigoto mod 目录中：
- `IOOHmod.ini`
- `resources/` 文件夹（UI 纹理）
- `shaders/` 文件夹（渲染着色器）

### 4. 游戏内操作

| 按键 | 功能 |
|------|------|
| ↑ / ↓ | 切换角色 |
| Enter | 显示 / 隐藏 UI |
| 小键盘 0-9、+-*/. | 控制当前角色的 mod 功能 |

## 自定义角色名称

编辑 `character_name_mapping.json` 添加角色名称映射规则，UI 中将显示友好的中文名称而非 mod 文件夹名。

## AI 辅助开发说明

本项目在开发过程中大量使用了 AI 编程辅助工具。如果你想修改或扩展本项目，推荐使用 AI 编码助手（如 Claude Code、Cursor 等）来理解代码结构和进行开发，可以显著提升效率。
