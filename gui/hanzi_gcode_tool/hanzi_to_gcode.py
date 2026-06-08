# -*- coding: utf-8 -*-
"""
汉字/中文文字转 G-code 工具
- 使用本机已安装的中文 TrueType/OpenType 字体生成文字轮廓路径
- 输出标准 G-code: G0 快速移动、G1 画线移动、M3/M5 或 Z 抬落笔
- 不内置字体文件；请使用 Windows 自带中文字体，如 simsun.ttc、msyh.ttc、simhei.ttf

依赖：pip install matplotlib numpy
示例：
python hanzi_to_gcode.py --text "北航机电" --font "C:/Windows/Fonts/simhei.ttf" --output hanzi.nc --height 20 --feed 800 --preview
"""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath

Point = Tuple[float, float]
Polyline = List[Point]


# 常用汉字单线笔画模板：坐标范围 0~1，y 向上。
# 说明：字体轮廓适合激光/雕刻轮廓，但写字机器人更适合“中心线笔画”。
# 对容易出问题的结构字优先使用模板，避免“田”只剩外框、内部十字丢失。
Stroke = List[Point]



# 英文/数字“正常字”单线模板：坐标范围 0~1，y 向上。
# 目标不是还原某个字体，而是让写字机器人按笔画中心线书写，避免英文字母默认镂空。
ASCII_STROKE_TEMPLATES: dict[str, List[Stroke]] = {
    "A": [[(0.12,0.10),(0.50,0.90),(0.88,0.10)], [(0.28,0.45),(0.72,0.45)]],
    "B": [[(0.18,0.10),(0.18,0.90),(0.62,0.90),(0.78,0.76),(0.62,0.56),(0.18,0.56)], [(0.18,0.56),(0.66,0.56),(0.82,0.38),(0.66,0.10),(0.18,0.10)]],
    "C": [[(0.82,0.78),(0.66,0.90),(0.30,0.88),(0.14,0.68),(0.14,0.30),(0.32,0.12),(0.68,0.10),(0.84,0.22)]],
    "D": [[(0.18,0.10),(0.18,0.90),(0.58,0.88),(0.82,0.66),(0.82,0.34),(0.58,0.12),(0.18,0.10)]],
    "E": [[(0.78,0.90),(0.18,0.90),(0.18,0.10),(0.82,0.10)], [(0.18,0.52),(0.66,0.52)]],
    "F": [[(0.18,0.10),(0.18,0.90),(0.82,0.90)], [(0.18,0.52),(0.66,0.52)]],
    "G": [[(0.84,0.76),(0.66,0.90),(0.30,0.88),(0.14,0.66),(0.14,0.30),(0.34,0.12),(0.70,0.12),(0.84,0.30),(0.84,0.48),(0.58,0.48)]],
    "H": [[(0.18,0.10),(0.18,0.90)], [(0.82,0.10),(0.82,0.90)], [(0.18,0.52),(0.82,0.52)]],
    "I": [[(0.25,0.90),(0.75,0.90)], [(0.50,0.90),(0.50,0.10)], [(0.25,0.10),(0.75,0.10)]],
    "J": [[(0.76,0.90),(0.76,0.28),(0.62,0.12),(0.36,0.10),(0.22,0.26)]],
    "K": [[(0.18,0.10),(0.18,0.90)], [(0.82,0.90),(0.18,0.52),(0.82,0.10)]],
    "L": [[(0.18,0.90),(0.18,0.10),(0.82,0.10)]],
    "M": [[(0.12,0.10),(0.12,0.90),(0.50,0.48),(0.88,0.90),(0.88,0.10)]],
    "N": [[(0.18,0.10),(0.18,0.90),(0.82,0.10),(0.82,0.90)]],
    "O": [[(0.50,0.92),(0.78,0.80),(0.88,0.50),(0.78,0.20),(0.50,0.08),(0.22,0.20),(0.12,0.50),(0.22,0.80),(0.50,0.92)]],
    "P": [[(0.18,0.10),(0.18,0.90),(0.64,0.90),(0.82,0.72),(0.64,0.54),(0.18,0.54)]],
    "Q": [[(0.50,0.92),(0.78,0.80),(0.88,0.50),(0.78,0.20),(0.50,0.08),(0.22,0.20),(0.12,0.50),(0.22,0.80),(0.50,0.92)], [(0.60,0.26),(0.88,0.02)]],
    "R": [[(0.18,0.10),(0.18,0.90),(0.64,0.90),(0.82,0.72),(0.64,0.54),(0.18,0.54)], [(0.46,0.54),(0.84,0.10)]],
    "S": [[(0.82,0.78),(0.64,0.90),(0.32,0.88),(0.16,0.72),(0.28,0.56),(0.68,0.46),(0.84,0.30),(0.68,0.12),(0.30,0.12),(0.14,0.24)]],
    "T": [[(0.12,0.90),(0.88,0.90)], [(0.50,0.90),(0.50,0.10)]],
    "U": [[(0.16,0.90),(0.16,0.28),(0.34,0.10),(0.66,0.10),(0.84,0.28),(0.84,0.90)]],
    "V": [[(0.12,0.90),(0.50,0.10),(0.88,0.90)]],
    "W": [[(0.10,0.90),(0.28,0.10),(0.50,0.55),(0.72,0.10),(0.90,0.90)]],
    "X": [[(0.14,0.90),(0.86,0.10)], [(0.86,0.90),(0.14,0.10)]],
    "Y": [[(0.12,0.90),(0.50,0.54),(0.88,0.90)], [(0.50,0.54),(0.50,0.10)]],
    "Z": [[(0.14,0.90),(0.86,0.90),(0.14,0.10),(0.86,0.10)]],
    "0": [[(0.50,0.92),(0.78,0.78),(0.88,0.50),(0.78,0.20),(0.50,0.08),(0.22,0.20),(0.12,0.50),(0.22,0.78),(0.50,0.92)], [(0.32,0.25),(0.68,0.75)]],
    "1": [[(0.38,0.72),(0.52,0.90),(0.52,0.10)], [(0.34,0.10),(0.72,0.10)]],
    "2": [[(0.18,0.70),(0.34,0.88),(0.66,0.88),(0.82,0.70),(0.18,0.10),(0.84,0.10)]],
    "3": [[(0.20,0.82),(0.70,0.86),(0.84,0.66),(0.62,0.52),(0.84,0.34),(0.70,0.14),(0.20,0.18)]],
    "4": [[(0.72,0.10),(0.72,0.90),(0.16,0.38),(0.86,0.38)]],
    "5": [[(0.82,0.90),(0.24,0.90),(0.18,0.56),(0.62,0.56),(0.84,0.38),(0.68,0.12),(0.24,0.14)]],
    "6": [[(0.78,0.78),(0.60,0.90),(0.32,0.82),(0.16,0.52),(0.18,0.24),(0.42,0.10),(0.72,0.18),(0.82,0.42),(0.62,0.58),(0.22,0.52)]],
    "7": [[(0.16,0.90),(0.86,0.90),(0.44,0.10)]],
    "8": [[(0.50,0.52),(0.76,0.66),(0.70,0.88),(0.50,0.94),(0.30,0.88),(0.24,0.66),(0.50,0.52),(0.78,0.36),(0.70,0.14),(0.50,0.06),(0.30,0.14),(0.22,0.36),(0.50,0.52)]],
    "9": [[(0.78,0.48),(0.58,0.42),(0.30,0.50),(0.20,0.74),(0.40,0.90),(0.70,0.82),(0.84,0.54),(0.78,0.22),(0.56,0.10),(0.28,0.18)]],
    ".": [[(0.50,0.12),(0.52,0.12)]],
    "-": [[(0.24,0.50),(0.76,0.50)]],
    "+": [[(0.24,0.50),(0.76,0.50)], [(0.50,0.76),(0.50,0.24)]],
    "/": [[(0.82,0.90),(0.18,0.10)]],
}
# 小写字母先复用大写单线结构，保证所有英文都可以“正常字”单线书写。
for _k, _v in list(ASCII_STROKE_TEMPLATES.items()):
    if "A" <= _k <= "Z":
        ASCII_STROKE_TEMPLATES[_k.lower()] = _v


