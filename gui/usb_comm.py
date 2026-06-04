"""
USB 通信模块 (CDC 虚拟串口)
"""

import serial
import serial.tools.list_ports
import logging
from typing import Callable, Optional
from threading import Thread, Lock, Event
import time

logger = logging.getLogger(__name__)


class USBCommunicator:
    """USB 通信器"""
    
    def __init__(self, baudrate: int = 115200):
        self.baudrate = baudrate
        self.port = None
        self._serial: Optional[serial.Serial] = None
        self._lock = Lock()
        self._rx_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._on_data_received: Optional[Callable] = None
        
    def list_ports(self) -> list:
        """列出所有可用的 USB CDC 端口"""
        ports = []
        for port_info in serial.tools.list_ports.comports():
            ports.append({
                'port': port_info.device,
                'description': port_info.description,
                'manufacturer': port_info.manufacturer
            })
        return ports
    
    def connect(self, port: str) -> bool:
        """连接到 USB CDC 设备
        
        Args:
            port: 串口（如 "COM3" 或 "/dev/ttyACM0"）
        
        Returns:
            连接是否成功
        """
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=1
            )
            self.port = port
            logger.info(f"Connected to {port} at {self.baudrate} baud")
            
            # 启动接收线程
            self._stop_event.clear()
            self._rx_thread = Thread(target=self._receive_loop, daemon=True)
            self._rx_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self._serial and self._serial.is_open:
            self._stop_event.set()
            if self._rx_thread:
                self._rx_thread.join(timeout=1)
            
            with self._lock:
                self._serial.close()
            logger.info("Disconnected")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._serial is not None and self._serial.is_open
    
    def send_data(self, data: bytes) -> bool:
        """发送数据
        
        Args:
            data: 字节数据
        
        Returns:
            发送是否成功
        """
        if not self.is_connected():
            logger.warning("Not connected, cannot send")
            return False
        
        try:
            with self._lock:
                self._serial.write(data)
                self._serial.flush()
            logger.debug(f"Sent {len(data)} bytes")
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False
    
    def set_data_callback(self, callback: Callable[[bytes], None]):
        """设置数据接收回调函数"""
        self._on_data_received = callback
    
    def _receive_loop(self):
        """接收数据循环"""
        buffer = b''
        
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    if self._serial and self._serial.in_waiting:
                        chunk = self._serial.read(self._serial.in_waiting)
                        buffer += chunk
                
                # 查找完整帧 (AA...FF)
                while True:
                    if len(buffer) < 5:
                        break
                    
                    # 找帧头
                    start_idx = buffer.find(b'\xAA')
                    if start_idx == -1:
                        buffer = b''
                        break
                    
                    if start_idx > 0:
                        buffer = buffer[start_idx:]
                    
                    # 检查最小长度
                    if len(buffer) < 5:
                        break
                    
                    # 数据长度
                    data_len = buffer[2]
                    frame_len = 5 + data_len  # header + cmd + len + data + checksum + tail
                    
                    if len(buffer) < frame_len:
                        break
                    
                    # 提取一帧
                    frame = buffer[:frame_len]
                    buffer = buffer[frame_len:]
                    
                    # 校验帧尾
                    if frame[-1] != 0xFF:
                        logger.warning("Invalid frame tail")
                        continue
                    
                    # 调用回调
                    if self._on_data_received:
                        try:
                            self._on_data_received(frame)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                
                time.sleep(0.01)
            
            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                time.sleep(0.1)
