#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成游戏内GUI资源
为角色选择器生成PNG纹理文件
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont


class GUIResourceGenerator:
    """生成GUI资源"""
    
    def __init__(self):
        self.config_file = "efmi_key_config.json"
        self.output_dir = "resources"
        self.font_size = 28
        self.bg_color = (20, 20, 20, 230)  # 半透明深色背景
        self.text_color = (220, 220, 220, 255)  # 浅灰色文字
        self.highlight_bg = (61, 90, 254, 255)  # 蓝色高亮背景
        self.highlight_text = (255, 255, 255, 255)  # 白色高亮文字
        
    def load_characters(self):
        """从配置文件加载角色列表"""
        if not os.path.exists(self.config_file):
            print(f"错误: 找不到配置文件 {self.config_file}")
            print("请先运行 key_context_configurator.py 扫描mod")
            return []
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get("mods", [])
        except Exception as e:
            print(f"加载配置失败: {e}")
            return []
    
    def get_font(self, size):
        """获取字体"""
        try:
            # 尝试使用系统中文字体
            return ImageFont.truetype("msyh.ttc", size)  # 微软雅黑
        except:
            try:
                return ImageFont.truetype("arial.ttf", size)
            except:
                return ImageFont.load_default()
    
    def generate_background(self):
        """生成GUI背景"""
        width, height = 800, 1000
        img = Image.new('RGBA', (width, height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 绘制边框
        draw.rectangle([0, 0, width-1, height-1], outline=(100, 100, 100, 255), width=3)
        
        output_path = os.path.join(self.output_dir, "gui_background.png")
        img.save(output_path)
        print(f"已生成: {output_path}")
    
    def generate_title(self):
        """生成标题"""
        width, height = 800, 120
        img = Image.new('RGBA', (width, height), (40, 40, 40, 255))
        draw = ImageDraw.Draw(img)
        
        # 绘制标题文字
        font = self.get_font(40)
        title = "角色选择 (Tab)"
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        draw.text((text_x, 30), title, fill=(255, 255, 255, 255), font=font)
        
        # 绘制底部分隔线
        draw.line([(20, height-2), (width-20, height-2)], fill=(100, 100, 100, 255), width=2)
        
        output_path = os.path.join(self.output_dir, "gui_title.png")
        img.save(output_path)
        print(f"已生成: {output_path}")
    
    def generate_character_item(self, character, selected=False):
        """生成角色列表项"""
        width, height = 700, 130
        
        # 背景色
        if selected:
            bg_color = self.highlight_bg
            text_color = self.highlight_text
        else:
            bg_color = (30, 30, 30, 200)
            text_color = self.text_color
        
        img = Image.new('RGBA', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 绘制边框
        border_color = (150, 150, 150, 255) if selected else (80, 80, 80, 255)
        draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=2)
        
        # 绘制选择指示器
        if selected:
            draw.text((20, 40), "▶", fill=text_color, font=self.get_font(40))
        
        # 绘制角色ID
        char_id = character.get("character_id", 0)
        id_text = f"[{char_id}]"
        draw.text((70, 45), id_text, fill=(150, 150, 150, 255), font=self.get_font(32))
        
        # 绘制角色名称
        char_name = character.get("name", "Unknown")
        draw.text((150, 45), char_name, fill=text_color, font=self.get_font(32))
        
        # 保存
        char_id = character.get("character_id", 0)
        suffix = "_selected" if selected else ""
        output_path = os.path.join(self.output_dir, f"character_{char_id}{suffix}.png")
        img.save(output_path)
        return output_path
    
    def generate_all_resources(self):
        """生成所有GUI资源"""
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 加载角色列表
        characters = self.load_characters()
        if not characters:
            print("没有找到角色数据")
            return
        
        print(f"找到 {len(characters)} 个角色")
        print("开始生成GUI资源...")
        
        # 生成背景和标题
        self.generate_background()
        self.generate_title()
        
        # 为每个角色生成普通和选中状态
        for char in characters:
            self.generate_character_item(char, selected=False)
            self.generate_character_item(char, selected=True)
            char_name = char.get("name", "Unknown")
            print(f"  ✓ 已生成: {char_name}")
        
        print(f"\n完成！共生成 {len(characters)*2 + 2} 个GUI资源")
        print(f"资源保存在: {self.output_dir}/")
        print("\n下一步:")
        print("1. 运行配置工具更新mod.ini中的GUI绘制代码")
        print("2. 将整个项目文件夹复制到游戏Mods目录")
        print("3. 游戏内按Tab测试GUI")


def main():
    generator = GUIResourceGenerator()
    generator.generate_all_resources()


if __name__ == "__main__":
    main()
