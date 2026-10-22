import os
import glob
import hashlib
import json
import time
import numpy as np
from PIL import Image
import imagehash
from collections import defaultdict

def get_canonical_hashes(img_path):
    """Compute raw sha256, normalized sha256, and rotation/flip invariant perceptual hash."""
    with open(img_path, "rb") as f:
        raw_bytes = f.read()
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    
    with Image.open(img_path) as img:
        size = img.size
        # Grayscale normalized
        img_gray = img.convert("L").resize((256, 256), Image.Resampling.BILINEAR)
        norm_sha256 = hashlib.sha256(np.array(img_gray).tobytes()).hexdigest()
        
        # Base dhash (8x8) and phash (8x8)
        d_h = imagehash.dhash(img_gray)
        p_h = imagehash.phash(img_gray)
        
        # 8 geometric transforms on the boolean 8x8 array
        d_arr = d_h.hash
        p_arr = p_h.hash
        
        transforms_d = [
            d_arr,
            np.rot90(d_arr, 1),
            np.rot90(d_arr, 2),
            np.rot90(d_arr, 3),
            np.fliplr(d_arr),
            np.flipud(d_arr),
            np.rot90(np.fliplr(d_arr), 1),
            np.rot90(np.fliplr(d_arr), 3),
        ]
        
        transforms_p = [
            p_arr,
            np.rot90(p_arr, 1),
            np.rot90(p_arr, 2),
            np.rot90(p_arr, 3),
            np.fliplr(p_arr),
            np.flipud(p_arr),
            np.rot90(np.fliplr(p_arr), 1),
            np.rot90(np.fliplr(p_arr), 3),
        ]
        
        # Represent each transformed boolean array as 64-bit hex
        hex_d = [imagehash.ImageHash(t).__str__() for t in transforms_d]
        hex_p = [imagehash.ImageHash(t).__str__() for t in transforms_p]
        
        canonical_dhash = min(hex_d)
        canonical_phash = min(hex_p)
        
        return {
            "path": img_path.replace("\\", "/"),
            "filename": os.path.basename(img_path),
            "size": size,
            "raw_sha256": raw_sha256,
            "norm_sha256": norm_sha256,
            "base_dhash": str(d_h),
            "canonical_dhash": canonical_dhash,
            "canonical_phash": canonical_phash,
        }

