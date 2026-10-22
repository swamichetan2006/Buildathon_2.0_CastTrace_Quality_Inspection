import json
import os
import hashlib
import numpy as np
import torch
from PIL import Image
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)

from casttrace_ml.model import build_model
from casttrace_ml.preprocessing import get_eval_transform
from casttrace_ml.quality_gate import check_image_quality
from casttrace_ml.unfamiliar_input import UnfamiliarInputGuard
from casttrace_ml.routing import wilson_score_interval

def sha256_of_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def evaluate_held_out_test():
    print("=== CASTTRACE AI: PHASE 3A-FINAL HELD-OUT EVALUATION ===", flush=True)

    # 1. Pre-evaluation cryptographic hash verification
    expected_hashes = {
        "model_best.pt": "ab2b592ab9a4cca3c97613d8e52d9f8abc2906dbef77cddd15c73d2da1c3c2da",
        "split_manifest.json": "7ab58f05d9055203150ad679d8501950003174eb8e78d4276eb4ea31e78799c7",
        "unfamiliar_guard_reference.json": "c39905c247cd881175439833661610ce8d0dbff18811057fb289dfb24c464abc",
    }

    print("\n1. Verifying frozen artifact hashes...")
    verified_hashes = {}
    for filename, expected_h in expected_hashes.items():
        filepath = os.path.join("ml", "artifacts", filename)
        actual_h = sha256_of_file(filepath)
        print(f"  {filename}: {actual_h}")
        assert actual_h == expected_h, f"Hash mismatch for {filename}: expected {expected_h}, got {actual_h}"
        verified_hashes[filename] = actual_h
    print("  Artifact verification SUCCESS: All frozen model artifacts match approved hashes.")

    # 2. Load manifest and verify test set count
    with open("ml/artifacts/split_manifest.json", "r") as f:
        manifest = json.load(f)
    test_items = manifest["test"]
    n_test = len(test_items)
    print(f"\n2. Loaded {n_test} held-out test images from split manifest.")
    assert n_test == 197, f"Expected exactly 197 test images, got {n_test}"

    # Load frozen metadata to check approved candidate thresholds
    with open("ml/artifacts/model_metadata.json", "r") as f:
        metadata = json.load(f)
    t_ok = metadata["validation_routing"]["candidate_thresholds"]["t_ok"]
    t_def = metadata["validation_routing"]["candidate_thresholds"]["t_def"]
    print(f"  Approved candidate routing thresholds: T_ok = {t_ok}, T_def = {t_def}")

    # 3. Load model and guard
    device = torch.device("cpu")
    checkpoint = torch.load("ml/artifacts/model_best.pt", map_location=device)
    model = build_model(architecture="resnet18", pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    guard = UnfamiliarInputGuard.load("ml/artifacts/unfamiliar_guard_reference.json")
    print(f"  Guard threshold: {guard.guard_threshold:.5f}")

    eval_transform = get_eval_transform()

    # 4. Execute one-time evaluation on test set
    test_records = []
    print("\n3. Executing ordered pipeline across 197 held-out test images...")
    with torch.no_grad():
        for i, item in enumerate(test_items):
            path = item["path"]
            label_idx = item["label_idx"]  # 0=GOOD, 1=DEFECTIVE
            raw_img = Image.open(path)

            # Stage 1: Quality Gate
            q_res = check_image_quality(raw_img)

            # Stage 2: Feature embedding & Unfamiliar guard
            tensor = eval_transform(raw_img.convert("RGB")).unsqueeze(0).to(device)
            emb = model.extract_features(tensor).squeeze().cpu().numpy()
            emb /= np.maximum(np.linalg.norm(emb), 1e-8)
            g_res = guard.evaluate(emb)

            # Stage 3: Classifier logits and probability
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze().cpu().numpy()
            score_defective = float(probs[1])

            # Stage 4: Ordered routing
            if not q_res.passed:
                outcome = "NEEDS_REVIEW"
                route_reason = f"Quality gate failure: {q_res.reason}"
            elif g_res.is_unfamiliar:
                outcome = "NEEDS_REVIEW"
                route_reason = f"Unfamiliar input guard alert (distance {g_res.distance:.5f} > cutoff {guard.guard_threshold:.5f})"
            elif score_defective <= t_ok:
                outcome = "LIKELY_OK"
                route_reason = f"High confidence conforming (P_def {score_defective:.5f} <= {t_ok})"
            elif score_defective >= t_def:
                outcome = "LIKELY_DEFECTIVE"
                route_reason = f"Defect detected (P_def {score_defective:.5f} >= {t_def})"
            else:
                outcome = "NEEDS_REVIEW"
                route_reason = f"Borderline score ({t_ok} < P_def {score_defective:.5f} < {t_def})"

            test_records.append({
                "filename": item["filename"],
                "path": path,
                "label_idx": label_idx,
                "label_name": "DEFECTIVE" if label_idx == 1 else "GOOD",
                "quality_passed": q_res.passed,
                "quality_reason": q_res.reason,
                "is_unfamiliar": g_res.is_unfamiliar,
                "guard_distance": float(g_res.distance),
                "score_defective": score_defective,
                "predicted_binary_class": 1 if score_defective >= 0.50 else 0,
                "routing_outcome": outcome,
                "routing_reason": route_reason,
            })

    # Ground truth counts
    y_true = np.array([r["label_idx"] for r in test_records])
    y_scores = np.array([r["score_defective"] for r in test_records])
    y_pred_binary = np.array([r["predicted_binary_class"] for r in test_records])

    total_good = int(np.sum(y_true == 0))
    total_def = int(np.sum(y_true == 1))
    print(f"\n4. Held-Out Ground Truth Distribution:")
    print(f"  Total Images: {n_test}")
    print(f"  Actual GOOD: {total_good}")
    print(f"  Actual DEFECTIVE: {total_def}")

    # Binary Classification Metrics at standard 0.50 threshold
    acc = float(accuracy_score(y_true, y_pred_binary))
    prec = float(precision_score(y_true, y_pred_binary, zero_division=0))
    rec = float(recall_score(y_true, y_pred_binary, zero_division=0))
    f1 = float(f1_score(y_true, y_pred_binary, zero_division=0))
    roc_auc = float(roc_auc_score(y_true, y_scores))
    pr_auc = float(average_precision_score(y_true, y_scores))
    cm = confusion_matrix(y_true, y_pred_binary)  # [[TN, FP], [FN, TP]]
    tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

    print(f"\n5. Standard Binary Classification Metrics (Threshold 0.50):")
    print(f"  Accuracy:  {acc*100:.2f}% ({tp+tn}/{n_test})")
    print(f"  Precision: {prec*100:.2f}% ({tp}/{tp+fp})")
    print(f"  Recall:    {rec*100:.2f}% ({tp}/{tp+fn})")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"  ROC-AUC:   {roc_auc:.4f}")
    print(f"  PR-AUC:    {pr_auc:.4f}")
    print(f"  Confusion Matrix: TN={tn}, FP={fp}, FN={fn}, TP={tp}")

    # Ordered Routing Table Analysis
    bucket_counts = {
        "LIKELY_OK": {"GOOD": 0, "DEFECTIVE": 0},
        "NEEDS_REVIEW": {"GOOD": 0, "DEFECTIVE": 0},
        "LIKELY_DEFECTIVE": {"GOOD": 0, "DEFECTIVE": 0},
    }
    review_causes = {
        "quality_gate": {"GOOD": 0, "DEFECTIVE": 0},
        "unfamiliar_guard": {"GOOD": 0, "DEFECTIVE": 0},
        "borderline_score": {"GOOD": 0, "DEFECTIVE": 0},
    }

    for r in test_records:
        lbl = r["label_name"]
        outcome = r["routing_outcome"]
        bucket_counts[outcome][lbl] += 1
        if outcome == "NEEDS_REVIEW":
            if not r["quality_passed"]:
                review_causes["quality_gate"][lbl] += 1
            elif r["is_unfamiliar"]:
                review_causes["unfamiliar_guard"][lbl] += 1
            else:
                review_causes["borderline_score"][lbl] += 1

    ok_good = bucket_counts["LIKELY_OK"]["GOOD"]
    ok_def = bucket_counts["LIKELY_OK"]["DEFECTIVE"]
    ok_total = ok_good + ok_def

    rev_good = bucket_counts["NEEDS_REVIEW"]["GOOD"]
    rev_def = bucket_counts["NEEDS_REVIEW"]["DEFECTIVE"]
    rev_total = rev_good + rev_def

    def_good = bucket_counts["LIKELY_DEFECTIVE"]["GOOD"]
    def_def = bucket_counts["LIKELY_DEFECTIVE"]["DEFECTIVE"]
    def_total = def_good + def_def

    # Reconciliation assertions
    total_routed = ok_total + rev_total + def_total
    sum_good = ok_good + rev_good + def_good
    sum_def = ok_def + rev_def + def_def
    assert total_routed == n_test, f"Total routed {total_routed} != {n_test}"
    assert sum_good == total_good, f"Sum GOOD {sum_good} != {total_good}"
    assert sum_def == total_def, f"Sum DEFECTIVE {sum_def} != {total_def}"

    # Routing metrics & Wilson CIs
    auto_coverage = (ok_total + def_total) / n_test
    auto_coverage_ci = wilson_score_interval(ok_total + def_total, n_test)

    review_rate = rev_total / n_test
    review_rate_ci = wilson_score_interval(rev_total, n_test)

    miss_rate = ok_def / total_def
    miss_rate_ci = wilson_score_interval(ok_def, total_def)

    for_rate = ok_def / ok_total if ok_total > 0 else 0.0
    for_ci = wilson_score_interval(ok_def, ok_total) if ok_total > 0 else (0.0, 0.0)

    prec_def = def_def / def_total if def_total > 0 else 0.0
    prec_def_ci = wilson_score_interval(def_def, def_total) if def_total > 0 else (0.0, 0.0)

    recall_def = def_def / total_def
    recall_def_ci = wilson_score_interval(def_def, total_def)

    print(f"\n6. Ordered Routing Pipeline Results (T_ok={t_ok}, T_def={t_def}):")
    print(f"  LIKELY_OK:        Total={ok_total} (Actual GOOD={ok_good}, Actual DEFECTIVE={ok_def})")
    print(f"  NEEDS_REVIEW:     Total={rev_total} (Actual GOOD={rev_good}, Actual DEFECTIVE={rev_def})")
    print(f"                    [Causes: Guard={review_causes['unfamiliar_guard']}, Borderline={review_causes['borderline_score']}, Quality={review_causes['quality_gate']}]")
    print(f"  LIKELY_DEFECTIVE: Total={def_total} (Actual GOOD={def_good}, Actual DEFECTIVE={def_def})")
    print(f"  Reconciliation:   Total={total_routed}/{n_test}, GOOD={sum_good}/{total_good}, DEFECTIVE={sum_def}/{total_def}")
    print(f"  Automated Coverage:      {auto_coverage*100:.2f}% ({ok_total+def_total}/{n_test}, 95% CI: [{auto_coverage_ci[0]*100:.2f}%, {auto_coverage_ci[1]*100:.2f}%])")
    print(f"  Mandatory Human Review:  {review_rate*100:.2f}% ({rev_total}/{n_test}, 95% CI: [{review_rate_ci[0]*100:.2f}%, {review_rate_ci[1]*100:.2f}%])")
    print(f"  Defective Miss Rate:     {miss_rate*100:.2f}% ({ok_def}/{total_def}, 95% CI: [{miss_rate_ci[0]*100:.2f}%, {miss_rate_ci[1]*100:.2f}%])")
    print(f"  False Omission Rate:     {for_rate*100:.2f}% ({ok_def}/{ok_total}, 95% CI: [{for_ci[0]*100:.2f}%, {for_ci[1]*100:.2f}%])")
    print(f"  Defective Precision:     {prec_def*100:.2f}% ({def_def}/{def_total}, 95% CI: [{prec_def_ci[0]*100:.2f}%, {prec_def_ci[1]*100:.2f}%])")
    print(f"  Defective Recall:        {recall_def*100:.2f}% ({def_def}/{total_def}, 95% CI: [{recall_def_ci[0]*100:.2f}%, {recall_def_ci[1]*100:.2f}%])")

    # Detailed Error Analysis
    unfamiliar_flags = [r for r in test_records if r["is_unfamiliar"]]
    borderline_cases = [r for r in test_records if r["routing_outcome"] == "NEEDS_REVIEW" and not r["is_unfamiliar"] and r["quality_passed"]]
    false_omissions = [r for r in test_records if r["routing_outcome"] == "LIKELY_OK" and r["label_name"] == "DEFECTIVE"]
    false_defects = [r for r in test_records if r["routing_outcome"] == "LIKELY_DEFECTIVE" and r["label_name"] == "GOOD"]

    print(f"\n7. Granular Error & Outlier Analysis:")
    print(f"  Unfamiliar Guard Flags ({len(unfamiliar_flags)}):")
    for u in unfamiliar_flags:
        print(f"    - {u['filename']}: actual={u['label_name']}, distance={u['guard_distance']:.5f}, score={u['score_defective']:.4f}")
    print(f"  Borderline Scores Routed to Review ({len(borderline_cases)}):")
    for b in borderline_cases:
        print(f"    - {b['filename']}: actual={b['label_name']}, score={b['score_defective']:.4f}")
    print(f"  False Omissions in LIKELY_OK ({len(false_omissions)}):")
    for fo in false_omissions:
        print(f"    - {fo['filename']}: actual={fo['label_name']}, score={fo['score_defective']:.4f}")
    print(f"  False Defect Flags in LIKELY_DEFECTIVE ({len(false_defects)}):")
    for fd in false_defects:
        print(f"    - {fd['filename']}: actual={fd['label_name']}, score={fd['score_defective']:.4f}")

    # Build comprehensive output artifact
    report_data = {
        "evaluation_name": "Phase 3A-Final Held-Out Test Evaluation",
        "timestamp_utc": "2026-10-22T05:15:00Z",
        "artifact_verification": verified_hashes,
        "sample_counts": {
            "total_test_images": n_test,
            "actual_good": total_good,
            "actual_defective": total_def,
        },
        "binary_classification_metrics_0_50": {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "confusion_matrix": {
                "true_negative_good": tn,
                "false_positive_defective": fp,
                "false_negative_good": fn,
                "true_positive_defective": tp,
            }
        },
        "ordered_routing_evaluation": {
            "thresholds": {"t_ok": t_ok, "t_def": t_def},
            "counts": {
                "LIKELY_OK": {"actual_good": ok_good, "actual_defective": ok_def, "total": ok_total},
                "NEEDS_REVIEW": {
                    "actual_good": rev_good,
                    "actual_defective": rev_def,
                    "total": rev_total,
                    "causes": review_causes,
                },
                "LIKELY_DEFECTIVE": {"actual_good": def_good, "actual_defective": def_def, "total": def_total},
            },
            "reconciliation": {
                "total_routed": total_routed,
                "sum_good": sum_good,
                "sum_def": sum_def,
                "balances_perfectly": (total_routed == n_test and sum_good == total_good and sum_def == total_def),
            },
            "metrics": {
                "automated_routing_coverage": {
                    "value": round(auto_coverage, 4),
                    "numerator": ok_total + def_total,
                    "denominator": n_test,
                    "ci_95": list(auto_coverage_ci),
                },
                "mandatory_human_review_rate": {
                    "value": round(review_rate, 4),
                    "numerator": rev_total,
                    "denominator": n_test,
                    "ci_95": list(review_rate_ci),
                },
                "defective_miss_rate": {
                    "value": round(miss_rate, 4),
                    "numerator": ok_def,
                    "denominator": total_def,
                    "ci_95": list(miss_rate_ci),
                    "target_met_point": miss_rate <= 0.05,
                    "target_met_upper_ci": miss_rate_ci[1] <= 0.05,
                },
                "false_omission_rate": {
                    "value": round(for_rate, 4),
                    "numerator": ok_def,
                    "denominator": ok_total,
                    "ci_95": list(for_ci),
                },
                "defective_precision": {
                    "value": round(prec_def, 4),
                    "numerator": def_def,
                    "denominator": def_total,
                    "ci_95": list(prec_def_ci),
                },
                "defective_recall": {
                    "value": round(recall_def, 4),
                    "numerator": def_def,
                    "denominator": total_def,
                    "ci_95": list(recall_def_ci),
                },
            }
        },
        "error_analysis": {
            "unfamiliar_guard_flags": unfamiliar_flags,
            "borderline_score_cases": borderline_cases,
            "false_omissions": false_omissions,
            "false_defects": false_defects,
        },
    }

    report_path = "ml/artifacts/test_evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n7. Written complete test evaluation report to {report_path}")

    # Update model_metadata.json with test evaluation section
    metadata["held_out_test_evaluation"] = {
        "status": "COMPLETED_ONE_TIME_EVALUATION",
        "timestamp_utc": "2026-10-22T05:15:00Z",
        "sample_size": n_test,
        "actual_good": total_good,
        "actual_defective": total_def,
        "binary_classification": report_data["binary_classification_metrics_0_50"],
        "ordered_routing": report_data["ordered_routing_evaluation"],
    }
    with open("ml/artifacts/model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("Updated ml/artifacts/model_metadata.json with held_out_test_evaluation section.")

if __name__ == "__main__":
    evaluate_held_out_test()
