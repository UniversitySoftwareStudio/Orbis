# Categorization Visualization Pack

## Pipeline Snapshot
- umbrella clusters: `250`
- total URL groups: `250`
- `needs_algorithm` groups: `42`
- taxonomy mapped: `208` / `208`
- taxonomy unresolved: `0`
- top-level categories in directional tree: `13`

## Figure Index
1. Step 1 - Chosen URL Depth Distribution: `01_depth_distribution_20260402_201024.png`
2. Step 1 - Largest Parent Clusters: `02_top_parent_clusters_20260402_201024.png`
3. Step 2 - Decision Distribution: `03_decision_distribution_20260402_201024.png`
4. Step 2 - Tail Signal Scatter: `04_tail_signal_scatter_20260402_201024.png`
5. Step 2 - Entropy vs Dominance: `05_entropy_dominance_scatter_20260402_201024.png`
6. Step 2 - Needs-Algorithm Top Groups: `06_needs_algorithm_top_groups_20260402_201024.png`
7. Step 3 - Shortlist Priority Load: `07_shortlist_priority_docs_20260402_201024.png`
8. Step 4 - Mapping Source Contribution: `08_mapping_source_docs_20260402_201024.png`
9. Step 4 - Top-Level Taxonomy Load: `09_top_level_docs_20260402_201024.png`
10. Step 4 - Decision to Top-Level Heatmap: `10_decision_top_level_heatmap_20260402_201024.png`
11. Step 5 - Directional Tree Coverage: `11_tree_top_level_category_counts_20260402_201024.png`

## Literature Mapping
- **Entropy diagnostics**: Shannon, C. E. (1948), *A Mathematical Theory of Communication*.
- **Hierarchical clustering**: Ward, J. H. (1963), minimum-variance agglomerative clustering.
- **Cluster quality**: Rousseeuw, P. J. (1987), silhouette width for cluster validation.
- **Scalable centroid clustering**: Sculley, D. (2010), Web-scale K-Means / MiniBatchKMeans.
- **Manifold learning stage**: PaCMAP (Pairwise Controlled Manifold Approximation Projection) for structure-preserving projection.
- **URL-text similarity foundation**: character n-gram TF-IDF + cosine neighborhood graph + connected components.
- **Decision gate design**: rule-based interpretable thresholds for traceable taxonomy assignment.