def run_audit():
    t0 = time.time()
    print("=== STEP 1: AUDITING casting_512x512 (1,300 IMAGES) ===", flush=True)
    c512_files = sorted(glob.glob("data/raw/casting/casting_512x512/casting_512x512/*/*.jpeg"))
    print(f"Found {len(c512_files)} files in casting_512x512.", flush=True)
    
    c512_records = []
    for i, path in enumerate(c512_files):
        label = "DEFECTIVE" if "def_front" in path else "GOOD"
        rec = get_canonical_hashes(path)
        rec["label"] = label
        c512_records.append(rec)
        if (i + 1) % 500 == 0 or (i + 1) == len(c512_files):
            print(f"  Processed {i + 1}/{len(c512_files)} 512x512 images ({time.time() - t0:.1f}s)", flush=True)
            
    # Check 1: Raw byte SHA-256 duplicates in 512x512
    raw_sha_groups = defaultdict(list)
    for r in c512_records:
        raw_sha_groups[r["raw_sha256"]].append(r)
    exact_dups = {k: v for k, v in raw_sha_groups.items() if len(v) > 1}
    print(f"\n1. Exact Byte-Level Duplicates in 512x512: {len(exact_dups)} clusters", flush=True)
    
    # Check 2: Normalized pixel SHA-256 duplicates
    norm_sha_groups = defaultdict(list)
    for r in c512_records:
        norm_sha_groups[r["norm_sha256"]].append(r)
    norm_dups = {k: v for k, v in norm_sha_groups.items() if len(v) > 1}
    print(f"2. Normalized Pixel SHA-256 Duplicates in 512x512: {len(norm_dups)} clusters", flush=True)
    
    # Check 3: Canonical (Rotation/Flip Invariant) Hash Duplicates
    canon_d_groups = defaultdict(list)
    for r in c512_records:
        canon_d_groups[r["canonical_dhash"]].append(r)
    canon_dups = {k: v for k, v in canon_d_groups.items() if len(v) > 1}
    print(f"3. Canonical Rotation/Flip Hash Identical Clusters in 512x512: {len(canon_dups)} clusters", flush=True)
    
    # Check 4: Cross-label collision (any cluster with both GOOD and DEFECTIVE)
    cross_label_collisions = []
    for k, v in canon_dups.items():
        labels = set(x["label"] for x in v)
        if len(labels) > 1:
            cross_label_collisions.append((k, v))
    print(f"4. Cross-label collisions in 512x512: {len(cross_label_collisions)}", flush=True)
    
    # STEP 2: Cross-Folder Comparison with casting_data
    print("\n=== STEP 2: CROSS-FOLDER AUDIT WITH casting_data (7,348 IMAGES) ===", flush=True)
    t1 = time.time()
    cdata_files = sorted(glob.glob("data/raw/casting/casting_data/casting_data/*/*/*.jpeg"))
    print(f"Found {len(cdata_files)} files in casting_data.", flush=True)
    
    # Map 512x512 canonical hashes
    c512_canon_map = defaultdict(list)
    for r in c512_records:
        c512_canon_map[r["canonical_dhash"]].append(r)
        
    cdata_matches_in_512 = 0
    cdata_test_matches_in_512 = 0
    cdata_train_matches_in_512 = 0
    
    for i, path in enumerate(cdata_files):
        rec = get_canonical_hashes(path)
        is_test = "test" in path
        if rec["canonical_dhash"] in c512_canon_map:
            cdata_matches_in_512 += 1
            if is_test:
                cdata_test_matches_in_512 += 1
            else:
                cdata_train_matches_in_512 += 1
        if (i + 1) % 2000 == 0 or (i + 1) == len(cdata_files):
            print(f"  Audited {i + 1}/{len(cdata_files)} casting_data files ({time.time() - t1:.1f}s)...", flush=True)
            
    print(f"\nResults of Cross-Folder Matching:", flush=True)
    print(f"  Total casting_data images: {len(cdata_files)}", flush=True)
    print(f"  Matches to 512x512 canonical rotation/flip hashes: {cdata_matches_in_512} ({cdata_matches_in_512 / len(cdata_files) * 100:.2f}%)", flush=True)
    print(f"  casting_data/train matching 512x512: {cdata_train_matches_in_512} / 6633 ({cdata_train_matches_in_512 / 6633 * 100:.2f}%)", flush=True)
    print(f"  casting_data/test matching 512x512: {cdata_test_matches_in_512} / 715 ({cdata_test_matches_in_512 / 715 * 100:.2f}%)", flush=True)
    
    audit_results = {
        "c512_total": len(c512_files),
        "c512_def": sum(1 for r in c512_records if r["label"] == "DEFECTIVE"),
        "c512_ok": sum(1 for r in c512_records if r["label"] == "GOOD"),
        "exact_byte_duplicates_512": len(exact_dups),
        "canon_hash_duplicates_512": len(canon_dups),
        "cross_label_collisions_512": len(cross_label_collisions),
        "cdata_total": len(cdata_files),
        "cdata_matches_in_512": cdata_matches_in_512,
        "cdata_train_matches_in_512": cdata_train_matches_in_512,
        "cdata_test_matches_in_512": cdata_test_matches_in_512,
    }
    
    os.makedirs("data/processed", exist_ok=True)
    with open("data/processed/dataset_audit.json", "w") as f:
        json.dump(audit_results, f, indent=2)
    print("\nSaved audit summary to data/processed/dataset_audit.json", flush=True)
    print(f"Total Audit Execution Time: {time.time() - t0:.1f}s", flush=True)

if __name__ == "__main__":
    run_audit()
