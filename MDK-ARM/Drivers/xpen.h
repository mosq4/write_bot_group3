/**
  ******************************************************************************
  * @file           :
  * @author         :
  * @brief          : 电磁铁抬落笔控制 (PE5 GPIO 输出)
  * @attention      : HIGH = 落笔 (电磁铁通电), LOW = 抬笔 (电磁铁断电)
  ******************************************************************************
  */
#ifndef __XPEN_H
#define __XPEN_H

/* ------------------------------ Includes ------------------------------ */

#include "stm32f4xx_hal.h"

/* ------------------------------ Class ------------------------------ */

namespace xpen
{

class Pen
{
private:
    uint8_t state = 0;

public:
    void Init(void);
    void Down(void);
    void Up(void);
    uint8_t IsDown(void);
};

} // namespace xpen

#endif
