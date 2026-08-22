#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 纹理生成器 - 为 3DMigoto 生成全局开关状态条

本脚本只负责两张状态条：
  resources/textures/status_enabled.png   启用：绿底白字「热键 已启用」
  resources/textures/status_disabled.png  禁用：红底白字「热键 已禁用」

徽章铺满小画布（约 560x80，圆角矩形几乎铺满、少量 padding），由主 ini 以
固定左下角四边形（x87/y87/z87/w87）渲染；小画布保证徽章在四边形内清晰可读。
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys


class UITextureGenerator:
    """UI 纹理生成器"""

    # 画布尺寸（约 560x80）
    CANVAS_WIDTH = 560
    CANVAS_HEIGHT = 80

    # 徽章 padding（占画布宽/高的比例，圆角矩形几乎铺满）
    PAD_X_RATIO = 0.02
    PAD_Y_RATIO = 0.10
    RADIUS_RATIO = 0.45

    STATUS_ENABLED_COLOR = (46, 170, 90, 255)    # 启用：绿
    STATUS_DISABLED_COLOR = (170, 60, 60, 255)   # 禁用：红
    STATUS_TEXT_COLOR = (255, 255, 255, 255)     # 徽章内文字：白

    ENABLED_TEXT = {"zh": "热键 已启用", "en": "Hotkeys ON"}
    DISABLED_TEXT = {"zh": "热键 已禁用", "en": "Hotkeys OFF"}

    def __init__(self, base_output_dir: str = None):
        self.base_output_dir = base_output_dir or self._get_output_dir()
        # 输出：游戏渲染资源写在 exe/脚本旁的 resources/textures
        self.output_dir = os.path.join(self.base_output_dir, "resources", "textures")

    @staticmethod
    def _get_output_dir() -> str:
        """Return the directory where generated files should be written."""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

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

    def save_image(self, img: Image.Image, filename: str):
        """保存图像为PNG格式（3DMigoto可直接加载）"""
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath, 'PNG')
        print(f"    保存: {filepath}")

    def _create_status(self, enabled: bool, lang: str):
        """生成一张状态条：绿底/红底 + 白色文字，徽章铺满画布。"""
        canvas = Image.new('RGBA', (self.CANVAS_WIDTH, self.CANVAS_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        pad_x = int(self.CANVAS_WIDTH * self.PAD_X_RATIO)
        pad_y = int(self.CANVAS_HEIGHT * self.PAD_Y_RATIO)
        radius = int(self.CANVAS_HEIGHT * self.RADIUS_RATIO)

        color = self.STATUS_ENABLED_COLOR if enabled else self.STATUS_DISABLED_COLOR
        draw.rounded_rectangle(
            [pad_x, pad_y, self.CANVAS_WIDTH - pad_x, self.CANVAS_HEIGHT - pad_y],
            radius=radius, fill=color,
        )

        label = (self.ENABLED_TEXT if enabled else self.DISABLED_TEXT)[lang]
        font = self.get_font(int(self.CANVAS_HEIGHT * 0.55), bold=True)
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        tx = (self.CANVAS_WIDTH - tw) // 2 - tb[0]
        ty = (self.CANVAS_HEIGHT - th) // 2 - tb[1]
        draw.text((tx, ty), label, font=font, fill=self.STATUS_TEXT_COLOR)

        filename = "status_enabled.png" if enabled else "status_disabled.png"
        self.save_image(canvas, filename)
        print(f"  生成: {filename} ({label})")

    def generate_all(self, lang: str = "zh"):
        """生成两张状态条纹理（启用/禁用）。"""
        os.makedirs(self.output_dir, exist_ok=True)
        print("=" * 60)
        print("开始生成UI纹理（状态条）...")
        print("=" * 60)
        self._create_status(True, lang)
        self._create_status(False, lang)
        print("=" * 60)
        print(f"UI纹理生成完成！输出目录: {self.output_dir}")
        print("=" * 60)


def main():
    """主函数"""
    generator = UITextureGenerator()
    generator.generate_all()


if __name__ == "__main__":
    main()
