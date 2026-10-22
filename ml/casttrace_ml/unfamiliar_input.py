"""Unfamiliar-input out-of-distribution guard using penultimate feature representation."""

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import torch
import torch.nn as nn


@dataclass
class GuardEvaluationResult:
    is_unfamiliar: bool
    distance: float
    threshold: float
    margin: float       # distance - threshold (positive indicates unfamiliar)
    details: Dict[str, Any]


class UnfamiliarInputGuard:
    """Out-of-distribution guard comparing feature embeddings against training reference distribution."""

    def __init__(
        self,
        prototypes: np.ndarray,          # Shape: [K, D], normalized unit vectors
        guard_threshold: float,
        metric: str = "cosine_distance",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.prototypes = prototypes.astype(np.float32)
        self.guard_threshold = float(guard_threshold)
        self.metric = metric
        self.metadata = metadata or {}

    def compute_distance(self, embedding: np.ndarray) -> float:
        """Compute minimum distance from embedding to reference prototype centroids."""
        # Ensure 1D unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            emb = embedding / norm
        else:
            emb = embedding

        if self.metric == "cosine_distance":
            # Cosine similarity to prototypes: s_i = emb . p_i
            sims = np.dot(self.prototypes, emb)
            dists = 1.0 - sims
            return float(np.min(dists))
        else:
            # Euclidean distance
            dists = np.linalg.norm(self.prototypes - emb, axis=1)
            return float(np.min(dists))

    def evaluate(self, embedding: np.ndarray) -> GuardEvaluationResult:
        """Evaluate whether an embedding falls outside the known training distribution."""
        dist = self.compute_distance(embedding)
        is_unfamiliar = dist > self.guard_threshold
        margin = dist - self.guard_threshold
        return GuardEvaluationResult(
            is_unfamiliar=is_unfamiliar,
            distance=round(dist, 5),
            threshold=round(self.guard_threshold, 5),
            margin=round(margin, 5),
            details={
                "metric": self.metric,
                "metadata": self.metadata,
            },
        )

    def save(self, file_path: str) -> str:
        """Serialize guard reference artifact to JSON and return its SHA-256 hash."""
        data = {
            "metric": self.metric,
            "guard_threshold": self.guard_threshold,
            "prototypes": self.prototypes.tolist(),
            "metadata": self.metadata,
        }
        content = json.dumps(data, indent=2).encode("utf-8")
        sha256 = hashlib.sha256(content).hexdigest()
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
        return sha256

    @classmethod
    def load(cls, file_path: str) -> "UnfamiliarInputGuard":
        """Load guard reference artifact from serialized JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        prototypes = np.array(data["prototypes"], dtype=np.float32)
        return cls(
            prototypes=prototypes,
            guard_threshold=data["guard_threshold"],
            metric=data.get("metric", "cosine_distance"),
            metadata=data.get("metadata", {}),
        )


def build_guard_reference(
    train_embeddings: np.ndarray,      # [N_train, D]
    train_labels: np.ndarray,          # [N_train] (0=GOOD, 1=DEFECTIVE)
    val_embeddings: np.ndarray,        # [N_val, D]
    model_version: str,
    feature_extractor_name: str,
    selection_percentile: float = 99.0,
) -> Tuple[UnfamiliarInputGuard, Dict[str, Any]]:
    """Build compact reference prototypes from training data and calibrate threshold on validation data."""
    # Normalize training embeddings to unit L2-norm
    train_norms = np.linalg.norm(train_embeddings, axis=1, keepdims=True)
    train_norms = np.where(train_norms > 0, train_norms, 1.0)
    train_emb_norm = train_embeddings / train_norms

    # Normalize validation embeddings
    val_norms = np.linalg.norm(val_embeddings, axis=1, keepdims=True)
    val_norms = np.where(val_norms > 0, val_norms, 1.0)
    val_emb_norm = val_embeddings / val_norms

    c_global = np.mean(train_emb_norm, axis=0, keepdims=True)
    c_global /= np.maximum(np.linalg.norm(c_global), 1e-8)

    protos = [c_global]
    def_mask = (train_labels == 1)
    ok_mask = (train_labels == 0)

    if np.sum(def_mask) > 0:
        c_def = np.mean(train_emb_norm[def_mask], axis=0, keepdims=True)
        c_def /= np.maximum(np.linalg.norm(c_def), 1e-8)
        protos.append(c_def)

    if np.sum(ok_mask) > 0:
        c_ok = np.mean(train_emb_norm[ok_mask], axis=0, keepdims=True)
        c_ok /= np.maximum(np.linalg.norm(c_ok), 1e-8)
        protos.append(c_ok)

    # Use centroids as the canonical prototypes
    prototypes = np.vstack(protos)  # [K, D]

    # Evaluate validation distances to compute threshold
    val_dists = []
    for emb in val_emb_norm:
        sims = np.dot(prototypes, emb)
        dists = 1.0 - sims
        val_dists.append(float(np.min(dists)))

    val_dists = np.array(val_dists)
    guard_threshold = float(np.percentile(val_dists, selection_percentile))

    stats = {
        "selection_rule": f"{selection_percentile}th_percentile_validation_in_distribution",
        "threshold": round(guard_threshold, 5),
        "val_distance_min": round(float(np.min(val_dists)), 5),
        "val_distance_mean": round(float(np.mean(val_dists)), 5),
        "val_distance_std": round(float(np.std(val_dists)), 5),
        "val_distance_p95": round(float(np.percentile(val_dists, 95)), 5),
        "val_distance_p99": round(float(np.percentile(val_dists, 99)), 5),
        "val_distance_max": round(float(np.max(val_dists)), 5),
    }

    metadata = {
        "model_version": model_version,
        "feature_extractor": feature_extractor_name,
        "train_samples_count": int(len(train_embeddings)),
        "val_samples_count": int(len(val_embeddings)),
        "prototype_count": int(len(prototypes)),
        "validation_stats": stats,
    }

    guard = UnfamiliarInputGuard(
        prototypes=prototypes,
        guard_threshold=guard_threshold,
        metric="cosine_distance",
        metadata=metadata,
    )
    return guard, metadata
