/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2023 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f4xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define STIM_FREQ 1000000.0f
#define SW2_Pin GPIO_PIN_2
#define SW2_GPIO_Port GPIOE
#define SW2_EXTI_IRQn EXTI2_IRQn
#define SW3_Pin GPIO_PIN_3
#define SW3_GPIO_Port GPIOE
#define SW3_EXTI_IRQn EXTI3_IRQn
#define SW4_Pin GPIO_PIN_4
#define SW4_GPIO_Port GPIOE
#define SW4_EXTI_IRQn EXTI4_IRQn
#define DIR_M3_Pin GPIO_PIN_12
#define DIR_M3_GPIO_Port GPIOD
#define nENBL_M3_Pin GPIO_PIN_14
#define nENBL_M3_GPIO_Port GPIOD
#define DIR_M2_Pin GPIO_PIN_15
#define DIR_M2_GPIO_Port GPIOD
#define nENBL_M2_Pin GPIO_PIN_7
#define nENBL_M2_GPIO_Port GPIOC
#define DIR_M1_Pin GPIO_PIN_8
#define DIR_M1_GPIO_Port GPIOC
#define nENBL_M1_Pin GPIO_PIN_8
#define nENBL_M1_GPIO_Port GPIOA
#define LED4_Pin GPIO_PIN_10
#define LED4_GPIO_Port GPIOC
#define LED3_Pin GPIO_PIN_11
#define LED3_GPIO_Port GPIOC
#define LED2_Pin GPIO_PIN_12
#define LED2_GPIO_Port GPIOC
#define LED1_Pin GPIO_PIN_0
#define LED1_GPIO_Port GPIOD
#define KEY4_Pin GPIO_PIN_1
#define KEY4_GPIO_Port GPIOD
#define KEY3_Pin GPIO_PIN_2
#define KEY3_GPIO_Port GPIOD
#define KEY2_Pin GPIO_PIN_3
#define KEY2_GPIO_Port GPIOD
#define KEY1_Pin GPIO_PIN_4
#define KEY1_GPIO_Port GPIOD
#define SW1_Pin GPIO_PIN_1
#define SW1_GPIO_Port GPIOE
#define SW1_EXTI_IRQn EXTI1_IRQn

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
