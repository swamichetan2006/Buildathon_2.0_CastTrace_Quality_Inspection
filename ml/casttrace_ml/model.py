"""PyTorch transfer learning binary classifier for pump impeller defect detection."""

import os
from typing import Dict, Any, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models


class CastingClassifier(nn.Module):
    """ResNet-18 transfer learning classifier with feature extraction capabilities for OOD detection."""

    def __init__(self, pretrained: bool = True, num_classes: int = 2, dropout: float = 0.2):
        super().__init__()
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        backbone = models.resnet18(weights=weights)

        # Retain feature extractor layers up to avgpool
        self.conv1 = backbone.conv1
        self.bn1 = backbone.bn1
        self.relu = backbone.relu
        self.maxpool = backbone.maxpool
        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.layer4 = backbone.layer4
        self.avgpool = backbone.avgpool

        # 512-dimensional penultimate representation
        self.feature_dim = backbone.fc.in_features  # 512

        # Classification head: Dropout + Linear
        self.classifier = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(self.feature_dim, num_classes),
        )

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract the 512-dimensional penultimate pooling feature vector."""
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        features = torch.flatten(x, 1)  # [B, 512]
        return features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning unnormalized class logits [B, 2].
        
        Class 0: GOOD
        Class 1: DEFECTIVE
        """
        features = self.extract_features(x)
        logits = self.classifier(features)
        return logits

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Compute softmax probabilities [B, 2]."""
        logits = self.forward(x)
        return F.softmax(logits, dim=1)


class MobileNetV3SmallClassifier(nn.Module):
    """MobileNetV3-Small transfer learning classifier with 576D feature extraction for OOD detection."""

    def __init__(self, pretrained: bool = True, num_classes: int = 2, dropout: float = 0.2):
        super().__init__()
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = models.mobilenet_v3_small(weights=weights)

        self.features = backbone.features
        self.avgpool = backbone.avgpool
        self.feature_dim = 576  # Penultimate feature dimension after avgpool

        self.classifier = nn.Sequential(
            nn.Linear(self.feature_dim, 1024),
            nn.Hardswish(),
            nn.Dropout(p=dropout),
            nn.Linear(1024, num_classes),
        )

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract the 576-dimensional penultimate pooling feature vector."""
        x = self.features(x)
        x = self.avgpool(x)
        features = torch.flatten(x, 1)  # [B, 576]
        return features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning unnormalized class logits [B, 2]."""
        features = self.extract_features(x)
        logits = self.classifier(features)
        return logits

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Compute softmax probabilities [B, 2]."""
        logits = self.forward(x)
        return F.softmax(logits, dim=1)


def build_model(
    architecture: str = "resnet18",
    pretrained: bool = True,
    num_classes: int = 2,
) -> nn.Module:
    """Build and return an initialized model instance (resnet18 or mobilenet_v3_small)."""
    arch = architecture.lower().replace("-", "_")
    if arch in ["mobilenet_v3_small", "mobilenetv3_small", "mobilenetv3"]:
        return MobileNetV3SmallClassifier(pretrained=pretrained, num_classes=num_classes)
    elif arch in ["resnet18", "resnet_18"]:
        return CastingClassifier(pretrained=pretrained, num_classes=num_classes)
    else:
        raise ValueError(f"Unsupported architecture: '{architecture}'. Choose 'mobilenet_v3_small' or 'resnet18'.")


def load_model_checkpoint(
    checkpoint_path: str,
    device: str = "cpu",
) -> Tuple[nn.Module, Dict[str, Any]]:
    """Load model weights and metadata from checkpoint."""
    checkpoint = torch.load(checkpoint_path, map_location=device)
    metadata = checkpoint.get("metadata", {})
    architecture = metadata.get("architecture", "resnet18")
    model = build_model(architecture=architecture, pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, metadata

