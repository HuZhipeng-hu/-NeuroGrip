"""Entry point for unsupervised EMG autoencoder training and evaluation."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.preprocessing import normalize

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from unsupervised.config import load_unsupervised_config
from unsupervised.dataset import UnsupervisedEventDataset
from unsupervised.model import EMGAutoencoder, InferenceEncoder, ReconstructionLossCell

from shared.run_utils import copy_config_snapshot, dump_json, ensure_run_dir


logger = logging.getLogger("unsupervised")


def _set_device(device_target: str, device_id: int) -> None:
    try:
        from mindspore import context
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("MindSpore is required for unsupervised training.") from exc

    context.set_context(mode=context.GRAPH_MODE, device_target=str(device_target), device_id=int(device_id))
    logger.info("MindSpore context configured: target=%s id=%d", device_target, device_id)


def _build_datasets(cfg):
    train_ds = UnsupervisedEventDataset(
        data_dir=cfg.data.data_dir,
        raw_data_cfg=cfg.data,
        recordings_manifest_path=cfg.data.recordings_manifest_path,
        flatten=True,
        augment_params={
            "noise_std": cfg.augmentation.noise_std,
            "temporal_shift_max": cfg.augmentation.temporal_shift_max,
            "scale_min": cfg.augmentation.scale_min,
            "scale_max": cfg.augmentation.scale_max,
        },
    )
    eval_ds = UnsupervisedEventDataset(
        data_dir=cfg.data.data_dir,
        raw_data_cfg=cfg.data,
        recordings_manifest_path=cfg.data.recordings_manifest_path,
        flatten=True,
        augment_params={},
    )
    return train_ds, eval_ds


def _encode_dataset(encoder: InferenceEncoder, dataset: UnsupervisedEventDataset, batch_size: int) -> Dict[str, np.ndarray]:
    import mindspore as ms

    encoder.set_train(False)
    features = dataset.features
    labels = dataset.labels
    embeddings: list[np.ndarray] = []
    for start in range(0, len(dataset), batch_size):
        end = min(len(dataset), start + batch_size)
        batch = ms.Tensor(features[start:end])
        z = encoder(batch)
        embeddings.append(z.asnumpy())
    if not embeddings:
        raise RuntimeError("No embeddings generated; dataset may be empty.")
    return {
        "embeddings": np.concatenate(embeddings, axis=0).astype(np.float32),
        "labels": labels,
    }


def _evaluate_embeddings(payload: Dict[str, np.ndarray], n_clusters: int) -> Dict[str, float]:
    embs = payload["embeddings"]
    # L2-normalize embeddings to tighten clusters before K-Means.
    embs = normalize(embs, norm="l2")
    if embs.shape[1] > 64:
        pca_dim = min(embs.shape[1], 64)
        embs = PCA(n_components=pca_dim, whiten=True, random_state=42).fit_transform(embs)
    labels = payload["labels"]
    kmeans = KMeans(n_clusters=n_clusters, n_init=20, random_state=42)
    preds = kmeans.fit_predict(embs)
    metrics: Dict[str, float] = {}
    if labels.size > 0:
        metrics["ari"] = float(adjusted_rand_score(labels, preds))
        metrics["nmi"] = float(normalized_mutual_info_score(labels, preds))
    if embs.shape[0] > n_clusters:
        metrics["silhouette"] = float(silhouette_score(embs, preds))
    return metrics


def run(cfg_path: str) -> None:
    cfg = load_unsupervised_config(cfg_path)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    _set_device(cfg.training.device_target, cfg.training.device_id)

    train_ds, eval_ds = _build_datasets(cfg)
    if len(train_ds) == 0:
        raise RuntimeError("Dataset is empty; ensure recordings_manifest.csv exists and is populated.")

    import mindspore as ms
    from mindspore import nn

    autoencoder = EMGAutoencoder(
        input_dim=train_ds.features.shape[1],
        embedding_dim=cfg.model.embedding_dim,
        hidden_dim=cfg.model.hidden_dim,
        dropout=cfg.model.dropout_rate,
    )
    loss_fn = nn.MSELoss()
    net_with_loss = ReconstructionLossCell(autoencoder, loss_fn)
    optimizer = nn.Adam(autoencoder.trainable_params(), learning_rate=cfg.training.learning_rate, weight_decay=cfg.training.weight_decay)
    train_net = nn.TrainOneStepCell(net_with_loss, optimizer)
    train_net.set_train()

    run_id, run_dir = ensure_run_dir(cfg.logging.run_root, run_id=None, default_tag=cfg.logging.run_tag)
    copy_config_snapshot(cfg_path, run_dir / "unsupervised_config.yaml")

    logger.info("Start unsupervised training: epochs=%d batch_size=%d samples=%d", cfg.training.epochs, cfg.training.batch_size, len(train_ds))
    history: list[dict[str, float]] = []
    for epoch in range(cfg.training.epochs):
        epoch_loss = 0.0
        batches = 0
        dataset_iter = train_ds.build_generator(
            batch_size=cfg.training.batch_size,
            shuffle=cfg.training.shuffle,
            num_workers=cfg.training.num_workers,
        )
        for batch in dataset_iter.create_dict_iterator():
            x = ms.Tensor(batch["features"])
            loss = train_net(x)
            epoch_loss += float(loss.asnumpy())
            batches += 1
        mean_loss = epoch_loss / max(1, batches)
        history.append({"epoch": epoch + 1, "loss": mean_loss})
        logger.info("Epoch %d/%d - recon_loss=%.6f", epoch + 1, cfg.training.epochs, mean_loss)

    history_path = dump_json(run_dir / "unsupervised_history.json", history)
    ckpt_path = run_dir / "unsupervised_autoencoder.ckpt"
    ms.save_checkpoint(autoencoder, str(ckpt_path))

    encoder = InferenceEncoder(autoencoder)
    encoded = _encode_dataset(encoder, eval_ds, batch_size=cfg.training.batch_size)
    metrics = _evaluate_embeddings(encoded, n_clusters=len(eval_ds.label_spec.class_names))
    embeddings_path = run_dir / "unsupervised_embeddings.npy"
    np.save(embeddings_path, encoded["embeddings"])

    summary = {
        "run_id": run_id,
        "checkpoint": str(ckpt_path),
        "embeddings": str(embeddings_path),
        "history": str(history_path),
        "metrics": metrics,
    }
    dump_json(run_dir / "unsupervised_summary.json", summary)
    logger.info("Unsupervised training complete. Metrics: %s", metrics)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unsupervised autoencoder training for EMG event windows")
    parser.add_argument("--config", default="configs/unsupervised_event_onset.yaml", help="Path to unsupervised YAML config")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.config)
