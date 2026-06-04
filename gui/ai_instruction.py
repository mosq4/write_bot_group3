"""
AI 汉字书写指令模块

提供 GUI ↔ AI (opencode CLI) 文件桥接:
1. GUI 将用户输入写入 gui/ai_request.txt
2. opencode AI 读取请求, 生成指令写入 gui/ai_response.json
3. GUI 监控 gui/ai_response.json, 加载并逐条执行

AI 响应 JSON 格式:
{
  "version": 1,
  "text": "你好",
  "font_size_mm": 20,
  "origin_x_mm": 50,
  "origin_y_mm": 100,
  "char_spacing_mm": 5,
  "pen_up_angle": 45,
  "pen_down_angle": 90,
  "speed": 3,
  "instructions": [
    {"action": "servo", "angle": 45},
    {"action": "move_abs", "x": 50, "y": 100, "speed": 5},
    {"action": "servo", "angle": 90},
    {"action": "line_interp", "x1": 50, "y1": 100, "x2": 70, "y2": 80, "speed": 3},
    ...
  ]
}
"""

import json
import os
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


AI_REQUEST_FILE = os.path.join(os.path.dirname(__file__), "ai_request.txt")
AI_RESPONSE_FILE = os.path.join(os.path.dirname(__file__), "ai_response.json")


@dataclass
class InstructionItem:
    """单条执行指令"""
    action: str                   # "servo" | "move_abs" | "move_rel" | "line_interp" | "arc_interp" | "home" | "stop" | "delay"
    params: dict = field(default_factory=dict)


@dataclass
class AIResponse:
    """AI 返回的完整指令集"""
    version: int = 1
    text: str = ""
    font_size_mm: float = 20.0
    origin_x_mm: float = 50.0
    origin_y_mm: float = 100.0
    char_spacing_mm: float = 5.0
    pen_up_angle: float = 15.0
    pen_down_angle: float = 90.0
    speed: int = 3
    instructions: list = field(default_factory=list)


def write_request(text: str, font_size: float = 20.0, origin_x: float = 50.0,
                  origin_y: float = 100.0, spacing: float = 5.0,
                  pen_up: float = 15.0, pen_down: float = 90.0,
                  speed: int = 3) -> str:
    """写入 AI 请求文件

    Returns:
        写入的文件路径
    """
    request = {
        "version": 1,
        "text": text,
        "font_size_mm": font_size,
        "origin_x_mm": origin_x,
        "origin_y_mm": origin_y,
        "char_spacing_mm": spacing,
        "pen_up_angle": pen_up,
        "pen_down_angle": pen_down,
        "speed": speed,
    }
    with open(AI_REQUEST_FILE, "w", encoding="utf-8") as f:
        json.dump(request, f, ensure_ascii=False, indent=2)
    return AI_REQUEST_FILE


