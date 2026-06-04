/**
  ******************************************************************************
  * @file           : 
  * @author         : Xiang Guo
  * @brief          : 
	* @date           : 2023/05/04
  ******************************************************************************
  * @attention
  *             
  *
  ******************************************************************************
  */

/* ------------------------------ Includes ------------------------------ */

#include "xstepper.h"
#include "stm32f4xx_hal.h"

/* ------------------------------ Defines ------------------------------ */

#define abs(x) ((x) > 0 ? (x) : -(x))

/* ------------------------------ Variables ------------------------------ */

/* ------------------------------ Functions ------------------------------ */

namespace xstepper
{
  Stepper::Stepper(TIM_HandleTypeDef *p_htim, uint32_t channel, uint32_t tim_freq, float step_angle, float step_division, GPIO_TypeDef *dir_port, uint16_t dir_pin, GPIO_TypeDef *n_enable_port, uint16_t n_enable_pin)
  : p_htim(p_htim), channel(channel), tim_freq(tim_freq), step_angle(step_angle), 
  step_division(step_division), dir_port(dir_port), dir_pin(dir_pin), n_enable_port(n_enable_port), n_enable_pin(n_enable_pin)
  {}

  void Stepper::MotionConfig(int8_t dir, uint32_t step_max_vel, uint32_t step_acc)
  {
    this->dir = dir;
    this->step_max_vel = step_max_vel;
    this->step_acc = step_acc;
    HAL_TIM_Base_Start_IT(this->p_htim);
  }

  void Stepper::SetMode(StepperMode_t mode)
  {
    this->mode = mode;
    if (mode == STEPPER_MODE_IDLE)
    {
      HAL_GPIO_WritePin(this->n_enable_port, this->n_enable_pin, GPIO_PIN_SET);
      this->is_running = false;
    }
    else
    {
      HAL_GPIO_WritePin(this->n_enable_port, this->n_enable_pin, GPIO_PIN_RESET);
    }
  }

  void Stepper::SetTargetAngle(float target_angle_f)
  {//此处位置环的速度恒为正值，在位置环中根据当前位置与目标位置的关系自动判断运动方向
    this->step_target_angle = (int64_t) (target_angle_f * this->step_division / this->step_angle);
    this->step_position_target_velocity = this->step_max_vel;
  }

  void Stepper::SetTargetAngleWithVel(float target_angle_f, float target_velocity_f)
  {
    //此处位置环的速度恒为正值，在位置环中根据当前位置与目标位置的关系自动判断运动方向
    this->step_target_angle = (int64_t) (target_angle_f * this->step_division / this->step_angle);
    this->step_position_target_velocity = (int32_t) (abs((target_velocity_f * this->step_division / this->step_angle)));
    this->step_position_target_velocity = this->step_position_target_velocity < this->step_max_vel ? this->step_position_target_velocity : this->step_max_vel  ;
  }

  void Stepper::SetTargetVelocity(float target_velocity_f)
  {
    //此处速度环的速度可以为正值也可以为负值，正值表示与坐标轴方向一致的运动，负值表示与坐标轴方向相反的运动
    int32_t step_velocity = (int32_t) (target_velocity_f * this->step_division / this->step_angle);
    this->step_target_velocity = abs(step_velocity) < this->step_max_vel ? step_velocity : (this->step_max_vel * target_velocity_f / abs(target_velocity_f));
  }

  void Stepper::SetVelocityHard(float target_velocity_f)
  {
    //此处速度环的速度可以为正值也可以为负值，正值表示与坐标轴方向一致的运动，负值表示与坐标轴方向相反的运动
    int32_t step_velocity = (int32_t) (target_velocity_f * this->step_division / this->step_angle);
    this->step_target_velocity = abs(step_velocity) < this->step_max_vel ? step_velocity : (this->step_max_vel * target_velocity_f / abs(target_velocity_f));
    this->step_current_velocity = this->step_target_velocity;
  }

  void Stepper::SetAngle(float angle_f)
  {
    this->step_current_angle = (int64_t) (angle_f * this->step_division / this->step_angle);
  }

