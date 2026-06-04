Arguments
content:
# XY 平台 GUI 统一说明

本文档是 `Firmware_Example/04_XY_Platform_Motion_Control/gui` 目录的统一说明文档
内容覆盖目录结构、功能模块、运行方式、通信协议、界面组成、数据流、测试与扩展点。

## 1. 简介与快速上手

### 1.1 项目简介
这是一个基于 `PyQt5` 的 XY 平台上位机，通过 USB CDC 虚拟串口与下位机通信，提供完整的人机交互与调试界面。

当前已实现的主要能力：
- USB 串口扫描、连接与断开
- 回零、紧急停止
- 绝对位移、相对位移
- 直线插补、圆弧插补
- 平台状态查询、实时坐标显示
- 轨迹可视化
- 日志输出与错误提示
- 简单的串口协议联调脚本

### 1.2 运行环境与依赖
- Python 3.8+
- Windows 或 Linux
- 下位机已枚举为 USB CDC 虚拟串口

**安装依赖：**
```bash
pip install -r requirements.txt
```
当前依赖见 `requirements.txt`：`PyQt5`, `matplotlib`, `pyserial`, `numpy`。

### 1.3 启动方式
在当前目录下运行：
```bash
python main.py
```
（也可以直接运行：`python gui.py`）

### 1.4 基本使用流程
1. 点击“刷新”，扫描可用串口。
2. 选择下位机对应端口。
3. 点击“连接”建立 USB 通信。
4. 根据需要执行控制动作（回零、位移、插补等）。
5. 通过右侧轨迹图和日志观察运行结果。
6. 需要时点击“查询状态”或开启自动查询。

---

## 2. 软件架构与模块

### 2.1 目录概览
```text
gui/
├── main.py             # 启动入口
├── gui.py              # 主窗口、控制面板、轨迹显示和交互逻辑
├── protocol.py         # 协议定义、命令打包、响应解析
├── usb_comm.py         # USB CDC 串口通信与后台接收线程
├── test_protocol.py    # 串口联调脚本
├── requirements.txt    # Python 依赖
└── README.md           # 本文档
```

### 2.2 总体架构
整体分为三层架构：
1. **启动入口层**：`main.py`
2. **应用层**：`gui.py`（包含主界面、控制器、画板和信号发射器）
3. **协议与通信层**：`protocol.py` + `usb_comm.py`

整体调用关系：
```text
main.py
  -> gui.main()
      -> MainWindow
          -> USBCommunicator (负责底层通信)
          -> XYPlatformController (负责动作控制，调用 Protocol 打包命令，处理响应)
          -> XYPlotCanvas (轨迹显示)
          -> SignalEmitter (Qt 信号机制)
```

### 2.3 核心模块说明
- **`main.py`**：轻量级入口，只负责启动 GUI。
- **`gui.py`**：核心应用层。包含主窗口 (`MainWindow`)、轨迹画布 (`XYPlotCanvas`)、平台控制器 (`XYPlatformController`) 以及用于跨线程通信的 `SignalEmitter`。
- **`protocol.py`**：协议层，包含命令定义 (`CommandType`)、状态定义 (`PlatformStatus`)、协议帧打包/解包 (`ProtocolFrame`)，以及请求构建（`CommandBuilder`）和响应解析(`ResponseParser`)。
- **`usb_comm.py`**：通信层，封装串口操作，维护后台接收线程 (`_receive_loop`) 并在读取到完整协议帧时触发回调。
- **`test_protocol.py`**：独立调试脚本，用于在不打开 GUI 的情况下进行串口验证和闭环测试。

### 2.4 数据流与线程模型
- **主线程（UI 线程）**：负责 Qt 事件循环、界面绘制、用户输入响应以及定时查询任务。
- **后台线程（通信线程）**：负责串口数据接收，字节流切帧。收到完整帧后回调给控制器，再通过 `SignalEmitter` 发射信号回到主线程更新 UI。
- **发送路径**：UI 交互 -> `XYPlatformController` -> `CommandBuilder` 生成协议 -> `USBCommunicator` 串口发送。
- **接收路径**：下位机状态帧 -> 串口接收线程 -> 回调 `XYPlatformController` -> 解包与解析`ResponseParser` -> `SignalEmitter` 发射信号 -> 主线程更新 UI。

