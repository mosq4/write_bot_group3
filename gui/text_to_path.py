"""
文字转路径引擎

将文字转换为 XY 平台的移动路径（笔画坐标序列）。
支持两种模式：
  1. AI 模式：调用 DeepSeek API 进行汉字笔画拆分（适合中文书写）
  2. 字体模式：从字体渲染图像骨架提取单线路径（适合英文/数字/符号）
"""

import json
import math
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

class Stroke:
    """单个笔画，由一系列坐标点构成"""
    def __init__(self, points: List[Tuple[float, float]]):
        self.points = points  # [(x, y), (x, y), ...]

    @property
    def is_empty(self) -> bool:
        return len(self.points) < 2

    def bounding_box(self) -> Tuple[float, float, float, float]:
        """返回 (x_min, y_min, x_max, y_max)"""
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)


class WritingPath:
    """完整的文字书写路径"""
    def __init__(self, strokes: List[Stroke] = None):
        self.strokes = strokes or []

    def add_stroke(self, stroke: Stroke):
        self.strokes.append(stroke)

    @property
    def is_empty(self) -> bool:
        return len(self.strokes) == 0

    def bounding_box(self) -> Tuple[float, float, float, float]:
        """返回整体 (x_min, y_min, x_max, y_max)"""
        if self.is_empty:
            return 0, 0, 0, 0
        x_min = min(s.bounding_box()[0] for s in self.strokes)
        y_min = min(s.bounding_box()[1] for s in self.strokes)
        x_max = max(s.bounding_box()[2] for s in self.strokes)
        y_max = max(s.bounding_box()[3] for s in self.strokes)
        return x_min, y_min, x_max, y_max

    def scale_and_center(self, target_width: float, target_height: float,
                         center_x: float, center_y: float):
        """缩放并对齐到指定区域中心"""
        if self.is_empty:
            return
        x_min, y_min, x_max, y_max = self.bounding_box()
        w = x_max - x_min
        h = y_max - y_min
        if w == 0 or h == 0:
            return
        scale = min(target_width / w, target_height / h) * 0.9  # 留 10% 边距
        mid_x = (x_min + x_max) / 2.0
        mid_y = (y_min + y_max) / 2.0
        for stroke in self.strokes:
            stroke.points = [
                (center_x + (x - mid_x) * scale,
                 center_y + (y - mid_y) * scale)
                for x, y in stroke.points
            ]

    def flip_y(self):
        """翻转 Y 轴（图像坐标 Y 向下 vs 平台坐标 Y 向上）"""
        for stroke in self.strokes:
            stroke.points = [(x, -y) for x, y in stroke.points]


# ---------------------------------------------------------------------------
# 字体单线模式（基于图像骨架提取）
#   1. 用 Pillow 渲染文字为图像
#   2. 骨架化（skeletonize）得到单像素宽中心线
#   3. 追踪骨架像素生成笔画路径
# ---------------------------------------------------------------------------

def _neighbors_8(y: int, x: int, h: int, w: int):
    """返回 (y, x) 的 8 邻域有效坐标"""
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                yield ny, nx


def _trace_skeleton(skel: 'np.ndarray') -> List[List[Tuple[int, int]]]:
    """将骨架二值图像追踪为连续的像素路径列表"""
    import numpy as np
    h, w = skel.shape
    visited = np.zeros_like(skel, dtype=bool)
    paths = []

    # 找到所有端点（只有 1 个骨架邻域的点）或分支点
    endpoints = []
    for y in range(h):
        for x in range(w):
            if not skel[y, x]:
                continue
            n = sum(1 for ny, nx in _neighbors_8(y, x, h, w) if skel[ny, nx])
            if n <= 1 or n >= 3:
                endpoints.append((y, x))

    # 如果没有任何端点（如闭合环），取所有点为起点
    if not endpoints:
        ys, xs = np.where(skel)
        if len(ys):
            endpoints = list(zip(ys.tolist(), xs.tolist()))

    # 从每个端点开始追踪
    for start in endpoints:
        if visited[start]:
            continue
        # 如果这个端点已经没有未访问的骨架邻域，跳过
        has_unvisited = any(
            not visited[ny, nx] and skel[ny, nx]
            for ny, nx in _neighbors_8(start[0], start[1], h, w)
        )
        if not has_unvisited and skel[start]:
            # 孤立点，直接作为路径
            if not visited[start]:
                visited[start] = True
                paths.append([start])
            continue

        stack = [start]
        path = []
        while stack:
            y, x = stack.pop()
            if visited[y, x] or not skel[y, x]:
                continue
            visited[y, x] = True
            path.append((x, y))  # (x, y) 坐标顺序

            # 找下一个未访问的骨架邻域
            for ny, nx in _neighbors_8(y, x, h, w):
                if not visited[ny, nx] and skel[ny, nx]:
                    stack.append((ny, nx))

        if len(path) >= 2:
            paths.append(path)

    return paths