HANZI_STROKE_TEMPLATES: dict[str, List[Stroke]] = {
    "一": [[(0.12, 0.55), (0.88, 0.55)]],
    "二": [[(0.18, 0.68), (0.82, 0.68)], [(0.10, 0.38), (0.90, 0.38)]],
    "三": [[(0.18, 0.74), (0.82, 0.74)], [(0.22, 0.55), (0.78, 0.55)], [(0.10, 0.32), (0.90, 0.32)]],
    "十": [[(0.16, 0.58), (0.84, 0.58)], [(0.50, 0.86), (0.50, 0.16)]],
    "口": [[(0.22, 0.78), (0.78, 0.78), (0.78, 0.24), (0.22, 0.24), (0.22, 0.78)]],
    "日": [[(0.25, 0.84), (0.75, 0.84), (0.75, 0.18), (0.25, 0.18), (0.25, 0.84)], [(0.25, 0.52), (0.75, 0.52)]],
    "田": [[(0.20, 0.82), (0.80, 0.82), (0.80, 0.18), (0.20, 0.18), (0.20, 0.82)], [(0.20, 0.50), (0.80, 0.50)], [(0.50, 0.82), (0.50, 0.18)]],
    "目": [[(0.25, 0.86), (0.75, 0.86), (0.75, 0.14), (0.25, 0.14), (0.25, 0.86)], [(0.25, 0.62), (0.75, 0.62)], [(0.25, 0.38), (0.75, 0.38)]],
    "中": [[(0.25, 0.70), (0.75, 0.70), (0.75, 0.34), (0.25, 0.34), (0.25, 0.70)], [(0.50, 0.88), (0.50, 0.12)]],
    "王": [[(0.20, 0.78), (0.80, 0.78)], [(0.26, 0.55), (0.74, 0.55)], [(0.12, 0.28), (0.88, 0.28)], [(0.50, 0.80), (0.50, 0.30)]],
    "土": [[(0.26, 0.66), (0.74, 0.66)], [(0.50, 0.82), (0.50, 0.24)], [(0.16, 0.24), (0.84, 0.24)]],
    "工": [[(0.22, 0.76), (0.78, 0.76)], [(0.50, 0.76), (0.50, 0.28)], [(0.16, 0.28), (0.84, 0.28)]],
    "干": [[(0.22, 0.78), (0.78, 0.78)], [(0.16, 0.56), (0.84, 0.56)], [(0.50, 0.78), (0.50, 0.16)]],
    "人": [[(0.52, 0.82), (0.40, 0.50), (0.18, 0.18)], [(0.52, 0.82), (0.64, 0.50), (0.86, 0.18)]],
    "大": [[(0.18, 0.58), (0.84, 0.58)], [(0.50, 0.84), (0.46, 0.58), (0.20, 0.16)], [(0.50, 0.58), (0.82, 0.16)]],
    "小": [[(0.50, 0.82), (0.50, 0.18)], [(0.38, 0.54), (0.18, 0.30)], [(0.62, 0.54), (0.84, 0.30)]],
    "木": [[(0.18, 0.60), (0.84, 0.60)], [(0.50, 0.84), (0.50, 0.16)], [(0.50, 0.60), (0.20, 0.24)], [(0.50, 0.60), (0.82, 0.24)]],
    "本": [[(0.18, 0.62), (0.84, 0.62)], [(0.50, 0.86), (0.50, 0.14)], [(0.50, 0.62), (0.20, 0.24)], [(0.50, 0.62), (0.82, 0.24)], [(0.34, 0.32), (0.66, 0.32)]],
}


