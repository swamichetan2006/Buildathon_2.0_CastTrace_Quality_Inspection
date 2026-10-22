import json
import os
import numpy as np
import torch
from PIL import Image

from casttrace_ml.model import build_model
from casttrace_ml.preprocessing import get_eval_transform
from casttrace_ml.quality_gate import check_image_quality
from casttrace_ml.unfamiliar_input import UnfamiliarInputGuard
from casttrace_ml.routing import wilson_score_interval

def run_ordered_routing_audit():
    device = torch.device("cpu")
    print(f"Loading checkpoint and manifest on {device}...", flush=True)

    # 1. Load split manifest
    with open("ml/artifacts/split_manifest.json", "r") as f:
        manifest = json.load(f)
    val_items = manifest["val"]
    print(f"Loaded {len(val_items)} validation items.")

    # 2. Load trained model
    checkpoint = torch.load("ml/artifacts/model_best.pt", map_location=device)
    model = build_model(architecture="resnet18", pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # 3. Load unfamiliar-input guard
    guard = UnfamiliarInputGuard.load("ml/artifacts/unfamiliar_guard_reference.json")
    print(f"Guard loaded. Threshold: {guard.guard_threshold:.5f}")

    eval_transform = get_eval_transform()

    # 4. Run ordered pipeline for each validation image
    val_records = []
    with torch.no_grad():
        for item in val_items:
            path = item["path"]
            label_idx = item["label_idx"]  # 0=GOOD, 1=DEFECTIVE
            raw_img = Image.open(path)

            # Stage 1: Quality Gate
            q_res = check_image_quality(raw_img)

            # Stage 2: Feature Embedding & Unfamiliar-Input Guard
            tensor = eval_transform(raw_img.convert("RGB")).unsqueeze(0).to(device)
            emb = model.extract_features(tensor).squeeze().cpu().numpy()
            emb /= np.maximum(np.linalg.norm(emb), 1e-8)
            g_res = guard.evaluate(emb)

            # Stage 3: Classifier Probability
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze().cpu().numpy()
            score_defective = float(probs[1])

            val_records.append({
                "filename": item["filename"],
                "path": path,
                "label_idx": label_idx,
                "label_name": "DEFECTIVE" if label_idx == 1 else "GOOD",
                "quality_passed": q_res.passed,
                "quality_reason": q_res.reason,
                "is_unfamiliar": g_res.is_unfamiliar,
                "guard_distance": float(g_res.distance),
                "score_defective": score_defective,
            })

    total_val = len(val_records)
    total_good = sum(1 for r in val_records if r["label_idx"] == 0)
    total_def = sum(1 for r in val_records if r["label_idx"] == 1)

    print(f"\nGround Truth Validation Distribution:")
    print(f"  Total Images: {total_val}")
    print(f"  Actual GOOD: {total_good}")
    print(f"  Actual DEFECTIVE: {total_def}")

    quality_failures = [r for r in val_records if not r["quality_passed"]]
    unfamiliar_flags = [r for r in val_records if r["is_unfamiliar"]]

    print(f"\nSafeguard Trigger Counts:")
    print(f"  Quality Gate Failures: {len(quality_failures)} / {total_val}")
    print(f"  Unfamiliar Guard Flags: {len(unfamiliar_flags)} / {total_val}")
    for u in unfamiliar_flags:
        print(f"    - {u['filename']}: actual={u['label_name']}, distance={u['guard_distance']:.5f} (cutoff={guard.guard_threshold:.5f}), score={u['score_defective']:.4f}")

    candidate_thresholds = [
        (0.20, 0.50, "Relaxed OK (0.20 / 0.50)"),
        (0.10, 0.50, "Conservative OK (0.10 / 0.50)"),
        (0.05, 0.50, "Strict OK (0.05 / 0.50)"),
        (0.01, 0.50, "Ultra-Strict Candidate (0.01 / 0.50) [Recommended]"),
        (0.005, 0.50, "Maximum Protection (0.005 / 0.50)"),
    ]

    sweep_results = []
    print(f"\n=================== ORDERED ROUTING EVALUATION ===================")

    for t_ok, t_def, name in candidate_thresholds:
        # Route each record through ordered pipeline:
        # 1. Quality gate -> if failed => NEEDS_REVIEW
        # 2. Unfamiliar guard -> if flagged => NEEDS_REVIEW
        # 3. Model score -> <= t_ok => LIKELY_OK, >= t_def => LIKELY_DEFECTIVE, else => NEEDS_REVIEW
        bucket_records = {
            "LIKELY_OK": {"GOOD": [], "DEFECTIVE": []},
            "NEEDS_REVIEW": {"GOOD": [], "DEFECTIVE": []},
            "LIKELY_DEFECTIVE": {"GOOD": [], "DEFECTIVE": []},
        }

        needs_review_reasons = {
            "quality_failure": {"GOOD": 0, "DEFECTIVE": 0},
            "unfamiliar_guard": {"GOOD": 0, "DEFECTIVE": 0},
            "borderline_score": {"GOOD": 0, "DEFECTIVE": 0},
        }

        for r in val_records:
            lbl = r["label_name"]
            if not r["quality_passed"]:
                outcome = "NEEDS_REVIEW"
                needs_review_reasons["quality_failure"][lbl] += 1
            elif r["is_unfamiliar"]:
                outcome = "NEEDS_REVIEW"
                needs_review_reasons["unfamiliar_guard"][lbl] += 1
            elif r["score_defective"] <= t_ok:
                outcome = "LIKELY_OK"
            elif r["score_defective"] >= t_def:
                outcome = "LIKELY_DEFECTIVE"
            else:
                outcome = "NEEDS_REVIEW"
                needs_review_reasons["borderline_score"][lbl] += 1

            bucket_records[outcome][lbl].append(r)

        # Compute exact counts
        ok_good = len(bucket_records["LIKELY_OK"]["GOOD"])
        ok_def = len(bucket_records["LIKELY_OK"]["DEFECTIVE"])
        ok_total = ok_good + ok_def

        rev_good = len(bucket_records["NEEDS_REVIEW"]["GOOD"])
        rev_def = len(bucket_records["NEEDS_REVIEW"]["DEFECTIVE"])
        rev_total = rev_good + rev_def

        def_good = len(bucket_records["LIKELY_DEFECTIVE"]["GOOD"])
        def_def = len(bucket_records["LIKELY_DEFECTIVE"]["DEFECTIVE"])
        def_total = def_good + def_def

        # Verification of reconciliation
        total_routed = ok_total + rev_total + def_total
        sum_good = ok_good + rev_good + def_good
        sum_def = ok_def + rev_def + def_def

        assert total_routed == 194, f"Total routed {total_routed} != 194"
        assert sum_good == 77, f"Sum of GOOD {sum_good} != 77"
        assert sum_def == 117, f"Sum of DEFECTIVE {sum_def} != 117"

        # Routing coverage and metrics
        auto_coverage = (ok_total + def_total) / total_val
        auto_coverage_ci = wilson_score_interval(ok_total + def_total, total_val)

        review_rate = rev_total / total_val
        review_rate_ci = wilson_score_interval(rev_total, total_val)

        # Defective-image miss rate (Defective images routed to LIKELY_OK / Total actual defective)
        miss_rate = ok_def / total_def
        miss_rate_ci = wilson_score_interval(ok_def, total_def)

        # False Omission Rate (Defective images in LIKELY_OK / Total in LIKELY_OK)
        for_rate = ok_def / ok_total if ok_total > 0 else 0.0
        for_ci = wilson_score_interval(ok_def, ok_total) if ok_total > 0 else (0.0, 0.0)

        # Defective-Class Precision (True Defective in LIKELY_DEFECTIVE / Total in LIKELY_DEFECTIVE)
        prec_def = def_def / def_total if def_total > 0 else 0.0
        prec_def_ci = wilson_score_interval(def_def, def_total) if def_total > 0 else (0.0, 0.0)

        # Defective-Class Recall in LIKELY_DEFECTIVE (True Defective in LIKELY_DEFECTIVE / Total actual defective)
        recall_def = def_def / total_def
        recall_def_ci = wilson_score_interval(def_def, total_def)

        res = {
            "name": name,
            "t_ok": t_ok,
            "t_def": t_def,
            "counts": {
                "LIKELY_OK": {
                    "actual_good": ok_good,
                    "actual_defective": ok_def,
                    "total": ok_total,
                },
                "NEEDS_REVIEW": {
                    "actual_good": rev_good,
                    "actual_defective": rev_def,
                    "total": rev_total,
                    "subcategories": {
                        "quality_gate_failures": needs_review_reasons["quality_failure"],
                        "unfamiliar_guard_flags": needs_review_reasons["unfamiliar_guard"],
                        "borderline_score": needs_review_reasons["borderline_score"],
                    }
                },
                "LIKELY_DEFECTIVE": {
                    "actual_good": def_good,
                    "actual_defective": def_def,
                    "total": def_total,
                },
            },
            "reconciliation": {
                "total_routed": total_routed,
                "sum_actual_good": sum_good,
                "sum_actual_defective": sum_def,
                "balances_perfectly": (total_routed == 194 and sum_good == 77 and sum_def == 117),
            },
            "metrics": {
                "automated_routing_coverage": {
                    "value": round(auto_coverage, 4),
                    "numerator": ok_total + def_total,
                    "denominator": total_val,
                    "ci_95": list(auto_coverage_ci),
                },
                "mandatory_human_review_rate": {
                    "value": round(review_rate, 4),
                    "numerator": rev_total,
                    "denominator": total_val,
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
        }
        sweep_results.append(res)

        print(f"\n--- {name} ---")
        print(f"  LIKELY_OK:        Total={ok_total} (Actual GOOD={ok_good}, Actual DEFECTIVE={ok_def})")
        print(f"  NEEDS_REVIEW:     Total={rev_total} (Actual GOOD={rev_good}, Actual DEFECTIVE={rev_def})")
        print(f"                    [Breakdown: Unfamiliar Guard={needs_review_reasons['unfamiliar_guard']}, Borderline={needs_review_reasons['borderline_score']}]")
        print(f"  LIKELY_DEFECTIVE: Total={def_total} (Actual GOOD={def_good}, Actual DEFECTIVE={def_def})")
        print(f"  Balance Check:    Total={total_routed}/194, GOOD={sum_good}/77, DEFECTIVE={sum_def}/117")
        print(f"  Automated Coverage:      {auto_coverage*100:.2f}% ({ok_total+def_total}/194, 95% CI: [{auto_coverage_ci[0]*100:.2f}%, {auto_coverage_ci[1]*100:.2f}%])")
        print(f"  Mandatory Human Review:  {review_rate*100:.2f}% ({rev_total}/194, 95% CI: [{review_rate_ci[0]*100:.2f}%, {review_rate_ci[1]*100:.2f}%])")
        print(f"  Defective Miss Rate:     {miss_rate*100:.2f}% ({ok_def}/117, 95% CI: [{miss_rate_ci[0]*100:.2f}%, {miss_rate_ci[1]*100:.2f}%])")
        print(f"  False Omission Rate:     {for_rate*100:.2f}% ({ok_def}/{ok_total}, 95% CI: [{for_ci[0]*100:.2f}%, {for_ci[1]*100:.2f}%])")
        print(f"  Defective Precision:     {prec_def*100:.2f}% ({def_def}/{def_total}, 95% CI: [{prec_def_ci[0]*100:.2f}%, {prec_def_ci[1]*100:.2f}%])")
        print(f"  Defective Recall:        {recall_def*100:.2f}% ({def_def}/{total_def}, 95% CI: [{recall_def_ci[0]*100:.2f}%, {recall_def_ci[1]*100:.2f}%])")

    # Save to artifacts
    with open("ml/artifacts/routing_uncertainty_analysis.json", "w") as f:
        json.dump(sweep_results, f, indent=2)
    print("\nSaved ml/artifacts/routing_uncertainty_analysis.json")

    # Update model_metadata.json with exact reconciled counts
    with open("ml/artifacts/model_metadata.json", "r") as f:
        meta = json.load(f)

    rec = next(r for r in sweep_results if r["t_ok"] == 0.01 and r["t_def"] == 0.50)
    meta["validation_routing"] = {
        "candidate_thresholds": {
            "t_ok": 0.01,
            "t_def": 0.50,
            "status": "Candidate threshold pending held-out test evaluation",
            "selection_bias_note": "Thresholds were selected on the validation set. Confidence intervals reflect validation sampling uncertainty and do not constitute an operational guarantee."
        },
        "ordered_pipeline_stages": [
            "1. Input image usability and quality gate (resolution, blur, photometric exposure)",
            "2. Unfamiliar-input guard (512D penultimate feature cosine distance vs training reference)",
            "3. Binary classifier score evaluated against calibrated routing thresholds",
            "4. Final image-level routing outcome (LIKELY_OK, NEEDS_REVIEW, LIKELY_DEFECTIVE)"
        ],
        "validation_ground_truth": {
            "total_images": 194,
            "actual_good": 77,
            "actual_defective": 117
        },
        "ordered_routing_counts": rec["counts"],
        "reconciliation": rec["reconciliation"],
        "metrics": rec["metrics"],
    }

    # Update dataset licence documentation in metadata
    meta["dataset_licence_review"] = {
        "dataset_name": "Real Life Industrial Dataset of Casting Product",
        "kaggle_url": "https://www.kaggle.com/datasets/ravirajsinh45/real-life-industrial-dataset-of-casting-product",
        "publisher": "ravirajsinh45 (Ravirajsinh Dabhi)",
        "original_source": "Pilot plant submersible pump impeller casting inspection",
        "licence": "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)",
        "commercial_use": "Prohibited (NonCommercial constraint)",
        "derivatives": "NoDerivatives constraint applies to distribution of modified material",
        "redistribution_status": "RESTRICTED. Local research/prototyping artifact only. Do not publish raw dataset or model weights.",
        "trained_weights_status": "Legal status of neural network weights under CC BY-NC-ND 4.0 is unverified/unresolved. Weights are retained locally as private project artifacts and must not be distributed."
    }

    with open("ml/artifacts/model_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("Updated ml/artifacts/model_metadata.json with reconciled routing and CC BY-NC-ND 4.0 licence details.")

if __name__ == "__main__":
    run_ordered_routing_audit()
