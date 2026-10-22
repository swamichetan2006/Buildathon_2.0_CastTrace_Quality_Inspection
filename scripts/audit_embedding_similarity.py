import os
import glob
import json
import time
import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms

def run_embedding_audit():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading pretrained ResNet-18 on {device}...", flush=True)
    
    # Load feature extractor
    weights = models.ResNet18_Weights.DEFAULT
    backbone = models.resnet18(weights=weights)
    modules = list(backbone.children())[:-1]  # Up to avgpool
    extractor = torch.nn.Sequential(*modules).to(device)
    extractor.eval()
    
    transform = transforms.Compose([
        transforms.Resize((224, 224), interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    # 1. Embed primary casting_512x512
    files_512 = sorted(glob.glob("data/raw/casting/casting_512x512/casting_512x512/*/*.jpeg"))
    print(f"Extracting embeddings for {len(files_512)} casting_512x512 images...", flush=True)
    
    embs_512 = []
    t0 = time.time()
    with torch.no_grad():
        for i, p in enumerate(files_512):
            img = Image.open(p).convert("RGB")
            t = transform(img).unsqueeze(0).to(device)
            feat = extractor(t).squeeze().cpu().numpy()
            feat /= np.maximum(np.linalg.norm(feat), 1e-8)
            embs_512.append(feat)
            if (i + 1) % 500 == 0 or (i + 1) == len(files_512):
                print(f"  512x512: {i + 1}/{len(files_512)} ({time.time() - t0:.1f}s)", flush=True)
                
    embs_512 = np.array(embs_512, dtype=np.float32)  # [1300, 512]
    
    # Check internal similarity within casting_512x512
    # Dot product between all normalized embeddings
    print("Computing pairwise similarity within casting_512x512...", flush=True)
    sim_matrix_512 = np.dot(embs_512, embs_512.T)
    np.fill_diagonal(sim_matrix_512, 0.0)  # Exclude self
    
    max_sims_internal = np.max(sim_matrix_512, axis=1)
    high_sim_pairs = []
    for i in range(len(files_512)):
        for j in range(i + 1, len(files_512)):
            if sim_matrix_512[i, j] > 0.98:
                high_sim_pairs.append((
                    os.path.basename(files_512[i]),
                    os.path.basename(files_512[j]),
                    float(sim_matrix_512[i, j]),
                    "DEFECTIVE" if "def_front" in files_512[i] else "GOOD",
                    "DEFECTIVE" if "def_front" in files_512[j] else "GOOD",
                ))
                
    print(f"Internal pairs in 512x512 with cosine similarity > 0.98: {len(high_sim_pairs)}", flush=True)
    for p in high_sim_pairs[:5]:
        print(f"  {p[0]} ({p[3]}) <-> {p[1]} ({p[4]}): sim={p[2]:.4f}", flush=True)
        
    # Check cross-label pairs
    cross_label_high_sim = [p for p in high_sim_pairs if p[3] != p[4]]
    print(f"Cross-label pairs with similarity > 0.98: {len(cross_label_high_sim)}", flush=True)

    # 2. Embed casting_data images to check cross-folder overlap
    files_cdata_train = sorted(glob.glob("data/raw/casting/casting_data/casting_data/train/*/*.jpeg"))
    files_cdata_test = sorted(glob.glob("data/raw/casting/casting_data/casting_data/test/*/*.jpeg"))
    print(f"\nChecking casting_data ({len(files_cdata_train)} train, {len(files_cdata_test)} test)...", flush=True)
    
    # Audit all test set images in casting_data against casting_512x512
    print(f"Auditing casting_data/test ({len(files_cdata_test)} images) against 512x512...", flush=True)
    embs_cdata_test = []
    with torch.no_grad():
        for p in files_cdata_test:
            img = Image.open(p).convert("RGB")
            t = transform(img).unsqueeze(0).to(device)
            feat = extractor(t).squeeze().cpu().numpy()
            feat /= np.maximum(np.linalg.norm(feat), 1e-8)
            embs_cdata_test.append(feat)
    embs_cdata_test = np.array(embs_cdata_test, dtype=np.float32)
    
    # Cross similarity: [715, 1300]
    sim_cdata_test = np.dot(embs_cdata_test, embs_512.T)
    max_sim_test = np.max(sim_cdata_test, axis=1)
    
    matches_99 = np.sum(max_sim_test >= 0.99)
    matches_95 = np.sum(max_sim_test >= 0.95)
    matches_90 = np.sum(max_sim_test >= 0.90)
    print(f"casting_data/test matches against 512x512:")
    print(f"  sim >= 0.99: {matches_99} / {len(files_cdata_test)} ({matches_99/len(files_cdata_test)*100:.1f}%)")
    print(f"  sim >= 0.95: {matches_95} / {len(files_cdata_test)} ({matches_95/len(files_cdata_test)*100:.1f}%)")
    print(f"  sim >= 0.90: {matches_90} / {len(files_cdata_test)} ({matches_90/len(files_cdata_test)*100:.1f}%)")

    # Sample audit of casting_data/train
    sample_cdata_train = files_cdata_train[::5]  # 1 in 5 sample = 1327 images
    print(f"\nAuditing sample of casting_data/train ({len(sample_cdata_train)} images) against 512x512...", flush=True)
    embs_cdata_train_samp = []
    with torch.no_grad():
        for p in sample_cdata_train:
            img = Image.open(p).convert("RGB")
            t = transform(img).unsqueeze(0).to(device)
            feat = extractor(t).squeeze().cpu().numpy()
            feat /= np.maximum(np.linalg.norm(feat), 1e-8)
            embs_cdata_train_samp.append(feat)
    embs_cdata_train_samp = np.array(embs_cdata_train_samp, dtype=np.float32)
    
    sim_cdata_train = np.dot(embs_cdata_train_samp, embs_512.T)
    max_sim_train = np.max(sim_cdata_train, axis=1)
    
    train_matches_99 = np.sum(max_sim_train >= 0.99)
    train_matches_95 = np.sum(max_sim_train >= 0.95)
    train_matches_90 = np.sum(max_sim_train >= 0.90)
    print(f"casting_data/train sample matches against 512x512:")
    print(f"  sim >= 0.99: {train_matches_99} / {len(sample_cdata_train)} ({train_matches_99/len(sample_cdata_train)*100:.1f}%)")
    print(f"  sim >= 0.95: {train_matches_95} / {len(sample_cdata_train)} ({train_matches_95/len(sample_cdata_train)*100:.1f}%)")
    print(f"  sim >= 0.90: {train_matches_90} / {len(sample_cdata_train)} ({train_matches_90/len(sample_cdata_train)*100:.1f}%)")

    # Verify that split groups in split_manifest.json do not cross train/val/test
    with open("ml/artifacts/split_manifest.json", "r") as f:
        manifest = json.load(f)
    train_clusters = set(x["cluster_id"] for x in manifest["train"])
    val_clusters = set(x["cluster_id"] for x in manifest["val"])
    test_clusters = set(x["cluster_id"] for x in manifest["test"])
    
    overlap_tv = train_clusters & val_clusters
    overlap_tt = train_clusters & test_clusters
    overlap_vt = val_clusters & test_clusters
    print(f"\nManifest Cluster Leakage Verification:")
    print(f"  Train & Val cluster overlap: {len(overlap_tv)}")
    print(f"  Train & Test cluster overlap: {len(overlap_tt)}")
    print(f"  Val & Test cluster overlap: {len(overlap_vt)}")

    summary = {
        "internal_high_sim_pairs_98": len(high_sim_pairs),
        "cross_label_high_sim_98": len(cross_label_high_sim),
        "cdata_test_matches_99": int(matches_99),
        "cdata_test_matches_95": int(matches_95),
        "cdata_train_sample_matches_95": int(train_matches_95),
        "cluster_leakage": {
            "train_val_overlap": len(overlap_tv),
            "train_test_overlap": len(overlap_tt),
            "val_test_overlap": len(overlap_vt),
        }
    }
    with open("ml/artifacts/embedding_similarity_audit.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nSaved embedding similarity audit to ml/artifacts/embedding_similarity_audit.json")

if __name__ == "__main__":
    run_embedding_audit()
