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

#include "my_config.h"
#include "XYplatform.h"
#include "main.h"
#include "tim.h"
#include "xLinearModule.h"
#include "xkey.h"


/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variables ------------------------------ */

xkey::Key g_key[4] = {xkey::Key(KEY1_GPIO_Port, KEY1_Pin, GPIO_PIN_RESET),
                      xkey::Key(KEY2_GPIO_Port, KEY2_Pin, GPIO_PIN_RESET),
                      xkey::Key(KEY3_GPIO_Port, KEY3_Pin, GPIO_PIN_RESET),
                      xkey::Key(KEY4_GPIO_Port, KEY4_Pin, GPIO_PIN_RESET)};

// xstepper::Stepper g_stepper[3] = {
//     xstepper::Stepper(&htim8, TIM_CHANNEL_4, STIM_FREQ, 1.8f, 32,
//     DIR_M1_GPIO_Port, DIR_M1_Pin, nENBL_M1_GPIO_Port, nENBL_M1_Pin),
//     xstepper::Stepper(&htim3, TIM_CHANNEL_1, STIM_FREQ, 1.8f, 32,
//     DIR_M2_GPIO_Port, DIR_M2_Pin, nENBL_M2_GPIO_Port, nENBL_M2_Pin),
//     xstepper::Stepper(&htim4, TIM_CHANNEL_2, STIM_FREQ, 1.8f, 32,
//     DIR_M3_GPIO_Port, DIR_M3_Pin, nENBL_M3_GPIO_Port, nENBL_M3_Pin)};

x_linear_module::LinearModule g_linearModule[2] = {
    x_linear_module::LinearModule(
        &htim8, TIM_CHANNEL_4, STIM_FREQ, 1.8f, 32, DIR_M1_GPIO_Port,
        DIR_M1_Pin, nENBL_M1_GPIO_Port, nENBL_M1_Pin, SW1_GPIO_Port, SW1_Pin,
        SW2_GPIO_Port, SW2_Pin, 4.0f),
    x_linear_module::LinearModule(
        &htim3, TIM_CHANNEL_1, STIM_FREQ, 1.8f, 32, DIR_M2_GPIO_Port,
        DIR_M2_Pin, nENBL_M2_GPIO_Port, nENBL_M2_Pin, SW3_GPIO_Port, SW3_Pin,
        SW4_GPIO_Port, SW4_Pin, 4.0f)};

xy_platform::XYplatform g_xyPlatform(&g_linearModule[0], &g_linearModule[1],0.1f,100.0f, 2.0f, 0.0f, 0.0f, 0.01f);


/* ------------------------------ Functions ------------------------------ */
