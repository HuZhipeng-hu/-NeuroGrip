from __future__ import annotations

from runtime.hardware.pca9685_actuator import PCA9685Actuator, SAFE_PROFILE_TEST_PY_V1
from shared.gestures import GestureType


def test_safe_profile_thumb_up_uses_test_py_angles() -> None:
    actuator = PCA9685Actuator(
        channels=[0, 1, 2, 3, 4],
        wrist_channel=5,
        safe_profile_preset=SAFE_PROFILE_TEST_PY_V1,
    )
    actuator._connected = True
    calls: list[tuple[int, float]] = []
    actuator._set_servo_angle = lambda channel, angle: calls.append((channel, angle))  # type: ignore[method-assign]

    actuator.execute_gesture(GestureType.THUMB_UP)

    assert calls == [
        (0, 180.0),
        (1, 0.0),
        (2, 0.0),
        (3, 0.0),
        (4, 0.0),
        (5, 120.0),
    ]


def test_safe_profile_tense_open_uses_open_pose() -> None:
    actuator = PCA9685Actuator(
        channels=[0, 1, 2, 3, 4],
        wrist_channel=5,
        safe_profile_preset=SAFE_PROFILE_TEST_PY_V1,
    )
    actuator._connected = True
    calls: list[tuple[int, float]] = []
    actuator._set_servo_angle = lambda channel, angle: calls.append((channel, angle))  # type: ignore[method-assign]

    actuator.execute_gesture(GestureType.TENSE_OPEN)

    assert calls == [
        (0, 180.0),
        (1, 180.0),
        (2, 180.0),
        (3, 180.0),
        (4, 180.0),
        (5, 120.0),
    ]


def test_safe_profile_wrist_cw_latches_open_pose_and_clockwise_wrist_angle() -> None:
    actuator = PCA9685Actuator(
        channels=[0, 1, 2, 3, 4],
        wrist_channel=5,
        safe_profile_preset=SAFE_PROFILE_TEST_PY_V1,
    )
    actuator._connected = True
    calls: list[tuple[int, float]] = []
    actuator._set_servo_angle = lambda channel, angle: calls.append((channel, angle))  # type: ignore[method-assign]

    actuator.execute_gesture(GestureType.WRIST_CW)

    assert calls == [
        (0, 180.0),
        (1, 180.0),
        (2, 180.0),
        (3, 180.0),
        (4, 180.0),
        (5, 0.0),
    ]


def test_safe_profile_switching_away_from_wrist_cw_restores_neutral_wrist() -> None:
    actuator = PCA9685Actuator(
        channels=[0, 1, 2, 3, 4],
        wrist_channel=5,
        safe_profile_preset=SAFE_PROFILE_TEST_PY_V1,
    )
    actuator._connected = True
    calls: list[tuple[int, float]] = []
    actuator._set_servo_angle = lambda channel, angle: calls.append((channel, angle))  # type: ignore[method-assign]

    actuator.execute_gesture(GestureType.WRIST_CW)
    actuator.execute_gesture(GestureType.TENSE_OPEN)

    assert calls[-1] == (5, 120.0)
