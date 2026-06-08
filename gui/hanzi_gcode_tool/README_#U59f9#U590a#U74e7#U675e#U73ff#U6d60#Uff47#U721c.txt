汉字转 G-code 工具说明
====================

一、实现思路
-----------
参考 TextToGcode-1.3.0 的思路：把字符转成点/线段，再输出 G0/G1 指令。
区别是：TextToGcode 只支持 a-z、0-9；本工具使用本机中文字体的字形轮廓，所以可以支持汉字。

注意：本工具生成的是“轮廓字”，不是单线字/手写笔画骨架字。
用于绘图笔、激光、雕刻都可以；如果你要一笔一画的笔画字，需要单线字体或笔画库。

二、安装依赖
-----------
推荐 Python 3.8+

pip install matplotlib numpy

如果要运行界面版：

pip install PyQt5 matplotlib numpy

三、命令行使用
-------------
Windows 示例：

python hanzi_to_gcode.py --text "北航机电" --font "C:/Windows/Fonts/simhei.ttf" --output hanzi.nc --height 20 --feed 800 --preview

常用字体路径：
C:/Windows/Fonts/simhei.ttf     黑体
C:/Windows/Fonts/simsun.ttc     宋体
C:/Windows/Fonts/msyh.ttc       微软雅黑

四、界面版使用
-------------

python hanzi_gcode_gui.py

输入文字、选择字体、设置字高和速度，然后点击“生成 G-code”。

五、输出指令说明
---------------
默认输出：
G21：毫米单位
G90：绝对坐标
G0：快速移动
G1：绘制移动
Z_UP/Z_DOWN：抬笔/落笔

如果你的平台没有 Z 轴，而是用电磁铁/舵机/激光开关，可以加 --m3m5：

python hanzi_to_gcode.py --text "测试" --font "C:/Windows/Fonts/simhei.ttf" --output test.nc --m3m5 --pen-on "M3" --pen-off "M5"

六、给 STM32 平台使用时的建议
----------------------------
如果你的 STM32 下位机只识别 X/Y 直线运动，可以解析 G0/G1 的 X、Y 坐标。
遇到 Z 或 M3/M5 时可以理解为抬笔/落笔控制。

最少需要支持：
G0 X.. Y..  快速移动到起点
G1 X.. Y..  按插补直线移动
M3 或 Z_DOWN：落笔
M5 或 Z_UP：抬笔

七、文件列表
-----------
hanzi_to_gcode.py      命令行核心程序
hanzi_gcode_gui.py     简单图形界面
sample_北航机电.nc      示例 G-code
sample_北航机电.png     示例路径预览