  void Stepper::SetPWM(uint32_t pwm_freq)
  {
    if (pwm_freq == 0)
    {
      __HAL_TIM_SET_AUTORELOAD(this->p_htim, 999);
      __HAL_TIM_SET_COMPARE(this->p_htim, this->channel, 0);
      // HAL_TIM_PWM_Stop_IT(this->p_htim, this->channel);
      this->is_running = false;
      return;
    }
    uint32_t arr = (this->tim_freq / pwm_freq);
    if (arr == 0)
    {
      arr = 1;
    }
    --arr;
    if (arr > 0xFFFF)
    {
      __HAL_TIM_SET_AUTORELOAD(this->p_htim, 0xFFFF);
      __HAL_TIM_SET_COMPARE(this->p_htim, this->channel, 0x7FFF);
      __HAL_TIM_SET_COUNTER(this->p_htim, 0);
      HAL_TIM_PWM_Start_IT(this->p_htim, this->channel);
      this->is_running = true;
    }
    else
    {
      __HAL_TIM_SET_AUTORELOAD(this->p_htim, arr);
      __HAL_TIM_SET_COMPARE(this->p_htim, this->channel, (arr + 1) / 2);
      __HAL_TIM_SET_COUNTER(this->p_htim, 0);
      HAL_TIM_PWM_Start_IT(this->p_htim, this->channel);
      this->is_running = true;
    }
  }

  void Stepper::OutputStepVelocity(int32_t step_velocity)
  {
    //注意这里的dir为电机的正反转方向，正转方向与坐标轴方向一致即为1，反转方向与坐标轴方向相反即为-1
    int32_t real_step_velocity = this->dir * step_velocity; // 转换为实际步进电机的速度
    if (real_step_velocity > 0)
    {
      HAL_GPIO_WritePin(this->dir_port, this->dir_pin, GPIO_PIN_SET);
    }
    else  
    {
      HAL_GPIO_WritePin(this->dir_port, this->dir_pin, GPIO_PIN_RESET);
    }
    this->SetPWM(abs(real_step_velocity));
  }

  int32_t Stepper::VelocityLoop(void)
  {
    // 按照当前pwm频率，计算当前加速度脉冲数
    uint32_t pwm_freq = this->tim_freq / (__HAL_TIM_GET_AUTORELOAD(this->p_htim) + 1);
    int32_t acc = this->step_acc / pwm_freq;
    if ((this->step_current_velocity + acc) < this->step_target_velocity)
    {
      this->step_current_velocity += acc;
    }
    else if ((this->step_current_velocity - acc) > this->step_target_velocity)
    {
      this->step_current_velocity -= acc;
    }
    else
    {
      this->step_current_velocity = this->step_target_velocity;
    }
    return this->step_current_velocity;
  }

  int32_t Stepper::PositionLoop(void)
  {
    // 判断是否到达目标位置
    if (this->step_current_angle == this->step_target_angle)
    {

      this->step_target_velocity = 0;
      this->step_current_velocity = 0;
      return 0;
    }

    // 判断当前速度方向
    int32_t vel_dir;
    if (this->step_target_angle > this->step_current_angle)
    {
      vel_dir = 1;
    }
    else
    {
      vel_dir = -1;
    }

    // 判断当前加减速状态
    // 计算减速区域长度
    uint32_t acc_len = (this->step_current_velocity * this->step_current_velocity) / (2 * this->step_acc);
    // 计算当前位置与目标位置的距离
    uint32_t pos_diff = abs(this->step_target_angle - this->step_current_angle);

    // 判断是否需要减速，在减速区域则目标速度为0，否则为设定速度
    if (pos_diff < acc_len)
    {
      this->step_target_velocity = 0;
    }
    else
    {
      this->step_target_velocity = vel_dir * this->step_position_target_velocity;
    }

    return this->VelocityLoop();
  }

  void Stepper::ControlLoop(void)
  {
    /* 更新电机状态 */
    if (this->is_running)
    {
      this->step_current_angle += this->step_current_velocity > 0 ? 1 : -1;
    }

    /* 运行控制回路 */
    switch (this->mode)
    {
      case STEPPER_MODE_IDLE:
        this->OutputStepVelocity(0);
        break;
      case STEPPER_MODE_VELOCITY:
        this->OutputStepVelocity(this->VelocityLoop());
        break;
      case STEPPER_MODE_POSITION:
        this->OutputStepVelocity(this->PositionLoop());
        break;
      default:
        break;
    }
  }
}
