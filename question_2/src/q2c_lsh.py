import os
import sys
import hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from normalize import normalize_text, word_shingles, jaccard_similarity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

LABEL_FILE = os.path.join(DATA_DIR, "labelled_pairs.csv")
NOTICE_DIR = os.path.join(DATA_DIR, "notices")

os.makedirs(RESULTS_DIR, exist_ok=True)

NUM_HASHES = 384
SHINGLE_SIZE = 5

print("=" * 60)
print("Q2(c) - LSH RETRIEVAL EXPERIMENT")
print("=" * 60)

# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------

print("\nLoading labelled pairs...")
pairs = pd.read_csv(LABEL_FILE)

print("Loading notices...")

files = [
    os.path.join(NOTICE_DIR, f)
    for f in os.listdir(NOTICE_DIR)
    if f.endswith(".csv")
]

notices = pd.concat(
    [pd.read_csv(f) for f in files],
    ignore_index=True
)

notices["notice_id"] = notices["notice_id"].astype(str)

notice_lookup = notices.set_index("notice_id").to_dict("index")

print(f"Notices loaded: {len(notices)}")
print(f"Labelled pairs: {len(pairs)}")


# ------------------------------------------------------------
# CREATE 384-D MINHASH SIGNATURES
# ------------------------------------------------------------

print("\nCreating MinHash signatures...")

rng = np.random.default_rng(42)

A = rng.integers(
    1,
    2**63 - 1,
    size=NUM_HASHES,
    dtype=np.uint64
)

B = rng.integers(
    0,
    2**63 - 1,
    size=NUM_HASHES,
    dtype=np.uint64
)

PRIME = np.uint64(18446744073709551557)


def hash_shingle(shingle):
    value = " ".join(shingle).encode("utf-8")

    digest = hashlib.blake2b(
        value,
        digest_size=8
    ).digest()

    return int.from_bytes(digest, "big")


def create_signature(shingles):

    if not shingles:
        return np.full(
            NUM_HASHES,
            np.uint64(2**64 - 1)
        )

    h = np.array(
        [hash_shingle(s) for s in shingles],
        dtype=np.uint64
    )

    signature = np.full(
        NUM_HASHES,
        np.uint64(2**64 - 1)
    )

    for i in range(NUM_HASHES):

        values = (
            A[i] * h + B[i]
        ) % PRIME

        signature[i] = values.min()

    return signature


signatures = {}
shingle_cache = {}

for i, (notice_id, notice) in enumerate(
    notice_lookup.items(),
    start=1
):

    text = normalize_text(
        notice["title"],
        notice["body"]
    )

    shingles = word_shingles(
        text,
        SHINGLE_SIZE
    )

    shingle_cache[notice_id] = shingles

    signatures[notice_id] = create_signature(shingles)

    if i % 2000 == 0:
        print(f"  {i}/{len(notice_lookup)}")


# ------------------------------------------------------------
# LSH
# ------------------------------------------------------------

# 384 hashes = 48 bands × 8 rows.
BANDS = 48
ROWS = 8

print("\nBuilding LSH index...")
print(f"Bands: {BANDS}")
print(f"Rows per band: {ROWS}")

lsh_buckets = {}

for notice_id, signature in signatures.items():

    for band in range(BANDS):

        start = band * ROWS
        end = start + ROWS

        band_values = signature[start:end]

        key = (
            band,
            hashlib.blake2b(
                band_values.tobytes(),
                digest_size=8
            ).digest()
        )

        if key not in lsh_buckets:
            lsh_buckets[key] = []

        lsh_buckets[key].append(notice_id)

print(f"LSH buckets created: {len(lsh_buckets):,}")


# ------------------------------------------------------------
# RETRIEVAL
# ------------------------------------------------------------

def retrieve_candidates(notice_id):

    signature = signatures[notice_id]

    candidates = set()

    for band in range(BANDS):

        start = band * ROWS
        end = start + ROWS

        band_values = signature[start:end]

        key = (
            band,
            hashlib.blake2b(
                band_values.tobytes(),
                digest_size=8
            ).digest()
        )

        candidates.update(
            lsh_buckets.get(key, [])
        )

    candidates.discard(notice_id)

    return candidates


