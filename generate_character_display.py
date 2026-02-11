#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成角色显示配置 - 将mod名称映射为可读的角色名称

功能：
1. 读取 efmi_key_config.json (mod名称到ID)
2. 应用 character_name_mapping.json 的模糊匹配规则
3. 生成 character_display.json (角色名称到ID)
4. 更新主控 mod.ini 的文本显示代码
"""

import os
import json
import re
from typing import Dict, List, Optional


class CharacterDisplayGenerator:
    """角色显示配置生成器"""
    
    def __init__(self):
        self.config_file = "efmi_key_config.json"
        self.mapping_file = "character_name_mapping.json"
        self.output_file = "character_display.json"
        self.main_ini = "mod.ini"
        
    def load_config(self) -> dict:
        """加载mod配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"错误：找不到配置文件 {self.config_file}")
            print("请先运行 key_context_configurator.py 扫描mods")
            return None
        except Exception as e:
            print(f"加载配置失败: {e}")
            return None
    
    def load_mapping_rules(self) -> dict:
        """加载角色名称映射规则"""
        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告：找不到映射文件 {self.mapping_file}")
            print("将使用默认规则（显示原始mod名称）")
            return {"match_rules": []}
        except Exception as e:
            print(f"加载映射规则失败: {e}")
            return {"match_rules": []}
    
    def match_character_name(self, mod_name: str, rules: List[dict]) -> str:
        """
        根据模糊匹配规则将mod名称映射为角色名称
        
        Args:
            mod_name: 原始mod名称
            rules: 匹配规则列表
            
        Returns:
            角色显示名称（未匹配则返回原mod名称）
        """
        mod_name_lower = mod_name.lower()
        
        for rule in rules:
            keywords = rule.get("keywords", [])
            display_name = rule.get("display_name", "")
            
            # 检查是否包含任一关键词
            for keyword in keywords:
                if keyword.lower() in mod_name_lower:
                    return display_name
        
        # 未匹配到任何规则，返回原始名称
        return mod_name
    
    def generate_display_config(self) -> bool:
        """生成显示配置文件"""
        config = self.load_config()
        if not config:
            return False
        
        mapping_data = self.load_mapping_rules()
        rules = mapping_data.get("match_rules", [])
        
        # 生成角色显示映射
        character_list = []
        id_to_name = {}
        
        for mod in config.get("mods", []):
            mod_name = mod.get("name", "Unknown")
            character_id = mod.get("character_id", -1)
            key_count = len(mod.get("key_bindings", []))
            has_detection = mod.get("has_character_detection", False)
            
            # 应用模糊匹配
            display_name = self.match_character_name(mod_name, rules)
            
            character_info = {
                "character_id": character_id,
                "display_name": display_name,
                "mod_name": mod_name,
                "key_count": key_count,
                "has_detection": has_detection
            }
            
            character_list.append(character_info)
            id_to_name[str(character_id)] = display_name
        
        # 生成输出配置
        output_config = {
            "version": "1.0",
            "generated_at": config.get("generated_at", ""),
            "total_characters": len(character_list),
            "id_to_name": id_to_name,
            "characters": character_list
        }
        
        # 保存到文件
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_config, f, ensure_ascii=False, indent=2)
            print(f"✓ 已生成显示配置: {self.output_file}")
            
            # 显示映射结果
            print("\n角色名称映射结果：")
            for char in character_list:
                match_status = "✓匹配" if char["display_name"] != char["mod_name"] else "原名"
                print(f"  ID {char['character_id']}: {char['mod_name']} → {char['display_name']} ({match_status})")
            
            return True
            
        except Exception as e:
            print(f"保存显示配置失败: {e}")
            return False
    
    def generate_ini_display_code(self) -> str:
        """生成mod.ini的文本显示代码"""
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                display_config = json.load(f)
        except:
            print("错误：请先运行 generate_display_config()")
            return ""
        
        id_to_name = display_config.get("id_to_name", {})
        total = display_config.get("total_characters", 0)
        
        # 生成条件分支代码
        lines = [
            "; ===== 角色名称显示（自动生成）=====",
            "[Constants]",
            "global persist $show_character_ui = 0  ; UI显示开关（0=隐藏, 1=显示）",
            "",
            "[KeyToggleUI]",
            "key = VK_RETURN",
            "type = standard",
            "run = CommandToggleUI",
            "",
            "[CommandToggleUI]",
            "if $show_character_ui == 0",
            "    $show_character_ui = 1",
            "else",
            "    $show_character_ui = 0",
            "endif",
            "",
            "[Present]",
            "post run = ShowCharacterName",
            "",
            "[ShowCharacterName]",
            "; 只在开关打开时显示",
            "if $show_character_ui == 1"
        ]
        
        # 为每个角色生成显示文本（嵌套if-else结构）
        for idx, char_id in enumerate(range(total)):
            char_name = id_to_name.get(str(char_id), f"Unknown_{char_id}")
            
            if idx == 0:
                lines.append(f"    if $selected_character == {char_id}")
            else:
                lines.append(f"    else if $selected_character == {char_id}")
            
            lines.append(f'        post $overlay_text = "当前选中: {char_name} (ID {char_id})"')
        
        if total > 0:
            lines.append("    else")
            lines.append('        post $overlay_text = "未选中角色"')
            lines.append("    endif")
        
        lines.append("endif")
        lines.append("; ===== 显示代码结束 =====")
        
        return "\n".join(lines)
    
    def update_main_ini(self) -> bool:
        """更新主控mod.ini，添加文本显示功能"""
        if not os.path.exists(self.main_ini):
            print(f"警告：主控ini不存在: {self.main_ini}")
            return False
        
        try:
            with open(self.main_ini, 'r', encoding='utf-8') as f:
                content = f.read()
            
            display_code = self.generate_ini_display_code()
            if not display_code:
                return False
            
            # 查找并替换显示代码块
            pattern = r'; ===== 角色名称显示.*?; ===== 显示代码结束 ====='
            if re.search(pattern, content, re.DOTALL):
                # 替换已存在的显示代码
                new_content = re.sub(pattern, display_code, content, flags=re.DOTALL)
                print("✓ 更新了已存在的显示代码")
            else:
                # 在文件末尾添加显示代码
                new_content = content.rstrip() + "\n\n" + display_code + "\n"
                print("✓ 添加了新的显示代码")
            
            # 写回文件
            with open(self.main_ini, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✓ 已更新主控ini: {self.main_ini}")
            return True
            
        except Exception as e:
            print(f"更新主控ini失败: {e}")
            return False


def main():
    """主函数"""
    print("=" * 60)
    print("角色显示配置生成器")
    print("=" * 60)
    
    generator = CharacterDisplayGenerator()
    
    # 步骤1：生成显示配置
    print("\n步骤1：生成角色显示配置...")
    if not generator.generate_display_config():
        print("失败：无法生成显示配置")
        return
    
    # 步骤2：更新主控ini
    print("\n步骤2：更新主控mod.ini...")
    if not generator.update_main_ini():
        print("失败：无法更新主控ini")
        return
    
    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)
    print("\n使用说明：")
    print("1. 将更新后的 mod.ini 复制到游戏Mods文件夹")
    print("2. 游戏内按Enter键切换UI显示/隐藏")
    print("3. 游戏内按↑↓键切换角色，屏幕会显示当前选中的角色名称")
    print("4. 修改 character_name_mapping.json 可自定义角色名称")
    print("5. 修改后重新运行本脚本即可更新")


if __name__ == "__main__":
    main()