# 笔顺字库：normal 模式优先使用这里。
# 每个字由若干“笔”组成，每一笔是一条 polyline；笔与笔之间会自动 M05 抬笔。
# 坐标范围 0~1，y 向上。笔画顺序按常见规范笔顺近似编排：先横后竖、先撇后捺、从上到下、从左到右、先外后内再封口。
# 注意：这是课程写字机器人用的轻量笔顺库，不是完整书法字库；未收录的汉字会回退到骨架中心线。
STROKE_ORDER_TEMPLATES: dict[str, List[Stroke]] = {
    # 基础笔画/结构字
    "一": [[(0.16, 0.55), (0.84, 0.55)]],
    "二": [[(0.24, 0.68), (0.76, 0.68)], [(0.14, 0.38), (0.86, 0.38)]],
    "三": [[(0.24, 0.74), (0.76, 0.74)], [(0.28, 0.55), (0.72, 0.55)], [(0.14, 0.32), (0.86, 0.32)]],
    "十": [[(0.18, 0.58), (0.82, 0.58)], [(0.50, 0.84), (0.50, 0.16)]],
    "干": [[(0.24, 0.78), (0.76, 0.78)], [(0.16, 0.56), (0.84, 0.56)], [(0.50, 0.78), (0.50, 0.14)]],
    "土": [[(0.28, 0.66), (0.72, 0.66)], [(0.50, 0.82), (0.50, 0.24)], [(0.16, 0.24), (0.84, 0.24)]],
    "王": [[(0.22, 0.78), (0.78, 0.78)], [(0.28, 0.56), (0.72, 0.56)], [(0.50, 0.80), (0.50, 0.30)], [(0.14, 0.28), (0.86, 0.28)]],
    "工": [[(0.22, 0.76), (0.78, 0.76)], [(0.50, 0.76), (0.50, 0.28)], [(0.16, 0.28), (0.84, 0.28)]],
    "人": [[(0.52, 0.82), (0.40, 0.50), (0.18, 0.18)], [(0.52, 0.82), (0.64, 0.50), (0.86, 0.18)]],
    "入": [[(0.42, 0.82), (0.54, 0.50), (0.82, 0.18)], [(0.42, 0.82), (0.30, 0.50), (0.16, 0.26)]],
    "大": [[(0.18, 0.58), (0.84, 0.58)], [(0.50, 0.84), (0.46, 0.58), (0.20, 0.16)], [(0.50, 0.58), (0.82, 0.16)]],
    "小": [[(0.50, 0.82), (0.50, 0.18)], [(0.38, 0.54), (0.18, 0.30)], [(0.62, 0.54), (0.84, 0.30)]],
    "木": [[(0.18, 0.60), (0.84, 0.60)], [(0.50, 0.84), (0.50, 0.16)], [(0.50, 0.60), (0.20, 0.24)], [(0.50, 0.60), (0.82, 0.24)]],
    "本": [[(0.18, 0.62), (0.84, 0.62)], [(0.50, 0.86), (0.50, 0.14)], [(0.50, 0.62), (0.20, 0.24)], [(0.50, 0.62), (0.82, 0.24)], [(0.34, 0.32), (0.66, 0.32)]],

    # 口框类：先竖，再横折，再内部，最后封口
    "口": [[(0.24, 0.78), (0.24, 0.22)], [(0.24, 0.78), (0.76, 0.78), (0.76, 0.22)], [(0.24, 0.22), (0.76, 0.22)]],
    "日": [[(0.26, 0.84), (0.26, 0.16)], [(0.26, 0.84), (0.74, 0.84), (0.74, 0.16)], [(0.26, 0.52), (0.74, 0.52)], [(0.26, 0.16), (0.74, 0.16)]],
    "目": [[(0.26, 0.86), (0.26, 0.14)], [(0.26, 0.86), (0.74, 0.86), (0.74, 0.14)], [(0.26, 0.62), (0.74, 0.62)], [(0.26, 0.38), (0.74, 0.38)], [(0.26, 0.14), (0.74, 0.14)]],
    "田": [[(0.20, 0.82), (0.20, 0.18)], [(0.20, 0.82), (0.80, 0.82), (0.80, 0.18)], [(0.20, 0.50), (0.80, 0.50)], [(0.50, 0.82), (0.50, 0.18)], [(0.20, 0.18), (0.80, 0.18)]],
    "中": [[(0.25, 0.70), (0.25, 0.34)], [(0.25, 0.70), (0.75, 0.70), (0.75, 0.34)], [(0.25, 0.34), (0.75, 0.34)], [(0.50, 0.88), (0.50, 0.12)]],
    "由": [[(0.50, 0.88), (0.50, 0.16)], [(0.24, 0.70), (0.24, 0.18)], [(0.24, 0.70), (0.76, 0.70), (0.76, 0.18)], [(0.24, 0.44), (0.76, 0.44)], [(0.24, 0.18), (0.76, 0.18)]],
    "国": [[(0.18, 0.84), (0.18, 0.16)], [(0.18, 0.84), (0.82, 0.84), (0.82, 0.16)], [(0.34, 0.68), (0.66, 0.68)], [(0.50, 0.68), (0.50, 0.34)], [(0.34, 0.48), (0.66, 0.48)], [(0.36, 0.30), (0.68, 0.30)], [(0.62, 0.42), (0.72, 0.32)], [(0.18, 0.16), (0.82, 0.16)]],

    # 常用字
    "字": [[(0.48,0.88),(0.52,0.80)], [(0.20,0.76),(0.20,0.64),(0.80,0.64),(0.80,0.76)], [(0.32,0.56),(0.68,0.56),(0.50,0.42)], [(0.50,0.42),(0.50,0.16)], [(0.24,0.30),(0.76,0.30)]],
    "文": [[(0.50,0.88),(0.50,0.78)], [(0.18,0.70),(0.82,0.70)], [(0.30,0.60),(0.50,0.38),(0.82,0.16)], [(0.70,0.58),(0.48,0.36),(0.18,0.16)]],
    "汉": [[(0.18,0.76),(0.28,0.66)], [(0.14,0.52),(0.25,0.44)], [(0.22,0.30),(0.12,0.14)], [(0.38,0.74),(0.76,0.74),(0.60,0.46),(0.34,0.18)], [(0.50,0.48),(0.84,0.18)]],
    "永": [[(0.50,0.90),(0.50,0.78)], [(0.34,0.70),(0.62,0.70),(0.48,0.52),(0.48,0.18)], [(0.36,0.50),(0.18,0.32)], [(0.58,0.56),(0.82,0.70)], [(0.56,0.46),(0.82,0.18)]],
    "飞": [[(0.24,0.76),(0.72,0.76),(0.62,0.56),(0.72,0.36),(0.86,0.24)], [(0.44,0.56),(0.26,0.28)], [(0.56,0.52),(0.72,0.44)]],
    "你": [[(0.34,0.86),(0.24,0.62),(0.14,0.42)], [(0.26,0.64),(0.26,0.16)], [(0.50,0.84),(0.42,0.68)], [(0.44,0.66),(0.82,0.66),(0.72,0.50)], [(0.62,0.66),(0.62,0.18)], [(0.50,0.42),(0.38,0.26)], [(0.74,0.42),(0.86,0.26)]],
    "好": [[(0.22,0.80),(0.36,0.80),(0.28,0.48),(0.14,0.22)], [(0.16,0.54),(0.40,0.54)], [(0.34,0.58),(0.18,0.16)], [(0.50,0.78),(0.80,0.78),(0.64,0.58)], [(0.64,0.58),(0.64,0.16)], [(0.46,0.44),(0.86,0.44)]],
    "我": [[(0.28,0.78),(0.58,0.84)], [(0.18,0.60),(0.58,0.64)], [(0.38,0.82),(0.38,0.18),(0.20,0.14)], [(0.18,0.42),(0.58,0.46)], [(0.58,0.86),(0.70,0.24),(0.84,0.16)], [(0.64,0.62),(0.84,0.72)], [(0.64,0.38),(0.82,0.56)]],
    "他": [[(0.34,0.86),(0.24,0.62),(0.14,0.42)], [(0.26,0.64),(0.26,0.16)], [(0.46,0.70),(0.46,0.22),(0.82,0.22),(0.84,0.36)], [(0.46,0.56),(0.82,0.66),(0.82,0.36)], [(0.64,0.82),(0.64,0.20)]],

    # 课程项目相关
    "机": [[(0.18,0.62),(0.42,0.62)], [(0.30,0.84),(0.30,0.16)], [(0.30,0.60),(0.12,0.30)], [(0.30,0.56),(0.44,0.36)], [(0.52,0.78),(0.78,0.78),(0.76,0.22)], [(0.52,0.78),(0.52,0.48),(0.48,0.24),(0.40,0.16)], [(0.76,0.42),(0.88,0.20)]],
    "电": [[(0.28,0.76),(0.28,0.34)], [(0.28,0.76),(0.72,0.76),(0.72,0.34)], [(0.28,0.55),(0.72,0.55)], [(0.28,0.34),(0.72,0.34)], [(0.50,0.88),(0.50,0.18),(0.82,0.18),(0.86,0.30)]],
    "写": [[(0.48,0.88),(0.52,0.80)], [(0.20,0.76),(0.20,0.64),(0.80,0.64),(0.80,0.76)], [(0.32,0.58),(0.72,0.58)], [(0.30,0.46),(0.68,0.46),(0.60,0.28),(0.36,0.28)], [(0.26,0.16),(0.76,0.16)]],
    "器": [[(0.20,0.80),(0.38,0.80),(0.38,0.64),(0.20,0.64),(0.20,0.80)], [(0.62,0.80),(0.80,0.80),(0.80,0.64),(0.62,0.64),(0.62,0.80)], [(0.34,0.56),(0.66,0.56)], [(0.50,0.66),(0.50,0.42)], [(0.22,0.34),(0.40,0.34),(0.40,0.18),(0.22,0.18),(0.22,0.34)], [(0.60,0.34),(0.78,0.34),(0.78,0.18),(0.60,0.18),(0.60,0.34)]],
    "北": [[(0.26,0.82),(0.26,0.18)], [(0.14,0.58),(0.38,0.58)], [(0.38,0.78),(0.38,0.18),(0.18,0.18)], [(0.62,0.82),(0.62,0.18),(0.84,0.28)], [(0.62,0.50),(0.82,0.62)]],
    "航": [[(0.22,0.86),(0.34,0.74)], [(0.16,0.70),(0.42,0.70)], [(0.20,0.58),(0.20,0.20)], [(0.20,0.52),(0.40,0.52)], [(0.20,0.36),(0.40,0.36)], [(0.52,0.84),(0.60,0.76)], [(0.46,0.68),(0.84,0.68)], [(0.56,0.56),(0.78,0.56),(0.76,0.24)], [(0.56,0.56),(0.56,0.34),(0.48,0.18)], [(0.76,0.38),(0.88,0.20)]],
    "学": [[(0.28,0.84),(0.36,0.72)], [(0.50,0.88),(0.50,0.74)], [(0.72,0.84),(0.64,0.72)], [(0.18,0.70),(0.18,0.58),(0.82,0.58),(0.82,0.70)], [(0.34,0.50),(0.68,0.50),(0.50,0.36)], [(0.50,0.36),(0.50,0.14)], [(0.26,0.26),(0.74,0.26)]],
}


