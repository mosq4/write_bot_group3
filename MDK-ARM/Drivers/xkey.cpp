/**
  ******************************************************************************
  * @file           :
  * @author         : Xiang Guo
  * @brief          : 
  * @date					  : 2023/05/07
  ******************************************************************************
  * @attention
  *
  *
  ******************************************************************************
  */

/* ------------------------------ Includes ------------------------------ */

#include "xkey.h"

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variables ------------------------------ */

/* ------------------------------ Functions ------------------------------ */

namespace xkey
{

  Key::Key(GPIO_TypeDef *key_port, uint16_t key_pin, GPIO_PinState pressed_state)
  {
    this->key_port = key_port;
    this->key_pin = key_pin;
    this->pressed_state = pressed_state;
  }

  void Key::update(void)
  {
    if (HAL_GPIO_ReadPin(key_port, key_pin) == pressed_state)
    {
      if (low_flag == 0)
      {
        button_clicked = 1;
        low_flag = 1;
      }
    }
    else
    {
			low_flag = 0;
      if (button_clicked == 1)
      {
        button_released = 1;
        button_clicked = 0;
      }
    }
  }

  uint8_t Key::clicked(void)
  {
    uint8_t temp = this->button_clicked;
    this->button_clicked = 0;
    return temp;
  }

  uint8_t Key::released(void)
  {
    uint8_t temp = this->button_released;
    this->button_released = 0;
    return temp;
  }
} // namespace xkey

