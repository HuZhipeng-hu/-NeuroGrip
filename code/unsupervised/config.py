"""Configuration loaders for unsupervised training pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, get_type_hints

import yaml


def _as_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


@dataclass
class UnsupervisedModelConfig:
    input_shape: List[int] = field(default_factory=lambda: [16, 24, 6])
    embedding_dim: int = 128
    hidden_dim: int = 512
    dropout_rate: float = 0.2

    @property
    def input_dim(self) -> int:
        return int(self.input_shape[0] * self.input_shape[1] * self.input_shape[2])


@dataclass
class UnsupervisedTrainingConfig:
    epochs: int = 40
    batch_size: int = 64
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    device_target: str = "CPU"
    device_id: int = 0
    shuffle: bool = True
    num_workers: int = 0


@dataclass
class UnsupervisedAugmentationConfig:
    noise_std: float = 0.02
    temporal_shift_max: int = 1
    scale_min: float = 0.9
    scale_max: float = 1.1


@dataclass
class UnsupervisedLoggingConfig:
    run_root: str = "artifacts/runs"
    run_tag: str = "unsupervised"


@dataclass
class UnsupervisedDataConfig:
    data_dir: str = "../data"
    recordings_manifest_path: str = "recordings_manifest.csv"
    label_mode: str = "event_onset"
    capture_mode_filter: str = "event_onset"
    target_db5_keys: List[str] = field(default_factory=lambda: ["TENSE_OPEN", "V_SIGN", "THUMB_UP", "WRIST_CW"])
    split_manifest_path: str = "artifacts/splits/event_onset_demo3_split_manifest.json"
    feature: Dict[str, Any] = field(default_factory=dict)
    device_sampling_rate_hz: int = 500


@dataclass
class UnsupervisedConfig:
    model: UnsupervisedModelConfig = field(default_factory=UnsupervisedModelConfig)
    training: UnsupervisedTrainingConfig = field(default_factory=UnsupervisedTrainingConfig)
    augmentation: UnsupervisedAugmentationConfig = field(default_factory=UnsupervisedAugmentationConfig)
    logging: UnsupervisedLoggingConfig = field(default_factory=UnsupervisedLoggingConfig)
    data: UnsupervisedDataConfig = field(default_factory=UnsupervisedDataConfig)


def _dict_to_dataclass(data: Dict[str, Any], cls):
    """Recursively convert a plain dict into the target dataclass.

    Handles forward references produced by `from __future__ import annotations` by
    resolving type hints with get_type_hints.
    """

    kwargs: Dict[str, Any] = {}
    type_hints = get_type_hints(cls)
    for field_obj in cls.__dataclass_fields__.values():  # type: ignore[attr-defined]
        if field_obj.name not in data:
            continue
        value = data[field_obj.name]
        field_type = type_hints.get(field_obj.name, field_obj.type)
        if hasattr(field_type, "__dataclass_fields__"):
            kwargs[field_obj.name] = _dict_to_dataclass(value or {}, field_type)
        else:
            kwargs[field_obj.name] = value
    return cls(**kwargs)


def load_unsupervised_config(path: str | Path) -> UnsupervisedConfig:
    with open(path, "r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    return _dict_to_dataclass(payload, UnsupervisedConfig)


__all__ = [
    "UnsupervisedModelConfig",
    "UnsupervisedTrainingConfig",
    "UnsupervisedAugmentationConfig",
    "UnsupervisedLoggingConfig",
    "UnsupervisedDataConfig",
    "UnsupervisedConfig",
    "load_unsupervised_config",
]
