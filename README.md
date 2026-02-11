# EFMI Key Context Manager v3.0

基于选择器的3DMigoto按键统一管理工具

## 🎯 核心机制

**选择器伪共享**：虽然3DMigoto变量无法跨mod传输，但**按键输入是全局的**！

```
用户按↓键 → 所有mod响应 → 各自计算 $selected_character++
结果：所有mod的变量值保持一致！
```

**双重判断**：
```ini
condition = $active0 == 1 && $selected_character == 0
            └─角色在场─┘    └─当前选中此角色─┘
```

## 📦 项目文件

```
IOOH/
├── key_context_configurator.py  ✓ 主程序（GUI配置工具）
├── mod.ini                      ✓ 选择器控制模板（可选）
├── efmi_key_config.json         ✓ 生成的配置文件
├── README.md                    ✓ 本文件
└── REFACTOR_NOTES.md            ✓ 重构说明
```

## 🚀 使用流程

### 步骤1: 运行配置工具

```bash
python key_context_configurator.py
```

1. 输入mods目录路径（或点击"浏览"按钮）
2. 点击"扫描并自动配置"
3. 等待完成（查看日志）

### 步骤2: 脚本自动完成

- ✅ 检测所有type=cycle的按键
- ✅ 为每个mod插入选择器控制代码
- ✅ 修改按键condition为双重判断
- ✅ 统一按键映射到小键盘0-9等
- ✅ 自动备份原始文件（.backup）

### 步骤3: 游戏内使用

- **↑键**：选择上一个角色（ID-1）
- **↓键**：选择下一个角色（ID+1）
- **小键盘0-9, +, -, *, /, .**：控制当前选中的角色

## � 按键分配

每个角色可用15个按键：
- **0-9** : VK_NUMPAD0 ~ VK_NUMPAD9
- **+** : VK_ADD
- **-** : VK_SUBTRACT
- ***** : VK_MULTIPLY
- **/** : VK_DIVIDE  
- **.** : VK_DECIMAL

## ⚙️ 高级说明

查看 [REFACTOR_NOTES.md](REFACTOR_NOTES.md) 了解：
- 技术实现细节
- 为何采用选择器机制
- v2.0→v3.0的重构原因

## 🛠 开发者信息

- **Python版本**: 3.7+
- **依赖**: tkinter (标准库)
- **目标**: 3DMigoto框架的ini文件

简洁、高效、统一 🎮

## 💡 工作示例

假设有2个角色mod，你为他们分配了ID：
- 角色A（character_id=0）
- 角色B（character_id=1）

游戏内操作：
```
1. 按↓键 → 所有mod计算: $selected_character = 1
2. 角色B检测: 在场($active1==1) && 被选中($selected_character==1) → ✓
3. 按小键盘0 → 只有角色B响应，角色A不响应
4. 按↑键 → 所有mod计算: $selected_character = 0  
5. 角色A检测: 在场($active0==1) && 被选中($selected_character==0) → ✓
6. 按小键盘0 → 只有角色A响应，角色B不响应
```

## 🐛 故障排查

**如果按键不生效**：

**如果按键不生效**：
1. 检查mod的ini文件中是否包含选择器控制代码（[KeySelectUp]/[KeySelectDown]）
2. 确认按键的condition是否为双重判断格式
3. 查看备份文件（.backup）对比修改前后的区别

**如果扫描不到mod**：
- 确保mod目录中有ini文件（mod.ini、default.ini等）
- 确保ini文件中有`type=cycle`的section
- 查看日志输出了解具体原因

---

**版本**: v3.0  
**更新日期**: 2026-02-11
