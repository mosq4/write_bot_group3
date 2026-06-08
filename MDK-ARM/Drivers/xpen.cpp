/**
  ******************************************************************************
  * @file           :
  * @author         :
  * @brief          : 电磁铁抬落笔控制实现 (PE5 GPIO)
  ******************************************************************************
  */

/* ------------------------------ Includes ------------------------------ */

#include "xpen.h"
#include "main.h"

/* ------------------------------ Functions ------------------------------ */

namespace xpen
{

void Pen::Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    __HAL_RCC_GPIOE_CLK_ENABLE();
    GPIO_InitStruct.Pin = PEN_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_PULLDOWN;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(PEN_GPIO_Port, &GPIO_InitStruct);
    Up(); // 默认抬笔，安全状态
}

void Pen::Down(void)
{
    HAL_GPIO_WritePin(PEN_GPIO_Port, PEN_Pin, GPIO_PIN_SET);
    state = 1;
}

void Pen::Up(void)
{
    HAL_GPIO_WritePin(PEN_GPIO_Port, PEN_Pin, GPIO_PIN_RESET);
    state = 0;
}

uint8_t Pen::IsDown(void)
{
    return state;
}

} // namespace xpen
