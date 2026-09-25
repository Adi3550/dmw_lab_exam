import os
import sys
import hashlib
import numpy as np
import pandas as pd

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
print("Q2(b) - FAST MINHASH EXPERIMENT")
print("=" * 60)

# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------

print("\nLoading labelled pairs...")
pairs = pd.read_csv(LABEL_FILE)
print(f"Labelled pairs loaded: {len(pairs)}")

print("\nLoading notices...")

files = [
    os.path.join(NOTICE_DIR, f)
    for f in os.listdir(NOTICE_DIR)
    if f.endswith(".csv")
]

notice_frames = []

for file in files:
    print(f"  Reading {os.path.basename(file)}")
    notice_frames.append(pd.read_csv(file))

notices = pd.concat(notice_frames, ignore_index=True)

notices["notice_id"] = notices["notice_id"].astype(str)

print(f"\nTotal notices: {len(notices)}")

notice_lookup = notices.set_index("notice_id").to_dict("index")


# ------------------------------------------------------------
# FAST HASH FUNCTION
# ------------------------------------------------------------

def hash_shingle(shingle):
    text = " ".join(shingle).encode("utf-8")

    digest = hashlib.blake2b(
        text,
        digest_size=8
    ).digest()

    return int.from_bytes(digest, "big")


# ------------------------------------------------------------
# CREATE BASE HASH VALUES
# ------------------------------------------------------------

print("\nCreating shingle hashes...")

hash_cache = {}

for i, (notice_id, notice) in enumerate(notice_lookup.items(), start=1):

    text = normalize_text(
        notice["title"],
        notice["body"]
    )

    shingles = word_shingles(
        text,
        SHINGLE_SIZE
    )

    # Hash every shingle only ONCE
    hashes = np.array(
        [hash_shingle(s) for s in shingles],
        dtype=np.uint64
    )

    hash_cache[notice_id] = {
        "shingles": shingles,
        "hashes": hashes
    }

    if i % 1000 == 0:
        print(f"  Processed {i}/{len(notice_lookup)}")


# ------------------------------------------------------------
# MINHASH SIGNATURE
# ------------------------------------------------------------

print("\nGenerating MinHash signatures...")

# Generate deterministic random coefficients
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


def create_signature(hash_values):

    if len(hash_values) == 0:
        return np.full(
            NUM_HASHES,
            np.uint64(2**64 - 1)
        )

    # Process hashes in vectorized blocks
    h = hash_values.astype(np.uint64)

    signature = np.full(
        NUM_HASHES,
        np.uint64(2**64 - 1)
    )

    for i in range(NUM_HASHES):

        values = (
            (A[i] * h + B[i])
            % PRIME
        )

        signature[i] = values.min()

    return signature


signature_cache = {}

for i, notice_id in enumerate(hash_cache, start=1):

    signature_cache[notice_id] = create_signature(
        hash_cache[notice_id]["hashes"]
    )

    if i % 1000 == 0:
        print(f"  Signatures: {i}/{len(hash_cache)}")


# ------------------------------------------------------------
# EVALUATE 900 LABELLED PAIRS
# ------------------------------------------------------------

print("\nCalculating exact vs MinHash similarity...")

results = []

for i, row in pairs.iterrows():

    id_a = str(row["notice_id_a"])
    id_b = str(row["notice_id_b"])

    label = str(row["label"]).lower()

    exact = jaccard_similarity(
        hash_cache[id_a]["shingles"],
        hash_cache[id_b]["shingles"]
    )

    estimated = np.mean(
        signature_cache[id_a] ==
        signature_cache[id_b]
    )

    error = abs(
        estimated - exact
    )

    results.append({
        "notice_id_a": id_a,
        "notice_id_b": id_b,
        "label": label,
        "exact_jaccard": exact,
        "minhash_jaccard": estimated,
        "absolute_error": error
    })

    if (i + 1) % 100 == 0:
        print(f"  Pairs: {i + 1}/900")


results_df = pd.DataFrame(results)


# ------------------------------------------------------------
# RESULTS
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("MINHASH ERROR RESULTS")
print("=" * 60)

errors = results_df["absolute_error"]

print(f"\nPairs tested             : {len(results_df)}")
print(f"Hash values per signature: {NUM_HASHES}")

print(f"\nMean absolute error      : {errors.mean():.6f}")
print(f"Median absolute error    : {errors.median():.6f}")
print(f"95th percentile error    : {errors.quantile(0.95):.6f}")
print(f"Maximum absolute error   : {errors.max():.6f}")


# ------------------------------------------------------------
# ERROR TOLERANCE
# ------------------------------------------------------------

print("\nError tolerance failures:")

for tolerance in [0.02, 0.05, 0.10]:

    failures = (
        results_df["absolute_error"] > tolerance
    ).sum()

    percentage = failures / len(results_df) * 100

    print(
        f"  > ±{tolerance:.2f}: "
        f"{failures} pairs "
        f"({percentage:.2f}%)"
    )


# ------------------------------------------------------------
# LABEL-WISE RESULTS
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("ERROR BY LABEL")
print("=" * 60)

for label in ["same", "different"]:

    subset = results_df[
        results_df["label"] == label
    ]

    print(f"\n{label.upper()}")

    print(
        f"Mean error   : "
        f"{subset['absolute_error'].mean():.6f}"
    )

    print(
        f"Median error : "
        f"{subset['absolute_error'].median():.6f}"
    )

    print(
        f"Max error    : "
        f"{subset['absolute_error'].max():.6f}"
    )


# ------------------------------------------------------------
# WORST FAILURES
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("TOP 10 WORST ESTIMATION FAILURES")
print("=" * 60)

worst = results_df.sort_values(
    "absolute_error",
    ascending=False
).head(10)

for _, row in worst.iterrows():

    print(
        f"\n{row['notice_id_a']} <-> "
        f"{row['notice_id_b']}"
    )

    print(f"Label          : {row['label']}")
    print(f"Exact Jaccard  : {row['exact_jaccard']:.6f}")
    print(f"MinHash        : {row['minhash_jaccard']:.6f}")
    print(f"Absolute error : {row['absolute_error']:.6f}")


# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

output_file = os.path.join(
    RESULTS_DIR,
    "q2b_minhash_results.csv"
)

results_df.to_csv(
    output_file,
    index=False
)

print("\n" + "=" * 60)
print("Q2(b) COMPLETED")
print("=" * 60)

print("\nResults saved to:")
print(output_file)