# ===== 2026-06 修复：补充常用复杂字单线笔顺模板 + 曲线英文模板 =====
def _arc_pts(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 8) -> Stroke:
    """生成归一化圆弧点，角度单位为度。"""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

# 让正常英文里的 B/C/O/S 等弧线有足够中间点，GUI 才能拟合出 G2/G3；同时仍保持单线字，不再镂空。
ASCII_STROKE_TEMPLATES.update({
    # B 分成竖线、上半封闭弧、下半封闭弧，避免圆弧拟合后不封口
    "B": [[(0.18,0.10),(0.18,0.90)], [(0.18,0.90),(0.58,0.90),(0.80,0.74),(0.62,0.56),(0.18,0.56)], [(0.18,0.56),(0.66,0.56),(0.84,0.34),(0.66,0.10),(0.18,0.10)]],
    "C": [_arc_pts(0.55,0.50,0.38,55,305,18)],
    "D": [[(0.18,0.10),(0.18,0.90)] + _arc_pts(0.42,0.50,0.40,90,-90,16)],
    "G": [_arc_pts(0.55,0.50,0.38,55,340,18) + [(0.84,0.48),(0.60,0.48)]],
    "O": [_arc_pts(0.50,0.50,0.40,90,450,24)],
    "P": [[(0.18,0.10),(0.18,0.90)] + _arc_pts(0.46,0.70,0.28,90,-90,12)],
    "Q": [_arc_pts(0.50,0.50,0.40,90,450,24), [(0.62,0.26),(0.86,0.06)]],
    "R": [[(0.18,0.10),(0.18,0.90)] + _arc_pts(0.46,0.70,0.28,90,-90,12), [(0.44,0.52),(0.84,0.10)]],
    "S": [_arc_pts(0.54,0.70,0.28,35,230,12) + _arc_pts(0.46,0.30,0.30,50,-160,12)],
    "U": [[(0.16,0.90),(0.16,0.34)] + _arc_pts(0.50,0.34,0.34,180,360,12) + [(0.84,0.90)]],
    "0": [_arc_pts(0.50,0.50,0.40,90,450,24), [(0.32,0.25),(0.68,0.75)]],
    "3": [_arc_pts(0.48,0.70,0.28,130,-90,12) + _arc_pts(0.48,0.30,0.30,90,-130,12)],
    "6": [_arc_pts(0.55,0.42,0.28,20,380,18) + [(0.28,0.62),(0.42,0.86),(0.72,0.82)]],
    "8": [_arc_pts(0.50,0.70,0.24,90,450,16) + _arc_pts(0.50,0.30,0.28,90,450,18)],
    "9": [_arc_pts(0.48,0.62,0.28,90,450,18) + [(0.76,0.46),(0.62,0.16),(0.32,0.14)]],
})
for _k, _v in list(ASCII_STROKE_TEMPLATES.items()):
    if "A" <= _k <= "Z":
        ASCII_STROKE_TEMPLATES[_k.lower()] = _v

# 对用户当前测试中出现的复杂字增加“可写、等宽、单线”的轻量笔顺模板。
# 这些模板不是艺术字体轮廓，而是写字机器人用的中心线笔画，重点保证：不重叠、不只剩一部分、粗细一致。
STROKE_ORDER_TEMPLATES.update({
    "量": [
        [(0.28,0.86),(0.72,0.86),(0.72,0.68),(0.28,0.68),(0.28,0.86)],
        [(0.28,0.77),(0.72,0.77)],
        [(0.18,0.58),(0.82,0.58)],
        [(0.28,0.48),(0.72,0.48)],
        [(0.28,0.38),(0.72,0.38)],
        [(0.50,0.58),(0.50,0.18)],
        [(0.22,0.28),(0.78,0.28)],
        [(0.14,0.16),(0.86,0.16)],
    ],
    "体": [
        [(0.30,0.86),(0.20,0.64),(0.12,0.44)],
        [(0.22,0.64),(0.22,0.16)],
        [(0.40,0.66),(0.86,0.66)],
        [(0.62,0.86),(0.62,0.16)],
        [(0.62,0.66),(0.42,0.36)],
        [(0.62,0.66),(0.84,0.36)],
        [(0.44,0.24),(0.82,0.24)],
    ],
    "微": [
        [(0.20,0.84),(0.10,0.70)], [(0.24,0.66),(0.12,0.52)], [(0.22,0.60),(0.22,0.16)],
        [(0.38,0.82),(0.34,0.70),(0.30,0.62)], [(0.44,0.82),(0.44,0.62)], [(0.32,0.62),(0.56,0.62)],
        [(0.34,0.52),(0.34,0.24)], [(0.54,0.52),(0.54,0.24)], [(0.34,0.38),(0.54,0.38)], [(0.30,0.22),(0.58,0.22)],
        [(0.68,0.84),(0.62,0.66),(0.60,0.46),(0.54,0.20)], [(0.62,0.64),(0.86,0.64)],
        [(0.78,0.82),(0.70,0.52),(0.62,0.32),(0.52,0.16)], [(0.68,0.50),(0.86,0.18)]
    ],
    "侯": [
        [(0.30,0.86),(0.20,0.64),(0.12,0.44)], [(0.22,0.64),(0.22,0.16)],
        [(0.40,0.82),(0.40,0.56)], [(0.40,0.82),(0.74,0.82),(0.74,0.64),(0.40,0.64)],
        [(0.48,0.58),(0.86,0.58)], [(0.62,0.70),(0.56,0.42)],
        [(0.42,0.42),(0.84,0.42)], [(0.62,0.42),(0.46,0.18)], [(0.62,0.42),(0.86,0.18)]
    ],
    "骁": [
        [(0.14,0.80),(0.36,0.80),(0.32,0.54)], [(0.16,0.66),(0.32,0.66)], [(0.12,0.50),(0.38,0.50)],
        [(0.32,0.54),(0.28,0.18),(0.12,0.18)], [(0.12,0.34),(0.36,0.34)],
        [(0.50,0.80),(0.82,0.80)], [(0.66,0.88),(0.66,0.58)], [(0.50,0.58),(0.86,0.58)],
        [(0.58,0.54),(0.48,0.24),(0.38,0.16)], [(0.72,0.54),(0.84,0.24),(0.88,0.16)],
        [(0.76,0.82),(0.86,0.70)]
    ],
    "航": [
        [(0.22,0.86),(0.34,0.74)], [(0.14,0.70),(0.42,0.70)], [(0.20,0.60),(0.20,0.18)],
        [(0.20,0.54),(0.40,0.54)], [(0.20,0.38),(0.40,0.38)], [(0.40,0.70),(0.36,0.18)],
        [(0.58,0.86),(0.64,0.76)], [(0.48,0.70),(0.86,0.70)],
        [(0.58,0.58),(0.78,0.58),(0.76,0.24)], [(0.58,0.58),(0.58,0.34),(0.50,0.18)],
        [(0.76,0.40),(0.88,0.18)]
    ],
})


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF) or (0xF900 <= code <= 0xFAFF)



