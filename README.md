# EFMI 按键上下文管理器

用有限的按键控制多个角色的服装切换系统 - **带游戏内可视化GUI**。

## 🎯 解决什么问题

当你安装多个角色mod时：
- ❌ 按一个键会同时触发所有角色
- ❌ 每个mod使用不同的按键，难以记忆

**本工具的解决方案**：
- ✅ **游戏内可视化GUI** - Tab键打开，直接看到角色列表
- ✅ 每个角色的按键自动统一为小键盘0-9
- ✅ 激活哪个角色，就只控制那个角色

## ⚠️ 使用前检查

### 必需文件检查清单
在运行前确保以下文件存在：

```
IOOH/
├── mod.ini                      ✓ 核心配置文件
├── shaders/
│   └── draw_2d.hlsl            ✓ GUI渲染shader
├── resources/                   ⚠ 需要生成（见步骤2）
│   ├── gui_background.png      ⚠ 运行步骤2生成
│   ├── gui_title.png           ⚠ 运行步骤2生成
│   ├── character_*.png         ⚠ 运行步骤2生成
│   └── character_*_selected.png ⚠ 运行步骤2生成
├── key_context_configurator.py  ✓ 配置工具
├── generate_gui_resources.py    ✓ GUI资源生成工具
└── efmi_key_config.json         ⚠ 运行步骤1生成
```

## 🚀 完整使用流程

### 步骤1: 配置mod按键

```bash
python key_context_configurator.py
```

操作：
1. 在GUI中输入或选择mods目录
2. 点击"扫描并自动配置"按钮
3. 等待扫描完成（会显示检测到的mod数量）
4. 检查日志输出确认：
   - ✓ "配置已保存到 efmi_key_config.json"
   - ✓ "已更新 mod.ini 中的GUI绘制代码"

**如果出现错误**：
- 确保mods目录路径正确
- 确保至少有一个mod包含`type=cycle`的按键

### 步骤2: 生成GUI资源图片

```bash
python generate_gui_resources.py
```

这会生成：
- `resources/gui_background.png` - GUI背景面板
- `resources/gui_title.png` - 标题栏
- `resources/character_X.png` - 每个角色的普通状态
- `resources/character_X_selected.png` - 每个角色的选中状态

**验证生成**：
```bash
dir resources
# 应该看到至少 2 + (角色数量×2) 个PNG文件
```

### 步骤3: 复制到游戏

将**整个IOOH文件夹**复制到游戏的Mods目录：
```
游戏目录/Mods/IOOH/
├── mod.ini
├── shaders/
├── resources/
└── ...
```

**注意**：
- ⚠️ 不要只复制mod.ini
- ⚠️ 必须保持文件夹结构
- ⚠️ shader和resources必须在正确的子目录

### 步骤4: 游戏内测试

1. 启动游戏
2. 按`Tab`键 → 应该看到GUI面板
3. 使用`↑/↓`键 → 选择角色（高亮会移动）
4. 按`Enter` → 激活角色并关闭GUI
5. 使用`小键盘0-9` → 控制当前激活的角色

**如果GUI不显示**：
- 检查3DMigoto控制台（F10）是否有shader错误
- 确认resources文件夹中的PNG都已生成
- 确认shaders/draw_2d.hlsl存在

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

## 🐛 完整故障排查指南

### 运行check_project.py检查

首先运行项目检查工具：
```bash
python check_project.py
```

这会显示所有文件的状态和缺失的内容。

### GUI不显示的原因

**问题1: 按Tab没反应**
- 检查：mod.ini是否在正确位置（游戏Mods/IOOH/mod.ini）
- 检查：是否有其他mod占用了Tab键
- 解决：在mod.ini中修改`[KeyToggleCharacterGUI]`的key值

**问题2: GUI显示但是空白**
- 检查：resources文件夹是否存在
- 检查：是否运行了generate_gui_resources.py
- 检查：PNG文件是否都已生成
- 解决：运行`python generate_gui_resources.py`

