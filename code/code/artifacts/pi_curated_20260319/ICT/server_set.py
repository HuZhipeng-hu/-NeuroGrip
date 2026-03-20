#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版 MG996R 舵机控制 (PCA9685 + openEuler)
只保留：指定通道 + 指定角度
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


# ── 常量 ────────────────────────────────────────────────

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


def main():
    parser = argparse.ArgumentParser(description="MG996R 舵机简易控制")
    parser.add_argument("-c", "--channel", type=int, default=0,
                        help="PCA9685 通道号 (0-15)，默认 0")
    parser.add_argument("-a", "--angle", type=float, required=True,
                        help="目标角度 (0.0 ~ 180.0)")
    parser.add_argument("--bus", type=int, default=I2C_BUS_DEFAULT,
                        help=f"I2C 总线编号，默认 {I2C_BUS_DEFAULT}")
    parser.add_argument("--release", action="store_true",
                        help="只释放通道，不设置角度")

    args = parser.parse_args()

    print(f"总线: /dev/i2c-{args.bus}   地址: 0x{PCA9685_ADDR:02X}")
    print(f"通道: {args.channel}   ", end="")

    try:
        servo = SimplePCA9685Servo(bus_number=args.bus)

        if args.release:
            print(f"释放通道 {args.channel}")
            servo.release(args.channel)
        else:
            print(f"设置角度 → {args.angle:.1f}°")
            servo.set_angle(args.channel, args.angle)
            time.sleep(0.6)  # 给舵机移动时间

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