def _quad(p0: Point, p1: Point, p2: Point, n: int) -> List[Point]:
    out = []
    for i in range(1, n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        out.append((x, y))
    return out


def _cubic(p0: Point, p1: Point, p2: Point, p3: Point, n: int) -> List[Point]:
    out = []
    for i in range(1, n + 1):
        t = i / n
        x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] +
             3 * (1 - t) * t**2 * p2[0] + t**3 * p3[0])
        y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] +
             3 * (1 - t) * t**2 * p2[1] + t**3 * p3[1])
        out.append((x, y))
    return out


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class GcodeConfig:
    text: str
    font: Optional[str] = None
    height: float = 20.0        # 字高，单位 mm
    x0: float = 0.0
    y0: float = 0.0
    char_gap: float = 3.0      # 字符间距，单位 mm
    line_gap: float = 8.0      # 行距附加值，单位 mm
    max_line_width: float = 280.0  # 自动换行宽度，单位 mm；<=0 表示不自动换行
    feed: float = 800.0
    travel_feed: float = 2000.0
    curve_segments: int = 8
    decimals: int = 3
    use_z: bool = True         # True: Z 抬落笔；False: M3/M5 开关笔/激光
    z_up: float = 3.0
    z_down: float = 0.0
    pen_on: str = "M3"
    pen_off: str = "M5"
    scale_y_flip: bool = False # 数控/绘图坐标通常 Y 向上；如屏幕坐标可设 True
    font_mode: str = "normal"  # normal=汉字库中心线；art=字体轮廓镂空
    hanzi_library_dir: Optional[str] = None  # Hanzi Writer Data 缓存目录
    auto_download_hanzi: bool = True         # 缺字时自动从 Hanzi Writer Data 下载单字 JSON


