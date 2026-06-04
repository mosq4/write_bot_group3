/**
  ******************************************************************************
  * @file           :
  * @author         : Xiang Guo
  * @brief          : brief
  * @date           : 2023/05/07
  ******************************************************************************
  * @attention
  *
	*
  ******************************************************************************
  */
#ifndef __XKEY_H
#define __XKEY_H

/* ------------------------------ Includes ------------------------------ */

#include "stm32f4xx_hal.h"

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variable Declarations ------------------------------ */

/* ------------------------------ Typedef ------------------------------ */

/* ------------------------------ Class ------------------------------ */

namespace xkey
{

  class Key
  {
  private:
    uint8_t low_flag = 0;
    uint8_t button_clicked = 0;
    uint8_t button_released = 0;

    GPIO_TypeDef *key_port;
    uint16_t key_pin;

    // 按键按下的电平
    GPIO_PinState pressed_state;

  public:
    Key(GPIO_TypeDef *key_port, uint16_t key_pin, GPIO_PinState pressed_state);
    void update(void);
    uint8_t clicked(void);
    uint8_t released(void);
  };

} // namespace xkey


#endif
