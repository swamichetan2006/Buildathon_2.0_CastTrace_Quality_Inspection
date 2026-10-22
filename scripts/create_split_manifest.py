import os
import glob
import hashlib
import json
import random
from collections import defaultdict
import numpy as np
from PIL import Image
import imagehash

def get_canonical_dhash(img_path):
    with Image.open(img_path) as img:
        img_gray = img.convert("L").resize((256, 256), Image.Resampling.BILINEAR)
        d_arr = imagehash.dhash(img_gray).hash
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
        hex_d = [imagehash.ImageHash(t).__str__() for t in transforms_d]
        return min(hex_d)

def create_manifest():
    random.seed(42)
    np.random.seed(42)

    files = sorted(glob.glob("data/raw/casting/casting_512x512/casting_512x512/*/*.jpeg"))
    print(f"Total files in primary dataset casting_512x512: {len(files)}")

    # Group by canonical rotation/flip hash to prevent leakage across splits
    cluster_map = defaultdict(list)
    image_metadata = {}

    for path in files:
        rel_path = path.replace("\\", "/")
        fn = os.path.basename(path)
        label = "DEFECTIVE" if "def_front" in path else "GOOD"
        
        with open(path, "rb") as f:
            raw_sha256 = hashlib.sha256(f.read()).hexdigest()
            
        canon_hash = get_canonical_dhash(path)
        
        meta = {
            "filename": fn,
            "path": rel_path,
            "label": label,
            "label_idx": 1 if label == "DEFECTIVE" else 0,
            "sha256": raw_sha256,
            "cluster_id": canon_hash,
        }
        image_metadata[fn] = meta
        cluster_map[canon_hash].append(meta)

    print(f"Total unique rotation/flip clusters: {len(cluster_map)}")

    # Split clusters stratified by label
    # Each cluster has a consistent label (verified 0 cross-label collisions in audit)
    def_clusters = []
    good_clusters = []

    for cluster_id, items in cluster_map.items():
        label = items[0]["label"]
        cluster_info = {
            "cluster_id": cluster_id,
            "label": label,
            "count": len(items),
            "items": items,
        }
        if label == "DEFECTIVE":
            def_clusters.append(cluster_info)
        else:
            good_clusters.append(cluster_info)

    print(f"Defective clusters: {len(def_clusters)}, Good clusters: {len(good_clusters)}")

    # Shuffle clusters deterministically
    random.shuffle(def_clusters)
    random.shuffle(good_clusters)

    def split_cluster_list(clusters, train_ratio=0.70, val_ratio=0.15):
        train, val, test = [], [], []
        total_items = sum(c["count"] for c in clusters)
        train_target = int(total_items * train_ratio)
        val_target = int(total_items * val_ratio)
        
        curr_train, curr_val, curr_test = 0, 0, 0
        for c in clusters:
            if curr_train + c["count"] <= train_target or (curr_val >= val_target and curr_test >= (total_items - train_target - val_target)):
                train.append(c)
                curr_train += c["count"]
            elif curr_val + c["count"] <= val_target or (curr_test >= (total_items - train_target - val_target)):
                val.append(c)
                curr_val += c["count"]
            else:
                test.append(c)
                curr_test += c["count"]
        return train, val, test

    train_def_c, val_def_c, test_def_c = split_cluster_list(def_clusters, 0.70, 0.15)
    train_good_c, val_good_c, test_good_c = split_cluster_list(good_clusters, 0.70, 0.15)

    def extract_items(cluster_list):
        items = []
        for c in cluster_list:
            items.extend(c["items"])
        return items

    train_items = extract_items(train_def_c) + extract_items(train_good_c)
    val_items = extract_items(val_def_c) + extract_items(val_good_c)
    test_items = extract_items(test_def_c) + extract_items(test_good_c)

    print(f"\nFinal Split Item Counts:")
    print(f"  Train: {len(train_items)} (Defective: {sum(1 for x in train_items if x['label'] == 'DEFECTIVE')}, Good: {sum(1 for x in train_items if x['label'] == 'GOOD')})")
    print(f"  Val:   {len(val_items)} (Defective: {sum(1 for x in val_items if x['label'] == 'DEFECTIVE')}, Good: {sum(1 for x in val_items if x['label'] == 'GOOD')})")
    print(f"  Test:  {len(test_items)} (Defective: {sum(1 for x in test_items if x['label'] == 'DEFECTIVE')}, Good: {sum(1 for x in test_items if x['label'] == 'GOOD')})")
    print(f"  Total: {len(train_items) + len(val_items) + len(test_items)}")

    manifest = {
        "dataset_name": "casting_512x512",
        "description": "Group-aware stratified train/val/test split of unaugmented casting_512x512 dataset",
        "random_seed": 42,
        "split_ratios": {"train": 0.70, "val": 0.15, "test": 0.15},
        "counts": {
            "total": len(files),
            "train": len(train_items),
            "val": len(val_items),
            "test": len(test_items),
            "train_defective": sum(1 for x in train_items if x['label'] == 'DEFECTIVE'),
            "train_good": sum(1 for x in train_items if x['label'] == 'GOOD'),
            "val_defective": sum(1 for x in val_items if x['label'] == 'DEFECTIVE'),
            "val_good": sum(1 for x in val_items if x['label'] == 'GOOD'),
            "test_defective": sum(1 for x in test_items if x['label'] == 'DEFECTIVE'),
            "test_good": sum(1 for x in test_items if x['label'] == 'GOOD'),
        },
        "train": sorted(train_items, key=lambda x: x["filename"]),
        "val": sorted(val_items, key=lambda x: x["filename"]),
        "test": sorted(test_items, key=lambda x: x["filename"]),
    }

    manifest_json = json.dumps(manifest, indent=2)
    manifest_hash = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
    manifest["split_manifest_sha256"] = manifest_hash

    os.makedirs("data/processed", exist_ok=True)
    manifest_path = "data/processed/split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSaved split manifest to {manifest_path}")
    print(f"Split Manifest SHA-256: {manifest_hash}")

if __name__ == "__main__":
    create_manifest()