class HanziToGcode:
    HANZI_DATA_URLS = (
        "https://cdn.jsdelivr.net/npm/hanzi-writer-data@latest/{char}.json",
        "https://raw.githubusercontent.com/chanind/hanzi-writer-data/master/data/{char}.json",
        "https://raw.githubusercontent.com/chanind/hanzi-writer-data/master/{char}.json",
    )

    def __init__(self, cfg: GcodeConfig):
        self.cfg = cfg
        self.font_prop = self._load_font(cfg.font)
        base_dir = Path(__file__).resolve().parent
        self.hanzi_library_dir = Path(cfg.hanzi_library_dir) if cfg.hanzi_library_dir else base_dir / "hanzi_writer_data"
        self.hanzi_library_dir.mkdir(parents=True, exist_ok=True)
        self._all_hanzi_cache = None
        self.last_external_hanzi_used = 0
        self.last_external_hanzi_missing = 0

    @staticmethod
    def _load_font(font: Optional[str]) -> FontProperties:
        if font:
            if os.path.exists(font):
                return FontProperties(fname=font)
            # 如果传的是字体名，如 SimHei，也尝试使用 family
            return FontProperties(family=font)
        # 默认尽量找中文字体；找不到就交给 matplotlib 默认字体
        candidates = [
            r"C:/Windows/Fonts/simhei.ttf",      # 黑体
            r"C:/Windows/Fonts/msyh.ttc",        # 微软雅黑
            r"C:/Windows/Fonts/msyh.ttf",
            r"C:/Windows/Fonts/simsun.ttc",      # 宋体
            r"C:/Windows/Fonts/simkai.ttf",      # 楷体
            r"C:/Windows/Fonts/STKAITI.TTF",
            r"C:/Windows/Fonts/STXINGKA.TTF",
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        ]
        for p in candidates:
            if os.path.exists(p):
                return FontProperties(fname=p)

        # 最后从系统字体列表里按名字搜索，避免 Windows 字体文件名大小写/版本差异导致找不到。
        try:
            from matplotlib import font_manager
            keywords = ("simhei", "msyh", "simsun", "simkai", "kaiti", "noto sans cjk", "source han", "pingfang")
            for fp in font_manager.findSystemFonts(fontpaths=None, fontext="ttf") + font_manager.findSystemFonts(fontpaths=None, fontext="ttc"):
                low = fp.replace("\\", "/").lower()
                if any(k in low for k in keywords):
                    return FontProperties(fname=fp)
        except Exception:
            pass
        return FontProperties()


    def _safe_char_filename(self, ch: str) -> str:
        """Windows/压缩包都安全的单字缓存文件名。"""
        return f"U{ord(ch):04X}.json"

    def _load_all_hanzi_data(self) -> Optional[dict]:
        """读取 hanzi-writer-data 的 all.json。

        支持两种格式：
        1) {"你": {...}, "好": {...}}
        2) [{"character":"你", ...}, ...]
        """
        if self._all_hanzi_cache is not None:
            return self._all_hanzi_cache
        for name in ("all.json", "_all_hanzi.json"):
            fp = self.hanzi_library_dir / name
            if not fp.exists():
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._all_hanzi_cache = data
                elif isinstance(data, list):
                    self._all_hanzi_cache = {item.get("character"): item for item in data if isinstance(item, dict) and item.get("character")}
                else:
                    self._all_hanzi_cache = {}
                return self._all_hanzi_cache
            except Exception:
                continue
        self._all_hanzi_cache = {}
        return self._all_hanzi_cache

    def _download_hanzi_writer_char(self, ch: str, out_path: Path) -> bool:
        """从 Hanzi Writer Data 下载单个汉字 JSON 到缓存目录。"""
        if not bool(getattr(self.cfg, "auto_download_hanzi", True)):
            return False
        quoted = urllib.parse.quote(ch)
        for tmpl in self.HANZI_DATA_URLS:
            url = tmpl.format(char=quoted)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "WritingRobot/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read()
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict) and ("medians" in data or "strokes" in data):
                    out_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    return True
            except Exception:
                continue
        return False

    def _load_hanzi_writer_char(self, ch: str) -> Optional[dict]:
        """读取 Hanzi Writer Data 单字数据。

        查找顺序：
        1. hanzi_writer_data/U4F60.json 这类安全文件名；
        2. hanzi_writer_data/你.json；
        3. hanzi_writer_data/all.json 或 _all_hanzi.json；
        4. 联网自动下载单字 JSON 并缓存。
        """
        if not _is_cjk(ch):
            return None
        candidates = [self.hanzi_library_dir / self._safe_char_filename(ch), self.hanzi_library_dir / f"{ch}.json"]
        for fp in candidates:
            if fp.exists():
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
        all_data = self._load_all_hanzi_data() or {}
        data = all_data.get(ch)
        if isinstance(data, dict):
            return data
        out_path = candidates[0]
        if self._download_hanzi_writer_char(ch, out_path):
            try:
                return json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _hanzi_writer_medians_polylines(self, ch: str, offset_x: float, offset_y: float) -> Optional[Tuple[List[Polyline], float]]:
        """使用 Hanzi Writer Data 的 medians 生成中心线书写轨迹。

        Hanzi Writer Data 的 medians 已经按笔顺给出每一笔的中心线，适合写字机器人；
        坐标通常在 0~1024 的字体坐标中，y 向下。这里统一映射到 height x height 的 mm 方框。
        """
        data = self._load_hanzi_writer_char(ch)
        if not data:
            self.last_external_hanzi_missing += 1
            return None
        medians = data.get("medians")
        if not isinstance(medians, list) or not medians:
            self.last_external_hanzi_missing += 1
            return None

        # 数据一般是 1024 坐标系。若遇到异常范围，按实际最大值兜底归一化。
        nums = []
        for stroke in medians:
            if isinstance(stroke, list):
                for p in stroke:
                    if isinstance(p, (list, tuple)) and len(p) >= 2:
                        try:
                            nums.extend([float(p[0]), float(p[1])])
                        except Exception:
                            pass
        if not nums:
            self.last_external_hanzi_missing += 1
            return None
        max_coord = max(1024.0, max(nums))
        h = float(self.cfg.height)
        pad = h * 0.03
        usable = h - 2 * pad
        polylines: List[Polyline] = []
        for stroke in medians:
            if not isinstance(stroke, list) or len(stroke) < 2:
                continue
            line: Polyline = []
            last_pt = None
            for p in stroke:
                if not isinstance(p, (list, tuple)) or len(p) < 2:
                    continue
                try:
                    nx = max(0.0, min(1.0, float(p[0]) / max_coord))
                    ny = max(0.0, min(1.0, 1.0 - float(p[1]) / max_coord))
                except Exception:
                    continue
                pt = (offset_x + pad + nx * usable, offset_y + pad + ny * usable)
                if last_pt is None or _dist(pt, last_pt) >= max(0.05, h * 0.002):
                    line.append(pt)
                    last_pt = pt
            if len(line) >= 2:
                polylines.append(line)
        if not polylines:
            self.last_external_hanzi_missing += 1
            return None
        self.last_external_hanzi_used += 1
        return polylines, h + self.cfg.char_gap

    def _template_polylines(self, ch: str, offset_x: float, offset_y: float) -> Optional[Tuple[List[Polyline], float]]:
        """把常用汉字/英文/数字按单线笔画模板转换为轨迹。

        normal 模式下优先使用它，这样写出来的是“笔画中心线”，不是字体外轮廓。
        art 模式会跳过模板，直接使用字体轮廓。
        """
        # 正常字优先使用“笔顺字库”：每个 polyline 就是一笔，生成 G-code 时会按这个顺序抬落笔。
        strokes = STROKE_ORDER_TEMPLATES.get(ch)
        if strokes is None:
            strokes = HANZI_STROKE_TEMPLATES.get(ch)
        if strokes is None:
            strokes = ASCII_STROKE_TEMPLATES.get(ch)
        if not strokes:
            return None

        h = float(self.cfg.height)
        x_pad = 0.04 * h
        y_pad = 0.04 * h
        w = h * (0.62 if (len(ch) == 1 and ord(ch) < 128 and ch != ch.upper()) else 0.72 if (len(ch) == 1 and ord(ch) < 128) else 1.0)
        polylines: List[Polyline] = []
        for stroke in strokes:
            poly: Polyline = []
            for nx, ny in stroke:
                x = offset_x + x_pad + nx * (w - 2 * x_pad)
                y = offset_y + y_pad + ny * (h - 2 * y_pad)
                poly.append((x, y))
            if len(poly) >= 2:
                polylines.append(poly)
        return polylines, w + self.cfg.char_gap

    def _char_polylines(self, ch: str, offset_x: float, offset_y: float) -> Tuple[List[Polyline], float]:
        mode = str(getattr(self.cfg, "font_mode", "normal") or "normal").lower()

        if _is_cjk(ch):
            if mode != "art":
                # 正常字：不再用自写汉字模板/骨架猜测，优先使用 Hanzi Writer Data 的 medians。
                # medians 是现成汉字库提供的“按笔顺中心线”，每一项就是一笔，最适合写字机器人。
                lib_polys = self._hanzi_writer_medians_polylines(ch, offset_x, offset_y)
                if lib_polys is not None:
                    return lib_polys
            # 艺术字或字库缺字：退回字体轮廓，保证至少能识别并生成可见字形。
            return self._outline_polylines(ch, offset_x, offset_y)

        if mode != "art":
            # 英文/数字正常字仍使用单线模板。
            templated = self._template_polylines(ch, offset_x, offset_y)
            if templated is not None:
                return templated

        # 艺术字/未知字符：使用字体轮廓。
        return self._outline_polylines(ch, offset_x, offset_y)

    def _outline_polylines(self, ch: str, offset_x: float, offset_y: float) -> Tuple[List[Polyline], float]:
        # TextPath 的 size 直接按 points 处理，这里把 size 设成 cfg.height，再以真实 bbox 微调到 mm。
        tp = TextPath((offset_x, offset_y), ch, size=self.cfg.height, prop=self.font_prop)
        vertices = tp.vertices
        codes = tp.codes
        if codes is None or len(vertices) == 0:
            return [], self.cfg.height * 0.5

        polylines: List[Polyline] = []
        current: Polyline = []
        start: Optional[Point] = None
        last: Optional[Point] = None
        i = 0
        while i < len(codes):
            code = codes[i]
            v = tuple(map(float, vertices[i]))
            if code == MplPath.MOVETO:
                if len(current) > 1:
                    polylines.append(current)
                current = [v]
                start = v
                last = v
                i += 1
            elif code == MplPath.LINETO:
                current.append(v)
                last = v
                i += 1
            elif code == MplPath.CURVE3:
                if last is None or i + 1 >= len(vertices):
                    i += 1
                    continue
                p1 = v
                p2 = tuple(map(float, vertices[i + 1]))
                current.extend(_quad(last, p1, p2, self.cfg.curve_segments))
                last = p2
                i += 2
            elif code == MplPath.CURVE4:
                if last is None or i + 2 >= len(vertices):
                    i += 1
                    continue
                p1 = v
                p2 = tuple(map(float, vertices[i + 1]))
                p3 = tuple(map(float, vertices[i + 2]))
                current.extend(_cubic(last, p1, p2, p3, self.cfg.curve_segments))
                last = p3
                i += 3
            elif code == MplPath.CLOSEPOLY:
                if start is not None and last is not None and _dist(last, start) > 1e-6:
                    current.append(start)
                if len(current) > 1:
                    polylines.append(current)
                current = []
                start = None
                last = None
                i += 1
            else:
                i += 1
        if len(current) > 1:
            polylines.append(current)

        # 获取字符宽度，用于排版
        bbox = tp.get_extents()
        advance = max(float(bbox.width), self.cfg.height * 0.5) + self.cfg.char_gap
        return polylines, advance


    def _find_font_file(self) -> Optional[str]:
        """尽量取得当前字体文件路径，给 PIL 光栅化使用。"""
        try:
            fname = self.font_prop.get_file()
            if fname and os.path.exists(fname):
                return fname
        except Exception:
            pass
        try:
            from matplotlib import font_manager
            return font_manager.findfont(self.font_prop, fallback_to_default=True)
        except Exception:
            return None

    @staticmethod
    def _zhang_suen_thin(binary: np.ndarray) -> np.ndarray:
        """纯 numpy/Python 版 Zhang-Suen 细化。True 表示黑色笔画。"""
        img = binary.astype(np.uint8).copy()
        changed = True
        h, w = img.shape
        while changed:
            changed = False
            for step in (0, 1):
                to_del = []
                for y in range(1, h - 1):
                    for x in range(1, w - 1):
                        if img[y, x] == 0:
                            continue
                        p2 = img[y - 1, x]
                        p3 = img[y - 1, x + 1]
                        p4 = img[y, x + 1]
                        p5 = img[y + 1, x + 1]
                        p6 = img[y + 1, x]
                        p7 = img[y + 1, x - 1]
                        p8 = img[y, x - 1]
                        p9 = img[y - 1, x - 1]
                        ns = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
                        if ns < 2 or ns > 6:
                            continue
                        seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
                        trans = sum((seq[i] == 0 and seq[i + 1] == 1) for i in range(8))
                        if trans != 1:
                            continue
                        if step == 0:
                            if p2 * p4 * p6 != 0 or p4 * p6 * p8 != 0:
                                continue
                        else:
                            if p2 * p4 * p8 != 0 or p2 * p6 * p8 != 0:
                                continue
                        to_del.append((y, x))
                if to_del:
                    changed = True
                    for y, x in to_del:
                        img[y, x] = 0
        return img.astype(bool)

    @staticmethod
    def _trace_skeleton(skel: np.ndarray, min_pixels: int = 3) -> List[List[Tuple[int, int]]]:
        """把骨架像素追踪成若干折线。返回像素坐标(x,y)折线。"""
        h, w = skel.shape
        pts = {(x, y) for y in range(h) for x in range(w) if skel[y, x]}
        if not pts:
            return []

        def nbrs(p):
            x, y = p
            out = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    q = (x + dx, y + dy)
                    if q in pts:
                        out.append(q)
            return out

        neigh = {p: nbrs(p) for p in pts}
        endpoints = [p for p, ns in neigh.items() if len(ns) <= 1]
        starts = endpoints[:] if endpoints else list(pts)
        used_edges = set()
        lines = []

        def edge(a, b):
            return tuple(sorted((a, b)))

        for st in starts:
            for nb in neigh.get(st, []):
                e = edge(st, nb)
                if e in used_edges:
                    continue
                line = [st, nb]
                used_edges.add(e)
                prev, cur = st, nb
                while True:
                    cands = [q for q in neigh.get(cur, []) if q != prev and edge(cur, q) not in used_edges]
                    if not cands:
                        break
                    # 优先保持方向，让折线少抖动
                    vx, vy = cur[0] - prev[0], cur[1] - prev[1]
                    def score(q):
                        wx, wy = q[0] - cur[0], q[1] - cur[1]
                        return -(vx * wx + vy * wy)
                    nxt = sorted(cands, key=score)[0]
                    used_edges.add(edge(cur, nxt))
                    line.append(nxt)
                    prev, cur = cur, nxt
                    if len(neigh.get(cur, [])) != 2:
                        break
                if len(line) >= min_pixels:
                    lines.append(line)

        # 处理没有端点的闭环残余边
        for a in list(pts):
            for b in neigh.get(a, []):
                if edge(a, b) not in used_edges:
                    line = [a, b]
                    used_edges.add(edge(a, b))
                    prev, cur = a, b
                    while True:
                        cands = [q for q in neigh.get(cur, []) if q != prev and edge(cur, q) not in used_edges]
                        if not cands:
                            break
                        nxt = cands[0]
                        used_edges.add(edge(cur, nxt))
                        line.append(nxt)
                        prev, cur = cur, nxt
                        if cur == a:
                            break
                    if len(line) >= min_pixels:
                        lines.append(line)
        return lines

    @staticmethod
    def _line_length(line: Polyline) -> float:
        return sum(_dist(line[i], line[i - 1]) for i in range(1, len(line)))

    @staticmethod
    def _dedupe_and_order_lines(lines: List[Polyline]) -> List[Polyline]:
        """去重复、去毛刺，并按就近原则排序骨架/轮廓线，减少反复空走。"""
        cleaned: List[Polyline] = []
        seen = set()
        for line in lines:
            pts: Polyline = []
            last = None
            for x, y in line:
                pt = (float(x), float(y))
                if last is None or _dist(pt, last) >= 0.08:
                    pts.append(pt)
                    last = pt
            if len(pts) < 2 or HanziToGcode._line_length(pts) < 0.60:
                continue
            key_f = tuple((round(x, 1), round(y, 1)) for x, y in pts)
            key_r = tuple(reversed(key_f))
            key = min(key_f, key_r)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(pts)
        if not cleaned:
            return []
        remaining = cleaned[:]
        ordered: List[Polyline] = []
        cur = None
        while remaining:
            if cur is None:
                idx = min(range(len(remaining)), key=lambda i: (remaining[i][0][0], -remaining[i][0][1]))
            else:
                idx = min(range(len(remaining)), key=lambda i: min(_dist(cur, remaining[i][0]), _dist(cur, remaining[i][-1])))
            line = remaining.pop(idx)
            if cur is not None and _dist(cur, line[-1]) < _dist(cur, line[0]):
                line = list(reversed(line))
            ordered.append(line)
            cur = line[-1]
        return ordered

    def _raster_centerline_polylines(self, ch: str, offset_x: float, offset_y: float) -> Optional[Tuple[List[Polyline], float]]:
        """未知汉字优先用光栅骨架中心线生成，避免只写外轮廓。"""
        if not _is_cjk(ch):
            return None
        try:
            from PIL import Image, ImageDraw, ImageFont
            font_file = self._find_font_file()
            if not font_file or not os.path.exists(font_file):
                return None
            pix = 160
            pad = 24
            font = ImageFont.truetype(font_file, pix)
            img = Image.new('L', (pix + pad * 2, pix + pad * 2), 255)
            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), ch, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (img.width - tw) // 2 - bbox[0]
            y = (img.height - th) // 2 - bbox[1]
            draw.text((x, y), ch, font=font, fill=0)
            arr = np.array(img)
            binary = arr < 160
            ys, xs = np.where(binary)
            if len(xs) == 0:
                return None
            # 裁剪到字形区域，减少边框空白影响
            x1, x2 = max(0, xs.min() - 2), min(binary.shape[1], xs.max() + 3)
            y1, y2 = max(0, ys.min() - 2), min(binary.shape[0], ys.max() + 3)
            crop = binary[y1:y2, x1:x2]
            skel = self._zhang_suen_thin(crop)
            pix_lines = self._trace_skeleton(skel, min_pixels=4)
            if not pix_lines:
                return None
            h_mm = float(self.cfg.height)
            scale = h_mm / max(1, crop.shape[0] - 1)
            w_mm = crop.shape[1] * scale
            polylines: List[Polyline] = []
            for pl in pix_lines:
                # 把连续像素转成mm；图像y向下，所以翻转成绘图y向上
                line = [(offset_x + px * scale, offset_y + (crop.shape[0] - 1 - py) * scale) for px, py in pl]
                # 去掉太短的小毛刺
                length = sum(_dist(line[i], line[i-1]) for i in range(1, len(line)))
                if length >= max(0.8, h_mm * 0.05):
                    polylines.append(line)
            polylines = self._dedupe_and_order_lines(polylines)
            if not polylines:
                return None
            # 如果骨架碎成过多短段，实际写出来会像乱线；此时退回字体轮廓，保证复杂常见字可识别。
            if len(polylines) > 80:
                return None
            return polylines, h_mm + self.cfg.char_gap
        except Exception:
            return None

    def text_to_polylines(self) -> List[Polyline]:
        all_lines: List[Polyline] = []
        x_cursor = self.cfg.x0
        y_cursor = self.cfg.y0
        max_width = float(getattr(self.cfg, "max_line_width", 0.0) or 0.0)

        for ch in self.cfg.text:
            if ch == "\n":
                x_cursor = self.cfg.x0
                y_cursor -= (self.cfg.height + self.cfg.line_gap)
                continue
            if ch == " ":
                space_adv = self.cfg.height * 0.5 + self.cfg.char_gap
                if max_width > 0 and (x_cursor - self.cfg.x0 + space_adv) > max_width:
                    x_cursor = self.cfg.x0
                    y_cursor -= (self.cfg.height + self.cfg.line_gap)
                else:
                    x_cursor += space_adv
                continue

            # 先在当前位置生成一次，拿到字符宽度；如果本行放不下则换行后重新生成。
            polys, adv = self._char_polylines(ch, x_cursor, y_cursor)
            if max_width > 0 and x_cursor > self.cfg.x0 and (x_cursor - self.cfg.x0 + adv) > max_width:
                x_cursor = self.cfg.x0
                y_cursor -= (self.cfg.height + self.cfg.line_gap)
                polys, adv = self._char_polylines(ch, x_cursor, y_cursor)
            all_lines.extend(polys)
            x_cursor += adv

        if self.cfg.scale_y_flip:
            all_lines = [[(x, -y) for x, y in line] for line in all_lines]
        return all_lines

    def _fmt(self, value: float) -> str:
        return f"{value:.{self.cfg.decimals}f}"

    def polylines_to_gcode(self, polylines: Sequence[Polyline]) -> List[str]:
        """将轮廓折线转换为下位机更容易执行的 G-code。

        关键修正：
        1. 笔画之间使用 G0 + M05/M03 区分抬笔/落笔，不再把换笔画的空走线当作 G1 画线。
        2. 保留小数坐标，不再 int() 取整，避免小字和曲线细节被截断。
        3. 不使用 polylines.index(poly)，避免重复笔画时找错下一个笔画。
        """
        c = self.cfg
        lines = [
            "G21",                 # 单位：mm
            "G90",                 # 绝对坐标
            f"G1 F{int(c.feed)}",
            c.pen_off,
        ]

        for poly in polylines:
            if len(poly) < 2:
                continue

            sx, sy = poly[0]
            lines.append(f"G0 X{self._fmt(sx)} Y{self._fmt(sy)} F{int(c.travel_feed)}")
            lines.append(c.pen_on)
            lines.append(f"G1 F{int(c.feed)}")

            last = None
            for x, y in poly:
                pt = (round(x, c.decimals), round(y, c.decimals))
                if pt == last:
                    continue
                lines.append(f"G1 X{self._fmt(x)} Y{self._fmt(y)}")
                last = pt
            lines.append(c.pen_off)

        lines.append(c.pen_off)
        return lines

    def save(self, output: str | Path) -> Path:
        output = Path(output)
        polylines = self.text_to_polylines()
        gcode = self.polylines_to_gcode(polylines)
        output.write_text("\n".join(gcode) + "\n", encoding="utf-8")
        return output


