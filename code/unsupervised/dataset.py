"""Unsupervised dataset utilities built on top of the event-onset loader."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterator, Tuple

import numpy as np
from mindspore.dataset import GeneratorDataset

from event_onset.config import EventDataConfig, EventFeatureConfig
from event_onset.dataset import EventClipDatasetLoader
from shared.label_modes import get_label_mode_spec


def _build_event_data_config(raw_cfg) -> EventDataConfig:
    feature_cfg = EventFeatureConfig()
    feature_cfg.emg_stft_window = int(raw_cfg.feature.get("emg_stft_window", feature_cfg.emg_stft_window))
    feature_cfg.emg_stft_hop = int(raw_cfg.feature.get("emg_stft_hop", feature_cfg.emg_stft_hop))
    feature_cfg.emg_n_fft = int(raw_cfg.feature.get("emg_n_fft", feature_cfg.emg_n_fft))
    feature_cfg.emg_freq_bins = int(raw_cfg.feature.get("emg_freq_bins", feature_cfg.emg_freq_bins))
    feature_cfg.context_window_ms = int(raw_cfg.feature.get("context_window_ms", feature_cfg.context_window_ms))
    feature_cfg.window_step_ms = int(raw_cfg.feature.get("window_step_ms", feature_cfg.window_step_ms))

    data_cfg = EventDataConfig()
    data_cfg.label_mode = str(raw_cfg.label_mode)
    data_cfg.capture_mode_filter = str(raw_cfg.capture_mode_filter)
    data_cfg.target_db5_keys = [str(v).strip().upper() for v in raw_cfg.target_db5_keys]
    data_cfg.split_manifest_path = str(raw_cfg.split_manifest_path)
    data_cfg.recordings_manifest_path = str(raw_cfg.recordings_manifest_path)
    data_cfg.device_sampling_rate_hz = int(raw_cfg.device_sampling_rate_hz)
    data_cfg.feature = feature_cfg
    # Ensure derived properties use updated feature/device sampling rate.
    data_cfg = replace(
        data_cfg,
        feature=feature_cfg,
    )
    return data_cfg


def _add_noise(x: np.ndarray, std: float) -> np.ndarray:
    if std <= 0:
        return x
    return x + np.random.normal(0.0, float(std), size=x.shape).astype(np.float32)


def _scale(x: np.ndarray, scale_min: float, scale_max: float) -> np.ndarray:
    if scale_min <= 0 or scale_max <= 0:
        return x
    factor = np.random.uniform(scale_min, scale_max)
    return x * float(factor)


def _temporal_shift(x: np.ndarray, max_shift: int) -> np.ndarray:
    if max_shift <= 0:
        return x
    shift = int(np.random.randint(-max_shift, max_shift + 1))
    if shift == 0:
        return x
    return np.roll(x, shift=shift, axis=-1)


def apply_augmentations(x: np.ndarray, *, noise_std: float, temporal_shift_max: int, scale_min: float, scale_max: float) -> np.ndarray:
    augmented = _add_noise(x, noise_std)
    augmented = _scale(augmented, scale_min, scale_max)
    augmented = _temporal_shift(augmented, temporal_shift_max)
    return augmented.astype(np.float32)


class UnsupervisedEventDataset:
    """Wrap event-onset windows for self-supervised training.

    The dataset keeps labels for downstream evaluation but does not use them for training.
    """

    def __init__(
        self,
        *,
        data_dir: str,
        raw_data_cfg,
        recordings_manifest_path: str | None,
        flatten: bool = True,
        augment_params: dict[str, float] | None = None,
    ) -> None:
        data_cfg = _build_event_data_config(raw_data_cfg)
        self.data_cfg = data_cfg
        self.flatten = bool(flatten)
        self.augment_params = augment_params or {}

        loader = EventClipDatasetLoader(
            data_dir=data_dir,
            data_config=data_cfg,
            recordings_manifest_path=recordings_manifest_path,
        )
        emg, _imu, labels, source_ids, metadata = loader.load_all_with_sources(return_metadata=True)  # type: ignore[assignment]
        self.raw_features = emg.astype(np.float32)
        self.labels = labels.astype(np.int32)
        self.source_ids = source_ids
        self.metadata = metadata
        self.label_spec = get_label_mode_spec(data_cfg.label_mode, data_cfg.target_db5_keys)
        if self.flatten:
            self.features = self.raw_features.reshape(self.raw_features.shape[0], -1)
        else:
            self.features = self.raw_features

    def __len__(self) -> int:  # pragma: no cover - trivial
        return int(self.features.shape[0])

    def __getitem__(self, idx: int) -> Tuple[np.ndarray, int]:
        raw = self.raw_features[idx]
        if self.augment_params:
            raw = apply_augmentations(
                raw,
                noise_std=float(self.augment_params.get("noise_std", 0.0)),
                temporal_shift_max=int(self.augment_params.get("temporal_shift_max", 0)),
                scale_min=float(self.augment_params.get("scale_min", 1.0)),
                scale_max=float(self.augment_params.get("scale_max", 1.0)),
            )
        x = raw.reshape(-1) if self.flatten else raw
        return x.astype(np.float32), int(self.labels[idx])

    def build_generator(self, batch_size: int, *, shuffle: bool, num_workers: int = 0) -> GeneratorDataset:
        def _iterator() -> Iterator[tuple[np.ndarray, np.int32]]:
            for i in range(len(self)):
                yield self[i]

        dataset = GeneratorDataset(
            source=_iterator,
            column_names=["features", "labels"],
            shuffle=bool(shuffle),
            num_parallel_workers=max(1, int(num_workers)),
        )
        dataset = dataset.batch(batch_size=batch_size, drop_remainder=True)
        return dataset


__all__ = [
    "UnsupervisedEventDataset",
    "apply_augmentations",
]