def _resample_path(points: List[Tuple[float, float]],
                   num_points: int = 30) -> List[Tuple[float, float]]:
    """对点序列进行等距重采样"""
    if len(points) < 2:
        return points

    seg_lens = []
    total = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i-1][0]
        dy = points[i][1] - points[i-1][1]
        seg_lens.append(math.hypot(dx, dy))
        total += seg_lens[-1]

    if total < 1e-6:
        return [points[0], points[-1]]

    result = [points[0]]
    target_dist = total / (num_points - 1)
    accumulated = 0.0
    seg_idx = 0
    for i in range(1, num_points - 1):
        target = i * target_dist
        while seg_idx < len(seg_lens) and accumulated + seg_lens[seg_idx] < target:
            accumulated += seg_lens[seg_idx]
            seg_idx += 1
        if seg_idx >= len(seg_lens):
            break
        t = (target - accumulated) / seg_lens[seg_idx] if seg_lens[seg_idx] > 0 else 0
        x = points[seg_idx][0] + t * (points[seg_idx+1][0] - points[seg_idx][0])
        y = points[seg_idx][1] + t * (points[seg_idx+1][1] - points[seg_idx][1])
        result.append((x, y))
    result.append(points[-1])
    return result


def text_to_path_font(text: str,
                      font_size: float = 100,
                      render_dpi: int = 200) -> WritingPath:
    """使用字体渲染+骨架提取生成单线书写路径（适合英文/数字/符号）

    原理：
      1. 用 Pillow 渲染文字为高分辨率图像
      2. 二值化后骨架化（中心线提取）
      3. 追踪骨架像素生成连续笔画

    需要 Pillow 和 scikit-image，若缺失会打印错误并返回空路径。

    Args:
        text: 要写的文字
        font_size: 内部渲染字号（越大细节越多）
        render_dpi: 渲染分辨率

    Returns:
        WritingPath 对象
    """
    path = WritingPath()

    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
    except ImportError:
        logger.error("需要安装 Pillow: pip install Pillow")
        return path

    # 计算图像尺寸
    margin = font_size
    img_w = int(font_size * len(text) * 1.5 + margin * 2)
    img_h = int(font_size * 2 + margin * 2)

    try:
        # 创建图像
        img = Image.new('L', (img_w, img_h), 255)
        draw = ImageDraw.Draw(img)

        # 尝试加载中文字体
        font = None
        font_candidates = [
            'C:/Windows/Fonts/msyh.ttc',        # 微软雅黑
            'C:/Windows/Fonts/simsun.ttc',      # 宋体
            'C:/Windows/Fonts/simhei.ttf',       # 黑体
            'arial.ttf',
            'Arial.ttf',
        ]
        for fp in font_candidates:
            try:
                font = ImageFont.truetype(fp, int(font_size))
                break
            except (OSError, IOError):
                continue
        if font is None:
            font = ImageFont.load_default()

        # 渲染文字
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # 居中绘制
        ox = (img_w - tw) // 2 - bbox[0]
        oy = (img_h - th) // 2 - bbox[1]
        draw.text((ox, oy), text, font=font, fill=0)

        # 二值化
        arr = np.array(img, dtype=np.uint8)
        binary = arr < 200

        if not binary.any():
            logger.warning("文字渲染后无有效像素")
            return path

    except Exception as e:
        logger.error(f"文字渲染失败: {e}")
        return path

    # 骨架化
    try:
        from skimage.morphology import skeletonize
        skel = skeletonize(binary)
    except ImportError:
        logger.warning("scikit-image 未安装，使用简单形态学细化")
        skel = _thin_simple(binary)

    if not skel.any():
        logger.warning("骨架提取结果为空")
        return path

    # 追踪骨架
    pixel_paths = _trace_skeleton(skel)

    if not pixel_paths:
        logger.warning("未能从骨架中追踪到路径")
        return path

    logger.info(f"骨架提取到 {len(pixel_paths)} 段路径")

    # 将像素路径转换为坐标（原点在左下角，Y 向上）
    for px_path in pixel_paths:
        if len(px_path) < 2:
            continue

        # 像素 → 坐标，Y 翻转（图像 Y 向下 → 数学 Y 向上）
        pts = []
        for px, py in px_path:
            x = px - img_w / 2.0
            y = -(py - img_h / 2.0)
            pts.append((x, y))

        # 重采样
        pts = _resample_path(pts, max(20, len(pts)))
        if len(pts) >= 2:
            path.add_stroke(Stroke(pts))

    return path


