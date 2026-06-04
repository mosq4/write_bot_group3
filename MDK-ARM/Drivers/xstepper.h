/**
  ******************************************************************************
  * @file           : 
  * @author         : Xiang Guo
  * @brief          : brief
  ******************************************************************************
  * @attention
  *
  ******************************************************************************
  */
#ifndef __XSTEPPER_H
#define __XSTEPPER_H

/* ------------------------------ Includes ------------------------------ */

#include "stm32f4xx_hal.h"

/* ------------------------------ Defines ------------------------------ */

#define STEPPER_PI 3.1415926535897932384626433832795f

/* ------------------------------ Variable Declarations ------------------------------ */

/* ------------------------------ Typedef ------------------------------ */

/* ------------------------------ Class ------------------------------ */

namespace xstepper
{
  typedef enum
  {
    STEPPER_MODE_IDLE,
    STEPPER_MODE_VELOCITY,
    STEPPER_MODE_POSITION,
  } StepperMode_t;

	class Stepper
  {
  public:
    /* PWM生成定时器 */
    TIM_HandleTypeDef *p_htim;
    uint32_t channel;
    uint32_t tim_freq;

    /* 步进电机参数 */
    float step_angle;    // 步距角
    float step_division; // 细分数

    /* 电机控制参数 */
    int8_t dir;               // 电机方向，由于物理正方向与接线和安装有关，用于调整电机期望的正方向
    int32_t step_max_vel; // 最大速度
    int32_t step_acc;    // 梯形加速度

    /* 电机控制引脚 */
    GPIO_TypeDef *dir_port;
    uint16_t dir_pin;
    GPIO_TypeDef *n_enable_port;
    uint16_t n_enable_pin;

    /* 电机状态 */
    StepperMode_t mode = STEPPER_MODE_IDLE;
    bool is_running = 0;
    int64_t step_target_angle; // 目标角度
    int64_t step_current_angle;
    int32_t step_target_velocity;
    int32_t step_current_velocity;

    /* 配置函数 */
    Stepper(TIM_HandleTypeDef *p_htim, uint32_t channel, uint32_t tim_freq, float step_angle, float step_division, GPIO_TypeDef *dir_port, uint16_t dir_pin, GPIO_TypeDef *n_enable_port, uint16_t n_enable_pin);

    /**
      * @brief  电机参数配置函数，包括电机方向、最大速度、加速度等，同时使能PWM定时器
      * @author Xiang Guo
      * @param  dir 电机方向，可选值为1或-1
      * @param  step_max_vel 最大速度，单位：pulse/s
      * @param  step_acc 加速度，单位：pulse/s^2
      * @retval none
      */
    void MotionConfig(int8_t dir, uint32_t step_max_vel, uint32_t step_acc);

    /* 电机控制函数 */
    /**
      * @brief  设置电机模式
      * @author Xiang Guo
      * @param  mode 电机模式，可选值为STEPPER_MODE_IDLE、STEPPER_MODE_VELOCIY、STEPPER_MODE_POSITION
      * @retval none
      */
    void SetMode(StepperMode_t mode);

    /**
      * @brief  速度控制模式下设置目标速度，使用梯形加减速
      * @author Xiang Guo
      * @param  target_velocity_f 目标速度，单位：度/s
      * @retval none
      */
    void SetTargetVelocity(float target_velocity_f);

    /**
      * @brief  速度控制模式下强制设置目标速度，不使用加减速
      * @author Xiang Guo
      * @param  target_velocity_f 目标速度，单位：度/s
      * @retval none
      */
    void SetVelocityHard(float target_velocity_f);

    /**
      * @brief  位置控制模式下设置目标角度，目标速度为最大速度
      * @author Xiang Guo
      * @param  target_angle_f 目标角度，单位：度
      * @retval none
      */
    void SetTargetAngle(float target_angle_f);

    /**
      * @brief  位置控制模式下设置目标角度，同时设置目标速度
      * @author Xiang Guo
      * @param  target_angle_f 目标角度，单位：度
      * @param  target_velocity_f 目标速度，单位：度/s
      * @retval none
      */
    void SetTargetAngleWithVel(float target_angle_f, float target_velocity_f);

    /**
      * @brief  设置当前角度
      * @author Xiang Guo
      * @param  angle_f 当前角度，单位：度
      * @retval none
      */
    void SetAngle(float angle_f);

    /**
      * @brief  控制回路，在PWM定时器中断中调用
      * @author Xiang Guo
      * @param  none
      * @retval none
      */
    void ControlLoop(void);

  private:
    int32_t step_position_target_velocity;

    /* 电机控制函数 */
    void SetPWM(uint32_t pwm_freq);
    void OutputStepVelocity(int32_t step_velocity);
    int32_t VelocityLoop(void);
    int32_t PositionLoop(void);
  };
}	// namespace xstepper


#endif

