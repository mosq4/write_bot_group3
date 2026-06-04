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

/* ------------------------------ Includes ------------------------------ */

#include "xLinearModule.h"
#include "stm32f4xx_hal.h"
#include "arm_math.h"
#include <math.h>

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ variables ------------------------------ */

/* ------------------------------ Functions ------------------------------ */

namespace x_linear_module
{
  LinearModule::LinearModule(TIM_HandleTypeDef *p_htim, uint32_t channel, uint32_t tim_freq, float step_angle, float step_division,
                            GPIO_TypeDef *dir_port, uint16_t dir_pin, GPIO_TypeDef *n_enable_port, uint16_t n_enable_pin,
                            GPIO_TypeDef *limit_switch1_port, uint16_t limit_switch1_pin,
                            GPIO_TypeDef *limit_switch2_port, uint16_t limit_switch2_pin,
                            float lead)
      : stepper(p_htim, channel, tim_freq, step_angle, step_division, dir_port, dir_pin, n_enable_port, n_enable_pin),
        limit_switch1_port(limit_switch1_port), limit_switch1_pin(limit_switch1_pin),
        limit_switch2_port(limit_switch2_port), limit_switch2_pin(limit_switch2_pin),
        lead(lead)
  {
  }

  void LinearModule::MotionConfig(int8_t dir, float max_vel, float acc)
  {

    int32_t step_max_vel = (int32_t) (abs((max_vel  / lead * 360.0f * stepper.step_division / stepper.step_angle)));
    int32_t step_acc = (int32_t) (abs((acc / lead * 360.0f * stepper.step_division / stepper.step_angle)));
    this->stepper.MotionConfig(dir, step_max_vel, step_acc);
    this->dir = dir;
    this->max_vel = max_vel;
    this->acc = acc;  
  }

  void LinearModule::SetMode(ModuleMode_t mode)
  {
    this->mode = mode;
    switch (mode)
    {
      case MODULE_MODE_IDLE:
        this->stepper.SetMode(xstepper::STEPPER_MODE_IDLE);
        break;
      case MODULE_MODE_VELOCITY:
        this->stepper.SetMode(xstepper::STEPPER_MODE_VELOCITY);
        break;
      case MODULE_MODE_POSITION:
        this->stepper.SetMode(xstepper::STEPPER_MODE_POSITION);
        break;
      case MODULE_MODE_ERROR:
        this->stepper.SetMode(xstepper::STEPPER_MODE_IDLE);
        break;
      default:
        break;
    }
  }

  void LinearModule::SetPosition(float position)
  {
    this->stepper.SetAngle(position / lead * 360.0f);
  }

  void LinearModule::SetTargetPosition(float position)
  {
    this->stepper.SetTargetAngle(position / lead * 360.0f);
  }

  void LinearModule::SetTargetPositionWithVelocity(float position, float velocity)
  {
    this->stepper.SetTargetAngleWithVel(position / lead * 360.0f, velocity / lead * 360.0f);
  }

  void LinearModule::SetTargetVelocity(float velocity)
  {
    this->stepper.SetTargetVelocity(velocity / lead * 360.0f);
  }

  void LinearModule::SetTargetVelocityHard(float velocity)
  {
    this->stepper.SetVelocityHard(velocity / lead * 360.0f);
  }

  float LinearModule::GetPosition(void)
  {
    return (float)((float)(this->stepper.step_current_angle) * (float)(this->stepper.step_angle) * this->lead / this->stepper.step_division / 360.0f);
  }

  void LinearModule::ControlLoop(void)
  {
    // 限位检测
    this->stepper.ControlLoop();
  }
  
}

