#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI纹理生成器 - 为3DMigoto生成带文本的PNG纹理

由于3DMigoto无法直接显示文本，此脚本生成包含文本的PNG图像纹理
用于游戏内GUI显示当前选中的角色名称和提示信息
"""

from PIL import Image, ImageDraw, ImageFont
import os
import json
from typing import List, Tuple


VK_DISPLAY_NAMES = {
    "VK_NUMPAD0": "Num0", "VK_NUMPAD1": "Num1", "VK_NUMPAD2": "Num2",
    "VK_NUMPAD3": "Num3", "VK_NUMPAD4": "Num4", "VK_NUMPAD5": "Num5",
    "VK_NUMPAD6": "Num6", "VK_NUMPAD7": "Num7", "VK_NUMPAD8": "Num8",
    "VK_NUMPAD9": "Num9", "VK_ADD": "Num+", "VK_SUBTRACT": "Num-",
    "VK_MULTIPLY": "Num*", "VK_DIVIDE": "Num/", "VK_DECIMAL": "Num.",
}

# 15个小键盘按键: (VK名, 显示符号, 文件名后缀)
NUMPAD_KEYS_INFO = [
    ("VK_NUMPAD0", "0", "num0"), ("VK_NUMPAD1", "1", "num1"),
    ("VK_NUMPAD2", "2", "num2"), ("VK_NUMPAD3", "3", "num3"),
    ("VK_NUMPAD4", "4", "num4"), ("VK_NUMPAD5", "5", "num5"),
    ("VK_NUMPAD6", "6", "num6"), ("VK_NUMPAD7", "7", "num7"),
    ("VK_NUMPAD8", "8", "num8"), ("VK_NUMPAD9", "9", "num9"),
    ("VK_ADD", "+", "add"), ("VK_SUBTRACT", "-", "subtract"),
    ("VK_MULTIPLY", "*", "multiply"), ("VK_DIVIDE", "/", "divide"),
    ("VK_DECIMAL", ".", "decimal"),
]


class UITextureGenerator:
    """UI纹理生成器"""

    def __init__(self):
        self.output_dir = "resources/textures"
        self.font_size = 32
        self.bg_color = (20, 20, 30, 200)  # 深色半透明背景
        self.text_color = (255, 255, 255, 255)  # 白色文本
        self.highlight_color = (100, 200, 255, 255)  # 高亮蓝色
        self.padding = 20
        
    def setup_directories(self):
        """创建必要的目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        
    def get_font(self, size: int = None):
        """获取字体，优先使用中文字体"""
        if size is None:
            size = self.font_size
            
        # 尝试Windows中文字体
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            "C:/Windows/Fonts/arial.ttf",   # Arial
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except:
                    continue
                    
        # 使用默认字体
        return ImageFont.load_default()
        
    def create_text_image(self, text: str, width: int = 400, height: int = 80,
                         bg_color: Tuple = None, text_color: Tuple = None,
                         centered: bool = True) -> Image.Image:
        """创建包含文本的图像
        
        Args:
            text: 要显示的文本
            width: 图像宽度
            height: 图像高度
            bg_color: 背景颜色 (R, G, B, A)
            text_color: 文字颜色 (R, G, B, A)
            centered: 是否居中对齐
        """
        if bg_color is None:
            bg_color = self.bg_color
        if text_color is None:
            text_color = self.text_color
            
        # 创建RGBA图像
        img = Image.new('RGBA', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 获取字体
        font = self.get_font()
        
        # 计算文本位置
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        if centered:
            x = (width - text_width) // 2
            y = (height - text_height) // 2
        else:
            x = self.padding
            y = (height - text_height) // 2
            
        # 绘制文本
        draw.text((x, y), text, font=font, fill=text_color)
        
        return img
        
    def create_character_selector_ui(self, character_names: List[str], selected_index: int = 0):
        """创建角色选择器UI图像
        
        为每个可能的选择状态生成一张图像
        """
        print(f"正在生成角色选择器UI图像...")
        
        # UI尺寸
        width = 500
        height = 100
        
        for idx, char_name in enumerate(character_names):
            # 生成未选中状态
            text = f"角色 {idx}: {char_name}"
            img = self.create_text_image(text, width, height,
                                        bg_color=self.bg_color,
                                        text_color=self.text_color)
            filename = f"character_{idx}_normal.png"
            self.save_image(img, filename)
            print(f"  生成: {filename}")
            
            # 生成选中状态（高亮）
            img_selected = self.create_text_image(text, width, height,
                                                 bg_color=(40, 80, 120, 220),
                                                 text_color=self.highlight_color)
            filename_selected = f"character_{idx}_selected.png"
            self.save_image(img_selected, filename_selected)
            print(f"  生成: {filename_selected}")
            
    def create_help_text(self):
        """创建帮助文本图像"""
        print("正在生成帮助文本...")
        
        help_texts = [
            ("↑↓: 切换角色", 350, 50),
            ("数字键: 控制功能", 350, 50),
            ("Enter: 显示/隐藏UI", 380, 50),
        ]
        
        for text, w, h in help_texts:
            img = self.create_text_image(text, w, h,
                                        bg_color=(10, 10, 20, 180),
                                        text_color=(200, 200, 200, 255))
            safe_name = text.replace(":", "_").replace("/", "_").replace(" ", "_")
            filename = f"help_{safe_name}.png"
            self.save_image(img, filename)
            print(f"  生成: {filename}")
            
    def create_background_panel(self):
        """创建背景面板图像"""
        print("正在生成背景面板...")
        
        # 主面板背景
        width, height = 600, 400
        img = Image.new('RGBA', (width, height), (15, 15, 25, 200))
        draw = ImageDraw.Draw(img)
        
        # 绘制边框
        border_color = (80, 120, 160, 255)
        draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=3)
        
        self.save_image(img, "panel_background.png")
        print("  生成: panel_background.png")
        
        # 小型UI背景
        small_img = Image.new('RGBA', (500, 100), (20, 20, 30, 200))
        draw_small = ImageDraw.Draw(small_img)
        draw_small.rectangle([0, 0, 499, 99], outline=border_color, width=2)
        self.save_image(small_img, "ui_background.png")
        print("  生成: ui_background.png")
        
    def create_key_icon_textures(self):
        """生成15个固定的小键盘按键图标纹理

        每个图标是一个小方块，显示按键符号（0-9, +, -, *, /, .）
        在INI中根据角色实际使用的键位条件绘制这些图标。
        """
        print("正在生成按键图标纹理...")

        font = self.get_font(28)
        icon_w, icon_h = 70, 55
        bg = (25, 30, 45, 220)
        border = (80, 140, 200, 255)
        text_fill = (220, 230, 255, 255)

        for vk_name, symbol, suffix in NUMPAD_KEYS_INFO:
            img = Image.new('RGBA', (icon_w, icon_h), bg)
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, icon_w - 1, icon_h - 1],
                           outline=border, width=2)
            # 居中绘制符号
            bbox = draw.textbbox((0, 0), symbol, font=font)
            tx = (icon_w - (bbox[2] - bbox[0])) // 2
            ty = (icon_h - (bbox[3] - bbox[1])) // 2
            draw.text((tx, ty), symbol, font=font, fill=text_fill)

            filename = f"key_{suffix}.png"
            self.save_image(img, filename)
            print(f"  生成: {filename}")

    def save_image(self, img: Image.Image, filename: str):
        """保存图像为PNG格式
        
        3DMigoto支持直接加载PNG纹理，无需转换为DDS
        """
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath, 'PNG')
        print(f"    保存: {filepath}")
        
    def generate_all(self, character_names: List[str] = None):
        """生成所有UI纹理"""
        self.setup_directories()

        if character_names is None:
            character_names, _ = self.load_character_names()

        print("=" * 60)
        print("开始生成UI纹理...")
        print("=" * 60)

        self.create_character_selector_ui(character_names)
        self.create_help_text()
        self.create_background_panel()
        self.create_key_icon_textures()

        print("=" * 60)
        print(f"UI纹理生成完成！输出目录: {self.output_dir}")
        print("PNG纹理可直接在3DMigoto中使用，无需转换为DDS")
        print("=" * 60)
        
    def load_character_names(self):
        """从key配置文件加载实际的mod，并映射到角色名称

        Returns:
            tuple: (character_names, mods_data)
        """
        try:
            # 1. 读取key配置，获取实际的mod列表
            with open('efmi_key_config.json', 'r', encoding='utf-8') as f:
                key_config = json.load(f)
                mods = key_config.get('mods', [])

            # 2. 读取角色名称映射字典
            with open('character_name_mapping.json', 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                match_rules = mapping_data.get('match_rules', [])

            # 3. 为每个mod找到对应的角色名称
            character_names = []
            for mod in mods:
                mod_name = mod.get('name', '').lower()

                # 尝试匹配规则
                matched = False
                for rule in match_rules:
                    keywords = [kw.lower() for kw in rule.get('keywords', [])]
                    if any(keyword in mod_name for keyword in keywords):
                        character_names.append(rule['display_name'])
                        matched = True
                        break

                # 如果没有匹配，使用原始mod名称
                if not matched:
                    character_names.append(mod.get('name', f'角色{len(character_names)}'))

            if not character_names:
                return ["角色0"], None
            return character_names, mods

        except Exception as e:
            print(f"警告: 加载配置文件失败: {e}")
            print("将使用默认角色列表")
            return ["角色0", "角色1", "角色2"], None


def main():
    """主函数"""
    generator = UITextureGenerator()
    
    # 从efmi_key_config.json自动读取实际配置的mod并映射到角色名称
    # 不再需要手动指定角色列表
    generator.generate_all()
    
    print("\n生成的文件可用于mod.ini中的Resource定义:")
    print("[ResourceCharacter0Selected]")
    print("filename = resources/textures/character_0_selected.png")
    print("\n然后在CustomShader中使用:")
    print("ps-t100 = ResourceCharacter0Selected")
    print("Draw = 4,0")


if __name__ == "__main__":
    main()
