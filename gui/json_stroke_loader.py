"""
JSON 笔画库加载器

从 all.json 中读取汉字笔画轨迹数据（medians 字段），
返回 WritingPath 供 G-code 编译使用。

数据来源：预存的汉字笔画分解库（9574 个字符）
"""

import json
import os
import logging
from typing import Optional, Dict, Tuple, List

from text_to_path import WritingPath, Stroke

logger = logging.getLogger(__name__)

# 全局缓存，避免重复加载
_cache: Optional[Dict] = None
_cache_path: Optional[str] = None


def _get_data_path() -> str:
    """获取 all.json 的路径"""
    # 优先从环境变量读取
    env_path = os.environ.get("STROKE_JSON_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    # 相对于项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "..", "all.json"),
        os.path.join(script_dir, "..", "..", "all.json"),
        os.path.join(script_dir, "..", "assets", "all.json"),
        os.path.join(script_dir, "..", "data", "all.json"),
    ]
    for p in candidates:
        normalized = os.path.normpath(p)
        if os.path.exists(normalized):
            return normalized

    # 最后尝试同级目录
    return os.path.join(script_dir, "..", "all.json")


def load_database(path: Optional[str] = None) -> Optional[Dict]:
    """加载 all.json 到内存（带缓存）

    Args:
        path: all.json 路径，None 则自动搜索

    Returns:
        字符字典 {char: {strokes, medians}}
    """
    global _cache, _cache_path

    if path is None:
        path = _get_data_path()

    if _cache is not None and _cache_path == path:
        return _cache

    if not os.path.exists(path):
        logger.error(f"笔画库文件不存在: {path}")
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            _cache = json.load(f)
        _cache_path = path
        logger.info(f"已加载笔画库: {len(_cache)} 个字符 ({path})")
        return _cache
    except Exception as e:
        logger.error(f"加载笔画库失败: {e}")
        return None


def get_strokes(char: str,
                db: Optional[Dict] = None) -> Optional[WritingPath]:
    """获取单个字符的笔画轨迹

    Args:
        char: 单个汉字
        db: 已加载的数据库，None 则自动加载

    Returns:
        WritingPath 对象，失败返回 None
    """
    if len(char) != 1:
        logger.warning(f"get_strokes 只接受单字符，收到 '{char}'")
        return None

    if db is None:
        db = load_database()
    if db is None:
        return None

    entry = db.get(char)
    if entry is None:
        logger.warning(f"笔画库中未找到字符 '{char}'")
        return None

    medians = entry.get("medians")
    if not medians or not isinstance(medians, list):
        logger.warning(f"字符 '{char}' 没有有效的 medians 数据")
        return None

    path = WritingPath()
    for median_points in medians:
        if len(median_points) < 2:
            continue
        # 坐标格式: [[x1, y1], [x2, y2], ...]
        # 已为数学坐标系（Y向上），直接使用
        points = [(float(p[0]), float(p[1])) for p in median_points]
        path.add_stroke(Stroke(points))

    return path


def decompose_text_via_json(text: str,
                            db: Optional[Dict] = None) -> Optional[WritingPath]:
    """将一段文字分解为笔画路径（从 JSON 笔画库读取）

    对 text 中每个字符查询笔画库，按书写顺序排列。
    跳过库中不存在的字符并记录警告。

    Args:
        text: 要书写的文字（支持多字）
        db: 已加载的数据库，None 则自动加载

    Returns:
        WritingPath 对象（仅包含原始笔画，未做排版偏移）
        * 如需自动排版，请使用 decompose_text_with_layout()
    """
    result = decompose_text_with_layout(text, db)
    if result is None:
        return None
    path, _ = result
    return path


def decompose_text_with_layout(text: str,
                                db: Optional[Dict] = None
                                ) -> Optional[Tuple[WritingPath, list]]:
    """将一段文字分解为笔画路径，并返回逐字符分组信息（含行号）

    支持多行输入：text 中的换行符（\\n）会作为强制换行标记，
    对应 char_group 中的 "line" 字段供排版使用。

    Returns:
        (WritingPath, char_groups) 或 None
        char_groups: [{"char": "你", "line": 0, "stroke_start": 0, ...}, ...]
    """
    if db is None:
        db = load_database()
    if db is None:
        return None

    path = WritingPath()
    char_groups = []
    missing = []

    # 按换行符分割，保留空行
    lines = text.split('\n')

    for line_idx, line in enumerate(lines):
        if not line.strip():
            # 空行：添加一个空标记，让排版时留出空行位置
            char_groups.append({
                "char": "",
                "line": line_idx,
                "stroke_start": len(path.strokes),
                "stroke_end": len(path.strokes),
                "points_start": 0,
                "points_end": 0,
                "is_empty_line": True,
            })
            continue

        for ch in line:
            char_path = get_strokes(ch, db)
            if char_path is None or char_path.is_empty:
                missing.append(ch)
                continue

            stroke_start = len(path.strokes)
            points_start = sum(len(s.points) for s in path.strokes)

            for stroke in char_path.strokes:
                path.add_stroke(stroke)

            stroke_end = len(path.strokes)
            points_end = sum(len(s.points) for s in path.strokes)

            char_groups.append({
                "char": ch,
                "line": line_idx,
                "stroke_start": stroke_start,
                "stroke_end": stroke_end,
                "points_start": points_start,
                "points_end": points_end,
                "is_empty_line": False,
            })

    if missing:
        logger.warning(f"以下字符在笔画库中不存在: {''.join(missing)}")

    if path.is_empty and not any(g.get("is_empty_line") for g in char_groups):
        logger.error("所有字符均未找到笔画数据")
        return None

    logger.info(f"从笔画库成功加载 {len(path.strokes)} 个笔画, "
                f"{len(char_groups)} 个字符, {line_idx + 1} 行")
    return path, char_groups


def database_info(db: Optional[Dict] = None) -> dict:
    """返回数据库统计信息"""
    if db is None:
        db = load_database()
    if db is None:
        return {"status": "not_loaded", "count": 0}

    return {
        "status": "loaded",
        "count": len(db),
        "path": _cache_path or "",
    }
