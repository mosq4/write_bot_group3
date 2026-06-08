"""
XY 平台通信协议定义
"""

import struct
from enum import IntEnum
from typing import Union, Tuple, List


class CommandType(IntEnum):
    """命令类型枚举"""
    HOME = 0x01                # 回零
    MOVE_ABS = 0x02            # 绝对位移
    MOVE_REL = 0x03            # 相对位移
    LINE_INTERP = 0x04         # 直线插补
    ARC_INTERP = 0x05          # 圆弧插补
    STOP = 0x06                # 停止
    QUERY_STATUS = 0x07        # 查询状态
    SERVO = 0x08               # 舵机控制
    PEN = 0x09                 # 抬落笔
    STATUS_RESPONSE = 0xF0      # 状态响应


class PlatformStatus(IntEnum):
    """平台状态"""
    IDLE = 0x00                # 空闲
    HOMING = 0x01              # 回零中
    INTERPING = 0x02              # 插补中
    MANUAL = 0x03              # 直接运动
    ERROR = 0xFF               # 错误


FRAME_HEADER = 0xAA
FRAME_TAIL = 0xFF


class ProtocolFrame:
    """USB 通信协议帧"""
    
    def __init__(self):
        self.header = FRAME_HEADER
        self.cmd = 0
        self.data = b''
        self.checksum = 0
        self.tail = FRAME_TAIL
    
    @staticmethod
    def calculate_checksum(cmd: int, data_len: int, data: bytes) -> int:
        """计算校验和 (XOR)"""
        checksum = cmd ^ data_len
        for byte in data:
            checksum ^= byte
        return checksum
    
    def pack(self, cmd: CommandType, data: bytes = b'') -> bytes:
        """打包帧为字节序列"""
        self.cmd = cmd
        self.data = data
        data_len = len(data)
        self.checksum = self.calculate_checksum(cmd, data_len, data)
        
        frame = bytes([
            self.header,
            self.cmd,
            data_len,
            *data,
            self.checksum,
            self.tail
        ])
        return frame
    
    @staticmethod
    def unpack(frame_data: bytes) -> Tuple[int, bytes]:
        """解包字节序列为 (cmd, data)"""
        if len(frame_data) < 5:
            raise ValueError("Frame too short")
        
        if frame_data[0] != FRAME_HEADER or frame_data[-1] != FRAME_TAIL:
            raise ValueError("Invalid frame header or tail")
        
        cmd = frame_data[1]
        data_len = frame_data[2]
        data = frame_data[3:3+data_len]
        checksum = frame_data[3+data_len]
        
        # 校验校验和
        calculated_checksum = ProtocolFrame.calculate_checksum(cmd, data_len, data)
        if checksum != calculated_checksum:
            raise ValueError(f"Checksum mismatch: {checksum} != {calculated_checksum}")
        
        return cmd, data


class CommandBuilder:
    """命令构建器"""
    
    @staticmethod
    def home() -> bytes:
        """构建回零命令"""
        return ProtocolFrame().pack(CommandType.HOME, b'')
    
    @staticmethod
    def move_abs(x: float, y: float, speed: int) -> bytes:
        """构建绝对位移命令
        
        Args:
            x: X 坐标 (mm)
            y: Y 坐标 (mm)
            speed: 速度 (mm/s)
        """
        data = struct.pack('<ffH', x, y, speed)
        return ProtocolFrame().pack(CommandType.MOVE_ABS, data)
    
    @staticmethod
    def move_rel(dx: float, dy: float, speed: int) -> bytes:
        """构建相对位移命令"""
        data = struct.pack('<ffH', dx, dy, speed)
        return ProtocolFrame().pack(CommandType.MOVE_REL, data)
    
    @staticmethod
    def line_interp(x1: float, y1: float, x2: float, y2: float, speed: int) -> bytes:
        """构建直线插补命令"""
        data = struct.pack('<ffffH', x1, y1, x2, y2, speed)
        return ProtocolFrame().pack(CommandType.LINE_INTERP, data)
    
    @staticmethod
    def arc_interp(
        xc: float,
        yc: float,
        radius: float,
        angle_start: float,
        angle_end: float,
        clockwise: bool,
        speed: int
    ) -> bytes:
        """构建圆弧插补命令
        
        Args:
            xc: 圆心 X 坐标
            yc: 圆心 Y 坐标
            radius: 半径
            angle_start: 起始角度 (度)
            angle_end: 终止角度 (度)
            clockwise: 方向，True=顺时针，False=逆时针
            speed: 速度
        """
        data = struct.pack(
            '<fffffBH',
            xc, yc, radius, angle_start, angle_end,
            1 if clockwise else 0,
            speed
        )
        return ProtocolFrame().pack(CommandType.ARC_INTERP, data)
    
    @staticmethod
    def stop() -> bytes:
        """构建停止命令"""
        return ProtocolFrame().pack(CommandType.STOP, b'')
    
    @staticmethod
    def query_status() -> bytes:
        """构建状态查询命令"""
        return ProtocolFrame().pack(CommandType.QUERY_STATUS, b'')
    
    @staticmethod
    def servo(servo_id: int, angle: float) -> bytes:
        """构建舵机控制命令
        
        Args:
            servo_id: 舵机ID (1~4)
            angle: 角度 (0~180)
        """
        data = struct.pack('<Bf', servo_id, angle)
        return ProtocolFrame().pack(CommandType.SERVO, data)
    
    @staticmethod
    def pen_down() -> bytes:
        """构建落笔命令"""
        return ProtocolFrame().pack(CommandType.PEN, b'\x01')
    
    @staticmethod
    def pen_up() -> bytes:
        """构建抬笔命令"""
        return ProtocolFrame().pack(CommandType.PEN, b'\x00')


class ResponseParser:
    """响应解析器"""
    
    @staticmethod
    def parse_status(data: bytes) -> dict:
        """解析状态响应
        
        Returns:
            {
                'x': 当前 X 坐标,
                'y': 当前 Y 坐标,
                'status': 平台状态,
                'error': 错误码
            }
        """
        if len(data) < 10:
            raise ValueError(f"Invalid status data length: {len(data)}")
        
        x, y, status, error = struct.unpack('<ffBB', data[:10])
        return {
            'x': x,
            'y': y,
            'status': PlatformStatus(status),
            'error': error
        }
