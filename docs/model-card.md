# CastTrace AI — Model Card: ResNet-18 Defect Classifier

**Model Card Version:** 1.0.0  
**Model Date:** 2026-10-22  
**Framework:** PyTorch 2.14 / Torchvision  
**Architecture:** ResNet-18 (512-dimensional penultimate feature representation)  
**Status:** Frozen, Validated, and Evaluated on Held-Out Test Set (Phase 3A-Final)

---

## 1. Model Details

- **Model Developer:** CastTrace AI Engineering Team (Buildathon 2.0).
- **Model Type:** Supervised Convolutional Neural Network (Transfer Learning via ImageNet-1K V1 weights with fine-tuned linear classification head).
- **Target Task:** Binary visual quality inspection of top-down submersible pump impeller castings (`0 = GOOD`, `1 = DEFECTIVE`).
- **Feature Extraction:** 512-dimensional feature embedding via adaptive average pooling layer, utilized for unfamiliar-input outlier detection.
- **Model Weights Artifact:** `ml/artifacts/model_best.pt` (SHA-256: `ab2b592ab9a4cca3c97613d8e52d9f8abc2906dbef77cddd15c73d2da1c3c2da`).
- **Inference Latency:** ~24.8 ms on CPU / ~4.2 ms on CUDA.

---

## 2. Intended Use & Workflow Role

### 2.1 Intended Applications
- **Automated Shop-Floor Triage:** Assist staging and in-process visual inspectors by scoring casting images and routing them into `LIKELY_OK`, `NEEDS_REVIEW`, and `LIKELY_DEFECTIVE`.
- **Quality Alert Escalation:** Trigger immediate shop-floor containment recommendations when consecutive high-probability defects are detected.
- **Audit Traceability:** Provide deterministic probability scores and feature embeddings stored with inspection records for auditability.

### 2.2 Out-of-Scope & Prohibited Uses
- **No Autonomous Batch Release:** The model is strictly prohibited from autonomously releasing production batches to shipping. Batch release is restricted to authorized `QUALITY_MANAGER` personnel.
- **No Direct Actuation of Scrap:** The model does not autonomously discard physical inventory; all containment decisions require human verification.
- **Uncalibrated Geometries:** Applying the model to non-impeller castings (e.g. engine blocks, valves) without retraining is prohibited.

---

## 3. Factors, Subpopulations & Environmental Sensitivity

- **Image Geometry:** Specifically calibrated for circular top-down views of 6-vane submersible pump impellers centered in frame.
- **Lighting Sensitivity:** Diffuse circular overhead illumination is assumed. Harsh oblique spot lighting can cause false alarms due to cast shadows mimicking blowholes.
- **Foreign Materials:** Machining oil droplets, metal dust, or water spots on the part surface may increase defect probability scores.

---

## 4. Metrics & Target Specifications

| Performance Domain | Metric | Target Specification | Held-Out Test Result | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Escaped Defects** | **Defective Miss Rate** | $\le 5.0\%$ | **0.00%** [95% CI: $0.00\%, 3.15\%$] | **Target Exceeded** |
| **False Rejections** | **False Omission Rate** | Minimise | **0.00%** [95% CI: $0.00\%, 5.35\%$] | **Optimal** |
| **Defect Flag Precision** | **Defective Precision** | $\ge 90.0\%$ | **98.33%** [95% CI: $94.13\%, 99.54\%$] | **Target Exceeded** |
| **Defect Flag Recall** | **Defective Recall** | Maximise | **100.00%** [95% CI: $96.85\%, 100.00\%$]| **Optimal** |
| **Triage Utility** | **Automated Coverage** | Retain utility | **95.43%** [95% CI: $91.55\%, 97.58\%$] | **Target Met** |
| **Review Workload** | **Mandatory Review Rate**| Controlled | **4.57%** [95% CI: $2.42\%, 8.45\%$] | **Target Met** |
| **Overall Discrimination**| **Balanced Accuracy** | $\ge 95.0\%$ | **98.73%** | **Target Exceeded** |
| **Separability** | **ROC-AUC** | $\ge 0.990$ | **0.9996** | **Target Exceeded** |

---

## 5. Training, Validation & Test Data

### 5.1 Dataset Provenance & Licensing
- **Source:** *Real Life Industrial Dataset of Casting Product* by Ravirajsinh Dabhi (`ravirajsinh45` on Kaggle).
- **Licence:** Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (**CC BY-NC-ND 4.0**).
- **Distribution Notice:** Dataset files and trained weights are retained strictly as private, local-only project artifacts.

### 5.2 Split Breakdown (1,300 Images Total)
- **Train (70%, 909 images):** 363 conforming, 546 defective.
- **Validation (15%, 194 images):** 77 conforming, 117 defective.
- **Held-Out Test (15%, 197 images):** 79 conforming, 118 defective.
- **Isolation Guarantee:** Perceptual hash rotation/flip clusters were grouped atomically to eliminate data leakage across splits.

---

## 6. Preprocessing & Defensive Safeguards

### 6.1 Deterministic Preprocessing
1. Center crop and resize to $300 \times 300$ square with bilinear interpolation.
2. Conversion to floating-point tensor in $[0.0, 1.0]$.
3. Channel standardization: ImageNet mean $[0.485, 0.456, 0.406]$, std $[0.229, 0.224, 0.225]$.

### 6.2 Defensive Safeguards (Ordered Pipeline)
- **Quality Gate:** Checks minimum resolution ($\ge 200 \times 200$), Laplacian blur variance ($\ge 100.0$), and mean photometric exposure ($30 \le \mu \le 225$).
- **Unfamiliar-Input Guard:** Compares penultimate 512-D normalized feature embedding against Gaussian reference distribution derived from training set. Cutoff threshold: $d_{\text{cutoff}} = 0.13709$.

---

## 7. Quantitative Results & Confusion Matrix

![Confusion Matrix](docs/assets/confusion_matrix.png)

### Summary of Held-Out Confusion Matrix:
- $TN = 77$ (True Conforming)
- $FP = 2$ (Conforming flagged with defect probability $\ge 0.50$)
- $FN = 0$ (Defect escaping undetected)
- $TP = 118$ (Defects correctly captured)

---

## 8. Limitations & Human Oversight

1. **Local License Constraint:** Weights and raw images must not be redistributed publicly due to CC BY-NC-ND 4.0 restrictions.
2. **Human-in-the-Loop:** All items routed to `NEEDS_REVIEW` and `LIKELY_DEFECTIVE` require visual sign-off by a certified human inspector.
3. **Threshold Calibration:** The approved candidate thresholds ($T_{\text{ok}} = 0.01, T_{\text{def}} = 0.50$) achieved 0.00% miss rate on the held-out test partition, confirming out-of-sample generalisation.
