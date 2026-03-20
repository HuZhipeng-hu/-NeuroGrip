#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械手 MG996R 舵机控制 (PCA9685 + openEuler)
支持：单通道测试 + 预设手势控制 (张开, ok, ✌, 握手, 转手腕)
"""

import time
import argparse
import sys

try:
    import smbus2 as smbus
except ImportError:
    try:
        import smbus
    except ImportError:
        print("请先安装 smbus2：  pip install smbus2")
        sys.exit(1)


# ── 常量与通道映射 ──────────────────────────────────────────────

PCA9685_ADDR     = 0x40
I2C_BUS_DEFAULT  = 7

PCA9685_MODE1    = 0x00
PCA9685_MODE2    = 0x01
PCA9685_PRESCALE = 0xFE
PCA9685_LED0_ON_L = 0x06

MODE1_RESTART = 0x80
MODE1_SLEEP   = 0x10
MODE1_AI      = 0x20
MODE2_OUTDRV  = 0x04

OSC_FREQ    = 25_000_000
PWM_STEPS   = 4096

SERVO_FREQ       = 50
SERVO_MIN_US     = 500     # 0°
SERVO_MAX_US     = 2500    # 180°
SERVO_RANGE_DEG  = 180

# 手指通道定义
CH_THUMB  = 0  # 大拇指
CH_PINKY  = 1  # 小拇指
CH_INDEX  = 2  # 食指
CH_RING   = 3  # 无名指
CH_MIDDLE = 4  # 中指
CH_WRIST  = 5  # 手腕

# 预设手势角度字典 (0度弯曲，180度伸开)
GESTURES = {
    # 张开：所有手指伸展
    "open": {CH_THUMB: 180, CH_INDEX: 180, CH_MIDDLE: 180, CH_RING: 180, CH_PINKY: 180},
    
    # OK：大拇指和食指弯曲相触，其余手指伸展
    "ok": {CH_THUMB: 0, CH_INDEX: 0, CH_MIDDLE: 180, CH_RING: 180, CH_PINKY: 180},
    
    # ✌ (剪刀手)：食指和中指伸展，其余弯曲
    "peace": {CH_THUMB: 0, CH_INDEX: 180, CH_MIDDLE: 180, CH_RING: 0, CH_PINKY: 0},
    
    # 握手预备：大拇指伸开，其余四指轻握 (弯曲)
    "handshake": {CH_THUMB: 180, CH_INDEX: 0, CH_MIDDLE: 0, CH_RING: 0, CH_PINKY: 0}
}


class SimplePCA9685Servo:
    """极简 PCA9685 + MG996R 控制"""

    def __init__(self, bus_number=I2C_BUS_DEFAULT, address=PCA9685_ADDR):
        self.bus = smbus.SMBus(bus_number)
        self.addr = address
        self._init()

    def _init(self):
        # 基本初始化 + 设置 50Hz
        self.bus.write_byte_data(self.addr, PCA9685_MODE2, MODE2_OUTDRV)
        self.bus.write_byte_data(self.addr, PCA9685_MODE1, MODE1_AI)

        # 计算预分频 → 50Hz
        prescale = round(OSC_FREQ / (PWM_STEPS * SERVO_FREQ)) - 1
        old_mode = self.bus.read_byte_data(self.addr, PCA9685_MODE1)
        self.bus.write_byte_data(self.addr, PCA9685_MODE1, old_mode | MODE1_SLEEP)
        self.bus.write_byte_data(self.addr, PCA9685_PRESCALE, prescale)
        self.bus.write_byte_data(self.addr, PCA9685_MODE1, old_mode)
        time.sleep(0.005)
        self.bus.write_byte_data(self.addr, PCA9685_MODE1, old_mode | MODE1_RESTART | MODE1_AI)

    def set_angle(self, channel: int, angle: float):
        """设置指定通道的角度 (0° ~ 180°)"""
        angle = max(0.0, min(SERVO_RANGE_DEG, float(angle)))

        # 角度 → 脉宽(μs) → ticks
        us = SERVO_MIN_US + (angle / SERVO_RANGE_DEG) * (SERVO_MAX_US - SERVO_MIN_US)
        period_us = 1_000_000 / SERVO_FREQ
        ticks = int(us * PWM_STEPS / period_us)
        ticks = max(0, min(4095, ticks))

        # 写入 PWM
        reg = PCA9685_LED0_ON_L + 4 * channel
        self.bus.write_i2c_block_data(self.addr, reg, [0, 0, ticks & 0xFF, ticks >> 8])

    def release(self, channel: int):
        """释放通道（停止输出）"""
        reg = PCA9685_LED0_ON_L + 4 * channel
        self.bus.write_i2c_block_data(self.addr, reg, [0, 0, 0, 0])

    def close(self):
        self.bus.close()

# ── 手势执行逻辑 ──────────────────────────────────────────────

def execute_gesture(servo, gesture_name):
    """执行静态手势"""
    print(f"执行手势: {gesture_name}")
    angles = GESTURES.get(gesture_name)
    if not angles:
        print(f"未知手势: {gesture_name}")
        return
        
    for channel, angle in angles.items():
        servo.set_angle(channel, angle)
    time.sleep(0.6) # 给舵机移动时间

def animate_wrist(servo):
    """动态转动手腕动作"""
    print("执行动作: 转手腕...")
    # 假设手腕初始在中立位 90度
    servo.set_angle(CH_WRIST, 90)
    time.sleep(0.5)
    
    # 转到 180度
    servo.set_angle(CH_WRIST, 180)
    time.sleep(0.8)
    
    # 转到 0度
    servo.set_angle(CH_WRIST, 0)
    time.sleep(0.8)
    
    # 回到 90度
    servo.set_angle(CH_WRIST, 120)
    time.sleep(0.5)


def sequence_demo(servo):
    """
    演示序列：张开 → OK → 张开 → ✌ → 张开 → 握手 → 张开 → 转手腕
    每个动作后都回到张开状态
    """
    print("=" * 50)
    print("开始手势序列演示")
    print("序列: 张开 → OK → 张开 → ✌ → 张开 → 握手 → 张开 → 转手腕")
    print("=" * 50)
    
    # 1. 张开
    print("\n[步骤 1/8]")
    execute_gesture(servo, "open")
    time.sleep(1)
    
    # 2. OK
    print("\n[步骤 2/8]")
    execute_gesture(servo, "ok")
    time.sleep(1)
    
    # 3. 张开
    print("\n[步骤 3/8]")
    execute_gesture(servo, "open")
    time.sleep(1)
    
    # 4. ✌ (peace)
    print("\n[步骤 4/8]")
    execute_gesture(servo, "peace")
    time.sleep(1)
    
    # 5. 张开
    print("\n[步骤 5/8]")
    execute_gesture(servo, "open")
    time.sleep(1)
    
    # 6. 握手
    print("\n[步骤 6/8]")
    execute_gesture(servo, "handshake")
    time.sleep(1)
    
    # 7. 张开
    print("\n[步骤 7/8]")
    execute_gesture(servo, "open")
    time.sleep(1)
    
    # 8. 转手腕
    print("\n[步骤 8/8]")
    animate_wrist(servo)
    
    print("\n" + "=" * 50)
    print("手势序列演示完成！")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="机械手预设手势与单舵机控制")
    parser.add_argument("-c", "--channel", type=int, help="单独控制的 PCA9685 通道号 (0-15)")
    parser.add_argument("-a", "--angle", type=float, help="单独控制的目标角度 (0.0 ~ 180.0)")
    parser.add_argument("-g", "--gesture", type=str, choices=['open', 'ok', 'peace', 'handshake', 'wrist'],
                        help="执行预设手势：张开(open), OK(ok), 剪刀手(peace), 握手(handshake), 转手腕(wrist)")
    parser.add_argument("--bus", type=int, default=I2C_BUS_DEFAULT,
                        help=f"I2C 总线编号，默认 {I2C_BUS_DEFAULT}")
    parser.add_argument("--release", action="store_true", help="只释放所有手指通道")
    parser.add_argument("--demo", action="store_true", help="运行完整手势序列演示")

    args = parser.parse_args()

    # 如果没有提供任何参数
    if not args.gesture and args.channel is None and not args.release and not args.demo:
        parser.print_help()
        sys.exit(0)

    print(f"总线: /dev/i2c-{args.bus}   地址: 0x{PCA9685_ADDR:02X}")

    try:
        servo = SimplePCA9685Servo(bus_number=args.bus)

        # 1. 释放通道逻辑
        if args.release:
            print("释放手指及手腕通道...")
            for ch in range(6):
                servo.release(ch)
            return

        # 2. 演示模式
        if args.demo:
            sequence_demo(servo)
            return

        # 3. 执行手势逻辑
        if args.gesture:
            if args.gesture == 'wrist':
                animate_wrist(servo)
            else:
                execute_gesture(servo, args.gesture)
        
        # 4. 单通道调试逻辑 (保留原版功能)
        elif args.channel is not None and args.angle is not None:
            print(f"通道: {args.channel} 设置角度 → {args.angle:.1f}°")
            servo.set_angle(args.channel, args.angle)
            time.sleep(0.6)

    except Exception as e:
        print(f"\n错误: {e}")
        print("请检查：")
        print("  1. 是否已安装 smbus2")
        print("  2. I2C 是否启用，设备是否存在")
        print("  3. PCA9685 接线和地址是否正确")
        sys.exit(1)

    finally:
        if 'servo' in locals():
            servo.close()


if __name__ == "__main__":
    main()