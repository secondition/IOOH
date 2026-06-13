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
import shutil
import sys
from typing import List, Tuple


class UITextureGenerator:
    """UI纹理生成器"""

    # 模板文件名
    MUBAN_FILENAME = "muban.png"

    # 叠加层在 muban 画布上的目标区域（占模板宽/高的比例）
    # 头像为左上角证件照式小图（3:4 竖向），不铺满整个边框内部。
    AVATAR_BOX = (0.0676, 0.1755, 0.4117, 0.4479)  # L, T, R, B

    # 文字层：角色名渲染在头像右侧、整体底边对齐头像底边。
    # 中文在上（偏大），英文在下（偏小），两行左对齐。
    TEXT_GAP = 0.03          # 文字左缘与头像右缘的水平间距（占模板宽比例）
    TEXT_CN_HEIGHT = 0.050   # 中文字高（占模板高比例，偏大）
    TEXT_EN_HEIGHT = 0.030   # 英文字高（占模板高比例，偏小）
    TEXT_LINE_GAP = 0.008    # 中英两行之间的垂直间距（占模板高比例）

    # 文字颜色：加粗纯黑，保证在白底模板上清晰可读
    TEXT_COLOR = (0, 0, 0, 255)

    # 状态图案：画在头像/名称下方的空白区，全局共用两张（启用/禁用）。
    # STATUS_BOX 为该图案的目标区域（占模板宽/高比例，居中绘制胶囊徽章）。
    STATUS_BOX = (0.20, 0.52, 0.80, 0.60)  # L, T, R, B
    STATUS_ENABLED_COLOR = (46, 170, 90, 255)    # 启用：绿
    STATUS_DISABLED_COLOR = (170, 60, 60, 255)   # 禁用：红
    STATUS_TEXT_COLOR = (255, 255, 255, 255)     # 徽章内文字：白

    # 按键提示层：状态图案下方的全局静态热键说明（不随角色变化）。
    # HINT_BOX 为提示区域（占模板宽/高比例），多行左对齐居中排版。
    HINT_BOX = (0.12, 0.66, 0.90, 0.94)  # L, T, R, B
    HINT_HEIGHT = 0.026                  # 每行字高（占模板高比例）
    HINT_COLOR = (40, 46, 58, 255)       # 提示文字颜色：深灰
    HINT_LINES = [
        "小键盘 0 : 显示 / 隐藏菜单",
        "PageUp / PageDown : 切换角色",
        "小键盘 2 : 启用 / 禁用角色",
    ]
    # 问号颜色：白框为纯白，用深灰问号
    QUESTION_COLOR = (90, 100, 120, 255)

    def __init__(self, base_output_dir: str = None):
        self.base_output_dir = base_output_dir or self._get_output_dir()
        # 输出：游戏渲染资源写在 exe/脚本旁的 resources/textures
        self.output_dir = os.path.join(self.base_output_dir, "resources", "textures")
        # 源素材：随包分发的 assets（头像 + muban 模板），只读
        self.assets_dir = self._get_assets_dir()
        self.avatar_dir = os.path.join(self.assets_dir, "avatars")
        self.muban_src = os.path.join(self.assets_dir, self.MUBAN_FILENAME)
        # muban 运行时副本：复制到输出目录供游戏渲染加载
        self.muban_path = os.path.join(self.output_dir, self.MUBAN_FILENAME)

    @staticmethod
    def _get_output_dir() -> str:
        """Return the directory where generated files should be written."""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def _get_assets_dir() -> str:
        """Return the directory containing bundled source assets (avatars + muban)."""
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "assets")

    def setup_directories(self):
        """创建输出目录，并把 muban 模板从源素材复制到输出供游戏渲染"""
        os.makedirs(self.output_dir, exist_ok=True)
        if not os.path.exists(self.muban_src):
            raise FileNotFoundError(f"缺少源模板文件: {self.muban_src}")
        shutil.copy2(self.muban_src, self.muban_path)

    def get_font(self, size: int, bold: bool = False):
        """获取中文字体"""
        if bold:
            font_paths = [
                "C:/Windows/Fonts/msyhbd.ttc",  # 微软雅黑 Bold
                "C:/Windows/Fonts/simhei.ttf",  # 黑体
            ]
        else:
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

    def _find_avatar(self, keywords: List[str]) -> str:
        """按关键词列表在 avatars 目录查找头像文件（不区分大小写）。
        关键词含英文名/中文名，与文件名（去扩展名）相等即匹配。"""
        if not os.path.isdir(self.avatar_dir):
            return ""
        targets = [kw.strip().lower() for kw in keywords if kw.strip()]
        for fname in os.listdir(self.avatar_dir):
            stem, ext = os.path.splitext(fname)
            if ext.lower() in (".dds", ".png", ".jpg", ".jpeg", ".webp") and stem.lower() in targets:
                return os.path.join(self.avatar_dir, fname)
        return ""

    def create_avatar_layer(self, char_id: int, keywords: List[str], size: Tuple[int, int]):
        """生成角色头像层：白框位置放头像，无头像则放问号"""
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        l, t, r, b = self._box_px(self.AVATAR_BOX, size)
        box_w, box_h = r - l, b - t

        avatar_path = self._find_avatar(keywords)
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

    def create_text_layer(self, char_id: int, name_cn: str, name_en: str, size: Tuple[int, int]):
        """生成角色文字层：头像右侧渲染中英双行名称（中文在上偏大、英文在下偏小），
        整体底边对齐头像底边，两行左对齐。"""
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        w, h = size

        # 锚点：头像右缘 + 间距为左缘；头像底边为文字整体底边
        _, _, av_r, av_b = self._box_px(self.AVATAR_BOX, size)
        x_left = av_r + int(self.TEXT_GAP * w)
        y_bottom = av_b

        cn_font = self.get_font(int(self.TEXT_CN_HEIGHT * h), bold=True)
        en_font = self.get_font(int(self.TEXT_EN_HEIGHT * h), bold=True)
        line_gap = int(self.TEXT_LINE_GAP * h)

        # 英文行：底边贴 y_bottom
        if name_en:
            en_bbox = draw.textbbox((0, 0), name_en, font=en_font)
            en_x = x_left - en_bbox[0]
            en_y = y_bottom - en_bbox[3]
            draw.text((en_x, en_y), name_en, font=en_font, fill=self.TEXT_COLOR)
            en_top = y_bottom - (en_bbox[3] - en_bbox[1])
        else:
            en_top = y_bottom

        # 中文行：底边贴英文行顶部 - 行间距
        cn_bottom = en_top - line_gap
        cn_bbox = draw.textbbox((0, 0), name_cn, font=cn_font)
        cn_x = x_left - cn_bbox[0]
        cn_y = cn_bottom - cn_bbox[3]
        draw.text((cn_x, cn_y), name_cn, font=cn_font, fill=self.TEXT_COLOR)

        filename = f"character_{char_id}_text.png"
        self.save_image(canvas, filename)
        print(f"  生成: {filename} (文字: {name_cn} / {name_en})")

    def create_status_layer(self, enabled: bool, size: Tuple[int, int]):
        """生成状态图案层（全局共用）：在头像/名称下方空白区画胶囊徽章。
        启用为绿底「已启用 ON」，禁用为红底「已禁用 OFF」。"""
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        l, t, r, b = self._box_px(self.STATUS_BOX, size)
        box_w, box_h = r - l, b - t
        radius = box_h // 2

        color = self.STATUS_ENABLED_COLOR if enabled else self.STATUS_DISABLED_COLOR
        # 胶囊形背景
        draw.rounded_rectangle([l, t, r, b], radius=radius, fill=color)

        # 徽章内文字
        label = "● 已启用 ON" if enabled else "○ 已禁用 OFF"
        font = self.get_font(int(box_h * 0.5), bold=True)
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        tx = l + (box_w - tw) // 2 - tb[0]
        ty = t + (box_h - th) // 2 - tb[1]
        draw.text((tx, ty), label, font=font, fill=self.STATUS_TEXT_COLOR)

        filename = "status_enabled.png" if enabled else "status_disabled.png"
        self.save_image(canvas, filename)
        print(f"  生成: {filename} (状态: {'启用' if enabled else '禁用'})")

    def create_hint_layer(self, size: Tuple[int, int]):
        """生成按键提示层（全局静态）：状态图案下方多行热键说明，居中排版。"""
        canvas = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        _, h = size

        l, t, r, b = self._box_px(self.HINT_BOX, size)
        box_w, box_h = r - l, b - t
        font = self.get_font(int(self.HINT_HEIGHT * h), bold=True)

        # 行高按字高 + 行距均分；多行整体在提示区垂直居中
        line_h = int(self.HINT_HEIGHT * h * 1.6)
        total_h = line_h * len(self.HINT_LINES)
        y = t + (box_h - total_h) // 2

        for line in self.HINT_LINES:
            tb = draw.textbbox((0, 0), line, font=font)
            tw = tb[2] - tb[0]
            x = l + (box_w - tw) // 2 - tb[0]
            draw.text((x, y - tb[1]), line, font=font, fill=self.HINT_COLOR)
            y += line_h

        self.save_image(canvas, "hint_keys.png")
        print(f"  生成: hint_keys.png (按键提示 {len(self.HINT_LINES)} 行)")

    def create_character_layers(self, characters: List[dict]):
        """为每个角色生成头像层与文字层
        characters 每项: {"display": 中文名, "display_en": 英文名, "keywords": 头像匹配关键词列表}
        """
        print("正在生成角色叠加层（头像/文字）...")
        size = self._muban_size()
        for idx, char in enumerate(characters):
            self.create_avatar_layer(idx, char["keywords"], size)
            self.create_text_layer(idx, char["display"], char.get("display_en", ""), size)
        # 状态图案：全局共用两张（启用/禁用），运行时按当前角色状态切换
        self.create_status_layer(True, size)
        self.create_status_layer(False, size)
        # 按键提示：全局静态一张
        self.create_hint_layer(size)

    def save_image(self, img: Image.Image, filename: str):
        """保存图像为PNG格式（3DMigoto可直接加载）"""
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath, 'PNG')
        print(f"    保存: {filepath}")

    def generate_all(self, characters: List[dict] = None):
        """生成所有UI纹理
        characters 每项: {"display": 显示名, "keywords": 头像匹配关键词列表}
        """
        self.setup_directories()

        if characters is None:
            characters, _ = self.load_character_names()

        print("=" * 60)
        print("开始生成UI纹理...")
        print("=" * 60)

        self.create_character_layers(characters)

        print("=" * 60)
        print(f"UI纹理生成完成！输出目录: {self.output_dir}")
        print(f"头像源目录: {self.avatar_dir}（按角色名命名，如 laevatain.png）")
        print("=" * 60)

    def load_character_names(self):
        """从key配置文件加载实际的mod，并映射到角色名称

        Returns:
            tuple: (characters, mods_data)
            characters 为列表，每项 dict:
              {"display": 中文显示名, "display_en": 英文显示名, "keywords": 匹配关键词列表}
            keywords 用于在 avatars 目录按文件名匹配头像（含英文名）。
        """
        key_config_path = os.path.join(self.base_output_dir, 'efmi_key_config.json')
        mapping_path = os.path.join(self.assets_dir, 'character_name_mapping.json')

        # 1. 读取key配置，获取实际的mod列表
        with open(key_config_path, 'r', encoding='utf-8') as f:
            key_config = json.load(f)
            mods = key_config.get('mods', [])

        # 2. 读取角色名称映射字典
        with open(mapping_path, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
            match_rules = mapping_data.get('match_rules', [])

        # 3. 为每个mod找到显示名与匹配关键词
        characters = []
        for mod in mods:
            mod_name = mod.get('name', '')
            mod_name_l = mod_name.lower()
            matched = False
            for rule in match_rules:
                keywords = rule.get('keywords', [])
                if any(kw.lower() in mod_name_l for kw in keywords):
                    characters.append({
                        "display": rule['display_name'],
                        "display_en": rule.get('display_en_name', ''),
                        "keywords": keywords + [mod_name],
                    })
                    matched = True
                    break
            if not matched:
                characters.append({
                    "display": mod_name or f'角色{len(characters)}',
                    "display_en": '',
                    "keywords": [mod_name],
                })

        return characters, mods


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
