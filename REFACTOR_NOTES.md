# EFMI Key Context Manager v3.0 - 重构完成

✅ **项目已成功重构！**

## 核心变更

### ✨ 新机制：选择器伪共享

虽然3DMigoto变量无法跨mod传输，但通过让所有mod同步计算同一个选择器变量，实现"伪共享"：

```
用户按↓键 → 所有mod响应 → 各自计算 $selected_character++
结果：所有mod的变量值保持一致！
```

### 🔄 工作原理

**双重判断**：
```ini
condition = $active0 == 1 && $selected_character == 0
            └─角色在场─┘    └─当前选中此角色─┘
```

**选择器控制**（所有mod相同代码）：
```ini
[KeySelectUp]
key = VK_UP
run = CommandListSelectUp  ; 所有mod同步-1

[KeySelectDown]
key = VK_DOWN
run = CommandListSelectDown  ; 所有mod同步+1
```

## 使用说明

### 1. 运行配置工具

```bash
python key_context_configurator.py
```

### 2. 扫描并配置

1. 输入mods目录路径
2. 点击"扫描并自动配置"
3. 脚本自动完成：
   - ✅ 为每个mod插入选择器控制代码
   - ✅ 修改按键condition为双重判断
   - ✅ 统一按键为小键盘0-9等
   - ✅ 自动备份原始文件

### 3. 游戏内使用

- **↑键**：选择上一个角色（ID-1）
- **↓键**：选择下一个角色（ID+1）
- **小键盘0-9, +, -, *, /, .**：控制当前选中的角色

## 示例场景

**3个角色mod：**
- ID 0: laevatain
- ID 1: 佩丽卡  
- ID 2: 其他角色

**场景：佩丽卡在场，但当前选中laevatain**

```
初始状态：
- $selected_character = 0 (所有mod)
- laevatain的 $active0 = 0 (不在场)
- 佩丽卡的 $object_detected = 1 (在场)

小键盘0 → 无效 ✗
原因：佩丽卡在场但 $selected_character != 1

按↓键一次：
- $selected_character = 1 (所有mod同步)

小键盘0 → 控制佩丽卡 ✓
原因：$object_detected == 1 && $selected_character == 1
```

## 技术细节

### Q: 为什么变量不能跨mod？

A: 3DMigoto的`global`变量作用域是单个mod文件夹，不同文件夹的变量互相独立。

### Q: 为什么这个方案可行？

A: **按键响应是全局的**！所有mod都接收到↑↓键，各自独立计算相同逻辑，最终结果一致。

### Q: 会不会出现不同步？

A: 只要：
1. 所有mod的选择器代码完全相同
2. 用户只通过↑↓键改变值（不手动修改）
3. 从相同初始值开始（persist保存）

就能保证同步。

## 文件说明

- `key_context_configurator.py` - 主程序（GUI）
- `mod.ini` - 主控mod模板（可选UI显示）
- `efmi_key_config.json` - 生成的配置
- `*.backup` - 自动备份文件

## 按键映射

单个mod内按检测顺序：
1. VK_NUMPAD0
2. VK_NUMPAD1
3. ...
10. VK_NUMPAD9
11. VK_ADD (+)
12. VK_SUBTRACT (-)
13. VK_MULTIPLY (*)
14. VK_DIVIDE (/)
15. VK_DECIMAL (.)

超过15个保留原键

## 注意事项

- ⚠️ 保留mod原有角色检测逻辑
- ⚠️ 角色ID由扫描顺序决定（按mod名排序）
- ⚠️ 建议手动备份mods文件夹
- ✅ 不修改角色检测变量
- ✅ 只修改按键绑定

## 更新日志

### v3.0 (2026-02-12) - 重构版
- ✨ 选择器伪共享机制
- ✨ 双重condition判断
- ✨ 保留原有角色检测
- 🗑️ 移除不可行的跨mod变量传输
- 🗑️ 移除GUI选择器

## 许可证

MIT License
