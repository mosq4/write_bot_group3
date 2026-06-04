/**
  ******************************************************************************
  * @file           :
  * @author         : Xiang Guo
  * @brief          : 
  * @date	          : 2023/05/07
  ******************************************************************************
  * @attention
  *
  *
  ******************************************************************************
  */

/* ------------------------------ Includes ------------------------------ */

#include "my_rtos.h"
#include "my_config.h"
#include "xusb.h"
#include "usb_device.h"
#include "usbd_cdc_if.h"
/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variables ------------------------------ */

/* ------------------------------ Functions ------------------------------ */

#ifdef __cplusplus
extern "C" {
#endif

void My_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim);

void StartDefaultTask(void *argument);
void StartDebugTask(void *argument);
void StartKeyScanTask(void *argument);
void StartUsbRxTask(void *argument);
#ifdef __cplusplus
}
#endif

/* ------------------------------ Interrupts ------------------------------ */
// 自定义定时器中断回调函数，放在main.c文件中的HAL_TIM_PeriodElapsedCallback中，分别用于x和y轴的控制循环
void My_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  if (htim->Instance == g_xyPlatform.x->stepper.p_htim->Instance)
  {
    g_xyPlatform.x->ControlLoop();
  }
  else if (htim->Instance == g_xyPlatform.y->stepper.p_htim->Instance)
  {
    g_xyPlatform.y->ControlLoop();
  }
}
// 外部中断回调函数，用于处理限位开关触发事件
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  osDelay(20);
  if (GPIO_Pin==g_xyPlatform.x->limit_switch1_pin)
  {
    //x轴回零边界
    if (HAL_GPIO_ReadPin(g_xyPlatform.x->limit_switch1_port, g_xyPlatform.x->limit_switch1_pin) == GPIO_PIN_SET)
    {
      if (g_xyPlatform.x->mode != x_linear_module::MODULE_MODE_POSITION)
      {
          g_xyPlatform.x->SetMode(x_linear_module::MODULE_MODE_POSITION);
          g_xyPlatform.x->SetPosition(-10);
          g_xyPlatform.x->SetTargetPosition(0);
          g_xyPlatform.x->SetTargetVelocityHard(0);
      }
    }
  }
  else if (GPIO_Pin == g_xyPlatform.x->limit_switch2_pin)
  {
    //x轴上限边界，对应错误状态
    if (HAL_GPIO_ReadPin(g_xyPlatform.x->limit_switch2_port, g_xyPlatform.x->limit_switch2_pin) == GPIO_PIN_SET)
    {
      g_xyPlatform.x->SetMode(x_linear_module::MODULE_MODE_ERROR);
      g_xyPlatform.x->SetTargetVelocityHard(0);
    }
  }
  else if (GPIO_Pin == g_xyPlatform.y->limit_switch1_pin)
  {
    if (HAL_GPIO_ReadPin(g_xyPlatform.y->limit_switch1_port, g_xyPlatform.y->limit_switch1_pin) == GPIO_PIN_SET)
    {
      //y轴回零边界
      if (g_xyPlatform.y->mode != x_linear_module::MODULE_MODE_POSITION)
      {
        g_xyPlatform.y->SetMode(x_linear_module::MODULE_MODE_POSITION);
        g_xyPlatform.y->SetPosition(-10);
        g_xyPlatform.y->SetTargetPosition(0);
        g_xyPlatform.y->SetTargetVelocityHard(0);
      }
    }
  }
  else if (GPIO_Pin == g_xyPlatform.y->limit_switch2_pin)
  {
    //y轴上限边界，对应错误状态
    if (HAL_GPIO_ReadPin(g_xyPlatform.y->limit_switch2_port, g_xyPlatform.y->limit_switch2_pin  ) == GPIO_PIN_SET)
    {
        // Handle limit switch trigger
        g_xyPlatform.y->SetMode(x_linear_module::MODULE_MODE_ERROR);
        g_xyPlatform.y->SetTargetVelocityHard(0);
    }
  }
}
/* ------------------------------ Tasks ------------------------------ */

/**
  * @brief  .
  * @author Xiang Guo
  * @param  none
  * @retval none
  */
void StartDefaultTask(void *argument)
{
  MX_USB_DEVICE_Init();
  g_xyPlatform.MotionConfig(1, 1, 10.0f, 500.0f);
  g_xyPlatform.x->SetMode(x_linear_module::MODULE_MODE_VELOCITY);
  g_xyPlatform.y->SetMode(x_linear_module::MODULE_MODE_VELOCITY);
  osThreadResume(debugTaskHandle);
  osThreadResume(keyScanTaskHandle);
  osThreadSuspend(defaultTaskHandle);
  /* Infinite loop */
  for (;;)
  {}
}

