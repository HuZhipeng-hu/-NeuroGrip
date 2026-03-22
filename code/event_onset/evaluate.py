"""Evaluation helpers for event-onset checkpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np

from event_onset.config import EventModelConfig
from event_onset.model import (
    build_event_model,
    combine_two_stage_public_probabilities_from_logits,
    is_two_stage_demo3_model,
    resolve_two_stage_command_classes,
)

try:
    import mindspore as ms
    from mindspore import Tensor, context, load_checkpoint, load_param_into_net
except Exception:
    ms = None  # type: ignore
    Tensor = None  # type: ignore
    context = None  # type: ignore
    load_checkpoint = None  # type: ignore
    load_param_into_net = None  # type: ignore

from training.reporting import compute_classification_report

logger = logging.getLogger(__name__)


def _softmax(logits: np.ndarray) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float32)
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp = np.exp(shifted)
    denom = np.sum(exp, axis=1, keepdims=True)
    denom = np.maximum(denom, 1e-12)
    return exp / denom


def _set_device(mode: str = "graph", target: str = "CPU", device_id: int = 0) -> None:
    if ms is None:
        raise RuntimeError("MindSpore is not available")
    mode_map = {"graph": context.GRAPH_MODE, "pynative": context.PYNATIVE_MODE}
    context.set_context(mode=mode_map.get(mode, context.GRAPH_MODE))
    context.set_context(device_target=target)
    if target.upper() == "GPU":
        context.set_context(device_id=device_id)


def load_event_model_from_checkpoint(
    ckpt_path: str | Path,
    model_config: EventModelConfig,
):
    if ms is None:
        raise RuntimeError("MindSpore is not available")
    model = build_event_model(model_config)
    params = load_checkpoint(str(ckpt_path))
    load_param_into_net(model, params)
    model.set_train(False)
    return model


def evaluate_event_model(
    model,
    emg_samples: np.ndarray,
    imu_samples: np.ndarray,
    labels: np.ndarray,
    class_names: Sequence[str],
    *,
    command_class_names: Sequence[str] | None = None,
) -> Dict[str, Any]:
    prediction_payload = predict_event_model(
        model,
        emg_samples=emg_samples,
        imu_samples=imu_samples,
        class_names=class_names,
        command_class_names=command_class_names,
    )
    return compute_classification_report(
        labels.astype(np.int32),
        prediction_payload["predictions"].astype(np.int32),
        class_names=class_names,
    )


def predict_event_model(
    model,
    *,
    emg_samples: np.ndarray,
    imu_samples: np.ndarray,
    class_names: Sequence[str],
    command_class_names: Sequence[str] | None = None,
) -> Dict[str, np.ndarray]:
    if ms is None:
        raise RuntimeError("MindSpore is not available")
    outputs = model(Tensor(emg_samples, ms.float32), Tensor(imu_samples, ms.float32))
    if is_two_stage_demo3_model(getattr(model, "config", None).model_type if getattr(model, "config", None) else ""):
        gate_logits, command_logits = outputs
        resolved_command_classes = (
            tuple(str(name).strip().upper() for name in command_class_names if str(name).strip())
            if command_class_names is not None
            else resolve_two_stage_command_classes(class_names)
        )
        public_probs = combine_two_stage_public_probabilities_from_logits(
            gate_logits.asnumpy(),
            command_logits.asnumpy(),
            command_class_names=resolved_command_classes,
        )
        predictions = np.argmax(public_probs, axis=1).astype(np.int32)
    else:
        logits = outputs.asnumpy()
        public_probs = _softmax(logits)
        predictions = np.argmax(public_probs, axis=1).astype(np.int32)
    confidences = public_probs[np.arange(int(public_probs.shape[0])), predictions]
    return {
        "predictions": predictions.astype(np.int32),
        "public_probs": np.asarray(public_probs, dtype=np.float32),
        "confidences": np.asarray(confidences, dtype=np.float32),
    }


def load_and_evaluate_event(
    ckpt_path: str | Path,
    emg_samples: np.ndarray,
    imu_samples: np.ndarray,
    labels: np.ndarray,
    class_names: Sequence[str],
    *,
    model_config: EventModelConfig,
    device_target: str = "CPU",
    device_id: int = 0,
    return_prediction_payload: bool = False,
    command_class_names: Sequence[str] | None = None,
) -> Dict[str, Any]:
    _set_device(target=device_target, device_id=device_id)
    model = load_event_model_from_checkpoint(ckpt_path=ckpt_path, model_config=model_config)
    logger.info("Loaded event checkpoint: %s", ckpt_path)
    prediction_payload = predict_event_model(
        model,
        emg_samples=emg_samples,
        imu_samples=imu_samples,
        class_names=class_names,
        command_class_names=command_class_names,
    )
    report = compute_classification_report(
        labels.astype(np.int32),
        prediction_payload["predictions"].astype(np.int32),
        class_names=class_names,
    )
    if return_prediction_payload:
        return {
            "report": report,
            "prediction_payload": prediction_payload,
        }
    return report
