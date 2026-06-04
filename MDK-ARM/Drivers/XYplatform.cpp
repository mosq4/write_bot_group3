/* ------------------------------ Includes ------------------------------ */
#include "XYplatform.h"
#include "arm_math.h"
#include "xLinearModule.h"
#include <math.h>

/* ------------------------------ Defines ------------------------------ */
#define abs(x) ((x) > 0 ? (x) : -(x))
#define POSITION_ERROR_THRESHOLD 0.01f
#define DEG_TO_RAD 0.01745329251994329577f

/* ------------------------------ variables ------------------------------ */

/* ------------------------------ Functions ------------------------------ */
static float LinearInterJudge(float x_real, float y_real, float x_target,
                              float y_target, float x_start, float y_start) {
  float x_e = x_target - x_start;
  float y_e = y_target - y_start;
  float x_i = x_real - x_start;
  float y_i = y_real - y_start;
  float f = x_e * y_i - x_i * y_e;
  return f;
}
static float CircularInterJudge(float x_real, float y_real, float center_x, float center_y, float radius) {
  float x_c = x_real - center_x;
  float y_c = y_real - center_y;
  float f = x_c * x_c + y_c * y_c - radius * radius;
  return f;
}
namespace xy_platform {
XYplatform::XYplatform(x_linear_module::LinearModule *x,
                       x_linear_module::LinearModule *y, float inter_step, float pid_limit_output,
                      float pid_kp, float pid_ki, float pid_kd,
                      float pid_time_period_s)
    : pos_pid_x(pid_kp, pid_ki, pid_kd, pid_limit_output, pid_time_period_s),
      pos_pid_y(pid_kp, pid_ki, pid_kd, pid_limit_output, pid_time_period_s),
      inter_step(inter_step) {
  this->x = x;
  this->y = y;
}

void XYplatform::MotionConfig(int8_t x_dir, int8_t y_dir, float max_vel,float acc) {
  this->x->MotionConfig(x_dir, max_vel, acc);
  this->y->MotionConfig(y_dir, max_vel, acc);
  this->max_vel = max_vel;
  this->acc = acc;
  this->x_dir = x_dir;
  this->y_dir = y_dir;
}

void XYplatform::FindHome(void) {
  this->mode = PLATFORM_MODE_FIND_HOME;
  this->x->SetMode(x_linear_module::MODULE_MODE_VELOCITY);
  this->y->SetMode(x_linear_module::MODULE_MODE_VELOCITY);
  this->x->SetTargetVelocity(-10.0f);
  this->y->SetTargetVelocity(-10.0f);
}

void XYplatform::MoveTo(float x, float y) {
  this->MoveTo(x, y, this->max_vel);
}

void XYplatform::MoveTo(float x, float y, float vel) {
  // 设置模式为手动模式
  this->mode = PLATFORM_MODE_MANUAL;
  this->x_target = x;
  this->y_target = y;

  // 在位置模式下，底层会根据目标位置自动决定方向，这里只传速度幅值。
  float dx = x - this->x_real;
  float dy = y - this->y_real;
  float abs_dx = abs(dx);
  float abs_dy = abs(dy);
  float max_delta = abs_dx > abs_dy ? abs_dx : abs_dy;

  float speed = abs(vel);


  float vel_x = 0.0f;
  float vel_y = 0.0f;
  if (max_delta > 0.0f) {
    vel_x = speed * abs_dx / max_delta;
    vel_y = speed * abs_dy / max_delta;
  }

  // 设置x和y目标位置
  this->x->SetMode(x_linear_module::MODULE_MODE_POSITION);
  this->y->SetMode(x_linear_module::MODULE_MODE_POSITION);
  this->x->SetTargetPositionWithVelocity(x, vel_x);
  this->y->SetTargetPositionWithVelocity(y, vel_y);
}

void XYplatform::MoveRelative(float dx, float dy, float vel) {
  float current_x = this->x->GetPosition();
  float current_y = this->y->GetPosition();
  this->MoveTo(current_x + dx, current_y + dy, vel);
}

void XYplatform::LinearInterpolation(float x, float y, float vel, float step) {
  // 从当前位置开始线性插补
  this->LinearInterpolation(this->x_real, this->y_real, x, y, vel, step);
}

void XYplatform::LinearInterpolation(float x_start, float y_start, float x_end,float y_end, float vel, float step) {
  // 先moveto到起始点
  this->MoveTo(x_start, y_start, vel);
  
  // 设置最终目标位置
  this->x_interpolation_final = x_end ;
  this->y_interpolation_final = y_end;
  
  // 设置插补参数
  this->inter_vel =vel;
  this->inter_step = abs(step);
  
  // 设置插补起始位置为起点
  this->x_interpolation_start = x_start;
  this->y_interpolation_start = y_start;
  this->x_interpolation_target = x_start;
  this->y_interpolation_target = y_start;
  
  // 标记正在等待到达起始点
  this->linear_waiting_start = true;
}

// 圆弧插补初始化函数：已清空，学生完成
void XYplatform::CircularInterpolation(float center_x, float center_y,
                                       float radius, float vel,
                                       float angle_start, float angle_end,
                                       bool clockwise, float step) {
    // 存储圆弧参数
    this->x_center = center_x;
    this->y_center = center_y;
    this->radius = radius;
    this->clockwise = clockwise;
    this->inter_vel = vel;
    this->inter_step = abs(step);

    // 计算起点和终点坐标
    float start_rad = angle_start * DEG_TO_RAD;
    float end_rad   = angle_end   * DEG_TO_RAD;
    float x_start = center_x + radius * cosf(start_rad);
    float y_start = center_y + radius * sinf(start_rad);
    float x_end   = center_x + radius * cosf(end_rad);
    float y_end   = center_y + radius * sinf(end_rad);

    // 设置最终目标
    this->x_interpolation_final = x_end;
    this->y_interpolation_final = y_end;

    // 设置插补起始位置
    this->x_interpolation_start = x_start;
    this->y_interpolation_start = y_start;
    this->x_interpolation_target = x_start;
    this->y_interpolation_target = y_start;

    // 先运动到圆弧起点，并标记等待
    this->MoveTo(x_start, y_start, vel);
    this->circular_waiting_start = true;
}

void XYplatform::ClosedLoopControl(float x_pos_ref, float y_pos_ref) {
  // 设置模式为闭环位置控制模式
  this->mode = PLATFORM_MODE_CLOSED_LOOP;
  // 设置x和y目标位置
  this->x_target = x_pos_ref;
  this->y_target = y_pos_ref;

  this->x->SetMode(x_linear_module::MODULE_MODE_VELOCITY);
  this->y->SetMode(x_linear_module::MODULE_MODE_VELOCITY);
}

void XYplatform::ControlLoop(void) {
  // 请完成此函数 Start

  // 更新x和y的实际位置
  this->x_real = this->x->GetPosition();
  this->y_real = this->y->GetPosition();

  // 根据模式进行不同的控制
  if (this->mode == PLATFORM_MODE_IDLE) {
  } 
  else if (this->mode == PLATFORM_MODE_MANUAL) {
    if (abs(this->x_real - this->x_target) <= POSITION_ERROR_THRESHOLD &&
        abs(this->y_real - this->y_target) <= POSITION_ERROR_THRESHOLD) {
      this->mode =PLATFORM_MODE_IDLE;
    }
    // 检查是否在等待线性插补启动
    if (this->linear_waiting_start) {
      // 检查是否已到达起始点
      if (abs(this->x_real - this->x_interpolation_start) <= POSITION_ERROR_THRESHOLD &&
          abs(this->y_real - this->y_interpolation_start) <= POSITION_ERROR_THRESHOLD) {
        // 已到达起始点，切换到线性插补模式
        this->mode = PLATFORM_MODE_LINEAR_INTERPOLATION;
        this->x->SetMode(x_linear_module::MODULE_MODE_POSITION);
        this->y->SetMode(x_linear_module::MODULE_MODE_POSITION);
        this->x_target = this->x_interpolation_final;
        this->y_target = this->y_interpolation_final;
        this->linear_waiting_start = false;
      }
    }
    // // 检查是否在等待圆弧插补启动
    else if (this->circular_waiting_start) {
      // 检查是否已到达起始点
      if (abs(this->x_real - this->x_interpolation_start) <= POSITION_ERROR_THRESHOLD &&
          abs(this->y_real - this->y_interpolation_start) <= POSITION_ERROR_THRESHOLD) {
        // 已到达起始点，切换到圆弧插补模式
        this->mode = PLATFORM_MODE_CIRCULAR_INTERPOLATION;
        this->x->SetMode(x_linear_module::MODULE_MODE_POSITION);
        this->y->SetMode(x_linear_module::MODULE_MODE_POSITION);
        this->x_target = this->x_interpolation_final;
        this->y_target = this->y_interpolation_final;
        this->circular_waiting_start = false;
      }
    }

  }
  else if (this->mode == PLATFORM_MODE_FIND_HOME) {
    if (abs(this->x_real) <= POSITION_ERROR_THRESHOLD &&
        abs(this->y_real) <= POSITION_ERROR_THRESHOLD&&
        this->x->mode == x_linear_module::MODULE_MODE_POSITION &&
        this->y->mode == x_linear_module::MODULE_MODE_POSITION) {
      this->mode = PLATFORM_MODE_IDLE;
    }
  } 
  else if (this->mode == PLATFORM_MODE_LINEAR_INTERPOLATION) {
    // 检查是否到达目标位置
    if (abs(this->x_real - this->x_target) <= POSITION_ERROR_THRESHOLD &&
        abs(this->y_real - this->y_target) <= POSITION_ERROR_THRESHOLD) {
      this->mode =PLATFORM_MODE_IDLE;
    }
    // //对水平/垂直直线做专门处理，避免 f==0 时插补轴不推进
    else if (abs(this->y_target - this->y_real)<= POSITION_ERROR_THRESHOLD) 
			{
       // 水平线：只推进 X，Y 保持常量
      if (abs(this->x_target - this->x_interpolation_target) <= this->inter_step) 
				{
        this->x_interpolation_target = this->x_target;
				} 
				else 
					{
        // @Additional code is required here.
					if (this->x_target > this->x_real) 
						{
							this->x_interpolation_target = this->x_real + this->inter_step;
						} 
					else 
						{
							this->x_interpolation_target = this->x_real - this->inter_step;
						}
				
					}
    }
    else if (abs(this->x_target - this->x_real)<= POSITION_ERROR_THRESHOLD) {
       // 垂直线：只推进 Y，X 保持常量
      if (abs(this->y_target - this->y_interpolation_target) <= this->inter_step) {
        this->y_interpolation_target = this->y_target;
      } else {
        // @Additional code is required here.
				if (this->y_target > this->y_real) 
						{
							this->y_interpolation_target = this->y_real + this->inter_step;
						} 
					else 
						{
							this->y_interpolation_target = this->y_real - this->inter_step;
						}
      }
    }
     //计算插补目标位置
    else if (this->x_target - this->x_real >0 &&this->y_target - this->y_real > 0) {
      // 第一象限
      if (LinearInterJudge(this->x_real, this->y_real, this->x_target,this->y_target, this->x_interpolation_start,this->y_interpolation_start) >= 0) {
        // 是否可以一步完成
        if (abs(this->x_target - this->x_interpolation_target) <=this->inter_step) {
          this->x_interpolation_target = this->x_target;
        } else {
          this->x_interpolation_target = this->x_real + this->inter_step;
        }
      } else {
        // 是否可以一步完成
        if (abs(this->y_target - this->y_interpolation_target) <=this->inter_step) {
          this->y_interpolation_target = this->y_target;
        } else {
          this->y_interpolation_target = this->y_real + this->inter_step;
        }
      }
    }
    else if (this->x_target - this->x_real <0 &&this->y_target - this->y_real >0) {
      // 第二象限
      if (LinearInterJudge(this->x_real, this->y_real, this->x_target,this->y_target, this->x_interpolation_start,this->y_interpolation_start) >= 0) {
        // 是否可以一步完成
        if (abs(this->y_target - this->y_interpolation_target) <=this->inter_step) {
          this->y_interpolation_target = this->y_target;
        } else {
          this->y_interpolation_target = this->y_real + this->inter_step;
        }
        
      } else {
        // 是否可以一步完成
        if (abs(this->x_target - this->x_interpolation_target) <=this->inter_step) {
          this->x_interpolation_target = this->x_target;
        } else {
          this->x_interpolation_target = this->x_real - this->inter_step;
        }
      }
    } else if (this->x_target - this->x_real < 0 &&this->y_target - this->y_real <0) {
      // 第三象限
      if (LinearInterJudge(this->x_real, this->y_real, this->x_target,this->y_target, this->x_interpolation_start,this->y_interpolation_start) >= 0) {
        // 是否可以一步完成
        if (abs(this->x_target - this->x_interpolation_target) <=this->inter_step) {
          this->x_interpolation_target = this->x_target;
        } else {
          this->x_interpolation_target = this->x_real - this->inter_step;
        }
      } else {
        // 是否可以一步完成
        if (abs(this->y_target - this->y_interpolation_target) <=this->inter_step) {
          this->y_interpolation_target = this->y_target;
        } else {
          this->y_interpolation_target = this->y_real - this->inter_step;
        }
      }
    } else if (this->x_target - this->x_real >0 &&this->y_target - this->y_real <0) {
      // 第四象限
      if (LinearInterJudge(this->x_real, this->y_real, this->x_target,this->y_target, this->x_interpolation_start,this->y_interpolation_start) >= 0) {
        // 是否可以一步完成
        if (abs(this->y_target - this->y_interpolation_target) <=this->inter_step) {
          this->y_interpolation_target = this->y_target;
        } else {
          this->y_interpolation_target = this->y_real - this->inter_step;
        }

      } else {
        // 是否可以一步完成
        if (abs(this->x_target - this->x_interpolation_target) <=this->inter_step) {
          this->x_interpolation_target = this->x_target;
        } else {
          this->x_interpolation_target = this->x_real + this->inter_step;
        }
      }
    }
    // 设定插补目标位置
    this->x->SetTargetPositionWithVelocity(this->x_interpolation_target,this->inter_vel);
    this->y->SetTargetPositionWithVelocity(this->y_interpolation_target,this->inter_vel);
  } 
  else if (this->mode == PLATFORM_MODE_CIRCULAR_INTERPOLATION) 
		{
    // 获取当前位置
    float x_real = this->x_real;
    float y_real = this->y_real;
    float x_end  = this->x_interpolation_final;
    float y_end  = this->y_interpolation_final;

    // 判断是否接近终点
    float dx_end = x_end - x_real;
    float dy_end = y_end - y_real;
    float dist_to_end = sqrtf(dx_end * dx_end + dy_end * dy_end);

    if (dist_to_end <= this->inter_step) 
			{
        // 直接以终点为目标，完成最后一步
        this->x_interpolation_target = x_end;
        this->y_interpolation_target = y_end;
			} 
			else 
				{
        // 圆弧插补逐点比较法
        float x_rel = x_real - this->x_center;
        float y_rel = y_real - this->y_center;
        float F = x_rel * x_rel + y_rel * y_rel - this->radius * this->radius;

        int8_t dx_sign = 0;
        int8_t dy_sign = 0;

        if (this->clockwise) 
					{ // 顺圆弧
            if (x_rel >= 0 && y_rel >= 0) 
							{ // SR1
                if (F >= 0) dy_sign = -1; 
								else dx_sign = 1;
							}
						else if (x_rel < 0 && y_rel >= 0) 
							{ // SR2
								if (F >= 0) dx_sign = 1;
								else dy_sign = 1;
							}
						else if (x_rel < 0 && y_rel < 0) 
							{ // SR3
								if (F >= 0) dy_sign = 1; 
								else dx_sign = -1;
							}
							else if (x_rel >= 0 && y_rel < 0) 
							{ // SR4
								if (F >= 0) dx_sign = -1; 
								else dy_sign = -1;
							}
					} 
				else 
					{ // 逆圆弧
            if (x_rel >= 0 && y_rel >= 0)
							{ // NR1
                if (F >= 0) dx_sign = -1;
								else dy_sign = 1;
							} 
							else if (x_rel < 0 && y_rel >= 0) 
								{ // NR2
                if (F >= 0) dy_sign = -1; 
								else dx_sign = -1;
								} 
							else if (x_rel < 0 && y_rel < 0) 
								{ // NR3
                if (F >= 0) dx_sign = 1; 
								else dy_sign = -1;
								} 
								else if (x_rel >= 0 && y_rel < 0) 
								{ // NR4
                if (F >= 0) dy_sign = 1;
								else dx_sign = -1;
								}
        }

        this->x_interpolation_target = x_real + dx_sign * this->inter_step;
        this->y_interpolation_target = y_real + dy_sign * this->inter_step;
    }

    // 发送插补目标位置与速度
    this->x->SetTargetPositionWithVelocity(this->x_interpolation_target, this->inter_vel);
    this->y->SetTargetPositionWithVelocity(this->y_interpolation_target, this->inter_vel);

    // 到达终点后切换为空闲
    if (fabsf(x_real - x_end) <= POSITION_ERROR_THRESHOLD &&
        fabsf(y_real - y_end) <= POSITION_ERROR_THRESHOLD &&
        this->x->mode == x_linear_module::MODULE_MODE_POSITION &&
        this->y->mode == x_linear_module::MODULE_MODE_POSITION) {
        this->mode = PLATFORM_MODE_IDLE;
    }
	}
  else if (this->mode == PLATFORM_MODE_CLOSED_LOOP) {
    // 判断是否到达目标位置
    if (abs(this->x_real - this->x_target) <= POSITION_ERROR_THRESHOLD &&
        abs(this->y_real - this->y_target) <= POSITION_ERROR_THRESHOLD) {
      this->x->SetTargetVelocity(0);
      this->y->SetTargetVelocity(0);
      this->mode = PLATFORM_MODE_IDLE;
      // 清零PID积分项
      this->pos_pid_x.integral = 0;
      this->pos_pid_y.integral = 0;
      return;
    }
    // 计算x和y的目标速度
    float vel_x = pos_pid_x.Calc(this->x_real);
    float vel_y = pos_pid_y.Calc(this->y_real);
    // 设置x和y的目标速度
    this->x->SetTargetVelocity(vel_x);
    this->y->SetTargetVelocity(vel_y);
  }

  // 请完成此函数 End
}

void XYplatform::Stop(void) {
  this->mode = PLATFORM_MODE_IDLE;
  this->x->SetTargetVelocityHard(0.0f);
  this->y->SetTargetVelocityHard(0.0f);
  this->x->SetMode(x_linear_module::MODULE_MODE_IDLE);
  this->y->SetMode(x_linear_module::MODULE_MODE_IDLE);
  this->pos_pid_x.integral = 0;
  this->pos_pid_y.integral = 0;
}

void XYplatform::GetStatus(float *curr_x, float *curr_y, uint8_t *status) {
  if (curr_x != nullptr) {
    *curr_x = this->x->GetPosition();
  }
  if (curr_y != nullptr) {
    *curr_y = this->y->GetPosition();
  }

  if (status != nullptr) {
    if (this->x->mode == x_linear_module::MODULE_MODE_ERROR ||
        this->y->mode == x_linear_module::MODULE_MODE_ERROR) {
      *status = 0xFF;
    } else if (this->mode == PLATFORM_MODE_FIND_HOME) {
      *status = 0x01;
    } else if (this->mode == PLATFORM_MODE_LINEAR_INTERPOLATION ||this->mode == PLATFORM_MODE_CIRCULAR_INTERPOLATION ||this->mode == PLATFORM_MODE_CLOSED_LOOP) {
      *status = 0x02;
    } 
    else if(this->mode==PLATFORM_MODE_MANUAL)
    {
      *status=0x03;
    }
    else {
      *status = 0x00;
    }
  }
}
} // namespace xy_platform