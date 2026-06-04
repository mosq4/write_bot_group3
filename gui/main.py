"""
运行 XY 平台上位机的主入口
"""

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from gui import main

if __name__ == '__main__':
    main()
