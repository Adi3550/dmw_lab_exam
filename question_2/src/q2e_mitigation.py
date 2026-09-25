import os
import pandas as pd
import psycopg2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

LABEL_FILE = os.path.join(DATA_DIR, "labelled_pairs.csv")

print("=" * 60)
print("Q2(e) - HOT BUCKET MITIGATION EXPERIMENT")
print("=" * 60)


# ============================================================
# LOAD LABELLED PAIRS
# ============================================================

pairs = pd.read_csv(LABEL_FILE)

pairs["notice_id_a"] = pairs["notice_id_a"].astype(str)
pairs["notice_id_b"] = pairs["notice_id_b"].astype(str)

print(f"\nLabelled pairs: {len(pairs)}")


# ============================================================
# LOAD LSH BUCKETS FROM POSTGRESQL
# ============================================================

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="annapurna",
    user="annapurna",
    password="annapurna"
)

cur = conn.cursor()

print("\nLoading LSH buckets from PostgreSQL...")

cur.execute("""
SELECT band, bucket_key, notice_id
FROM tender_retrieval.lsh_bucket;
""")

rows = cur.fetchall()

print(f"Bucket memberships loaded: {len(rows):,}")


# ============================================================
# BUILD IN-MEMORY BUCKET INDEX
# ============================================================

buckets = {}

for band, bucket_key, notice_id in rows:

    key = (band, bucket_key)

    if key not in buckets:
        buckets[key] = []

    buckets[key].append(str(notice_id))


# Notice -> buckets
notice_buckets = {}

for key, members in buckets.items():

    for notice_id in members:

        if notice_id not in notice_buckets:
            notice_buckets[notice_id] = []

        notice_buckets[notice_id].append(key)


print(f"Unique buckets: {len(buckets):,}")
print(f"Notices indexed: {len(notice_buckets):,}")


# ============================================================
# BUCKET SIZES
# ============================================================

bucket_sizes = {
    key: len(members)
    for key, members in buckets.items()
}


# ============================================================
# RETRIEVAL FUNCTION
# ============================================================

def retrieve_candidates(notice_id, max_bucket_size=None):

    candidates = set()

    for key in notice_buckets.get(notice_id, []):

        size = bucket_sizes[key]

        # Mitigation:
        # Ignore buckets larger than the selected cap.
        if (
            max_bucket_size is not None
            and size > max_bucket_size
        ):
            continue

        candidates.update(buckets[key])

    candidates.discard(notice_id)

    return candidates


# ============================================================
# EXPERIMENT
# ============================================================

caps = [
    None,
    25,
    50,
    100
]

results = []

for cap in caps:

    print("\n" + "-" * 60)

    if cap is None:
        print("BASELINE - NO BUCKET CAP")
    else:
        print(f"MITIGATION - MAX BUCKET SIZE = {cap}")

    total_candidate_work = 0
    same_retrieved = 0
    same_total = 0

    candidate_counts = []

    for _, row in pairs.iterrows():

        id_a = row["notice_id_a"]
        id_b = row["notice_id_b"]

        candidates = retrieve_candidates(
            id_a,
            cap
        )

        candidate_count = len(candidates)

        candidate_counts.append(candidate_count)

        total_candidate_work += candidate_count

        if row["label"].lower() == "same":

            same_total += 1

            if id_b in candidates:
                same_retrieved += 1

    recall = (
        same_retrieved / same_total
        if same_total > 0
        else 0
    )

    mean_candidates = (
        sum(candidate_counts)
        / len(candidate_counts)
    )

    median_candidates = sorted(
        candidate_counts
    )[len(candidate_counts) // 2]

    print(
        f"Candidate work : "
        f"{total_candidate_work:,}"
    )

    print(
        f"Same recall    : "
        f"{recall:.4f}"
    )

    print(
        f"Mean candidates: "
        f"{mean_candidates:.2f}"
    )

    print(
        f"Median candidates: "
        f"{median_candidates:.2f}"
    )

    results.append({
        "bucket_cap": (
            "none"
            if cap is None
            else cap
        ),
        "candidate_work": total_candidate_work,
        "same_pairs_retrieved": same_retrieved,
        "same_pairs_total": same_total,
        "recall": recall,
        "mean_candidates": mean_candidates,
        "median_candidates": median_candidates
    })


# ============================================================
# SAVE
# ============================================================

results_df = pd.DataFrame(results)

output_file = os.path.join(
    RESULTS_DIR,
    "q2e_mitigation_results.csv"
)

results_df.to_csv(
    output_file,
    index=False
)

print("\n" + "=" * 60)
print("MITIGATION COMPARISON")
print("=" * 60)

print(
    results_df.to_string(index=False)
)

print("\nSaved:")
print(output_file)


cur.close()
conn.close()

print("\n" + "=" * 60)
print("Q2(e) MITIGATION EXPERIMENT COMPLETED")
print("=" * 60)