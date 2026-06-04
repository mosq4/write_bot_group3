# XY 平台运动控制系统开发指南

## 1. 项目概述

本项目是一个**机电一体化课程大作业**——XY 平台运动控制系统，由下位机（STM32F407 嵌入式 C++）和上位机（Python PyQt5 GUI）两部分组成，通过 USB CDC 虚拟串口通信。

- **硬件平台**: STM32F407VETx (Cortex-M4F, LQFP100 封装)
- **RTOS**: FreeRTOS (CMSIS-RTOS V2，4 个任务已激活运行)
- **开发环境**: STM32CubeMX + MDK-ARM (Keil) + Python 3.8+
- **机械结构**: 两轴步进电机驱动的 XY 平台 (丝杆导程 4mm) + 舵机抬落笔机构
- **AI 集成**: DeepSeek API 自动生成汉字书写指令

## 2. 目录结构

```
大作业/
├── XY_Platform_Motion_Control.ioc   # STM32CubeMX 项目配置文件 (gitignore)
├── .mxproject                       # CubeMX 辅助文件 (gitignore)
├── AGENTS.md                        # 本开发指南
├── .gitignore                       # git 排除规则
├── Core/                            # STM32 HAL 层自动生成代码
│   ├── Inc/                         # 头文件 (main.h gpio.h tim.h FreeRTOSConfig.h 等)
│   └── Src/                         # 源文件 (main.c freertos.c gpio.c tim.c 等)
├── Drivers/                         # STM32 HAL 驱动库 (CMSIS + HAL)
├── Middlewares/                     # FreeRTOS + USB Device Library 源码
├── MDK-ARM/                         # Keil 工程文件 + 用户代码
│   ├── App/                         # ★ 应用层 (config + RTOS 任务实现)
│   │   ├── my_config.h/cpp          # 全局对象实例化 (电机/按键/XY平台)
│   │   └── my_rtos.h/cpp            # 4 个 FreeRTOS 任务实现 + 定时器回调
│   ├── Drivers/                     # ★ 硬件驱动层 (C++ 类)
│   │   ├── xstepper.h/cpp           # 步进电机驱动 (梯形加减速)
│   │   ├── xLinearModule.h/cpp      # 直线模组 (丝杆转换 + 限位)
│   │   ├── XYplatform.h/cpp         # XY 平台直线/圆弧插补 + PID
│   │   ├── xkey.h/cpp               # 按键扫描
│   │   ├── xusb.h/cpp               # 串口协议解析 (USB CDC)
│   │   └── pid.h/cpp                # PID 控制器
│   ├── startup_stm32f407xx.s        # 启动文件
│   └── XY_Platform_Motion_Control/  # 编译输出 (gitignore)
├── USB_DEVICE/                      # USB CDC 虚拟串口
│   ├── App/                         # usbd_cdc_if (环形队列接收)
│   └── Target/                      # usbd_conf (USB 配置)
└── gui/                             # ★ 上位机 Python 代码
    ├── main.py                      # 启动入口
    ├── gui.py                       # PyQt5 主窗口 (含 AI 汉字书写面板)
    ├── protocol.py                  # 通信协议定义 (帧构建/解析/7种命令)
    ├── usb_comm.py                  # 串口通信 (后台接收线程)
    ├── ai_instruction.py            # ★ AI 指令 JSON 格式 + Prompt 模板 + API 调用
    ├── deepseek_client.py           # ★ DeepSeek API 客户端
    ├── test_protocol.py             # 命令行联调脚本
    ├── requirements.txt             # Python 依赖
    ├── apikey.txt                   # DeepSeek API Key (需创建, gitignore)
    └── README.md                    # GUI 详细说明文档
```

## 3. 嵌入式外设配置

| 外设 | 用途 | 备注 |
|------|------|------|
| USB_OTG_FS | 上位机通信 (CDC 虚拟串口) | PA11/PA12 |
| TIM8 CH4 | M1 步进电机 PWM (X 轴) | APB2, 168MHz, 基频 1MHz |
| TIM3 CH1 | M2 步进电机 PWM (Y 轴) | APB1, 84MHz, 基频 1MHz |
| TIM4 CH2 | M3 步进电机 PWM (预留) | 未实例化 |
| TIM5 CH1~4 | 4 路舵机 PWM | 20ms 周期，抬落笔用 |
| GPIO PE1~PE4 | 行程开关 SW1~SW4 | EXTI1~4 中断 |
| GPIO PD0~PD4 | LED1~4, KEY1~4 | 按键低电平有效 |

### 电机参数
- 步距角: 1.8° (200 步/圈)
- 细分: 32x (6400 脉冲/圈)
- 丝杆导程: 4.0 mm/圈
- **脉冲当量**: 1600 脉冲/mm

### 引脚映射
| 信号 | 引脚 | 说明 |
|------|------|------|
| M1 DIR (X) | PC8 | 方向控制 |
| M1 nENBL (X) | PA8 | 使能 (LOW=使能) |
| M2 DIR (Y) | PD15 | 方向控制 |
| M2 nENBL (Y) | PC7 | 使能 (LOW=使能) |
| LED1~4 | PD0, PC12, PC11, PC10 | LED3 在收到命令时翻转 |
| KEY1~4 | PD4, PD3, PD2, PD1 | 低电平有效 |
| SW1/SW2 (X) | PE1/PE2 | X 轴原点/远端限位 |
| SW3/SW4 (Y) | PE3/PE4 | Y 轴原点/远端限位 |

