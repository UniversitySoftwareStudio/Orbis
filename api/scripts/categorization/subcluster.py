"""
Sub-cluster URLs within each category using cosine similarity.
Uses agglomerative clustering — no k needed, groups by similarity threshold.

Outputs: subcluster_samples.json  {category: {cluster_id: [urls]}}
"""

import json
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from collections import defaultdict

DIR = __import__("os").path.dirname(__file__)

DISTANCE_THRESHOLD = 0.3   # lower = tighter groups (tune this)

print("Loading embeddings...")
with open(f"{DIR}/url_embeddings.json") as f:
    raw = json.load(f)

# Build lookup: url -> embedding
emb_map = {item["url"]: item["embedding"] for item in raw}

print("Loading cluster samples...")
with open(f"{DIR}/cluster_samples.json") as f:
    samples = json.load(f)

out = {}

for category, urls in samples.items():
    valid = [(u, emb_map[u]) for u in urls if u in emb_map]
    if len(valid) < 2:
        out[category] = {"0": [u for u, _ in valid]}
        continue

    url_list = [u for u, _ in valid]
    X = np.array([e for _, e in valid], dtype=np.float32)

    # Normalize for cosine similarity
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    X = X / np.clip(norms, 1e-10, None)

    model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=DISTANCE_THRESHOLD,
        metric="cosine",
        linkage="average",
    )
    labels = model.fit_predict(X)

    groups = defaultdict(list)
    for url, label in zip(url_list, labels):
        groups[int(label)].append(url)

    sorted_groups = dict(
        sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)
    )

    n_clusters = len(sorted_groups)
    print(f"{category}: {len(urls)} URLs → {n_clusters} sub-clusters")
    for cid, cluster_urls in sorted_groups.items():
        print(f"  [{cid}] {len(cluster_urls):4d}  {cluster_urls[0].split('/')[-1][:60]}")

    out[category] = sorted_groups

out_path = f"{DIR}/subcluster_samples.json"
with open(out_path, "w") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print(f"\nSaved to {out_path}")