def read_response() -> Optional[AIResponse]:
    """读取 AI 响应文件

    Returns:
        AIResponse 对象, 文件不存在或格式错误时返回 None
    """
    if not os.path.exists(AI_RESPONSE_FILE):
        return None
    try:
        with open(AI_RESPONSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        resp = AIResponse(
            version=data.get("version", 1),
            text=data.get("text", ""),
            font_size_mm=data.get("font_size_mm", 20.0),
            origin_x_mm=data.get("origin_x_mm", 50.0),
            origin_y_mm=data.get("origin_y_mm", 100.0),
            char_spacing_mm=data.get("char_spacing_mm", 5.0),
            pen_up_angle=data.get("pen_up_angle", 15.0),
            pen_down_angle=data.get("pen_down_angle", 90.0),
            speed=data.get("speed", 3),
            instructions=data.get("instructions", []),
        )
        return resp
    except (json.JSONDecodeError, KeyError):
        return None


def clear_response() -> None:
    """清除 AI 响应文件"""
    if os.path.exists(AI_RESPONSE_FILE):
        os.remove(AI_RESPONSE_FILE)


# ---------- AI Prompt 模板 ----------

AI_PROMPT_TEMPLATE = """你是一个汉字书写机器人路径规划器。请根据用户输入的汉字，生成XY平台运动控制指令序列。

## 写字参数
- 字体大小: {font_size}mm × {font_size}mm
- 字符间距: {spacing}mm
- 每字原点 (左上角): ({origin_x}, {origin_y})，第一个字原点为给定值，后续每个字 X 偏移 font_size + spacing
- 写字区域: X 轴向右, Y 轴向下
- 速度: 书写 {speed} mm/s, 空移 5 mm/s
- 电磁铁控制: pen_up 抬笔, pen_down 落笔

## 用户输入
"{text}"

## 指令格式
请返回 JSON，格式如下:
```json
{{
  "version": 1,
  "text": "{text}",
  "font_size_mm": {font_size},
  "origin_x_mm": {origin_x},
  "origin_y_mm": {origin_y},
  "char_spacing_mm": {spacing},
  "pen_up_angle": {pen_up},
  "pen_down_angle": {pen_down},
  "speed": {speed},
  "instructions": [
    {{"action": "pen_up"}},
    {{"action": "move_abs", "x": 50, "y": 100, "speed": 5}},
    {{"action": "pen_down"}},
    {{"action": "line_interp", "x1": 50, "y1": 100, "x2": 60, "y2": 90, "speed": {speed}}},
    {{"action": "line_interp", "x1": 60, "y1": 90, "x2": 70, "y2": 100, "speed": {speed}}},
    {{"action": "pen_up"}}
  ]
}}
```

## 规则
1. 落笔前必须先抬笔移动到起点
2. 每个笔画: 抬笔→空移到起点→落笔→书写笔画→抬笔
3. 使用 "pen_up" / "pen_down" 控制电磁铁通断电 (通=落, 断=抬)
4. 逐点比较法插补只支持直线和圆弧，用直线近似所有笔画
5. 笔画的起点/终点坐标在字框内 (origin_x ~ origin_x+font_size, origin_y ~ origin_y+font_size)
6. **只输出 JSON，不要加任何解释或```json标记**"""


def build_prompt(text: str, font_size: float = 20.0, origin_x: float = 50.0,
                 origin_y: float = 100.0, spacing: float = 5.0,
                 pen_up: float = 15.0, pen_down: float = 90.0,
                 speed: int = 3) -> str:
    """构建发送给 AI 的 prompt"""
    return AI_PROMPT_TEMPLATE.format(
        text=text,
        font_size=font_size,
        origin_x=origin_x,
        origin_y=origin_y,
        spacing=spacing,
        pen_up=pen_up,
        pen_down=pen_down,
        speed=speed,
    )


def generate_via_api(text: str, api_key: str,
                     font_size: float = 20.0, origin_x: float = 50.0,
                     origin_y: float = 100.0, spacing: float = 5.0,
                     pen_up: float = 15.0, pen_down: float = 90.0,
                     speed: int = 3) -> Optional[AIResponse]:
    """通过 DeepSeek API 直接生成汉字书写指令

    Args:
        text: 要书写的汉字
        api_key: DeepSeek API key
        ...: 其他写字参数

    Returns:
        AIResponse 对象, 失败返回 None
    """
    from deepseek_client import DeepSeekClient
    import re

    prompt = build_prompt(text, font_size, origin_x, origin_y, spacing,
                          pen_up, pen_down, speed)

    client = DeepSeekClient(api_key)
    logger.info(f"Calling DeepSeek API for text: {text}")
    raw = client.generate_writing_instructions(prompt)

    if not raw:
        return None

    raw = raw.strip()
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()

    first_brace = raw.find('{')
    last_brace = raw.rfind('}')
    if first_brace != -1 and last_brace != -1:
        raw = raw[first_brace:last_brace + 1]

    try:
        data = json.loads(raw)
        resp = AIResponse(
            version=data.get("version", 1),
            text=data.get("text", text),
            font_size_mm=data.get("font_size_mm", font_size),
            origin_x_mm=data.get("origin_x_mm", origin_x),
            origin_y_mm=data.get("origin_y_mm", origin_y),
            char_spacing_mm=data.get("char_spacing_mm", spacing),
            pen_up_angle=data.get("pen_up_angle", pen_up),
            pen_down_angle=data.get("pen_down_angle", pen_down),
            speed=data.get("speed", speed),
            instructions=data.get("instructions", []),
        )
        with open(AI_RESPONSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return resp
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse DeepSeek response: {e}")
        logger.debug(f"Raw response: {raw}")
        return None
