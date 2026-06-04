/**
  ******************************************************************************
  * @file           : 
  * @author         : Xiang Guo
  * @date           : 2023/xx/xx
  * @brief          : 
  ******************************************************************************
  * @attention
  *             
  *             
  ******************************************************************************
  */
#ifndef __XLINEARMODULE_H
#define __XLINEARMODULE_H

/* ------------------------------ Includes ------------------------------ */

#include "stm32f4xx_hal.h"
#include "xstepper.h"

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variable Declarations ------------------------------ */

/* ------------------------------ Typedef ------------------------------ */

/* ------------------------------ Class ------------------------------ */

namespace x_linear_module
{
  typedef enum
  {
    MODULE_MODE_IDLE,
    MODULE_MODE_VELOCITY,
    MODULE_MODE_POSITION,
    MODULE_MODE_ERROR,
  } ModuleMode_t;

  class LinearModule
  {
  public:
    /* 丝杠参数 */
    float lead;    // 导程，单位mm/rev
    //控制参数
    int8_t dir;    // 电机方向，由于物理正方向与接线和安装有关，用于调整电机期望的正方向
    float max_vel; // 最大速度，单位mm/s
    float acc;     // 加速度，单位mm/s^2

    /* 限位开关 */
    GPIO_TypeDef *limit_switch1_port;
    uint16_t limit_switch1_pin;
    GPIO_TypeDef *limit_switch2_port;
    uint16_t limit_switch2_pin;

    /* 直线模组状态 */
    ModuleMode_t mode = MODULE_MODE_IDLE;
    int64_t step_target_angle;

    xstepper::Stepper stepper;

    LinearModule(TIM_HandleTypeDef *p_htim, uint32_t channel, uint32_t tim_freq, float step_angle, float step_division,
                 GPIO_TypeDef *dir_port, uint16_t dir_pin, GPIO_TypeDef *n_enable_port, uint16_t n_enable_pin,
                 GPIO_TypeDef *limit_switch1_port, uint16_t limit_switch1_pin,
                 GPIO_TypeDef *limit_switch2_port, uint16_t limit_switch2_pin,
                 float lead);

    /**
      * @brief  设置直线模组运动参数，并使能PWM控制定时器
      * @author Xiang Guo
      * @param  dir: 电机方向，1为正方向，-1为负方向
      * @param  max_vel: 最大速度，单位mm/s
      * @param  acc: 加速度，单位mm/s^2
      * @retval none
      */
    void MotionConfig(int8_t dir, float max_vel, float acc);

    /**
      * @brief  设置直线模组运动模式
      * @author Xiang Guo
      * @param  mode: 运动模式，可选值为MODULE_MODE_VELOCIY，MODULE_MODE_POSITION，MODULE_MODE_IDLE和MODULE_MODE_ERROR
      * @retval none
      */
    void SetMode(ModuleMode_t mode);

    /**
      * @brief  覆盖直线模组当前位置
      * @author Xiang Guo
      * @param  position: 位置，单位mm
      * @retval none
      */
    void SetPosition(float position);

    /**
      * @brief  设置目标位置，目标速度为最大速度
      * @author Xiang Guo
      * @param  position: 目标位置，单位mm
      * @retval none
      */
    void SetTargetPosition(float position);

    /**
      * @brief  设置目标位置，同时设置运动过程的目标速度
      * @author Xiang Guo
      * @param  position: 目标位置，单位mm
      * @param  velocity: 目标速度，单位mm/s
      * @retval none
      */
    void SetTargetPositionWithVelocity(float position, float velocity);

    /**
      * @brief  设置目标速度，启用梯形加减速
      * @author Xiang Guo
      * @param  velocity: 目标速度，单位mm/s
      * @retval none
      */
    void SetTargetVelocity(float velocity);

    /**
      * @brief  设置目标速度，不启用梯形加减速
      * @author Xiang Guo
      * @param  velocity: 目标速度，单位mm/s
      * @retval none
      */
    void SetTargetVelocityHard(float velocity);

    /**
      * @brief  获取当前位置
      * @author Xiang Guo
      * @param  none
      * @retval none
      */
    float GetPosition(void);

    /**
      * @brief  控制回路，在PWM定时器中断中调用
      * @author Xiang Guo
      * @param  target_velocity_f 目标速度，单位：度/s
      * @retval none
      */
    void ControlLoop(void);
  };
  
}


#endif

