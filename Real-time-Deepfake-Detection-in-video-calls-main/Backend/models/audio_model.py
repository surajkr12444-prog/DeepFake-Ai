import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models

try:
    from config import VOICE_MODEL_PATH
except (ImportError, ValueError):
    from Backend.config import VOICE_MODEL_PATH

class AttentionPool(nn.Module):
    def __init__(self, in_dim: int):
        super().__init__()
        self.attn = nn.Linear(in_dim, 1)

    def forward(self, x):
        # x: [B, T, D]
        scores = self.attn(x)              # [B, T, 1]
        weights = F.softmax(scores, dim=1) # [B, T, 1]
        return (weights * x).sum(dim=1)    # [B, D]

class CRNNWithAttn(nn.Module):
    """
    CRNN with Attention pooling for Audio Deepfake & Voice Fraud Detection:
    ResNet18 Backbone -> Bi-GRU Temporal Sequence Modeling -> Attention Pooling -> Classification Head
    Trained on ASVspoof 2019 and synthetic speech corpora.
    """
    def __init__(self, pretrained: bool = False, hidden_size: int = 128, num_layers: int = 1, dropout: float = 0.2):
        super().__init__()
        resnet = models.resnet18()
        # Adapt conv1 to accept 2-channel audio feature representation
        resnet.conv1 = nn.Conv2d(2, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.backbone = nn.Sequential(*list(resnet.children())[:-2])

        self.gru = nn.GRU(
            input_size=512,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0
        )

        self.attn_pool = AttentionPool(hidden_size * 2)

        self.classifier = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 1)
        )

    def forward(self, x):
        # x: [B, 2, F, T]
        feat = self.backbone(x)            # [B, 512, F', T']
        feat = feat.mean(dim=2)            # collapse freq -> [B, 512, T']
        feat = feat.permute(0, 2, 1)       # -> [B, T', 512]
        out, _ = self.gru(feat)            # -> [B, T', 2*hidden_size]
        pooled = self.attn_pool(out)       # -> [B, 2*hidden_size]
        return self.classifier(pooled)     # -> [B, 1]

def load_audio_model(weights_path: str = None):
    """
    Loads trained weights for CRNNWithAttn audio deepfake recognition.
    Searches VOICE_MODEL_PATH and local models directories.
    """
    candidate_paths = []
    if weights_path:
        candidate_paths.append(weights_path)
    if VOICE_MODEL_PATH:
        candidate_paths.append(VOICE_MODEL_PATH)

    # Local fallback candidates
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths.append(os.path.join(base_dir, "best_model10.pth"))
    candidate_paths.append(os.path.join(base_dir, "audio_model.pth"))
    candidate_paths.append(os.path.join(os.path.dirname(base_dir), "voice", "models", "best_model10.pth"))

    for path in candidate_paths:
        if path and os.path.exists(path):
            try:
                model = CRNNWithAttn(pretrained=False)
                state_dict = torch.load(path, map_location="cpu")
                model.load_state_dict(state_dict)
                model.eval()
                print(f"[AudioModel] Successfully loaded trained weights from: {path}")
                return model, True
            except Exception as e:
                print(f"[AudioModel] Error loading checkpoint from {path}: {e}")

    return None, False