# ------------------------------------------------------------
# EVALUATE LABELLED PAIRS
# ------------------------------------------------------------

print("\nEvaluating labelled pairs...")

pair_results = []

for i, row in pairs.iterrows():

    id_a = str(row["notice_id_a"])
    id_b = str(row["notice_id_b"])

    label = str(row["label"]).lower()

    candidates = retrieve_candidates(id_a)

    retrieved = id_b in candidates

    exact = jaccard_similarity(
        shingle_cache[id_a],
        shingle_cache[id_b]
    )

    pair_results.append({
        "notice_id_a": id_a,
        "notice_id_b": id_b,
        "label": label,
        "true_similarity": exact,
        "retrieved": retrieved,
        "candidate_count": len(candidates)
    })

    if (i + 1) % 100 == 0:
        print(f"  {i + 1}/900")


pair_df = pd.DataFrame(pair_results)


# ------------------------------------------------------------
# OVERALL RETRIEVAL RECALL
# ------------------------------------------------------------

same_pairs = pair_df[
    pair_df["label"] == "same"
]

recall = same_pairs["retrieved"].mean()

print("\n" + "=" * 60)
print("RETRIEVAL RESULTS")
print("=" * 60)

print(f"\nSame pairs: {len(same_pairs)}")
print(f"Retrieved same pairs: {same_pairs['retrieved'].sum()}")
print(f"Recall: {recall:.4f}")

print(
    f"\nMean candidate count: "
    f"{pair_df['candidate_count'].mean():.2f}"
)

print(
    f"Median candidate count: "
    f"{pair_df['candidate_count'].median():.2f}"
)

print(
    f"Maximum candidate count: "
    f"{pair_df['candidate_count'].max()}"
)


# ------------------------------------------------------------
# SURVIVAL BY SIMILARITY
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("SURVIVAL PROBABILITY BY TRUE SIMILARITY")
print("=" * 60)

bins = [
    0.0,
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.01
]

pair_df["similarity_bin"] = pd.cut(
    pair_df["true_similarity"],
    bins=bins,
    right=False
)

survival = (
    pair_df
    .groupby("similarity_bin", observed=False)
    .agg(
        pairs=("retrieved", "count"),
        survived=("retrieved", "sum"),
        survival_probability=("retrieved", "mean"),
        mean_candidates=("candidate_count", "mean")
    )
    .reset_index()
)

print(survival.to_string(index=False))


# ------------------------------------------------------------
# PLOT
# ------------------------------------------------------------

plot_df = survival[
    survival["pairs"] > 0
].copy()

x = [
    interval.left
    for interval in plot_df["similarity_bin"]
]

y = plot_df["survival_probability"]

plt.figure(figsize=(8, 5))

plt.plot(
    x,
    y,
    marker="o"
)

plt.xlabel("True Jaccard Similarity")
plt.ylabel("Retrieval Survival Probability")
plt.title("LSH Retrieval Survival vs True Similarity")
plt.ylim(0, 1.05)
plt.grid(True)

plot_file = os.path.join(
    RESULTS_DIR,
    "q2c_survival_probability.png"
)

plt.savefig(
    plot_file,
    dpi=150,
    bbox_inches="tight"
)

plt.close()

print("\nPlot saved to:")
print(plot_file)


# ------------------------------------------------------------
# SAVE TABLE
# ------------------------------------------------------------

survival_file = os.path.join(
    RESULTS_DIR,
    "q2c_survival_results.csv"
)

survival.to_csv(
    survival_file,
    index=False
)

pair_file = os.path.join(
    RESULTS_DIR,
    "q2c_pair_results.csv"
)

pair_df.to_csv(
    pair_file,
    index=False
)

print("\nResults saved:")
print(survival_file)
print(pair_file)

print("\n" + "=" * 60)
print("Q2(c) COMPLETED")
print("=" * 60)