/**
  * @brief  .
  * @param  none
  * @retval none
  */
void StartDebugTask(void *argument)
{
  for (;;)
  { 
//     if (g_key[0].released())
//     {
// //      g_linearModule[0].SetTargetVelocity(-10.0f);
//         g_xyPlatform.FindHome();
//     }
//     if (g_key[1].released())
//     {
// //      g_linearModule[1].SetTargetVelocity(-10.0f);
//       g_linearModule[0].SetTargetVelocityHard(0.0f);
//       g_linearModule[1].SetTargetVelocityHard(0.0f);
//     }
//     if (g_key[2].released())
//     {
//       g_linearModule[0].SetTargetVelocity(10.0f);
//     }
//     if (g_key[3].released())
//     {
//       g_linearModule[1].SetTargetVelocity(10.0f);
//     }
    g_xyPlatform.ControlLoop();
    osDelay(1);
  }
}

/**
  * @brief  Key scan task, update key states every 50ms.
  * @param  none
  * @retval none
  */
void StartKeyScanTask(void *argument)
{
  for (;;)
  {
    for (uint8_t i = 0; i < 4; i++)
    {
      g_key[i].update();
    }
    osDelay(50);
  }
}

void StartUsbRxTask(void *argument)
{
 (void)argument;

  /* 解析过程中先缓存“单个 USB 包”和“连续字节流”两层数据：
   * packet_buf  用来接收 USB CDC 回调从队列里取出的单个包；
   * stream_buf  用来拼接多个包，解决一条协议帧被 USB 分包的情况。
   */
  uint8_t cmd = 0U;
  uint8_t *data = nullptr;
  uint8_t data_len = 0U;
  uint8_t packet_buf[64];
  uint32_t packet_len = 0U;
  uint8_t stream_buf[512];
  uint16_t stream_len = 0U;

  for (;;)
  {
    /* 等待 USB 接收回调置位通知，避免任务空转。 */
    (void)osThreadFlagsWait(USB_RX_THREAD_FLAG_DATA, osFlagsWaitAny, osWaitForever);

    /* 把队列中的 USB 包全部取空，并顺序拼接到 stream_buf 中。 */
    while (USB_CDC_RxPop(packet_buf, sizeof(packet_buf), &packet_len))
    {
      /* 如果当前缓冲区装不下新包，直接清空重新开始，避免旧残留影响解析。 */
      if ((stream_len + packet_len) > sizeof(stream_buf))
      {
        stream_len = 0U;
      }

      /* 将本次 USB 包追加到连续流尾部。 */
      memcpy(&stream_buf[stream_len], packet_buf, packet_len);
      stream_len += (uint16_t)packet_len;

      /* 在连续流中查找完整协议帧：
       * [HEADER][CMD][LEN][DATA...][CHECKSUM][TAIL]
       * 最短长度为 5 字节，因此少于 5 字节时不可能构成完整帧。
       */
      uint16_t parse_pos = 0U;
      while ((stream_len - parse_pos) >= 5U)
      {
        /* 先找帧头，跳过无效字节或半包残留。 */
        if (stream_buf[parse_pos] != FRAME_HEADER)
        {
          parse_pos++;
          continue;
        }

        /* 第 3 个字节是数据长度，整帧长度 = 1(头) + 1(cmd) + 1(len) + data + 1(checksum) + 1(尾)。 */
        uint16_t frame_len = (uint16_t)stream_buf[parse_pos + 2U] + 5U;
        if ((stream_len - parse_pos) < frame_len)
        {
          /* 当前还没有收齐整帧，保留残余数据等待后续 USB 包补齐。 */
          break;
        }

        /* 帧尾正确时才进入命令解析，避免把噪声数据误判成有效帧。 */
        if (stream_buf[parse_pos + frame_len - 1U] == FRAME_TAIL)
        {
          /* usb_parse_command 负责做结构校验和校验和校验；通过后交给命令处理器。 */
          if (usb_parse_command(&stream_buf[parse_pos], frame_len, &cmd, &data, &data_len))
          {
            usb_handle_command(cmd, data, data_len);
          }

          /* 这帧已经处理完，继续扫描后续数据。 */
          parse_pos += frame_len;
        }
        else
        {
          /* 帧尾不匹配，说明当前位置不是合法帧头，向后移动 1 字节继续找。 */
          parse_pos++;
        }
      }

      /* 把未处理完的尾部残留前移，留给下一次 USB 包继续拼接。 */
      if (parse_pos > 0U)
      {
        uint16_t remain = (uint16_t)(stream_len - parse_pos);
        if (remain > 0U)
        {
          memmove(stream_buf, &stream_buf[parse_pos], remain);
        }
        stream_len = remain;
      }
    }
  }
}
