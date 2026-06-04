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
#ifndef __MY_RTOS_H
#define __MY_RTOS_H

/* ------------------------------ Includes ------------------------------ */

#include "cmsis_os2.h"

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variable Declarations ------------------------------ */

extern osThreadId_t defaultTaskHandle;
extern osThreadId_t debugTaskHandle;
extern osThreadId_t keyScanTaskHandle;
extern osThreadId_t usbRxTaskHandle;
/* ------------------------------ Typedef ------------------------------ */

/* ------------------------------ Class ------------------------------ */


#endif
