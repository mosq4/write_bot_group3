#include "xusb.h"
#include "main.h"
#include "my_config.h"
#include "usbd_cdc_if.h"

/**
 * @brief  校验和计算（XOR）
 */
static inline uint8_t usb_cmd_calc_checksum(uint8_t cmd, uint8_t data_len, const uint8_t *data)
{
    uint8_t checksum = cmd ^ data_len;
    for (int i = 0; i < data_len; i++) {
        checksum ^= data[i];
    }
    return checksum;
}

/**
 * @brief  打包并发送应答帧
 * 
 * 使用示例：
 * uint8_t status_data[10];
 * // 填充状态数据...
 * usb_send_response(CMD_STATUS_RESPONSE, status_data, 10);
 */
void usb_send_response(uint8_t cmd, const uint8_t *data, uint8_t data_len)
{
    /* 
     * 帧格式: [HEADER] [CMD] [LEN] [DATA...] [CHECKSUM] [TAIL]
     * 需要通过 CDC_Transmit_FS 发送
     */
    uint8_t tx_buf[256];
    uint8_t checksum = usb_cmd_calc_checksum(cmd, data_len, (uint8_t*)data);
    
    int idx = 0;
    tx_buf[idx++] = FRAME_HEADER;
    tx_buf[idx++] = cmd;
    tx_buf[idx++] = data_len;
    
    if (data_len > 0) {
        memcpy(&tx_buf[idx], data, data_len);
        idx += data_len;
    }
    
    tx_buf[idx++] = checksum;
    tx_buf[idx++] = FRAME_TAIL;
    
    CDC_Transmit_FS(tx_buf, idx);
    /* 外部调用：CDC_Transmit_FS(tx_buf, idx); */
}

int usb_parse_command(const uint8_t *frame, uint16_t frame_len,
                      uint8_t *cmd, uint8_t **data, uint8_t *data_len)
{
    if ((frame == nullptr) || (cmd == nullptr) || (data == nullptr) || (data_len == nullptr)) {
        return 0;
    }

    if (frame_len < 5) return 0;
    
    if (frame[0] != FRAME_HEADER || frame[frame_len-1] != FRAME_TAIL) {
        return 0;
    }
    
    *cmd = frame[1];
    *data_len = frame[2];
    if (frame_len != (uint16_t)(*data_len) + 5U) {
        return 0;
    }
    *data = (uint8_t*)&frame[3];
    
    /* 校验校验和 */
    uint8_t expected_checksum = usb_cmd_calc_checksum(*cmd, *data_len, *data);
    uint8_t actual_checksum = frame[3 + *data_len];
    
    if (expected_checksum != actual_checksum) {
        return 0;
    }
    
    return 1;
}

/**
 * @brief  处理命令的主函数
 * 
 * 需要用户实现以下外部函数：
 * - xy_platform_home()  : 回零
 * - xy_platform_move_abs(x, y, speed) : 绝对位移
 * - xy_platform_move_rel(dx, dy, speed) : 相对位移
 * - xy_platform_line_interp(...) : 直线插补
 * - xy_platform_arc_interp(...) : 圆弧插补
 * - xy_platform_stop() : 停止
 * - xy_platform_get_status(x, y, status, error) : 获取状态
 */
void usb_handle_command(uint8_t cmd, uint8_t *data, uint8_t data_len)
{
    float x, y, dx, dy, speed;
    uint16_t speed_int;
    HAL_GPIO_TogglePin(LED3_GPIO_Port, LED3_Pin); // 调试用：每收到一个命令就切换一次LED状态
    switch (cmd)
    {
        case CMD_HOME:
            /* 回零命令 */
            // xy_platform_home();
            g_xyPlatform.FindHome();
            break;
        
        case CMD_MOVE_ABS:
            /* 绝对位移: data = [x(4B) y(4B) speed(2B)] */
            if (data_len >= 10) {
                memcpy(&x, &data[0], 4);
                memcpy(&y, &data[4], 4);
                memcpy(&speed_int, &data[8], 2);
                g_xyPlatform.MoveTo(x, y, (float)speed_int);
            }
            break;
        
        case CMD_MOVE_REL:
            /* 相对位移 */
            if (data_len >= 10) {
                memcpy(&dx, &data[0], 4);
                memcpy(&dy, &data[4], 4);
                memcpy(&speed_int, &data[8], 2);
                g_xyPlatform.MoveRelative(dx, dy, (float)speed_int);
            }
            break;
        
        case CMD_LINE_INTERP:
            /* 直线插补: [x1(4B) y1(4B) x2(4B) y2(4B) speed(2B)]
               注意：x1/y1 保留读取但不再使用，插补从当前实际位置开始，
               避免"等待到达起始点"导致 G-code 逐段执行延迟叠加。 */
            if (data_len >= 18) {
                float x1, y1, x2, y2;
                memcpy(&x1, &data[0], 4);
                memcpy(&y1, &data[4], 4);
                memcpy(&x2, &data[8], 4);
                memcpy(&y2, &data[12], 4);
                memcpy(&speed_int, &data[16], 2);
                (void)x1; (void)y1;
                g_xyPlatform.LinearInterpolation(x2, y2,
                                                 (float)speed_int,
                                                 g_xyPlatform.inter_step);
            }
            break;
        
        case CMD_ARC_INTERP:
            /* 圆弧插补: [xc(4B) yc(4B) radius(4B) angle_start(4B) angle_end(4B) speed(2B)] */
            if (data_len >= 23) {
                float xc, yc, radius, angle_start, angle_end;
                bool clockwise;
                memcpy(&xc, &data[0], 4);
                memcpy(&yc, &data[4], 4);
                memcpy(&radius, &data[8], 4);
                memcpy(&angle_start, &data[12], 4);
                memcpy(&angle_end, &data[16], 4);
                memcpy(&clockwise, &data[20], 1);
                memcpy(&speed_int, &data[21], 2);
                g_xyPlatform.CircularInterpolation(xc, yc, radius,
                                                   (float)speed_int, angle_start, angle_end, clockwise,
                                                   g_xyPlatform.inter_step);
            }
            break;
        
        case CMD_STOP:
            /* 停止 */
            g_xyPlatform.Stop();
            g_pen.Up(); // 紧急停止时抬笔
            break;
        
        case CMD_QUERY_STATUS:
            /* 查询状态：需要回复 STATUS_RESPONSE */
            {
                float curr_x = 0, curr_y = 0;
                uint8_t status = 0;
                
                g_xyPlatform.GetStatus(&curr_x, &curr_y, &status);
                
                /* 打包响应 */
                uint8_t response[10];
                memcpy(&response[0], &curr_x, 4);
                memcpy(&response[4], &curr_y, 4);
                response[8] = status;
                response[9] = 0;
                
                usb_send_response(CMD_STATUS_RESPONSE, response, 10);
            }
            break;
        
        case CMD_SERVO:
            /* 舵机控制: data = [id(1B) angle(4B float)] */
            if (data_len >= 5) {
                uint8_t servo_id = data[0];
                float angle;
                memcpy(&angle, &data[1], 4);
                if (servo_id == 1) {
                    if (angle > 45.0f)
                        g_pen.Down();
                    else
                        g_pen.Up();
                }
            }
            break;
        
        case CMD_PEN:
            /* 抬落笔: data = [state(1B)]  0=抬笔 1=落笔 */
            if (data_len >= 1) {
                if (data[0])
                    g_pen.Down();
                else
                    g_pen.Up();
            }
            break;
        
        default:
            break;
    }
}