## 4. FreeRTOS 任务

| 任务名 | 优先级 | 栈大小 | 状态 | 说明 |
|--------|--------|--------|------|------|
| defaultTask | Normal | 128×4 | ⚠ 自挂起 | 初始化后挂起，仅启动 USB 和 key/debug 任务 |
| debugTask | Normal | 512×4 | ✅ 运行 | **主控制循环** 1ms 周期，运行 `g_xyPlatform.ControlLoop()` |
| keyScanTask | BelowNormal | 128×4 | ✅ 运行 | 50ms 周期按键扫描 |
| usbRxTask | Normal | 512×4 | ✅ 运行 | USB CDC 接收线程，协议帧解析 + 命令分发 |

### 启动流程
```
main() → osKernelStart()
  → defaultTask: MX_USB_DEVICE_Init() → MotionConfig() → 恢复 debugTask/keyScanTask → 自挂起
  → debugTask: while(1) { g_xyPlatform.ControlLoop(); osDelay(1); }
  → keyScanTask: while(1) { g_key[i].update(); osDelay(50); }
  → usbRxTask: while(1) { 等待 USB_RX_THREAD_FLAG_DATA → 解析帧 → usb_handle_command() }
```

## 5. 通信协议

### 帧格式
```
[0xAA] [CMD(1B)] [LEN(1B)] [DATA(N B)] [CHECKSUM(1B)] [0xFF]
校验和 = CMD ^ LEN ^ DATA[0] ^ ... ^ DATA[N-1]
```

### 命令集（上位机 → 下位机）

| 命令 | 代码 | 数据 | 说明 |
|------|------|------|------|
| HOME | 0x01 | 无 | 回零 (两轴分别 -10mm/s 向原点运动) |
| MOVE_ABS | 0x02 | x(f) y(f) speed(u16) | 绝对位置移动 (手动模式梯形速度分配) |
| MOVE_REL | 0x03 | dx(f) dy(f) speed(u16) | 相对位移 |
| LINE_INTERP | 0x04 | x1(f) y1(f) x2(f) y2(f) speed(u16) | 直线插补 (先移动到起点再插补) |
| ARC_INTERP | 0x05 | xc(f) yc(f) r(f) θ1(f) θ2(f) cw(B) speed(u16) | 圆弧插补 |
| STOP | 0x06 | 无 | 紧急停止 |
| QUERY_STATUS | 0x07 | 无 | 查询状态 |

### 状态响应（下位机 → 上位机）

代码 `0xF0`, 数据: `x(float) y(float) status(1B) error(1B)` 共 10 bytes

| Status | 值 | 含义 |
|--------|-----|------|
| IDLE | 0x00 | 空闲 |
| HOMING | 0x01 | 回零中 |
| INTERPING | 0x02 | 插补中 |
| MANUAL | 0x03 | 手动运动 |
| ERROR | 0xFF | 错误 |

## 6. 下位机架构

### 数据流
```
GUI (Python)
  │ USB CDC
  ▼
USB ISR → CDC_Receive_FS() → 环形队列 (16×64B)
                                   │ USB_RX_THREAD_FLAG_DATA
                                   ▼
usbRxTask: USB_CDC_RxPop() → 帧解析 (0xAA...0xFF)
       → usb_parse_command() → usb_handle_command()
                                   │
                                   ▼
           g_xyPlatform: FindHome / MoveTo / LinearInterpolation / CircularInterpolation
                                   │
                                   ▼
debugTask (1ms): g_xyPlatform.ControlLoop()
  │ 逐点比较法插补 (直线/圆弧)
  │ PID 闭环控制
  │ 设置 LinearModule 目标位置/速度
                                   │
                                   ▼
TIM ISR → My_TIM_PeriodElapsedCallback()
  → LinearModule::ControlLoop() → Stepper::ControlLoop()
     → PositionLoop / VelocityLoop → OutputStepVelocity()
        → GPIO 方向 + PWM 频率
```

### 软件层次
```
应用层:    my_rtos.cpp (4 个 RTOS 任务 + 定时器/中断回调)
平台层:    XYplatform (插补算法 + PID + 状态机)
模组层:    xLinearModule (丝杆转换 + 限位开关)
驱动层:    xstepper (梯形加减速 + PWM 输出)
协议层:    xusb (帧解析 + 命令分发)
HAL 层:    STM32 HAL (CubeMX 生成)
```

## 7. 插补算法

采用**逐点比较法**：

### 直线插补 (`ControlLoop` LINEAR_INTERPOLATION)
- 4 个象限分别处理 (偏差函数 F = Xe·Y - X·Ye)
- F ≥ 0 走 X，F < 0 走 Y
- 步距: `inter_step` (默认 0.1mm)