---

## 3. GUI 功能与界面交互

主界面由左右两个区域组成。界面事件不直接访问串口，而是通过控制层转发，实现逻辑分离。

### 3.1 左侧控制区
- **连接组**：端口选择、刷新、连接/断开。
- **状态组**：连接状态、实时 X/Y 坐标、平台工作状态。
- **基础控制组**：回零、紧急停止。
- **运动控制组**：绝对位移、相对位移、直线插补、圆弧插补。

### 3.2 右侧显示区
- **XY 轨迹图**：展示当前位置、目标点和历史运动轨迹。
- **日志面板**：实时输出通信和操作日志。
- **状态查询**：提供手动查询按钮与自动查询复选框。

---

## 4. 通信协议

### 4.1 帧格式
所有数据按以下格式发送：
```text
[0xAA] [CMD] [LEN] [DATA...] [CHECKSUM] [0xFF]
```
- **Header (1B)**: 固定 `0xAA`
- **Cmd (1B)**: 命令字
- **Len (1B)**: 数据负载长度
- **Data (N B)**: 负载数据
- **Checksum (1B)**: `cmd ^ len ^ data[0] ^ data[1] ^ ...`
- **Tail (1B)**: 固定 `0xFF`

### 4.2 命令集
| 命令 | 代码 | 数据格式 | 说明 |
|------|------|----------|------|
| HOME | `0x01` | 无 | 回零 |
| MOVE_ABS | `0x02` | `x(float) y(float) speed(uint16)` | 绝对位移 |
| MOVE_REL | `0x03` | `dx(float) dy(float) speed(uint16)` | 相对位移 |
| LINE_INTERP | `0x04` | `x1 y1 x2 y2 speed` | 直线插补 |
| ARC_INTERP | `0x05` | `xc yc radius angle_start angle_end clockwise speed` | 圆弧插补 |
| STOP | `0x06` | 无 | 紧急停止 |
| QUERY_STATUS | `0x07` | 无 | 查询状态 |

### 4.3 状态响应 (`0xF0`)
状态响应命令代码为 `0xF0`，负载格式：
`x(4B) | y(4B) | status(1B) | error(1B)`

**Status (1B)**:
`IDLE = 0x00`, `HOMING = 0x01`, `INTERPING = 0x02`, `MANUAL = 0x03`, `ERROR = 0xFF`

---

## 5. 常见问题与调试

### 5.1 调试方法
- **GUI 日志**：通过界面右侧日志面板查看连接与收发错误。
- **终端 DEBUG**：可在代码中启用 `logging.basicConfig(level=logging.DEBUG)` 获得详尽输出。
- **无 UI 测试**：运行 `python test_protocol.py [COM_PORT]` 验证底层收发。

### 5.2 常见问题排查
- **扫描不到设备**：检查 USB 线缆，下位机是否上电，Linux 用户检查 `/dev/tty*` 设备。
- **连接失败**：确保端口未被占用，或配置正确的 Linux 用户组权限 (`sudo usermod -a -G dialout $USER`)。
- **日志显示无响应/坐标不更新**：检查下位机是否返回了 `STATUS_RESPONSE` 且协议格式一致。
- **轨迹显示异常**：确保上位机和下位机的坐标系单位以及相对位置对齐。

---

## 6. 维护与扩展建议

### 6.1 扩展点
如果后续需要增加功能，请参考以下位置：
1. **新指令/响应**：在 `protocol.py` 增加常量和解析逻辑。
2. **新动作封装**：在 `XYPlatformController` 中添加相应方法。
3. **新 UI 控件**：在 `gui.py` 扩展对应的控制面板。
4. **进阶功能**：增加数据持久化记录、轨迹导出/回放等。

### 6.2 维护须知
本 `README.md` 是当前 GUI 目录的唯一说明入口。如遇架构、协议或文件结构的变更，请同步更新此文档，避免拆分多份文档造成信息不一致。
file_path:
f:BeihangMechatronicsLecture\Firmware_Example\04_XY_Platform_Motion_Control\gui\README.md