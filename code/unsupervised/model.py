"""Simple autoencoder for EMG STFT features."""

from __future__ import annotations

try:  # Local import guard to avoid hard dependency during linting
    import mindspore.nn as nn
    import mindspore.ops as ops
    from mindspore import Tensor
    MINDSPORE_AVAILABLE = True
except ImportError:  # pragma: no cover - handled at runtime
    MINDSPORE_AVAILABLE = False


def _check_mindspore():
    if not MINDSPORE_AVAILABLE:
        raise ImportError(
            "MindSpore is required for unsupervised training. Install mindspore>=2.7.1."
        )


if MINDSPORE_AVAILABLE:

    class EMGAutoencoder(nn.Cell):
        """Fully-connected autoencoder on flattened STFT windows."""

        def __init__(self, input_dim: int, embedding_dim: int = 128, hidden_dim: int = 512, dropout: float = 0.2):
            super().__init__()
            self.input_dim = int(input_dim)
            self.embedding_dim = int(embedding_dim)
            self.encoder = nn.SequentialCell(
                nn.Dense(self.input_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(p=dropout),
                nn.Dense(hidden_dim, embedding_dim),
            )
            self.decoder = nn.SequentialCell(
                nn.Dense(embedding_dim, hidden_dim),
                nn.ReLU(),
                nn.Dense(hidden_dim, self.input_dim),
            )

        def construct(self, x: Tensor):
            z = self.encoder(x)
            recon = self.decoder(z)
            return z, recon

    class ReconstructionLossCell(nn.Cell):
        """Wrap autoencoder with reconstruction loss for TrainOneStepCell."""

        def __init__(self, network: EMGAutoencoder, loss_fn: nn.Cell):
            super().__init__()
            self.network = network
            self.loss_fn = loss_fn

        def construct(self, x):
            _, recon = self.network(x)
            return self.loss_fn(recon, x)

    class InferenceEncoder(nn.Cell):
        """Expose encoder-only forward for embedding extraction."""

        def __init__(self, network: EMGAutoencoder):
            super().__init__()
            self.encoder = network.encoder

        def construct(self, x):
            return self.encoder(x)

else:

    class EMGAutoencoder:  # pragma: no cover - placeholder for docs
        def __init__(self, *args, **kwargs):
            _check_mindspore()

    class ReconstructionLossCell:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            _check_mindspore()

    class InferenceEncoder:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            _check_mindspore()


__all__ = [
    "EMGAutoencoder",
    "ReconstructionLossCell",
    "InferenceEncoder",
]
