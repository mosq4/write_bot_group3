#!/usr/bin/env python3
"""
XY 平台协议联调脚本

基于当前 gui/ 目录中的 protocol.py 和 usb_comm.py，
用于在不启动 GUI 的情况下直接验证平台级命令收发。
"""

import argparse
import sys
import time

from protocol import (
    CommandBuilder,
    CommandType,
    PlatformStatus,
    ProtocolFrame,
    ResponseParser,
)
from usb_comm import USBCommunicator


def list_ports() -> list:
    """列出当前可用端口。"""
    comm = USBCommunicator()
    return comm.list_ports()


def print_ports(ports: list):
    """打印端口列表。"""
    if not ports:
        print("无可用端口")
        return

    print("可用端口:")
    for port_info in ports:
        manufacturer = port_info.get("manufacturer") or "Unknown"
        print(f"  {port_info['port']}: {port_info['description']} [{manufacturer}]")


def resolve_port(port_arg: str | None) -> str | None:
    """解析目标端口。

    - 如果显式传入端口，直接使用。
    - 如果未传入且只扫描到一个端口，自动选中。
    - 如果未传入且端口数不是 1，提示用户显式指定。
    """
    ports = list_ports()

    if port_arg:
        return port_arg

    if len(ports) == 1:
        selected = ports[0]["port"]
        print(f"[*] 未指定端口，自动选择 {selected}")
        return selected

    print_ports(ports)
    if not ports:
        return None

    print("[-] 检测到多个端口，请显式指定，例如: python test_protocol.py COM3")
    return None


def format_status(status_info: dict) -> str:
    """格式化状态响应。"""
    status = status_info["status"]
    if isinstance(status, PlatformStatus):
        status_name = status.name
    else:
        status_name = str(status)

    return (
        f"X={status_info['x']:.2f} mm, "
        f"Y={status_info['y']:.2f} mm, "
        f"STATUS={status_name}, "
        f"ERROR={status_info['error']}"
    )


def decode_frame(frame_data: bytes):
    """解析收到的协议帧并打印结果。"""
    cmd, data = ProtocolFrame.unpack(frame_data)

    if cmd == CommandType.STATUS_RESPONSE:
        status_info = ResponseParser.parse_status(data)
        print(f"[RX] {frame_data.hex().upper()}")
        print(f"     {format_status(status_info)}")
        return {
            "cmd": cmd,
            "raw": frame_data,
            "parsed": status_info,
        }

    print(f"[RX] {frame_data.hex().upper()} (CMD=0x{cmd:02X}, LEN={len(data)})")
    return {
        "cmd": cmd,
        "raw": frame_data,
        "parsed": None,
    }


def send_command(comm: USBCommunicator, label: str, payload: bytes, delay_s: float) -> bool:
    """发送单条命令并等待一小段时间。"""
    print(f"\n[*] {label}")
    print(f"[TX] {payload.hex().upper()}")

    success = comm.send_data(payload)
    if not success:
        print("[-] 发送失败")
        return False

    time.sleep(delay_s)
    return True


def test_communication(port: str, baudrate: int = 115200, speed: int = 5, delay_s: float = 0.3):
    """执行与当前 GUI 对齐的一组基础联调动作。"""
    comm = USBCommunicator(baudrate=baudrate)
    received_frames = []

    def on_data(frame_data: bytes):
        try:
            decoded = decode_frame(frame_data)
            received_frames.append(decoded)
        except Exception as exc:
            print(f"[RX-ERROR] 解析失败: {exc}")
            print(f"           RAW={frame_data.hex().upper()}")

    print("[*] 扫描端口...")
    print_ports(comm.list_ports())

    print(f"\n[*] 连接到 {port} @ {baudrate} baud ...")
    if not comm.connect(port):
        print("[-] 连接失败")
        return 1

    comm.set_data_callback(on_data)
    print("[+] 已连接")

    try:
        sequence = [
            ("查询状态", CommandBuilder.query_status()),
            ("回零", CommandBuilder.home()),
            ("再次查询状态", CommandBuilder.query_status()),
            (f"绝对位移到 (10, 20)，速度 {speed}", CommandBuilder.move_abs(10.0, 20.0, speed)),
            ("查询状态", CommandBuilder.query_status()),
            (
                f"相对位移 (+5, -3)，速度 {speed}",
                CommandBuilder.move_rel(5.0, -3.0, speed),
            ),
            ("查询状态", CommandBuilder.query_status()),
            (
                f"直线插补 (0, 0) -> (50, 50)，速度 {speed}",
                CommandBuilder.line_interp(0.0, 0.0, 50.0, 50.0, speed),
            ),
            ("查询状态", CommandBuilder.query_status()),
            (
                f"圆弧插补，圆心 (25, 25)，半径 10，0° -> 90°，逆时针，速度 {speed}",
                CommandBuilder.arc_interp(25.0, 25.0, 10.0, 0.0, 90.0, False, speed),
            ),
            ("查询状态", CommandBuilder.query_status()),
            ("紧急停止", CommandBuilder.stop()),
            ("最终查询状态", CommandBuilder.query_status()),
        ]

        for label, payload in sequence:
            if not send_command(comm, label, payload, delay_s):
                return 1

        print(f"\n[+] 测试完成，共收到 {len(received_frames)} 个响应帧")
        return 0

    finally:
        comm.disconnect()
        print("[*] 已断开连接")


def main():
    parser = argparse.ArgumentParser(description="XY 平台协议联调工具")
    parser.add_argument("port", nargs="?", help="串口名，例如 COM3 或 /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200, help="波特率，默认 115200")
    parser.add_argument("--speed", type=int, default=5, help="测试速度，默认 5")
    parser.add_argument("--delay", type=float, default=0.3, help="每条命令后的等待时间，默认 0.3 秒")
    parser.add_argument("--list", action="store_true", help="仅列出可用端口")

    args = parser.parse_args()

    if args.list:
        print_ports(list_ports())
        return 0

    port = resolve_port(args.port)
    if not port:
        return 1

    return test_communication(
        port=port,
        baudrate=args.baud,
        speed=args.speed,
        delay_s=args.delay,
    )


if __name__ == "__main__":
    sys.exit(main())