def preview(polylines: Sequence[Polyline], out_png: str | Path):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    for line in polylines:
        xs = [p[0] for p in line]
        ys = [p[1] for p in line]
        ax.plot(xs, ys)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True)
    ax.set_xlabel("X / mm")
    ax.set_ylabel("Y / mm")
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="汉字/中文文字转 G-code")
    p.add_argument("--text", required=True, help="要转换的文字，例如：北航机电")
    p.add_argument("--font", default=None, help="中文字体路径或字体名，例如 C:/Windows/Fonts/simhei.ttf")
    p.add_argument("--output", default="output.txt", help="输出 G-code 文件")
    p.add_argument("--height", type=float, default=20.0, help="字高 mm")
    p.add_argument("--x0", type=float, default=0.0)
    p.add_argument("--y0", type=float, default=0.0)
    p.add_argument("--char-gap", type=float, default=3.0)
    p.add_argument("--line-gap", type=float, default=8.0)
    p.add_argument("--max-line-width", type=float, default=280.0, help="自动换行宽度mm，<=0关闭")
    p.add_argument("--feed", type=float, default=800.0)
    p.add_argument("--travel-feed", type=float, default=2000.0)
    p.add_argument("--segments", type=int, default=8, help="曲线离散段数，越大越圆滑")
    p.add_argument("--m3m5", action="store_true", help="使用 M3/M5 开关笔，而不是 Z 轴抬落笔")
    p.add_argument("--z-up", type=float, default=3.0)
    p.add_argument("--z-down", type=float, default=0.0)
    p.add_argument("--pen-on", default="M3")
    p.add_argument("--pen-off", default="M5")
    p.add_argument("--preview", action="store_true", help="同时输出预览 PNG")
    return p


def main():
    args = build_argparser().parse_args()
    cfg = GcodeConfig(
        text=args.text,
        font=args.font,
        height=args.height,
        x0=args.x0,
        y0=args.y0,
        char_gap=args.char_gap,
        line_gap=args.line_gap,
        max_line_width=args.max_line_width,
        feed=args.feed,
        travel_feed=args.travel_feed,
        curve_segments=args.segments,
        use_z=not args.m3m5,
        z_up=args.z_up,
        z_down=args.z_down,
        pen_on=args.pen_on,
        pen_off=args.pen_off,
    )
    conv = HanziToGcode(cfg)
    out = conv.save(args.output)
    print(f"已生成: {out}")
    if args.preview:
        png = Path(args.output).with_suffix(".png")
        preview(conv.text_to_polylines(), png)
        print(f"已生成预览: {png}")


if __name__ == "__main__":
    main()