**问题3: Shader错误（F10控制台）**
- 检查：shaders/draw_2d.hlsl是否存在
- 检查：文件路径是否正确（必须是shaders子目录）
- 解决：确保整个文件夹结构完整复制到游戏

### 扫描不到mod

**检查mod文件夹**：
```bash
# 在mods目录运行
dir /s *.ini
# 应该看到各个mod的ini文件
```

**检查ini内容**：
打开一个mod的ini文件，搜索`type = cycle`，如果没有找到说明该mod不支持。

**查看扫描日志**：
配置工具会显示每个mod的扫描结果，注意看：
- "只检测包含 type=cycle 的按键"
- "✓ ModName: file.ini (X个cycle按键)"

### 按键不生效

**激活角色检查**：
1. 按Tab打开GUI
2. 用↑/↓选择角色（应该看到高亮移动）
3. 按Enter确认（GUI应该关闭）
4. 现在小键盘才会控制该角色

**条件检查**：
打开被修改的mod ini文件，查找按键section：
```ini
[KeySomething]
key = VK_NUMPAD0
condition = $active_character == 1  # ← 必须有这一行
type = cycle
```

### 资源文件问题

**PNG生成失败**：
- 检查：是否安装了PIL库 (`pip install pillow`)
- 检查：efmi_key_config.json是否存在
- 查看：generate_gui_resources.py的错误输出

**PNG文件路径错误**：
确保目录结构：
```
IOOH/
├── mod.ini
├── resources/
│   ├── gui_background.png
│   ├── gui_title.png
│   ├── character_1.png
│   └── character_1_selected.png
└── shaders/
    └── draw_2d.hlsl
```

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

### 常见错误信息

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| "找不到配置文件" | 未运行步骤1 | 运行key_context_configurator.py |
| "shader编译失败" | shader文件缺失 | 确认shaders/draw_2d.hlsl存在 |
| "纹理加载失败" | PNG文件缺失 | 运行generate_gui_resources.py |
| "未检测到mod" | mod无cycle按键 | 检查mod的ini文件 |

## 📁 项目文件说明

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

## ⚠️ 注意事项

### 按键数量限制
- 每个mod最多支持**15个cycle按键**
- 超过15个的按键会保持原始配置并显示警告

### 备份文件
- 工具会自动创建`.backup`备份文件
- 如需恢复原始配置，将.backup重命名即可

### 配置文件
- `efmi_key_config.json`在工具根目录
- 角色选择GUI依赖此文件显示角色列表
- 每次扫描都会自动更新此文件

### 只处理cycle按键
工具只会修改`type=cycle`的按键（模型切换功能），其他类型的按键不受影响。

## 🔍 FAQ

**Q: 角色选择GUI显示示例数据？**

A: 说明没有找到`efmi_key_config.json`文件
- 运行配置工具并点击"扫描并自动配置"
- 查看日志确认"✓ 配置已保存到..."

**Q: 扫描后没有检测到mod？**

A: 可能原因：
- mod文件夹中没有.ini文件
- .ini文件中没有`type=cycle`的按键
- 工具跳过了自身目录

**Q: 游戏内按键不生效？**

A: 检查：
1. 是否通过Tab键激活了对应角色
2. mod.ini是否在游戏的Mods文件夹中
3. 查看.ini文件是否包含`condition = $active_character == X`

## 📄 配置文件格式

`efmi_key_config.json`示例：

```json
{
  "version": "1.0",
  "generated_at": "2026-02-11T10:30:00",
  "mods_directory": "d:/mods",
  "mods": [
    {
      "name": "角色A",
      "character_id": 1,
      "key_bindings": [
        {
          "section": "KeySwap1",
          "key": "VK_NUMPAD0",
          "original_key": "VK_F1",
          "description": "衣服切换"
        }
      ]
    }
  ]
}
```
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
