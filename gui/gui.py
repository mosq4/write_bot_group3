"""
PyQt5 图形界面主窗口 - 美化版本，带 XY 平台坐标图
"""

import sys
import math
import logging
from datetime import datetime
from typing import Optional
from collections import deque

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QStatusBar, QGroupBox, QTextEdit, QMessageBox, QCheckBox,
    QScrollArea, QSplitter, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as patches

from protocol import (
    CommandBuilder, ResponseParser, CommandType, PlatformStatus, ProtocolFrame
)
from usb_comm import USBCommunicator
from ai_instruction import generate_via_api, generate_via_api_multiline, build_prompt, AIResponse, write_request, read_response, clear_response
from deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

STATUS_QUERY_INTERVAL_MS = 50
PLOT_X_MIN = -10
PLOT_X_MAX = 300
PLOT_Y_MIN = -10
PLOT_Y_MAX = 300


class SignalEmitter(QObject):
    """信号发射器（用于线程安全的 UI 更新）"""
    status_updated = pyqtSignal(dict)  # 状态更新信号
    log_message = pyqtSignal(str)      # 日志消息信号
    error_occurred = pyqtSignal(str)   # 错误信号
    connected = pyqtSignal(bool)       # 连接状态信号


class XYPlotCanvas(FigureCanvas):
    """XY 平台实时坐标图"""
    
    def __init__(self, parent=None, width=6, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax.grid(True, linestyle='--', alpha=0.4)
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_title('XY Real-time Position')
        
        self._apply_plot_bounds()
        self.ax.set_aspect('equal', adjustable='box')
        
        self._draw_workspace()
        
        self.trajectory_x = deque(maxlen=500)
        self.trajectory_y = deque(maxlen=500)
        self.trajectory_line, = self.ax.plot([], [], 'o-', color='tab:blue', markersize=2, linewidth=1, alpha=0.7)
        
        self.current_point, = self.ax.plot([], [], 'o', color='tab:red', markersize=10, label='Current')
        
        self.target_point, = self.ax.plot([], [], 's', color='tab:green', markersize=8, label='Target', alpha=0.7)
        
        self.ax.legend(loc='upper right')
        
        self.fig.tight_layout()
        self.draw_idle()

    def _apply_plot_bounds(self):
        """统一固定 XY 位置图范围为 (-10, 300) * (-10, 300)。"""
        self.ax.set_xlim(PLOT_X_MIN, PLOT_X_MAX)
        self.ax.set_ylim(PLOT_Y_MIN, PLOT_Y_MAX)
    
    def _draw_workspace(self):
        """绘制工作区域"""
        # rect = patches.Rectangle(
        #     (PLOT_X_MIN, PLOT_Y_MIN),
        #     PLOT_X_MAX - PLOT_X_MIN,
        #     PLOT_Y_MAX - PLOT_Y_MIN,
        #     fill=False,
        #     edgecolor='black',
        #     linewidth=1.5,
        #     linestyle='--',
        #     alpha=0.7
        # )
        # self.ax.add_patch(rect)
        for spine in self.ax.spines.values():
            spine.set_visible(True)
            spine.set_color('black')
            spine.set_linewidth(1.2)
    
    def update_current_position(self, x: float, y: float):
        """更新当前位置"""
        self.current_point.set_data([x], [y])
        
        # 添加到轨迹
        if not self.trajectory_x or abs(x - self.trajectory_x[-1]) > 0.1 or abs(y - self.trajectory_y[-1]) > 0.1:
            self.trajectory_x.append(x)
            self.trajectory_y.append(y)
            self.trajectory_line.set_data(list(self.trajectory_x), list(self.trajectory_y))
        
        self._apply_plot_bounds()
        self.draw_idle()
    
    def set_target_position(self, x: float, y: float):
        """更新目标位置"""
        self.target_point.set_data([x], [y])
        self._apply_plot_bounds()
        self.draw_idle()
    
    def clear_trajectory(self):
        """清除轨迹"""
        self.trajectory_x.clear()
        self.trajectory_y.clear()
        self.trajectory_line.set_data([], [])
        self._apply_plot_bounds()
        self.draw_idle()


class XYPlatformController:
    """XY 平台控制器"""
    
    def __init__(self, communicator: USBCommunicator, signal_emitter: SignalEmitter):
        self.comm = communicator
        self.signal = signal_emitter
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_status = PlatformStatus.IDLE
        self.error_code = 0
    
    def send_command(self, cmd_bytes: bytes, cmd_name: str = ""):
        """发送命令"""
        if not self.comm.is_connected():
            self.signal.error_occurred.emit("未连接到设备")
            return False
        
        success = self.comm.send_data(cmd_bytes)
        if success:
            self.signal.log_message.emit(f"✓ {cmd_name}")
        else:
            self.signal.error_occurred.emit(f"✗ 发送失败: {cmd_name}")
        
        return success
    
    def home(self):
        """回零"""
        return self.send_command(CommandBuilder.home(), "回零")
    
    def move_abs(self, x: float, y: float, speed: int):
        """绝对位移"""
        return self.send_command(
            CommandBuilder.move_abs(x, y, speed),
            f"移动到 ({x:.1f}, {y:.1f})"
        )
    
    def move_rel(self, dx: float, dy: float, speed: int):
        """相对位移"""
        return self.send_command(
            CommandBuilder.move_rel(dx, dy, speed),
            f"相对移动 Δ({dx:.1f}, {dy:.1f})"
        )
    
    def line_interp(self, x1: float, y1: float, x2: float, y2: float, speed: int):
        """直线插补"""
        return self.send_command(
            CommandBuilder.line_interp(x1, y1, x2, y2, speed),
            f"直线: ({x1:.1f}, {y1:.1f}) → ({x2:.1f}, {y2:.1f})"
        )
    
    def arc_interp(
        self,
        xc: float,
        yc: float,
        radius: float,
        angle_start: float,
        angle_end: float,
        clockwise: bool,
        speed: int
    ):
        """圆弧插补"""
        direction_text = "顺时针" if clockwise else "逆时针"
        return self.send_command(
            CommandBuilder.arc_interp(xc, yc, radius, angle_start, angle_end, clockwise, speed),
            (
                f"圆弧: 圆心({xc:.1f}, {yc:.1f}) 半径{radius:.1f}mm "
                f"起始角{angle_start:.1f}° 终止角{angle_end:.1f}° {direction_text}"
            )
        )
    
    def stop(self):
        """停止"""
        return self.send_command(CommandBuilder.stop(), "紧急停止")
    
    def pen_down(self):
        """落笔"""
        return self.send_command(CommandBuilder.pen_down(), "落笔")
    
    def pen_up(self):
        """抬笔"""
        return self.send_command(CommandBuilder.pen_up(), "抬笔")
    
    def servo(self, servo_id: int, angle: float):
        """舵机控制"""
        return self.send_command(
            CommandBuilder.servo(servo_id, angle),
            f"舵机{servo_id} → {angle:.1f}°"
        )
    
    def query_status(self):
        """查询状态"""
        return self.send_command(CommandBuilder.query_status(), "查询状态")
    
    def handle_response(self, frame_data: bytes):
        """处理响应数据"""
        try:
            cmd, data = ProtocolFrame.unpack(frame_data)
            
            if cmd == CommandType.STATUS_RESPONSE:
                status_info = ResponseParser.parse_status(data)
                self.current_x = status_info['x']
                self.current_y = status_info['y']
                self.current_status = status_info['status']
                self.error_code = status_info['error']
                
                self.signal.status_updated.emit(status_info)
        
        except Exception as e:
            self.signal.error_occurred.emit(f"解析响应出错: {e}")


class MainWindow(QMainWindow):
    """主窗口 - 现代化设计"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XY 平台运动控制系统 v2.0")
        self.setGeometry(50, 50, 1600, 900)
        
        # 应用现代化主题
        self.apply_theme()
        
        # 信号发射器
        self.signal_emitter = SignalEmitter()
        
        # USB 通信
        self.comm = USBCommunicator(baudrate=115200)
        self.comm.set_data_callback(self.on_usb_data_received)
        
        # 平台控制器
        self.controller = XYPlatformController(self.comm, self.signal_emitter)
        
        # 连接信号
        self.signal_emitter.status_updated.connect(self.on_status_updated)
        self.signal_emitter.log_message.connect(self.on_log_message)
        self.signal_emitter.error_occurred.connect(self.on_error)
        self.signal_emitter.connected.connect(self.on_connected)
        
        # 定时器：定期查询状态
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.on_query_status)
        
        # AI 汉字书写：指令队列和定时器
        self.ai_queue = deque()
        self.ai_timer = QTimer()
        self.ai_timer.timeout.connect(self._on_ai_tick)
        self.api_key = ""

        # 工作区边界（mm），回零后由限位开关确定物理范围
        self.workspace_x_max = 300.0
        self.workspace_y_max = 300.0

        # 边界检测状态机
        self._boundary_timer = QTimer()
        self._boundary_timer.timeout.connect(self._boundary_detect_tick)
        self._boundary_step = -1  # -1=空闲, 0~5=检测步骤
        
        # 初始化 UI
        self.init_ui()
        
        # 日志
        self.setup_logging()
    
    def apply_theme(self):
        """应用简洁样式（不做颜色美化）"""
        stylesheet = """
        QGroupBox {
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        
        QPushButton {
            padding: 6px 10px;
        }
        
        QPushButton:hover {
            border: 1px solid #808080;
        }
        
        QPushButton:pressed {
            border: 1px solid #606060;
        }
        
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            border: 1px solid #a0a0a0;
            border-radius: 4px;
            padding: 4px;
        }
        
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border: 1px solid #606060;
        }
        
        QTextEdit {
            border: 1px solid #a0a0a0;
            border-radius: 4px;
            font-family: 'Courier New';
            font-size: 10px;
        }
        """
        self.setStyleSheet(stylesheet)
    
    def setup_logging(self):
        """配置日志"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def init_ui(self):
        """初始化 UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout()
        
        # 左侧：控制面板
        left_widget = self.create_control_panel()
        
        # 右侧：图表和日志
        right_widget = self.create_plot_and_log_panel()
        
        # 使用分割器实现可调整的布局
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
        
        # 状态栏
        self.statusBar().showMessage("✓ 就绪")
    
    def create_control_panel(self) -> QWidget:
        """创建控制面板"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 连接控制
        conn_group = self.create_connection_group()
        layout.addWidget(conn_group)
        
        # 状态显示
        status_group = self.create_status_group()
        layout.addWidget(status_group)
        
        # 基础控制
        basic_group = self.create_basic_control_group()
        layout.addWidget(basic_group)
        
        # 运动控制（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        motion_widget = QWidget()
        motion_layout = QVBoxLayout()
        
        motion_layout.addWidget(self.create_positioning_group())
        motion_layout.addWidget(self.create_line_interp_group())
        motion_layout.addWidget(self.create_arc_interp_group())
        motion_layout.addWidget(self.create_ai_panel())
        motion_layout.addStretch()
        
        motion_widget.setLayout(motion_layout)
        scroll.setWidget(motion_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_connection_group(self) -> QGroupBox:
        """连接控制组"""
        group = QGroupBox("连接")
        layout = QGridLayout()
        
        layout.addWidget(QLabel("选择端口:"), 0, 0)
        self.port_combo = QComboBox()
        layout.addWidget(self.port_combo, 0, 1)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.on_refresh_ports)
        refresh_btn.setMaximumWidth(80)
        layout.addWidget(refresh_btn, 0, 2)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.on_connect_toggle)
        layout.addWidget(self.connect_btn, 1, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def create_status_group(self) -> QGroupBox:
        """状态显示组"""
        group = QGroupBox("状态")
        layout = QGridLayout()
        
        # 连接状态
        layout.addWidget(QLabel("连接:"), 0, 0)
        self.status_indicator = QLabel("●")
        self.status_indicator.setFont(QFont("Arial", 20))
        layout.addWidget(self.status_indicator, 0, 1)
        
        self.connection_status_label = QLabel("离线")
        layout.addWidget(self.connection_status_label, 0, 2)
        
        # X 坐标
        layout.addWidget(QLabel("X (mm):"), 1, 0)
        self.x_display = QLabel("0.00")
        self.x_display.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.x_display, 1, 1, 1, 2)
        
        # Y 坐标
        layout.addWidget(QLabel("Y (mm):"), 2, 0)
        self.y_display = QLabel("0.00")
        self.y_display.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(self.y_display, 2, 1, 1, 2)
        
        # 运动状态
        layout.addWidget(QLabel("状态:"), 3, 0)
        self.platform_status_display = QLabel("IDLE")
        self.platform_status_display.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.platform_status_display, 3, 1, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def create_basic_control_group(self) -> QGroupBox:
        """基础控制组"""
        group = QGroupBox("基础控制")
        layout = QVBoxLayout()
        
        home_btn = QPushButton("回零")
        home_btn.setMinimumHeight(40)
        home_btn.setFont(QFont("Arial", 11, QFont.Bold))
        home_btn.clicked.connect(self.controller.home)
        layout.addWidget(home_btn)
        
        stop_btn = QPushButton("紧急停止")
        stop_btn.setMinimumHeight(40)
        stop_btn.setFont(QFont("Arial", 11, QFont.Bold))
        stop_btn.clicked.connect(self.controller.stop)
        layout.addWidget(stop_btn)
        
        group.setLayout(layout)
        return group
    
    def create_positioning_group(self) -> QGroupBox:
        """绝对/相对位移控制组"""
        group = QGroupBox("位移控制")
        layout = QGridLayout()
        
        # 绝对位移
        layout.addWidget(QLabel("绝对位移"), 0, 0, 1, 4)
        layout.addWidget(QLabel("X (mm):"), 1, 0)
        layout.addWidget(QLabel("Y (mm):"), 1, 2)
        
        self.abs_x_input = QDoubleSpinBox()
        self.abs_x_input.setRange(-500, 500)
        self.abs_x_input.setValue(0)
        layout.addWidget(self.abs_x_input, 2, 0, 1, 2)
        
        self.abs_y_input = QDoubleSpinBox()
        self.abs_y_input.setRange(-500, 500)
        self.abs_y_input.setValue(0)
        layout.addWidget(self.abs_y_input, 2, 2, 1, 2)
        
        layout.addWidget(QLabel("速度:"), 3, 0)
        self.abs_speed_input = QSpinBox()
        self.abs_speed_input.setRange(0, 50)
        self.abs_speed_input.setValue(10)
        layout.addWidget(self.abs_speed_input, 3, 1, 1, 3)
        
        move_abs_btn = QPushButton("移动到点")
        move_abs_btn.clicked.connect(self.on_move_abs)
        layout.addWidget(move_abs_btn, 4, 0, 1, 4)
        
        # 相对位移
        layout.addWidget(QLabel("相对位移"), 5, 0, 1, 4)
        layout.addWidget(QLabel("ΔX (mm):"), 6, 0)
        layout.addWidget(QLabel("ΔY (mm):"), 6, 2)
        
        self.rel_x_input = QDoubleSpinBox()
        self.rel_x_input.setRange(-500, 500)
        layout.addWidget(self.rel_x_input, 7, 0, 1, 2)
        
        self.rel_y_input = QDoubleSpinBox()
        self.rel_y_input.setRange(-500, 500)
        layout.addWidget(self.rel_y_input, 7, 2, 1, 2)
        
        layout.addWidget(QLabel("速度:"), 8, 0)
        self.rel_speed_input = QSpinBox()
        self.rel_speed_input.setRange(0, 50)
        self.rel_speed_input.setValue(10)
        layout.addWidget(self.rel_speed_input, 8, 1, 1, 3)
        
        move_rel_btn = QPushButton("相对移动")
        move_rel_btn.clicked.connect(self.on_move_rel)
        layout.addWidget(move_rel_btn, 9, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def create_line_interp_group(self) -> QGroupBox:
        """直线插补控制组"""
        group = QGroupBox("直线插补")
        layout = QGridLayout()
        
        layout.addWidget(QLabel("起点 X:"), 0, 0)
        self.line_x1_input = QDoubleSpinBox()
        self.line_x1_input.setRange(-500, 500)
        layout.addWidget(self.line_x1_input, 0, 1)
        
        layout.addWidget(QLabel("终点 X:"), 0, 2)
        self.line_x2_input = QDoubleSpinBox()
        self.line_x2_input.setRange(-500, 500)
        layout.addWidget(self.line_x2_input, 0, 3)
        
        layout.addWidget(QLabel("起点 Y:"), 1, 0)
        self.line_y1_input = QDoubleSpinBox()
        self.line_y1_input.setRange(-500, 500)
        layout.addWidget(self.line_y1_input, 1, 1)
        
        layout.addWidget(QLabel("终点 Y:"), 1, 2)
        self.line_y2_input = QDoubleSpinBox()
        self.line_y2_input.setRange(-500, 500)
        layout.addWidget(self.line_y2_input, 1, 3)
        
        layout.addWidget(QLabel("速度:"), 2, 0)
        self.line_speed_input = QSpinBox()
        self.line_speed_input.setRange(0, 50)
        self.line_speed_input.setValue(10)
        layout.addWidget(self.line_speed_input, 2, 1, 1, 3)
        
        line_btn = QPushButton("执行直线插补")
        line_btn.clicked.connect(self.on_line_interp)
        layout.addWidget(line_btn, 3, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def create_arc_interp_group(self) -> QGroupBox:
        """圆弧插补控制组"""
        group = QGroupBox("圆弧插补")
        layout = QGridLayout()
        
        layout.addWidget(QLabel("圆心 X:"), 0, 0)
        self.arc_xc_input = QDoubleSpinBox()
        self.arc_xc_input.setRange(-500, 500)
        layout.addWidget(self.arc_xc_input, 0, 1)
        
        layout.addWidget(QLabel("圆心 Y:"), 0, 2)
        self.arc_yc_input = QDoubleSpinBox()
        self.arc_yc_input.setRange(-500, 500)
        layout.addWidget(self.arc_yc_input, 0, 3)
        
        layout.addWidget(QLabel("半径:"), 1, 0)
        self.arc_radius_input = QDoubleSpinBox()
        self.arc_radius_input.setRange(0, 500)
        self.arc_radius_input.setValue(10)
        layout.addWidget(self.arc_radius_input, 1, 1)
        
        layout.addWidget(QLabel("起始角 (°):"), 1, 2)
        self.arc_start_angle_input = QDoubleSpinBox()
        self.arc_start_angle_input.setDecimals(1)
        self.arc_start_angle_input.setRange(-360, 360)
        self.arc_start_angle_input.setSingleStep(1.0)
        self.arc_start_angle_input.setValue(0)
        layout.addWidget(self.arc_start_angle_input, 1, 3)
        
        layout.addWidget(QLabel("终止角 (°):"), 2, 0)
        self.arc_end_angle_input = QDoubleSpinBox()
        self.arc_end_angle_input.setDecimals(1)
        self.arc_end_angle_input.setRange(-360, 360)
        self.arc_end_angle_input.setSingleStep(1.0)
        self.arc_end_angle_input.setValue(90)
        layout.addWidget(self.arc_end_angle_input, 2, 1)

        layout.addWidget(QLabel("方向:"), 2, 2)
        self.arc_direction_combo = QComboBox()
        self.arc_direction_combo.addItem("逆时针", False)
        self.arc_direction_combo.addItem("顺时针", True)
        layout.addWidget(self.arc_direction_combo, 2, 3)

        layout.addWidget(QLabel("速度:"), 3, 0)
        self.arc_speed_input = QSpinBox()
        self.arc_speed_input.setRange(0, 50)
        self.arc_speed_input.setValue(10)
        layout.addWidget(self.arc_speed_input, 3, 1, 1, 3)
        
        arc_btn = QPushButton("执行圆弧插补")
        arc_btn.clicked.connect(self.on_arc_interp)
        layout.addWidget(arc_btn, 4, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def create_plot_and_log_panel(self) -> QWidget:
        """创建图表和日志面板"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 坐标图
        plot_group = QGroupBox("XY 平台位置")
        plot_layout = QVBoxLayout()
        
        self.canvas = XYPlotCanvas(self, width=8, height=5, dpi=100)
        plot_layout.addWidget(self.canvas)
        
        # 清除轨迹按钮
        clear_btn = QPushButton("清除轨迹")
        clear_btn.clicked.connect(lambda: self.canvas.clear_trajectory())
        plot_layout.addWidget(clear_btn)
        
        plot_group.setLayout(plot_layout)
        layout.addWidget(plot_group, 2)
        
        # 日志面板
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        query_btn = QPushButton("查询状态")
        query_btn.clicked.connect(self.on_query_status)
        button_layout.addWidget(query_btn)
        
        self.auto_query_check = QCheckBox("自动查询 (0.05s)")
        self.auto_query_check.toggled.connect(self.on_auto_query_toggled)
        button_layout.addWidget(self.auto_query_check)
        
        button_layout.addStretch()
        log_layout.addLayout(button_layout)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group, 1)
        
        widget.setLayout(layout)
        return widget
    
    # ===== 事件处理 =====
    
    def on_refresh_ports(self):
        """刷新端口列表"""
        self.port_combo.clear()
        ports = self.comm.list_ports()
        
        if not ports:
            self.port_combo.addItem("-- 无可用端口 --")
        else:
            for port_info in ports:
                self.port_combo.addItem(
                    f"{port_info['port']} ({port_info['description']})",
                    port_info['port']
                )
        
        self.on_log_message(f"扫描到 {len(ports)} 个端口")
    
    def on_connect_toggle(self):
        """连接/断开切换"""
        if self.comm.is_connected():
            self.comm.disconnect()
            self.connect_btn.setText("连接")
            self.signal_emitter.connected.emit(False)
            self.status_timer.stop()
        else:
            port = self.port_combo.currentData()
            if port is None:
                QMessageBox.warning(self, "警告", "请先选择端口")
                return
            
            success = self.comm.connect(port)
            if success:
                self.connect_btn.setText("断开")
                self.signal_emitter.connected.emit(True)
                self.on_log_message(f"✓ 已连接到 {port}")
                
                # 查询一次初始状态
                self.controller.query_status()
                
                # 启动自动查询（如果勾选）
                if self.auto_query_check.isChecked():
                    self.status_timer.start(STATUS_QUERY_INTERVAL_MS)
            else:
                QMessageBox.critical(self, "错误", "连接失败")
    
    def on_usb_data_received(self, data: bytes):
        """USB 数据接收回调"""
        self.controller.handle_response(data)
    
    def on_status_updated(self, status_info: dict):
        """状态更新"""
        self.x_display.setText(f"{status_info['x']:.2f}")
        self.y_display.setText(f"{status_info['y']:.2f}")
        
        # 更新图表
        self.canvas.update_current_position(status_info['x'], status_info['y'])
        
        status = status_info['status']
        status_text = {
            PlatformStatus.IDLE: "空闲",
            PlatformStatus.HOMING: "回零中",
            PlatformStatus.INTERPING: "插补中",
            PlatformStatus.ERROR: "错误",
            PlatformStatus.MANUAL: "直接运动"
        }.get(status, "未知")
        
        self.platform_status_display.setText(status_text)
        
        # 更新指示灯
        if status == PlatformStatus.IDLE:
            self.status_indicator.setText("●")
        elif status == PlatformStatus.INTERPING or status == PlatformStatus.HOMING or status == PlatformStatus.MANUAL:
            self.status_indicator.setText("◐")
        else:
            self.status_indicator.setText("■")
    
    def on_log_message(self, msg: str):
        """日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def on_error(self, error_msg: str):
        """错误处理"""
        self.on_log_message(f"❌ {error_msg}")
    
    def on_connected(self, connected: bool):
        """连接状态变化"""
        if connected:
            self.status_indicator.setText("●")
            self.connection_status_label.setText("已连接")
        else:
            self.status_indicator.setText("■")
            self.connection_status_label.setText("离线")
    
    def on_move_abs(self):
        """执行绝对位移"""
        x = self.abs_x_input.value()
        y = self.abs_y_input.value()
        speed = self.abs_speed_input.value()
        self.canvas.set_target_position(x, y)
        self.controller.move_abs(x, y, speed)
    
    def on_move_rel(self):
        """执行相对位移"""
        dx = self.rel_x_input.value()
        dy = self.rel_y_input.value()
        speed = self.rel_speed_input.value()
        self.controller.move_rel(dx, dy, speed)
    
    def on_line_interp(self):
        """执行直线插补"""
        x1 = self.line_x1_input.value()
        y1 = self.line_y1_input.value()
        x2 = self.line_x2_input.value()
        y2 = self.line_y2_input.value()
        speed = self.line_speed_input.value()
        self.canvas.set_target_position(x2, y2)
        self.controller.line_interp(x1, y1, x2, y2, speed)
    
    def on_arc_interp(self):
        """执行圆弧插补"""
        xc = self.arc_xc_input.value()
        yc = self.arc_yc_input.value()
        radius = self.arc_radius_input.value()
        angle_start = self.arc_start_angle_input.value()
        angle_end = self.arc_end_angle_input.value()
        clockwise = bool(self.arc_direction_combo.currentData())
        speed = self.arc_speed_input.value()
        self.canvas.set_target_position(xc + radius * math.cos(math.radians(angle_end)), yc + radius * math.sin(math.radians(angle_end)))
        self.controller.arc_interp(xc, yc, radius, angle_start, angle_end, clockwise, speed)
    
    def on_query_status(self):
        """查询状态"""
        self.controller.query_status()
    
    def on_auto_query_toggled(self, checked: bool):
        """自动查询勾选"""
        if checked and self.comm.is_connected():
            self.status_timer.start(STATUS_QUERY_INTERVAL_MS)
        else:
            self.status_timer.stop()
    
    # ===== AI 汉字书写面板 =====
    
    def create_ai_panel(self) -> QGroupBox:
        """创建 AI 汉字书写面板"""
        group = QGroupBox("AI 汉字书写")
        layout = QGridLayout()
        
        # 输入汉字
        layout.addWidget(QLabel("输入汉字:"), 0, 0)
        self.char_input = QLineEdit()
        self.char_input.setPlaceholderText("请输入要书写的汉字...")
        layout.addWidget(self.char_input, 0, 1, 1, 3)
        
        # API Key
        layout.addWidget(QLabel("API Key:"), 1, 0)
        self.apikey_input = QLineEdit()
        self.apikey_input.setPlaceholderText("sk-... (留空则从环境变量/apikey.txt读取)")
        self.apikey_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.apikey_input, 1, 1, 1, 3)
        
        # 字体大小
        layout.addWidget(QLabel("字号(mm):"), 2, 0)
        self.font_size_input = QDoubleSpinBox()
        self.font_size_input.setRange(5, 200)
        self.font_size_input.setValue(20)
        layout.addWidget(self.font_size_input, 2, 1)
        
        # 书写速度
        layout.addWidget(QLabel("速度:"), 2, 2)
        self.ai_speed_input = QSpinBox()
        self.ai_speed_input.setRange(1, 50)
        self.ai_speed_input.setValue(3)
        layout.addWidget(self.ai_speed_input, 2, 3)
        
        # 起点坐标
        layout.addWidget(QLabel("起点X:"), 3, 0)
        self.ai_origin_x = QDoubleSpinBox()
        self.ai_origin_x.setRange(0, 500)
        self.ai_origin_x.setValue(50)
        layout.addWidget(self.ai_origin_x, 3, 1)
        
        layout.addWidget(QLabel("起点Y:"), 3, 2)
        self.ai_origin_y = QDoubleSpinBox()
        self.ai_origin_y.setRange(0, 500)
        self.ai_origin_y.setValue(100)
        layout.addWidget(self.ai_origin_y, 3, 3)
        
        # 字间距
        layout.addWidget(QLabel("字间距:"), 4, 0)
        self.ai_spacing = QDoubleSpinBox()
        self.ai_spacing.setRange(0, 50)
        self.ai_spacing.setValue(5)
        layout.addWidget(self.ai_spacing, 4, 1)

        # 行间距
        layout.addWidget(QLabel("行间距:"), 4, 2)
        self.line_spacing_input = QDoubleSpinBox()
        self.line_spacing_input.setRange(0, 50)
        self.line_spacing_input.setValue(5)
        layout.addWidget(self.line_spacing_input, 4, 3)

        # 工作区边界
        layout.addWidget(QLabel("X最大:"), 5, 0)
        self.workspace_x_input = QDoubleSpinBox()
        self.workspace_x_input.setRange(10, 500)
        self.workspace_x_input.setValue(self.workspace_x_max)
        layout.addWidget(self.workspace_x_input, 5, 1)

        layout.addWidget(QLabel("Y最大:"), 5, 2)
        self.workspace_y_input = QDoubleSpinBox()
        self.workspace_y_input.setRange(10, 500)
        self.workspace_y_input.setValue(self.workspace_y_max)
        layout.addWidget(self.workspace_y_input, 5, 3)

        # 边界检测按钮 + 自动换行
        detect_btn = QPushButton("检测边界")
        detect_btn.clicked.connect(self.on_detect_boundary)
        layout.addWidget(detect_btn, 6, 0, 1, 2)

        self.auto_wrap_check = QCheckBox("自动换行")
        self.auto_wrap_check.setChecked(True)
        layout.addWidget(self.auto_wrap_check, 6, 2, 1, 2)
        
        # 状态标签
        self.ai_status_label = QLabel("就绪")
        self.ai_status_label.setFont(QFont("Arial", 9))
        layout.addWidget(self.ai_status_label, 7, 0, 1, 4)
        
        # 生成并执行按钮
        gen_btn = QPushButton("生成并执行")
        gen_btn.setMinimumHeight(32)
        gen_btn.setFont(QFont("Arial", 10, QFont.Bold))
        gen_btn.clicked.connect(self.on_ai_generate_and_execute)
        layout.addWidget(gen_btn, 8, 0, 1, 2)
        
        # 停止按钮
        stop_btn = QPushButton("停止书写")
        stop_btn.clicked.connect(self.on_ai_stop)
        layout.addWidget(stop_btn, 8, 2, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def on_ai_generate_and_execute(self):
        """调用 AI 生成指令并开始执行（支持自动换行）"""
        text = self.char_input.text().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请输入要书写的汉字")
            return

        if not self.comm.is_connected():
            QMessageBox.warning(self, "警告", "请先连接到设备")
            return

        api_key = self.apikey_input.text().strip()
        if not api_key:
            import os
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                try:
                    key_path = os.path.join(os.path.dirname(__file__), "apikey.txt")
                    if os.path.exists(key_path):
                        with open(key_path, "r") as f:
                            api_key = f.readline().strip()
                except Exception:
                    pass
        if not api_key:
            QMessageBox.warning(self, "警告", "请配置 DeepSeek API Key")
            return

        self.api_key = api_key

        font_size = self.font_size_input.value()
        origin_x = self.ai_origin_x.value()
        origin_y = self.ai_origin_y.value()
        spacing = self.ai_spacing.value()
        line_spacing = self.line_spacing_input.value()
        speed = self.ai_speed_input.value()

        # 同步工作区边界
        self.workspace_x_max = self.workspace_x_input.value()
        self.workspace_y_max = self.workspace_y_input.value()

        use_wrap = self.auto_wrap_check.isChecked()
        if use_wrap:
            lines = self._wrap_text_lines(text, origin_x, origin_y,
                                          font_size, spacing, line_spacing,
                                          self.workspace_x_max)
            if len(lines) > 1:
                self.signal_emitter.log_message.emit(
                    f"自动换行: {len(text)}字 → {len(lines)}行"
                )
            # 检查 Y 方向是否溢出工作区
            last_line_y = origin_y + (len(lines) - 1) * (font_size + line_spacing)
            if last_line_y + font_size > self.workspace_y_max:
                self.signal_emitter.log_message.emit(
                    f"⚠ 警告: 文字可能超出 Y 边界 (最后一行 Y={last_line_y:.0f}, "
                    f"最大Y={self.workspace_y_max:.0f})"
                )
            self.ai_status_label.setText(f"正在生成「{text}」的书写指令({len(lines)}行)...")
            self.signal_emitter.log_message.emit(
                f"AI: 正在生成「{text}」的书写指令({len(lines)}行)..."
            )
            try:
                resp = generate_via_api_multiline(
                    lines, api_key,
                    font_size=font_size, spacing=spacing,
                    pen_up=15.0, pen_down=90.0, speed=speed,
                    workspace_x=self.workspace_x_max
                )
            except Exception as e:
                self.ai_status_label.setText("API调用失败")
                self.signal_emitter.error_occurred.emit(f"AI API 调用失败: {e}")
                return
        else:
            self.ai_status_label.setText(f"正在生成「{text}」的书写指令...")
            self.signal_emitter.log_message.emit(f"AI: 正在生成「{text}」的书写指令...")
            try:
                resp = generate_via_api(
                    text, api_key,
                    font_size=font_size,
                    origin_x=origin_x,
                    origin_y=origin_y,
                    spacing=spacing,
                    speed=speed
                )
            except Exception as e:
                self.ai_status_label.setText("API调用失败")
                self.signal_emitter.error_occurred.emit(f"AI API 调用失败: {e}")
                return

        if not resp or not resp.instructions:
            self.ai_status_label.setText("AI 未返回有效指令")
            self.signal_emitter.error_occurred.emit("AI 未返回有效指令")
            return

        self.ai_queue.clear()
        for item in resp.instructions:
            self.ai_queue.append(item)

        count = len(self.ai_queue)
        pen_up_count = sum(1 for it in resp.instructions if it.get("action") == "pen_up")
        pen_down_count = sum(1 for it in resp.instructions if it.get("action") == "pen_down")
        move_count = sum(1 for it in resp.instructions if it.get("action") in ("move_abs", "move_rel"))
        line_count = sum(1 for it in resp.instructions if it.get("action") == "line_interp")
        self.signal_emitter.log_message.emit(
            f"AI: 生成 {count} 条指令 (pen_up={pen_up_count} pen_down={pen_down_count} "
            f"move={move_count} line={line_count})，开始执行"
        )

        # 写 AI 调试日志
        import json
        try:
            import os as _os
            debug_path = _os.path.join(_os.path.dirname(__file__), "ai_debug.log")
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(f"# AI 响应调试日志\n")
                f.write(f"# 原文: {text}\n")
                f.write(f"# 指令总数: {count}\n")
                f.write(f"# pen_up={pen_up_count} pen_down={pen_down_count} move={move_count} line={line_count}\n")
                f.write(f"# --- 完整指令列表 ---\n")
                for i, item in enumerate(resp.instructions):
                    f.write(f"[{i:03d}] {json.dumps(item, ensure_ascii=False)}\n")
        except Exception:
            pass

        self.ai_status_label.setText(f"共 {count} 条指令，开始执行...")
        self.ai_timer.start(200)
    
    def on_ai_stop(self):
        """停止 AI 书写"""
        self.ai_timer.stop()
        self.ai_queue.clear()
        self.ai_status_label.setText("已停止")
        self.controller.stop()
        self.controller.pen_up()
        self.signal_emitter.log_message.emit("AI: 书写已停止")

    # ===== 工作区边界检测 =====

    def on_detect_boundary(self):
        """启动边界检测：依次检测 X/Y 远端限位"""
        if not self.comm.is_connected():
            QMessageBox.warning(self, "警告", "请先连接到设备")
            return

        if self._boundary_step >= 0:
            return

        # 确保自动查询开启，否则状态机无法感知限位触发
        self._auto_query_was_on = self.auto_query_check.isChecked()
        if not self._auto_query_was_on:
            self.auto_query_check.setChecked(True)
            self.status_timer.start(STATUS_QUERY_INTERVAL_MS)
            self.signal_emitter.log_message.emit("边界检测: 已自动开启状态轮询")

        self._boundary_step = 0
        self._last_known_y = self.controller.current_y
        self._last_known_x = self.controller.current_x
        self.signal_emitter.log_message.emit("边界检测: 正在向 X 远端移动...")
        self.ai_status_label.setText("检测 X 边界...")
        self.controller.move_abs(500.0, self.controller.current_y, 30)
        self._boundary_timer.start(500)

    def _boundary_detect_tick(self):
        """边界检测状态机，由定时器驱动"""
        status = self.controller.current_status

        if self._boundary_step == 0:
            if status == PlatformStatus.ERROR:
                self._ws_x_max = self.controller.current_x
                self.signal_emitter.log_message.emit(
                    f"边界检测: X 远端 = {self._ws_x_max:.1f} mm"
                )
                self.controller.stop()
                self._boundary_step = 1
                self.controller.move_abs(10.0, self.controller.current_y, 30)
            elif status == PlatformStatus.IDLE:
                # 正常走完了500mm（没碰到限位）—— 以当前位置为界
                self._ws_x_max = self.controller.current_x
                self.signal_emitter.log_message.emit(
                    f"边界检测: X 远端(无阻挡) = {self._ws_x_max:.1f} mm"
                )
                self._boundary_step = 2

        elif self._boundary_step == 1:
            if status == PlatformStatus.IDLE:
                self._boundary_step = 2

        elif self._boundary_step == 2:
            self.ai_status_label.setText("检测 Y 边界...")
            self.signal_emitter.log_message.emit("边界检测: 正在向 Y 远端移动...")
            self.controller.move_abs(self.controller.current_x, 500.0, 30)
            self._boundary_step = 3

        elif self._boundary_step == 3:
            if status == PlatformStatus.ERROR:
                self._ws_y_max = self.controller.current_y
                self.signal_emitter.log_message.emit(
                    f"边界检测: Y 远端 = {self._ws_y_max:.1f} mm"
                )
                self.controller.stop()
                self._boundary_step = 4
                self.controller.move_abs(self.controller.current_x, 10.0, 30)
            elif status == PlatformStatus.IDLE:
                self._ws_y_max = self.controller.current_y
                self.signal_emitter.log_message.emit(
                    f"边界检测: Y 远端(无阻挡) = {self._ws_y_max:.1f} mm"
                )
                self._boundary_step = 5

        elif self._boundary_step == 4:
            if status == PlatformStatus.IDLE:
                self._boundary_step = 5

        elif self._boundary_step == 5:
            self._boundary_timer.stop()
            self._boundary_step = -1
            # 恢复自动查询状态
            if not self._auto_query_was_on:
                self.auto_query_check.setChecked(False)
                self.status_timer.stop()
            # 回填 UI
            self.workspace_x_input.setValue(self._ws_x_max)
            self.workspace_y_input.setValue(self._ws_y_max)
            self.workspace_x_max = self._ws_x_max
            self.workspace_y_max = self._ws_y_max
            self.ai_status_label.setText(
                f"边界: X={self._ws_x_max:.0f} Y={self._ws_y_max:.0f} mm"
            )
            self.signal_emitter.log_message.emit(
                f"边界检测完成: Xmax={self._ws_x_max:.1f} Ymax={self._ws_y_max:.1f}"
            )

    # ===== 自动换行辅助 =====

    @staticmethod
    def _wrap_text_lines(text: str, origin_x: float, origin_y: float,
                         font_size: float, spacing: float, line_spacing: float,
                         x_max: float) -> list:
        """将文本按工作区宽度拆分为多行，返回 [(line_text, x_start, y_start), ...]"""
        available_x = x_max - origin_x
        if available_x <= 0:
            available_x = font_size + spacing
        chars_per_line = max(1, int(available_x / (font_size + spacing)))
        lines = []
        for i in range(0, len(text), chars_per_line):
            line_text = text[i:i + chars_per_line]
            line_y = origin_y + len(lines) * (font_size + line_spacing)
            lines.append((line_text, origin_x, line_y))
        return lines
    
    def _on_ai_tick(self):
        """AI 指令队列定时执行"""
        if not self.ai_queue:
            self.ai_timer.stop()
            self.ai_status_label.setText("执行完成")
            self.signal_emitter.log_message.emit("AI: 所有指令执行完成")
            return
        
        item = self.ai_queue.popleft()
        action = item.get("action", "")
        
        try:
            if action == "pen_up":
                self.controller.pen_up()
            elif action == "pen_down":
                self.controller.pen_down()
            elif action == "servo":
                self.controller.servo(
                    item.get("id", 1),
                    float(item.get("angle", 90))
                )
            elif action == "move_abs":
                self.controller.move_abs(
                    float(item.get("x", 0)),
                    float(item.get("y", 0)),
                    int(item.get("speed", 5))
                )
            elif action == "move_rel":
                self.controller.move_rel(
                    float(item.get("dx", 0)),
                    float(item.get("dy", 0)),
                    int(item.get("speed", 5))
                )
            elif action == "line_interp":
                self.controller.line_interp(
                    float(item.get("x1", 0)),
                    float(item.get("y1", 0)),
                    float(item.get("x2", 0)),
                    float(item.get("y2", 0)),
                    int(item.get("speed", 3))
                )
            elif action == "arc_interp":
                self.controller.arc_interp(
                    float(item.get("xc", 0)),
                    float(item.get("yc", 0)),
                    float(item.get("radius", 10)),
                    float(item.get("angle_start", 0)),
                    float(item.get("angle_end", 90)),
                    bool(item.get("clockwise", False)),
                    int(item.get("speed", 3))
                )
            elif action == "home":
                self.controller.home()
            elif action == "stop":
                self.controller.stop()
            elif action == "delay":
                pass  # 单纯等待一拍的指令，由定时器间隔提供
            else:
                self.signal_emitter.log_message.emit(f"AI: 未知指令类型 {action}，跳过")
        except Exception as e:
            self.signal_emitter.error_occurred.emit(f"AI 指令执行失败 [{action}]: {e}")
        
        remaining = len(self.ai_queue)
        if remaining > 0 and remaining % 10 == 0:
            self.ai_status_label.setText(f"剩余 {remaining} 条指令...")
    
    def closeEvent(self, event):
        """关闭事件"""
        if self.comm.is_connected():
            self.comm.disconnect()
        event.accept()


def main():
    app = __import__('PyQt5.QtWidgets', fromlist=['QApplication']).QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