### 圆弧插补 (`ControlLoop` CIRCULAR_INTERPOLATION)
- 8 种情况: SR1~SR4 (顺圆), NR1~NR4 (逆圆)
- 偏差函数 F = X² + Y² - R²
- 不能一次性画整圆，需分两段 (270°+90°)

### 脉冲当量
```
1 mm = (1/4.0) rev = 90° = (90 × 32 / 1.8) = 1600 脉冲
```

## 8. 上位机 AI 汉字书写流程

```
GUI 输入汉字 → 点击[生成并执行]
     │
     ├─→ DeepSeek API (dev/deepseek_chat)
     │     prompt 模板自动注入写字参数
     │
     ├─→ API 返回指令 JSON
     │     { "instructions": [
     │         {"action":"pen_up"},
     │         {"action":"move_abs", ...},
     │         {"action":"pen_down"},
     │         {"action":"line_interp", ...},
     │         ...
     │       ]}
     │
     └─→ 自动逐条执行 (QTimer 队列, 200ms间隔)
           pen_up/pen_down → CMD_PEN (0x09, 舵机控制)
           move_abs       → CMD_MOVE_ABS (0x02)
           line_interp    → CMD_LINE_INTERP (0x04)
```

### API Key 配置 (优先级)

| 方式 | 说明 |
|------|------|
| GUI 输入框 | 本次会话有效 |
| 环境变量 `DEEPSEEK_API_KEY` | 永久有效 |
| `gui/apikey.txt` 第一行 | 永久有效, **已加入 gitignore** |

## 9. 关键代码位置

| 功能 | 文件 | 说明 |
|------|------|------|
| 主函数入口 | `Core/Src/main.c` | 初始化 + 启动 FreeRTOS |
| FreeRTOS 任务定义 | `Core/Src/freertos.c:51` | 4 个任务创建 (弱函数, 由 my_rtos.cpp 覆盖) |
| **全局对象实例化** | `MDK-ARM/App/my_config.cpp` | g_key[], g_linearModule[], g_xyPlatform |
| **4 个 RTOS 任务实现** | `MDK-ARM/App/my_rtos.cpp` | StartDefaultTask/StartDebugTask/StartKeyScanTask/StartUsbRxTask |
| **定时器回调** | `MDK-ARM/App/my_rtos.cpp:My_TIM_PeriodElapsedCallback` | 分发到各轴 ControlLoop |
| **EXTI 限位回调** | `MDK-ARM/App/my_rtos.cpp:HAL_GPIO_EXTI_Callback` | 原点归零 / 远端报错 |
| 步进电机驱动 | `MDK-ARM/Drivers/xstepper.cpp` | 梯形加减速 + PWM 输出 |
| 直线模组 | `MDK-ARM/Drivers/xLinearModule.cpp` | 丝杆角度↔位移转换 |
| **XY 平台插补** | `MDK-ARM/Drivers/XYplatform.cpp` | 直线/圆弧逐点比较法 + PID |
| PID 控制器 | `MDK-ARM/Drivers/pid.cpp` | 位置式 PID + 抗积分饱和 |
| **协议解析** | `MDK-ARM/Drivers/xusb.cpp` | 帧解析 + 命令分发 + 状态响应 (0xF0) |
| USB CDC 接收 | `USB_DEVICE/App/usbd_cdc_if.c:85` | 环形队列 + 线程标志通知 |
| 协议定义 | `gui/protocol.py` | 7 种命令 |
| GUI 主窗口 | `gui/gui.py` | 含 AI 写字面板 + XY 轨迹图 |
| **AI 指令模块** | `gui/ai_instruction.py` | Prompt + API 调用 |
| **DeepSeek 客户端** | `gui/deepseek_client.py` | API 通信 |
| USB 通信 | `gui/usb_comm.py` | 后台接收线程 |

## 10. 编译与运行

### 下位机
- STM32CubeMX 打开 `XY_Platform_Motion_Control.ioc` 生成代码
- MDK-ARM 打开 `MDK-ARM/XY_Platform_Motion_Control.uvprojx` 编译下载

### 上位机
```bash
cd gui
pip install -r requirements.txt

# 配置 API Key (三选一)
echo sk-xxxxxxxxxxxxxxxx > gui/apikey.txt

python main.py
```

## 11. 注意事项

- `XYplatform::CircularInterpolation` 不能一次性画整圆，需分两段
- 插补算法逐点比较法，脉冲当量 1600 脉冲/mm
- `usb_parse_command` 和 `usb_handle_command` 在 usbRxTask 中执行，不在中断上下文
- USB CDC 接收使用环形队列 (16×64B)，丢包计数 `USB_CDC_RxDropCount`
- PID 默认参数: kp=2.0, ki=0, kd=0, output_limit=100, period=0.01s (暂未启用，CLOSED_LOOP 模式预留)
- 限位开关 EXTI 中断处理有 20ms 消抖
- `apikey.txt`, `ai_response.json`, `ai_request.txt` 已加入 gitignore
- 编译输出 `MDK-ARM/XY_Platform_Motion_Control/` 及其 `.o` `.d` `.axf` `.hex` 等已加入 gitignore
- `.ioc` 和 `.mxproject` 已加入 gitignore
