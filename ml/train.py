"""Model training, validation, baseline comparison, guard reference building, and threshold optimization."""

import argparse
import hashlib
import json
import os
import random
import time
from typing import Dict, List, Tuple, Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from PIL import Image
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

from casttrace_ml.model import CastingClassifier, build_model
from casttrace_ml.preprocessing import get_train_transform, get_eval_transform, DEFAULT_INPUT_SIZE, IMAGENET_MEAN, IMAGENET_STD
from casttrace_ml.routing import optimize_routing_thresholds, evaluate_routing, RoutingThresholds
from casttrace_ml.unfamiliar_input import build_guard_reference, UnfamiliarInputGuard


class CastingDataset(Dataset):
    """PyTorch Dataset loading images from manifest entries."""

    def __init__(self, items: List[Dict[str, Any]], transform=None):
        self.items = items
        self.transform = transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        item = self.items[idx]
        path = item["path"]
        label = item["label_idx"]  # 0 for GOOD, 1 for DEFECTIVE
        image = Image.open(path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label, item["filename"]


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_majority_baseline(train_labels: np.ndarray, val_labels: np.ndarray) -> Dict[str, Any]:
    """Compute majority-class baseline performance on validation split."""
    # Count training labels
    counts = np.bincount(train_labels)
    majority_class = int(np.argmax(counts))  # 1 for DEFECTIVE
    majority_class_name = "DEFECTIVE" if majority_class == 1 else "GOOD"
    
    val_preds = np.full_like(val_labels, majority_class)
    # Naive constant probability = 1.0 for predicted class
    val_probs = np.full_like(val_labels, 1.0 if majority_class == 1 else 0.0, dtype=np.float32)

    acc = float(accuracy_score(val_labels, val_preds))
    prec = float(precision_score(val_labels, val_preds, pos_label=1, zero_division=0))
    rec = float(recall_score(val_labels, val_preds, pos_label=1, zero_division=0))
    f1 = float(f1_score(val_labels, val_preds, pos_label=1, zero_division=0))
    # ROC-AUC is 0.5 for a constant prediction
    roc_auc = 0.5000

    return {
        "strategy": "Majority Class Predictor",
        "predicted_class": majority_class_name,
        "validation_accuracy": round(acc, 4),
        "validation_precision": round(prec, 4),
        "validation_recall": round(rec, 4),
        "validation_f1": round(f1, 4),
        "validation_roc_auc": round(roc_auc, 4),
        "notes": "Always predicts DEFECTIVE; achieves 0% coverage on GOOD items and cannot meet 90% precision.",
    }


def train_epoch(model, dataloader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    
    for images, labels, _ in dataloader:
        images = images.to(device)
        labels = labels.to(device)
        
        optimizer.zero_grad()
        logits = model(images)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item() * images.size(0)
        _, preds = torch.max(logits, 1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)
        
    return total_loss / total, correct / total


def evaluate_epoch(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for images, labels, _ in dataloader:
            images = images.to(device)
            labels = labels.to(device)
            
            logits = model(images)
            loss = criterion(logits, labels)
            probs = torch.softmax(logits, dim=1)
            
            total_loss += loss.item() * images.size(0)
            _, preds = torch.max(logits, 1)
            
            all_preds.extend(preds.cpu().numpy())
            # Probability of DEFECTIVE (index 1)
            all_probs.extend(probs[:, 1].cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            
    total = len(all_labels)
    val_loss = total_loss / total
    y_true = np.array(all_labels)
    y_pred = np.array(all_preds)
    y_prob = np.array(all_probs)
    
    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, pos_label=1, zero_division=0))
    rec = float(recall_score(y_true, y_pred, pos_label=1, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, pos_label=1, zero_division=0))
    roc_auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.5
    
    metrics = {
        "loss": round(val_loss, 4),
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
    }
    return metrics, y_prob, y_true


def extract_all_features(model, dataloader, device) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    all_features = []
    all_labels = []
    with torch.no_grad():
        for images, labels, _ in dataloader:
            images = images.to(device)
            feats = model.extract_features(images)
            all_features.append(feats.cpu().numpy())
            all_labels.extend(labels.numpy())
    return np.vstack(all_features), np.array(all_labels)


def create_unrelated_eval_set(save_dir: str = "data/unrelated_eval") -> List[str]:
    """Generate a small, separately documented benchmark set of 10 out-of-distribution synthetic & texture images."""
    os.makedirs(save_dir, exist_ok=True)
    unrelated_paths = []

    # 1. High-frequency random noise
    np.random.seed(101)
    im1 = Image.fromarray(np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8))
    p1 = os.path.join(save_dir, "unrelated_noise.png").replace("\\", "/")
    im1.save(p1)
    unrelated_paths.append(p1)

    # 2. Checkerboard pattern
    chk = np.indices((256, 256)).sum(axis=0) % 32 < 16
    im2 = Image.fromarray((chk * 255).astype(np.uint8)).convert("RGB")
    p2 = os.path.join(save_dir, "unrelated_checkerboard.png").replace("\\", "/")
    im2.save(p2)
    unrelated_paths.append(p2)

    # 3. Horizontal striping
    stripes = np.tile(np.linspace(0, 255, 256, dtype=np.uint8), (256, 1))
    im3 = Image.fromarray(stripes).convert("RGB")
    p3 = os.path.join(save_dir, "unrelated_stripes.png").replace("\\", "/")
    im3.save(p3)
    unrelated_paths.append(p3)

    # 4. Diagonal color gradient
    x = np.linspace(0, 255, 256)
    y = np.linspace(0, 255, 256)
    xx, yy = np.meshgrid(x, y)
    im4 = Image.fromarray(np.stack([xx, yy, 255 - xx], axis=-1).astype(np.uint8))
    p4 = os.path.join(save_dir, "unrelated_gradient.png").replace("\\", "/")
    im4.save(p4)
    unrelated_paths.append(p4)

    # 5. Concentric rings (bullseye)
    r = np.sqrt((xx - 128)**2 + (yy - 128)**2)
    im5 = Image.fromarray(((np.sin(r / 8) > 0) * 255).astype(np.uint8)).convert("RGB")
    p5 = os.path.join(save_dir, "unrelated_bullseye.png").replace("\\", "/")
    im5.save(p5)
    unrelated_paths.append(p5)

    # 6-10. Geometric text / natural texture simulations
    for i in range(6, 11):
        arr = np.random.normal(128, 40, (256, 256, 3)).clip(0, 255).astype(np.uint8)
        arr[50:100, 50:100] = [220, 30, 30]  # Red square block
        im_i = Image.fromarray(arr)
        pi = os.path.join(save_dir, f"unrelated_synthetic_{i}.png").replace("\\", "/")
        im_i.save(pi)
        unrelated_paths.append(pi)

    return unrelated_paths


def run_training(smoke: bool = False):
    set_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== CastTrace AI Training Pipeline [Device: {device}] ===")
    if smoke:
        print(">>> RUNNING IN --smoke MODE: Using small sample subset for 1 epoch to verify pipeline. <<<")

    # Load split manifest
    manifest_path = "data/processed/split_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_sha256 = manifest.get("split_manifest_sha256", "")

    train_items = manifest["train"]
    val_items = manifest["val"]

    if smoke:
        def_train = [x for x in train_items if x["label_idx"] == 1][:16]
        ok_train = [x for x in train_items if x["label_idx"] == 0][:16]
        train_items = def_train + ok_train

        def_val = [x for x in val_items if x["label_idx"] == 1][:8]
        ok_val = [x for x in val_items if x["label_idx"] == 0][:8]
        val_items = def_val + ok_val

    train_labels = np.array([x["label_idx"] for x in train_items])
    val_labels = np.array([x["label_idx"] for x in val_items])

    # Compute Majority Baseline
    baseline_stats = compute_majority_baseline(train_labels, val_labels)
    print("\n--- Majority-Class Baseline Performance (Validation) ---", flush=True)
    for k, v in baseline_stats.items():
        print(f"  {k}: {v}", flush=True)

    # Compute Class Weights for Loss Function
    n_total = len(train_labels)
    n_def = int(np.sum(train_labels == 1))
    n_good = int(np.sum(train_labels == 0))
    w_good = n_total / (2.0 * max(n_good, 1))
    w_def = n_total / (2.0 * max(n_def, 1))
    class_weights = torch.tensor([w_good, w_def], dtype=torch.float32).to(device)

    # Datasets and Loaders
    train_transform = get_train_transform()
    eval_transform = get_eval_transform()

    train_ds = CastingDataset(train_items, transform=train_transform)
    val_ds = CastingDataset(val_items, transform=eval_transform)
    val_ds_no_aug = CastingDataset(val_items, transform=eval_transform)
    train_ds_eval = CastingDataset(train_items, transform=eval_transform)

    batch_size = 16 if smoke else 32
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    val_loader_eval = DataLoader(val_ds_no_aug, batch_size=batch_size, shuffle=False)
    train_loader_eval = DataLoader(train_ds_eval, batch_size=batch_size, shuffle=False)

    # Model Setup
    model = build_model(pretrained=True, num_classes=2)
    # Freeze lower conv layers (conv1, bn1, layer1, layer2) to prevent overfitting on small data
    for param in [model.conv1, model.bn1, model.layer1, model.layer2]:
        for p in param.parameters():
            p.requires_grad = False

    model.to(device)

    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=2e-4,
        weight_decay=1e-4,
    )

    epochs = 1 if smoke else 5
    best_f1 = -1.0
    best_model_state = None
    best_metrics = {}
    best_val_probs = None

    print(f"\n--- Beginning Training ({epochs} epochs, {len(train_items)} train images, {len(val_items)} val images) ---")
    for epoch in range(1, epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        val_metrics, val_probs, _ = evaluate_epoch(model, val_loader_eval, criterion, device)
        dt = time.time() - t0

        print(f"Epoch {epoch:02d}/{epochs:02d} [{dt:.1f}s]: "
              f"Train Loss={train_loss:.4f}, Acc={train_acc:.4f} | "
              f"Val Loss={val_metrics['loss']:.4f}, Acc={val_metrics['accuracy']:.4f}, "
              f"Prec={val_metrics['precision']:.4f}, Rec={val_metrics['recall']:.4f}, "
              f"F1={val_metrics['f1_score']:.4f}, AUC={val_metrics['roc_auc']:.4f}")

        if val_metrics["f1_score"] > best_f1:
            best_f1 = val_metrics["f1_score"]
            best_metrics = val_metrics
            best_model_state = {k: v.cpu() for k, v in model.state_dict().items()}
            best_val_probs = val_probs

    # Load best state dict for final evaluation and artifact generation
    model.load_state_dict({k: v.to(device) for k, v in best_model_state.items()})
    model.eval()

    print("\n--- Final Validation Metrics (Best Checkpoint) ---")
    for k, v in best_metrics.items():
        print(f"  {k}: {v}")

    # Optimize Three-Tier Routing Thresholds on Validation Split
    print("\n--- Optimizing Validation Routing Thresholds ---")
    routing_thresholds, routing_eval = optimize_routing_thresholds(
        val_scores=best_val_probs,
        val_labels=val_labels,
        target_precision=0.90,
        target_miss_rate=0.05,
    )
    routing_summary = routing_eval.to_dict()
    print(f"  Selected Thresholds: T_ok <= {routing_thresholds.t_ok}, T_def >= {routing_thresholds.t_def}")
    print(f"  Coverage: Automated={routing_summary['coverage']['automated_routing_coverage']*100:.1f}%, "
          f"Human Review Rate={routing_summary['coverage']['review_rate']*100:.1f}%")
    print(f"  LIKELY_DEFECTIVE Precision: {routing_summary['likely_defective_precision']['value']*100:.1f}% "
          f"(95% CI: {routing_summary['likely_defective_precision']['ci_95']}, Target Met: {routing_summary['likely_defective_precision']['target_met']})")
    print(f"  LIKELY_OK Defective Miss Rate: {routing_summary['likely_ok_miss_rate']['value']*100:.1f}% "
          f"(95% CI: {routing_summary['likely_ok_miss_rate']['ci_95']}, Target Met: {routing_summary['likely_ok_miss_rate']['target_met']})")
    print(f"  False Omission Rate (FOR): {routing_summary['false_omission_rate']['value']*100:.1f}% "
          f"(95% CI: {routing_summary['false_omission_rate']['ci_95']})")

    # Build and Calibrate Unfamiliar-Input Guard
    print("\n--- Extracting Features for Unfamiliar-Input Guard ---")
    train_features, train_y = extract_all_features(model, train_loader_eval, device)
    val_features, val_y = extract_all_features(model, val_loader_eval, device)

    guard, guard_meta = build_guard_reference(
        train_embeddings=train_features,
        train_labels=train_y,
        val_embeddings=val_features,
        model_version="v1.0.0-resnet18",
        feature_extractor_name="resnet18_avgpool_512d",
        selection_percentile=99.0,
    )
    print(f"  Guard Threshold (99th percentile): {guard.guard_threshold:.5f}")
    print(f"  Val In-Distribution Stats: Mean={guard_meta['validation_stats']['val_distance_mean']:.5f}, "
          f"P95={guard_meta['validation_stats']['val_distance_p95']:.5f}, "
          f"Max={guard_meta['validation_stats']['val_distance_max']:.5f}")

    # Evaluate Guard on Unrelated Images Benchmark Collection
    print("\n--- Evaluating Guard on Unrelated Benchmark Collection ---")
    unrelated_paths = create_unrelated_eval_set()
    ood_flags = 0
    ood_distances = []
    eval_transform_fn = get_eval_transform()

    for p in unrelated_paths:
        img = Image.open(p).convert("RGB")
        tensor = eval_transform_fn(img).unsqueeze(0).to(device)
        with torch.no_grad():
            emb = model.extract_features(tensor).cpu().numpy().squeeze(0)
        res = guard.evaluate(emb)
        ood_distances.append(res.distance)
        if res.is_unfamiliar:
            ood_flags += 1

    ood_detection_rate = ood_flags / len(unrelated_paths)
    print(f"  Unrelated Images Evaluated: {len(unrelated_paths)}")
    print(f"  Detected Out-of-Distribution: {ood_flags}/{len(unrelated_paths)} ({ood_detection_rate*100:.1f}%)")
    print(f"  Mean OOD Distance: {np.mean(ood_distances):.5f} (Guard Threshold: {guard.guard_threshold:.5f})")

    # In-distribution false-flag rate on validation set
    val_flags = 0
    for v_emb in val_features:
        res = guard.evaluate(v_emb)
        if res.is_unfamiliar:
            val_flags += 1
    val_false_flag_rate = val_flags / len(val_features)
    print(f"  In-Distribution Validation False-Flag Rate: {val_flags}/{len(val_features)} ({val_false_flag_rate*100:.2f}%)")

    # If smoke mode: finish verification without overwriting production artifacts
    if smoke:
        print("\n>>> SMOKE RUN SUCCESSFUL! Pipeline verified end-to-end. Exiting without overwriting production artifacts. <<<")
        return

    # Save Artifacts
    artifacts_dir = "ml/artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)

    weights_path = os.path.join(artifacts_dir, "model_best.pt")
    torch.save({
        "model_state_dict": best_model_state,
        "metadata": {
            "model_version": "v1.0.0-resnet18",
            "architecture": "ResNet-18",
            "input_size": list(DEFAULT_INPUT_SIZE),
            "class_mapping": {"0": "GOOD", "1": "DEFECTIVE"},
            "train_samples": len(train_items),
            "val_samples": len(val_items),
        }
    }, weights_path)

    with open(weights_path, "rb") as f:
        weights_sha256 = hashlib.sha256(f.read()).hexdigest()

    guard_path = os.path.join(artifacts_dir, "unfamiliar_guard_reference.json")
    guard_sha256 = guard.save(guard_path)

    metadata = {
        "model_version": "v1.0.0-resnet18",
        "model_architecture": "ResNet-18",
        "dataset_source": "casting_512x512",
        "dataset_total_images": 1300,
        "split_manifest_sha256": manifest_sha256,
        "class_mapping": {"0": "GOOD", "1": "DEFECTIVE"},
        "input_size": list(DEFAULT_INPUT_SIZE),
        "preprocessing_parameters": {
            "normalization_mean": IMAGENET_MEAN,
            "normalization_std": IMAGENET_STD,
            "interpolation": "bilinear",
        },
        "weights_file": "model_best.pt",
        "weights_sha256": weights_sha256,
        "guard_reference_file": "unfamiliar_guard_reference.json",
        "guard_reference_sha256": guard_sha256,
        "guard_threshold": guard.guard_threshold,
        "guard_evaluation": {
            "unrelated_eval_samples": len(unrelated_paths),
            "unrelated_detection_rate": ood_detection_rate,
            "validation_false_flag_rate": val_false_flag_rate,
            "limitations": "Small synthetic & texture collection tests gross distributional shift; does not guarantee detection of arbitrary unseen industrial cast products.",
        },
        "routing_thresholds": {
            "t_ok": routing_thresholds.t_ok,
            "t_def": routing_thresholds.t_def,
        },
        "baseline_comparison": {
            "majority_baseline": baseline_stats,
            "model_fine_tuning": best_metrics,
            "improvement_accuracy": round(best_metrics["accuracy"] - baseline_stats["validation_accuracy"], 4),
            "improvement_precision": round(best_metrics["precision"] - baseline_stats["validation_precision"], 4),
            "improvement_roc_auc": round(best_metrics["roc_auc"] - baseline_stats["validation_roc_auc"], 4),
        },
        "validation_metrics": best_metrics,
        "validation_routing": routing_summary,
        "provenance": {
            "random_seed": 42,
            "train_epochs": epochs,
            "optimizer": "AdamW",
            "learning_rate": 2e-4,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    }

    metadata_path = os.path.join(artifacts_dir, "model_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved production checkpoint: {weights_path} (SHA-256: {weights_sha256})")
    print(f"Saved guard reference: {guard_path} (SHA-256: {guard_sha256})")
    print(f"Saved model metadata: {metadata_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CastTrace AI Training & Checkpoint Generator")
    parser.add_argument("--smoke", action="store_true", help="Run fast 1-epoch smoke verification on small subset")
    args = parser.parse_args()
    run_training(smoke=args.smoke)
