"""PCA9685-backed prosthesis actuator."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .base import ActuatorBase
from shared.gestures import GestureType, NUM_FINGERS, get_finger_angles

logger = logging.getLogger(__name__)

try:
    from smbus2 import SMBus

    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    SMBus = None  # type: ignore


PCA9685_MODE1 = 0x00
PCA9685_PRESCALE = 0xFE
PCA9685_LED0_ON_L = 0x06

SAFE_PROFILE_DEFAULT = "default"
SAFE_PROFILE_TEST_PY_V1 = "test_py_v1"


class PCA9685Actuator(ActuatorBase):
    """Drive five finger servos and an optional wrist servo through PCA9685."""

    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_address: int = 0x40,
        frequency: int = 50,
        angle_open: float = 0.0,
        angle_half: float = 90.0,
        angle_closed: float = 180.0,
        min_pulse_ms: float = 0.5,
        max_pulse_ms: float = 2.5,
        channels: Optional[List[int]] = None,
        wrist_channel: Optional[int] = None,
        safe_profile_preset: str = SAFE_PROFILE_DEFAULT,
        wrist_neutral_angle: float = 120.0,
        wrist_cw_angle: float = 0.0,
    ) -> None:
        self._bus_num = int(i2c_bus)
        self._address = int(i2c_address)
        self._frequency = int(frequency)
        self._angle_open = float(angle_open)
        self._angle_half = float(angle_half)
        self._angle_closed = float(angle_closed)
        self._min_pulse = float(min_pulse_ms)
        self._max_pulse = float(max_pulse_ms)
        self._channels = list(channels or [0, 1, 2, 3, 4])
        self._wrist_channel = None if wrist_channel is None else int(wrist_channel)
        self._safe_profile_preset = str(safe_profile_preset or SAFE_PROFILE_DEFAULT).strip().lower()
        self._wrist_neutral_angle = float(wrist_neutral_angle)
        self._wrist_cw_angle = float(wrist_cw_angle)

        self._bus: Optional[SMBus] = None
        self._connected = False
        self._current_angles = [self._angle_open] * NUM_FINGERS
        self._current_gesture: Optional[GestureType] = None
        self._current_wrist_angle = self._wrist_neutral_angle

    def connect(self) -> bool:
        if not SMBUS_AVAILABLE:
            logger.warning("smbus2 is missing; actuator falls back to dry mode.")
            self._connected = True
            return True

        try:
            self._bus = SMBus(self._bus_num)
            self._bus.write_byte_data(self._address, PCA9685_MODE1, 0x00)
            time.sleep(0.01)
            self._set_frequency(self._frequency)
            self._connected = True
            self.execute_gesture(GestureType.RELAX)
            logger.info(
                "Actuator connected: bus=%s addr=0x%02X freq=%sHz preset=%s wrist_channel=%s",
                self._bus_num,
                self._address,
                self._frequency,
                self._safe_profile_preset,
                self._wrist_channel,
            )
            return True
        except Exception as exc:  # pragma: no cover - hardware path
            logger.error("Actuator connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._connected:
            try:
                self.execute_gesture(GestureType.RELAX)
                time.sleep(0.5)
            except Exception:
                pass
        if self._bus is not None:
            self._bus.close()
        self._connected = False
        logger.info("Actuator disconnected")

    def execute_gesture(self, gesture: GestureType) -> None:
        if not self._connected:
            logger.warning("Actuator is not connected; skipping gesture=%s", gesture.name)
            return

        angles = self._resolve_finger_angles(gesture)
        self.set_finger_angles(angles)
        wrist_angle = self._resolve_wrist_angle(gesture)
        if self._wrist_channel is not None and wrist_angle is not None:
            self._set_servo_angle(self._wrist_channel, wrist_angle)
            self._current_wrist_angle = float(wrist_angle)
        self._current_gesture = gesture

    def set_finger_angles(self, angles: List[float]) -> None:
        if len(angles) != NUM_FINGERS:
            raise ValueError(f"Expected {NUM_FINGERS} finger angles, got {len(angles)}")
        for index, angle in enumerate(angles):
            self._set_servo_angle(self._channels[index], float(angle))
            self._current_angles[index] = float(angle)

    def is_connected(self) -> bool:
        return self._connected

    def get_info(self) -> Dict[str, Any]:
        return {
            "type": "PCA9685Actuator",
            "i2c_bus": self._bus_num,
            "i2c_address": f"0x{self._address:02X}",
            "frequency": self._frequency,
            "connected": self._connected,
            "safe_profile_preset": self._safe_profile_preset,
            "wrist_channel": self._wrist_channel,
            "wrist_neutral_angle": self._wrist_neutral_angle,
            "wrist_cw_angle": self._wrist_cw_angle,
            "current_gesture": self._current_gesture.name if self._current_gesture else None,
            "current_angles": list(self._current_angles),
            "current_wrist_angle": self._current_wrist_angle,
        }

    def _resolve_finger_angles(self, gesture: GestureType) -> List[float]:
        safe_angles = self._safe_profile_angles().get(gesture)
        if safe_angles is not None:
            return safe_angles
        return get_finger_angles(
            gesture,
            angle_open=self._angle_open,
            angle_half=self._angle_half,
            angle_closed=self._angle_closed,
        )

    def _resolve_wrist_angle(self, gesture: GestureType) -> Optional[float]:
        if self._wrist_channel is None:
            return None
        if gesture == GestureType.WRIST_CW:
            return self._wrist_cw_angle
        if gesture == GestureType.WRIST_CCW:
            return 180.0
        return self._wrist_neutral_angle

    def _safe_profile_angles(self) -> Dict[GestureType, List[float]]:
        if self._safe_profile_preset != SAFE_PROFILE_TEST_PY_V1:
            return {}
        return {
            GestureType.RELAX: [180.0, 180.0, 180.0, 180.0, 180.0],
            GestureType.TENSE_OPEN: [180.0, 180.0, 180.0, 180.0, 180.0],
            GestureType.THUMB_UP: [180.0, 0.0, 0.0, 0.0, 0.0],
            GestureType.WRIST_CW: [180.0, 180.0, 180.0, 180.0, 180.0],
            GestureType.WRIST_CCW: [180.0, 180.0, 180.0, 180.0, 180.0],
            GestureType.OK: [0.0, 0.0, 180.0, 180.0, 180.0],
            GestureType.OK_SIGN: [0.0, 0.0, 180.0, 180.0, 180.0],
            GestureType.YE: [0.0, 180.0, 180.0, 0.0, 0.0],
            GestureType.V_SIGN: [0.0, 180.0, 180.0, 0.0, 0.0],
        }

    def _set_frequency(self, freq: int) -> None:
        if self._bus is None:
            return
        prescale = int(25_000_000.0 / (4096.0 * float(freq)) - 1)
        old_mode = self._bus.read_byte_data(self._address, PCA9685_MODE1)
        self._bus.write_byte_data(self._address, PCA9685_MODE1, (old_mode & 0x7F) | 0x10)
        self._bus.write_byte_data(self._address, PCA9685_PRESCALE, prescale)
        self._bus.write_byte_data(self._address, PCA9685_MODE1, old_mode)
        time.sleep(0.005)
        self._bus.write_byte_data(self._address, PCA9685_MODE1, old_mode | 0x80)

    def _set_servo_angle(self, channel: int, angle: float) -> None:
        clipped = max(0.0, min(180.0, float(angle)))
        pulse_ms = self._min_pulse + ((self._max_pulse - self._min_pulse) * clipped / 180.0)
        period_ms = 1000.0 / float(self._frequency)
        pulse_count = int(pulse_ms / period_ms * 4096)

        if self._bus is not None:
            reg = PCA9685_LED0_ON_L + 4 * int(channel)
            self._bus.write_byte_data(self._address, reg, 0)
            self._bus.write_byte_data(self._address, reg + 1, 0)
            self._bus.write_byte_data(self._address, reg + 2, pulse_count & 0xFF)
            self._bus.write_byte_data(self._address, reg + 3, pulse_count >> 8)
