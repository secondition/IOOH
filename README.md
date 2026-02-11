# EFMI 按键上下文管理器

用有限的按键控制多个角色的服装切换系统。

## 🎯 解决什么问题

当你安装多个角色mod时：
- ❌ 按一个键会同时触发所有角色
- ❌ 每个mod使用不同的按键，难以记忆

**本工具的解决方案**：
- ✅ Tab键打开GUI，上下键选择角色
- ✅ 每个角色的按键自动统一为小键盘0-9
- ✅ 激活哪个角色，就只控制那个角色

## 🚀 快速开始

### 1. 配置mod

运行配置工具：
```bash
python key_context_configurator.py
```

1. 选择mods目录（包含所有角色mod的文件夹）
2. 点击"扫描"（自动检测所有mod的按键）
3. 点击"应用修改"（自动修改所有mod并备份）

### 2. 游戏内使用

```
Tab      → 打开角色选择GUI
↑/↓      → 选择角色
Enter    → 激活选中的角色
ESC      → 关闭GUI

小键盘   → 控制当前激活的角色（最多15个按键）
  0-9    → 前10个按键
  * + - / . → 第11-15个按键
```

## 📖 详细说明

### 工作原理

1. **扫描mod**：自动检测所有mod文件夹中的.ini文件（mod.ini、default.ini等）
2. **识别按键**：只检测 `type=cycle` 的按键（模型切换功能）
3. **自动分配**：按检测顺序分配小键盘0-9（第1个按键→0，第2个→1...）
4. **添加条件**：为每个按键添加 `$active_character == X` 条件
5. **自动备份**：所有修改前自动创建.backup备份文件

### 按键分配规则

**不按功能固定映射，而是按检测顺序自动分配到小键盘**

可用按键（共15个）：
1. 数字键：0-9（10个）
2. 运算符：* + - /（4个）
3. 小数点：.（1个）

例如某个mod检测到5个按键：
```
第1个检测到的 → 小键盘0
第2个检测到的 → 小键盘1
第3个检测到的 → 小键盘2
第4个检测到的 → 小键盘3
第5个检测到的 → 小键盘4
```

如果检测到12个按键：
```
第1-10个 → 小键盘0-9
第11个 → 小键盘*
第12个 → 小键盘+
```

如果超过15个按键，超出部分保持原按键不变（会有警告提示）。

### 示例

假设有2个mod：

**ModA检测到**：
```ini
[Keycoat] type=cycle   → 分配小键盘0
[Keyshoes] type=cycle  → 分配小键盘1
```

**ModB检测到（12个按键）**：
```ini
[KeySwap_1] type=cycle  → 分配小键盘0
[KeySwap_2] type=cycle  → 分配小键盘1
...
[KeySwap_10] type=cycle → 分配小键盘9
[KeySwap_11] type=cycle → 分配小键盘*
[KeySwap_12] type=cycle → 分配小键盘+
```

**游戏内使用**：
1. Tab → 选择ModA → Enter激活
2. 小键盘0 → 切换coat
3. 小键盘1 → 切换shoes
4. Tab → 选择ModB → Enter激活
5. 小键盘0-9 → 触发Swap_1到Swap_10
6. 小键盘* → 触发Swap_11
7. 小键盘+ → 触发Swap_12

## 🔧 配置工具详解

### 扫描规则

**会被检测的**：
- ✓ 所有.ini文件（mod.ini、default.ini、config.ini等）
- ✓ 包含 `key = XXX` 的section
- ✓ 包含 `type = cycle` 的section

**会被跳过的**：
- ✗ EFMI_KeyContext_Manager文件夹（工具自身）
- ✗ type=standard 或其他类型的按键
- ✗ 没有type的按键

### 日志输出示例

```
开始扫描目录: d:\mods
只检测包含 type=cycle 的按键（模型切换功能）...
扫描完成，发现 3 个支持模型切换的mod
  ✓ PelicaMod: default.ini (5个cycle按键)
  ⚠ CharacterA: mod.ini, config.ini (18个cycle按键，超过15个)
  ✓ CharacterB: settings.ini (3个cycle按键)
已自动按检测顺序分配小键盘按键（0-9 + */+-.，共15个）
表格更新完成，共扫描 4 个ini文件，26 个cycle按键绑定
```

注意：超过15个按键的mod会显示警告，超出部分保持原按键。

### 修改内容

工具会修改每个按键section：

**修改前**：
```ini
[Keycoat]
condition = $object_detected
key = VK_LEFT
type = cycle
$coat = 0,1
```

**修改后**：
```ini
[Keycoat]
condition = $object_detected && $active_character == 1
key = VK_NUMPAD0
type = cycle
$coat = 0,1
```

## ⚙️ 自定义按键

如果Tab键冲突，可以修改 `mod.ini`：

```ini
[KeyToggleCharacterGUI]
key = VK_TAB          ; 改为 VK_GRAVE (~ 键) 等

[KeyPreviousCharacter]
key = VK_UP           ; 改为其他键

[KeyNextCharacter]
key = VK_DOWN         ; 改为其他键
```

常用键码：`VK_GRAVE` (~键)、`VK_F1`-`VK_F12`、`VK_LSHIFT`、`VK_LCONTROL`

## 🐛 问题排查

### 扫描不到mod
- 检查mod文件夹中是否有.ini文件
- 检查ini文件中是否有 `type = cycle` 的按键
- 查看日志确认是否被跳过

### 按键不生效
- 确认EFMI_KeyContext_Manager已加载
- 按Tab打开GUI并用Enter激活角色
- 检查是否与其他mod冲突

### 恢复原始配置
每个被修改的ini文件都有.backup备份：
```bash
# 恢复单个文件
copy mod.ini.backup mod.ini

# 批量恢复（PowerShell）
Get-ChildItem -Recurse -Filter "*.backup" | ForEach-Object {
    Copy-Item $_.FullName ($_.FullName -replace '.backup$','') -Force
}
```

## 📁 项目文件

```
EFMI_KeyContext_Manager/
├── mod.ini                           # 主控mod配置
├── key_context_configurator.py      # 配置工具（GUI）
├── character_selector_gui_preview.py # GUI预览工具
└── README.md                         # 本文档
```

## 💡 技术说明

- **全局变量**：`$active_character`（当前激活的角色ID，0=未激活）
- **GUI控制**：`$gui_visible`（GUI是否显示），`$selected_character_index`（当前选中索引）
- **条件判断**：所有按键添加 `condition = ... && $active_character == X`
- **自动分配**：按检测顺序分配小键盘按键（0-9, */+-.，共15个）
- **备份保护**：修改前自动创建.backup文件
- **超限处理**：超过15个按键的部分保持原按键不变

## 🎉 特点总结

- ✅ **自动化**：扫描→分配→修改，一键完成
- ✅ **通用性**：支持任意格式的mod.ini、default.ini等
- ✅ **智能识别**：只处理type=cycle的模型切换功能
- ✅ **顺序分配**：不需要理解功能，按顺序分配0-9
- ✅ **安全保护**：自动备份，可随时恢复
- ✅ **GUI选择**：可视化选择角色，不需要记忆按键
- ✅ **无限扩展**：不受功能键数量限制

---

**版本**：v2.1  
**更新日期**：2026-02-11  
**作者**：EFMI Community
