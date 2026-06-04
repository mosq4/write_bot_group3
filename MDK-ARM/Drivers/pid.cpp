/**
 ******************************************************************************
 * @file           :
 * @author         : Guo Xiang
 * @brief          : 
 * @date           : 2023/04/13
 ******************************************************************************
 * @attention
 *
 *
 ******************************************************************************
 */

/* ------------------------------ Includes ------------------------------ */

#include "pid.h"

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variables ------------------------------ */

/* ------------------------------ Functions ------------------------------ */

namespace pid
{
  Pid::Pid(float kp, float ki, float kd, float output_limit, float time_period_s)
  {
    this->kp = kp;
    this->ki = ki;
    this->kd = kd;
    this->output_limit = output_limit;
    this->time_period_s = time_period_s;
    this->integral = 0;
    this->derivative = 0;
    this->target = 0;
    this->feedback = 0;
    this->error = 0;
    this->error_last = 0;
    this->output = 0;
  }

  Pid::~Pid()
  {
  }

  void Pid::SetTarget(float target)
  {
    this->target = target;
  }

  void Pid::SetKp(float kp)
  {
    this->kp = kp;
  }

  void Pid::SetKi(float ki)
  {
    this->ki = ki;
  }

  void Pid::SetKd(float kd)
  {
    this->kd = kd;
  }

  void Pid::SetOutputLimit(float output_limit)
  {
    this->output_limit = output_limit;
  }

  float Pid::Calc(float feedback)
  {
    this->feedback = feedback;
    this->error = this->target - this->feedback;
    this->integral += this->error * this->time_period_s;
    this->derivative = (this->error - this->error_last) / this->time_period_s;
    this->output = this->kp * this->error + this->ki * this->integral + this->kd * this->derivative;
    this->error_last = this->error;
    if (this->output > this->output_limit)
    {
      this->output = this->output_limit;
      this->integral *= 0.99;
    }
    else if (this->output < -this->output_limit)
    {
      this->output = -this->output_limit;
      this->integral *= 0.99;
    }
    return this->output;
  }
} // namespace pid
