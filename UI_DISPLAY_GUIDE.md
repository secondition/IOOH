# EFMI 游戏内UI显示功能说明

## ✨ 新增功能

游戏内实时显示当前选中的角色名称！

## 🎯 功能特点

1. **自动名称映射**：将复杂的mod名称映射为可读的角色名称
2. **模糊匹配规则**：支持多关键词匹配，不区分大小写
3. **游戏内显示**：屏幕上实时显示"当前选中: 莱万汀 (ID 0)"
4. **完全可自定义**：编辑JSON文件即可修改显示名称

## 📋 工作流程

### 方案1：使用主配置工具（推荐）

```bash
python key_context_configurator.py
```

主配置工具会自动：
1. 扫描并配置所有mod
2. 生成角色显示配置
3. 更新主控ini的UI代码

### 方案2：单独更新显示配置

如果只需要更新角色名称映射：

```bash
python generate_character_display.py
```

## 🎨 自定义角色名称

### 步骤1：编辑映射规则

编辑 `character_name_mapping.json`：

```json
{
  "match_rules": [
    {
      "keywords": ["laevatain", "莱万汀", "雷瓦汀"],
      "display_name": "莱万汀"
    },
    {
      "keywords": ["perlica", "pelica", "佩丽卡"],
      "display_name": "佩丽卡"
    }
  ]
}
```

**匹配规则说明**：
- `keywords`: 关键词列表（不区分大小写）
- `display_name`: 游戏内显示的名称
- 匹配逻辑：mod名称包含任一关键词即匹配

### 步骤2：重新生成配置

```bash
python generate_character_display.py
```

### 步骤3：复制到游戏

将更新后的 `mod.ini` 复制到游戏Mods文件夹。

## 📁 相关文件

| 文件 | 说明 | 是否需要手动编辑 |
|------|------|-----------------|
| `character_name_mapping.json` | 名称映射规则 | ✓ 可自定义 |
| `character_display.json` | 生成的显示配置 | ✗ 自动生成 |
| `mod.ini` | 主控mod文件 | ✗ 自动更新 |

## 🎮 游戏内效果

### 按键操作

- **↑键** → 选择上一个角色
  - 屏幕显示：`当前选中: 佩丽卡 (ID 1)`
- **↓键** → 选择下一个角色
  - 屏幕显示：`当前选中: 莱万汀 (ID 0)`
- **小键盘** → 控制当前选中的角色

### 显示示例

```
游戏屏幕左上角显示：
┌─────────────────────────┐
│ 当前选中: 莱万汀 (ID 0) │
└─────────────────────────┘
```

## 💡 实现原理

### 模糊匹配

```python
# 示例：匹配 "laevatain_mk3l_7fa3f"
keywords = ["laevatain", "莱万汀"]
if "laevatain" in "laevatain_mk3l_7fa3f".lower():
    display_name = "莱万汀"  # ✓ 匹配成功
```

### 3DMigoto文本显示

```ini
[Present]
post run = ShowCharacterName

[ShowCharacterName]
if $selected_character == 0
    post $overlay_text = "当前选中: 莱万汀 (ID 0)"
else if $selected_character == 1
    post $overlay_text = "当前选中: 佩丽卡 (ID 1)"
endif
```

## ❓ 常见问题

**Q: 如何添加新的角色映射？**

A: 编辑 `character_name_mapping.json`，添加新的规则：
```json
{
  "keywords": ["新角色关键词1", "新角色关键词2"],
  "display_name": "新角色显示名称"
}
```

**Q: 显示的名称不对怎么办？**

A: 检查关键词是否包含在mod名称中，可以添加更多关键词增加匹配成功率。

**Q: 可以修改显示位置和样式吗？**

A: 当前使用3DMigoto的`$overlay_text`功能，位置由3DMigoto控制。如需自定义样式，需要编写shader。

**Q: 显示文本不更新？**

A: 
1. 确认 `mod.ini` 已复制到游戏Mods文件夹
2. 重启游戏或按F10重载3DMigoto配置

## 🔧 技术细节

### 生成的文件结构

**character_display.json**:
```json
{
  "id_to_name": {
    "0": "莱万汀",
    "1": "佩丽卡"
  },
  "characters": [
    {
      "character_id": 0,
      "display_name": "莱万汀",
      "mod_name": "laevatain_mk3l_7fa3f"
    }
  ]
}
```

### 修改历史

- **v3.0**: 新增游戏内UI显示功能
- **v3.0**: 支持角色名称模糊匹配
- **v3.0**: 自动集成到主配置工具

---

**版本**: v3.0  
**更新日期**: 2026-02-12
