# EFMI Key Context Manager

基于图像GUI的3DMigoto mod按键管理系统

## 使用步骤

### 1. 生成UI纹理
```bash
python generate_ui_textures.py
```

### 2. 安装
将整个文件夹复制到游戏Mods目录：
```
[游戏目录]/Mods/EFMI_KeyManager/
```

## 游戏内操作

- **↑/↓** - 切换角色
- **Enter** - 显示/隐藏UI
- **数字键** - 控制当前角色功能

## 核心文件

- `mod.ini` - mod配置
- `generate_ui_textures.py` - 生成UI纹理
- `key_context_configurator.py` - 配置按键绑定
- `shaders/draw_2d_ui.hlsl` - UI绘制着色器
- `character_name_mapping.json` - 角色名称配置

## 技术实现

由于3DMigoto不支持文本渲染，使用Python生成带文本的PNG图像，通过HLSL着色器绘制2D四边形显示UI。

参考：Snaccubus的EndminF MegaMenu Mod

## 许可证

MIT License
