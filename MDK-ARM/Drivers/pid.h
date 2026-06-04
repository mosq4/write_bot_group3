/**
 ******************************************************************************
 * @file           :
 * @author         : Guo Xiang
 * @brief          : 本文件定义了一个PID类，用于PID控制
 * @date           : 2023/04/13
 ******************************************************************************
 * @attention
 *              本文件定义了一个PID类，用于PID控制，使用位置式PID算法。
 *              PID类中通过在输出饱和时对积分项进行衰减来防止积分饱和。
 ******************************************************************************
 */
#ifndef __PID_H
#define __PID_H

/* ------------------------------ Includes ------------------------------ */

/* ------------------------------ Defines ------------------------------ */

/* ------------------------------ Variable Declarations ------------------------------ */

/* ------------------------------ Typedef ------------------------------ */

/* ------------------------------ Class ------------------------------ */

namespace pid
{

  class Pid
  {
  public:
    float kp, ki, kd;
    float output_limit;

    float time_period_s;
    float integral;
    float derivative;

    float target;
    float feedback;
    float error;
    float error_last;

    float output;

    Pid(float kp, float ki, float kd, float output_limit, float time_period_s);
    ~Pid();
    void SetTarget(float target);
    void SetKp(float kp);
    void SetKi(float ki);
    void SetKd(float kd);
    void SetOutputLimit(float output_limit);
    float Calc(float feedback);
  };

} // namespace pid

#endif
