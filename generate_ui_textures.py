#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI纹理生成器 - 为3DMigoto生成角色头像层与文字层

muban.png 是游戏内UI的背景模板（已内置按键提示与箭头）。本脚本在与
muban 等大的透明画布上，分别生成两类叠加层，供 ini 以相同的面板四边形
依次叠加渲染：

  1. character_<id>_avatar.png —— 角色头像层
     在模板「白框」位置渲染角色头像（resources/avatars/<角色名>.png）；
     若该角色没有头像文件，则在同一位置渲染问号。
  2. character_<id>_text.png —— 角色文字层
     在模板白框右侧位置渲染角色名（透明底文字图像）。

三层（muban / avatar / text）使用完全相同的面板四边形坐标，对齐由画布
等大保证，无需 ini 做任何位置换算。
"""

from PIL import Image, ImageDraw, ImageFont
import os
import json
import sys
from typing import List, Tuple


class UITextureGenerator:
    """UI纹理生成器"""

    # 模板文件名
    MUBAN_FILENAME = "muban.png"

    # 叠加层在 muban 画布上的目标区域（占模板宽/高的比例）
    # 由 muban.png 实测得出：白框为头像区，其右侧空白图案区为文字区。
    AVATAR_BOX = (0.2233, 0.4155, 0.3777, 0.7658)  # L, T, R, B
    TEXT_BOX = (0.4042, 0.4511, 0.8814, 0.8157)    # L, T, R, B

    # 文字颜色：模板文字区为浅色图案，用深色文字保证可读性
    TEXT_COLOR = (28, 34, 46, 255)
    # 问号颜色：白框为纯白，用深灰问号
    QUESTION_COLOR = (90, 100, 120, 255)

    def __init__(self, base_output_dir: str = None):
        self.base_output_dir = base_output_dir or self._get_output_dir()
        self.output_dir = os.path.join(self.base_output_dir, "resources", "textures")
        self.avatar_dir = os.path.join(self.base_output_dir, "resources", "avatars")
        self.muban_path = os.path.join(self.output_dir, self.MUBAN_FILENAME)

    @staticmethod
    def _get_output_dir() -> str:
        """Return the directory where generated files should be written."""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def setup_directories(self):
        """创建必要的目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.avatar_dir, exist_ok=True)

    def get_font(self, size: int):
        """获取中文字体"""
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            "C:/Windows/Fonts/arial.ttf",   # Arial
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _muban_size(self) -> Tuple[int, int]:
        """读取模板尺寸，所有叠加层均以此为画布大小"""
        with Image.open(self.muban_path) as im:
            return im.size

    def _box_px(self, box: Tuple[float, float, float, float],
                size: Tuple[int, int]) -> Tuple[int, int, int, int]:
        """把比例区域换算为像素区域 (L, T, R, B)"""
        w, h = size
        l, t, r, b = box
        return int(l * w), int(t * h), int(r * w), int(b * h)

    def _find_avatar(self, char_name: str) -> str:
        """按角色名在 avatars 目录查找头像文件（不区分大小写）"""
        if not os.path.isdir(self.avatar_dir):
            return ""
        target = char_name.strip().lower()
        for fname in os.listdir(self.avatar_dir):
            stem, ext = os.path.splitext(fname)
            if ext.lower() in (".dds", ".png", ".jpg", ".jpeg", ".webp") and stem.lower() == target:
                return os.path.join(self.avatar_dir, fname)
        return ""

    def create_avatar_layer(self, char_id: int, char_name: str, size: Tuple[int, int]):
        """生成角色头像层：白框位置放头像，无头像则放问号"""
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        l, t, r, b = self._box_px(self.AVATAR_BOX, size)
        box_w, box_h = r - l, b - t

        avatar_path = self._find_avatar(char_name)
        if avatar_path:
            # 按比例缩放铺满白框（cover），居中裁剪。
            # dds 源通常上下颠倒，需翻正；png/jpg 等按原方向不翻转。
            src = Image.open(avatar_path).convert('RGBA')
            if os.path.splitext(avatar_path)[1].lower() == '.dds':
                src = src.transpose(Image.FLIP_TOP_BOTTOM)
            scale = max(box_w / src.width, box_h / src.height)
            new_w, new_h = max(1, round(src.width * scale)), max(1, round(src.height * scale))
            resized = src.resize((new_w, new_h), Image.LANCZOS)
            crop_l = (new_w - box_w) // 2
            crop_t = (new_h - box_h) // 2
            cropped = resized.crop((crop_l, crop_t, crop_l + box_w, crop_t + box_h))
            canvas.paste(cropped, (l, t), cropped)
            note = f"头像: {os.path.basename(avatar_path)}"
        else:
            # 无头像：白框内居中渲染问号
            draw = ImageDraw.Draw(canvas)
            font = self.get_font(int(box_h * 0.7))
            bbox = draw.textbbox((0, 0), "?", font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = l + (box_w - tw) // 2 - bbox[0]
            y = t + (box_h - th) // 2 - bbox[1]
            draw.text((x, y), "?", font=font, fill=self.QUESTION_COLOR)
            note = "无头像 → 问号"

        filename = f"character_{char_id}_avatar.png"
        self.save_image(canvas, filename)
        print(f"  生成: {filename} ({note})")

    def create_text_layer(self, char_id: int, char_name: str, size: Tuple[int, int]):
        """生成角色文字层：在文字区渲染透明底角色名，自适应字号"""
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        l, t, r, b = self._box_px(self.TEXT_BOX, size)
        box_w, box_h = r - l, b - t

        # 自适应字号：从大到小，直到文字宽高都能放进文字区
        font_size = int(box_h * 0.9)
        while font_size > 8:
            font = self.get_font(font_size)
            bbox = draw.textbbox((0, 0), char_name, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= box_w and th <= box_h:
                break
            font_size -= 2
        else:
            font = self.get_font(8)
            bbox = draw.textbbox((0, 0), char_name, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        x = l + (box_w - tw) // 2 - bbox[0]
        y = t + (box_h - th) // 2 - bbox[1]
        draw.text((x, y), char_name, font=font, fill=self.TEXT_COLOR)

        filename = f"character_{char_id}_text.png"
        self.save_image(canvas, filename)
        print(f"  生成: {filename} (文字: {char_name})")

    def create_character_layers(self, character_names: List[str]):
        """为每个角色生成头像层与文字层"""
        print("正在生成角色叠加层（头像/文字）...")
        size = self._muban_size()
        for idx, char_name in enumerate(character_names):
            self.create_avatar_layer(idx, char_name, size)
            self.create_text_layer(idx, char_name, size)

    def save_image(self, img: Image.Image, filename: str):
        """保存图像为PNG格式（3DMigoto可直接加载）"""
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath, 'PNG')
        print(f"    保存: {filepath}")

    def generate_all(self, character_names: List[str] = None):
        """生成所有UI纹理"""
        self.setup_directories()

        if not os.path.exists(self.muban_path):
            raise FileNotFoundError(f"缺少模板文件: {self.muban_path}")

        if character_names is None:
            character_names, _ = self.load_character_names()

        print("=" * 60)
        print("开始生成UI纹理...")
        print("=" * 60)

        self.create_character_layers(character_names)

        print("=" * 60)
        print(f"UI纹理生成完成！输出目录: {self.output_dir}")
        print(f"头像源目录: {self.avatar_dir}（按角色名命名，如 laevatain.png）")
        print("=" * 60)

    def load_character_names(self):
        """从key配置文件加载实际的mod，并映射到角色名称

        Returns:
            tuple: (character_names, mods_data)
        """
        key_config_path = os.path.join(self.base_output_dir, 'efmi_key_config.json')
        mapping_path = os.path.join(self._get_output_dir(), 'character_name_mapping.json')

        # 1. 读取key配置，获取实际的mod列表
        with open(key_config_path, 'r', encoding='utf-8') as f:
            key_config = json.load(f)
            mods = key_config.get('mods', [])

        # 2. 读取角色名称映射字典
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
            match_rules = mapping_data.get('match_rules', [])

        # 3. 为每个mod找到对应的角色名称
        character_names = []
        for mod in mods:
            mod_name = mod.get('name', '').lower()
            matched = False
            for rule in match_rules:
                keywords = [kw.lower() for kw in rule.get('keywords', [])]
                if any(keyword in mod_name for keyword in keywords):
                    character_names.append(rule['display_name'])
                    matched = True
                    break
            if not matched:
                character_names.append(mod.get('name', f'角色{len(character_names)}'))

        return character_names, mods


def main():
    """主函数"""
    generator = UITextureGenerator()
    generator.generate_all()

    print("\n生成的文件可用于mod.ini中的Resource定义:")
    print("[ResourceAvatar0]")
    print("filename = resources/textures/character_0_avatar.png")
    print("[ResourceText0]")
    print("filename = resources/textures/character_0_text.png")


if __name__ == "__main__":
    main()