def _thin_simple(binary, iterations: int = 15) -> 'np.ndarray':
    """简单的迭代形态学细化（scikit-image 不可用时的降级方案）"""
    import numpy as np
    from scipy.ndimage import binary_erosion, generate_binary_structure

    if binary.dtype != bool:
        binary = binary > 0

    s = generate_binary_structure(2, 1)  # 4 邻域
    result = binary.copy()

    for _ in range(iterations):
        eroded = binary_erosion(result, structure=s)
        diff = result & ~eroded
        if not diff.any():
            break
        result = eroded

    return result


# ---------------------------------------------------------------------------
# 将路径转换为命令序列
# ---------------------------------------------------------------------------

def path_to_commands(path: WritingPath, pen_down_speed: int = 8,
                     pen_up_speed: int = 20) -> List[Tuple[str, list]]:
    """将 WritingPath 转换为命令序列

    Args:
        path: 书写路径
        pen_down_speed: 落笔书写速度 (mm/s)
        pen_up_speed: 抬笔移动速度 (mm/s)

    Returns:
        命令列表，每个元素为 (命令名, [参数...])
        例如: [("PEN_DOWN", []), ("MOVE_ABS", [x, y, speed]), ("PEN_UP", []), ...]
    """
    commands = []
    if path.is_empty:
        return commands

    for stroke in path.strokes:
        if len(stroke.points) < 2:
            continue

        # 移动到笔画起点（抬笔状态）
        x0, y0 = stroke.points[0]
        commands.append(("PEN_UP", []))
        commands.append(("MOVE_ABS", [x0, y0, pen_up_speed]))

        # 落笔
        commands.append(("PEN_DOWN", []))

        # 沿着笔画路径移动
        for i in range(1, len(stroke.points)):
            x, y = stroke.points[i]
            commands.append(("MOVE_ABS", [x, y, pen_down_speed]))

    # 最后抬笔
    commands.append(("PEN_UP", []))

    return commands


def path_to_gcode(path: WritingPath, pen_down_speed: int = 8,
                  pen_up_speed: int = 20) -> List[str]:
    """将 WritingPath 转换为 G-code 风格的字符串列表（调试用）

    返回格式：每行一个操作，如 "PEN_DOWN", "G00 X10 Y20 S20", ...
    """
    commands = path_to_commands(path, pen_down_speed, pen_up_speed)
    lines = []
    for cmd, args in commands:
        if cmd == "PEN_UP":
            lines.append("PEN_UP")
        elif cmd == "PEN_DOWN":
            lines.append("PEN_DOWN")
        elif cmd == "MOVE_ABS":
            lines.append(f"G00 X{args[0]:.3f} Y{args[1]:.3f} S{args[2]}")
    return lines
