import os
import sys
import pandas as pd

# Allow importing normalize.py from the same folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from normalize import normalize_text, word_shingles, jaccard_similarity


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

LABEL_FILE = os.path.join(DATA_DIR, "labelled_pairs.csv")

os.makedirs(RESULTS_DIR, exist_ok=True)


# ---------------------------------------------------------
# LOAD LABELLED PAIRS
# ---------------------------------------------------------

print("=" * 60)
print("Q2(a) - SIMILARITY EXPERIMENT")
print("=" * 60)

print("\nLoading labelled pairs...")

pairs = pd.read_csv(LABEL_FILE)

print(f"Labelled pairs loaded: {len(pairs)}")

print("\nColumns:")
print(list(pairs.columns))

print("\nLabel distribution:")
print(pairs["label"].value_counts())


# ---------------------------------------------------------
# FIND NOTICE FILES
# ---------------------------------------------------------

print("\nSearching for notice files...")

notice_dir = os.path.join(DATA_DIR, "notices")

files = [
    os.path.join(notice_dir, f)
    for f in os.listdir(notice_dir)
    if f.endswith(".csv")
]

print(f"Notice files found: {len(files)}")


# ---------------------------------------------------------
# LOAD NOTICES
# ---------------------------------------------------------

print("\nLoading notices...")

notice_frames = []

for file in files:
    print(f"  Reading {os.path.basename(file)}")

    df = pd.read_csv(file)

    notice_frames.append(df)


notices = pd.concat(notice_frames, ignore_index=True)

print(f"\nTotal notices loaded: {len(notices)}")

print("\nNotice columns:")
print(list(notices.columns))


# ---------------------------------------------------------
# CREATE NOTICE LOOKUP
# ---------------------------------------------------------

notices["notice_id"] = notices["notice_id"].astype(str)

notice_lookup = notices.set_index("notice_id").to_dict("index")

# ---------------------------------------------------------
# CALCULATE SIMILARITY
# ---------------------------------------------------------

print("\nCalculating Jaccard similarities...")

results = []

for i, row in pairs.iterrows():

    id_a = str(row["notice_id_a"])
    id_b = str(row["notice_id_b"])

    label = row["label"]

    notice_a = notice_lookup[id_a]
    notice_b = notice_lookup[id_b]

    text_a = normalize_text(
        notice_a["title"],
        notice_a["body"]
    )

    text_b = normalize_text(
        notice_b["title"],
        notice_b["body"]
    )

    shingles_3_a = word_shingles(text_a, 3)
    shingles_3_b = word_shingles(text_b, 3)

    shingles_5_a = word_shingles(text_a, 5)
    shingles_5_b = word_shingles(text_b, 5)

    similarity_3 = jaccard_similarity(
        shingles_3_a,
        shingles_3_b
    )

    similarity_5 = jaccard_similarity(
        shingles_5_a,
        shingles_5_b
    )

    results.append({
        "id_a": id_a,
        "id_b": id_b,
        "label": label,
        "jaccard_3": similarity_3,
        "jaccard_5": similarity_5
    })

    if (i + 1) % 100 == 0:
        print(f"  Processed {i + 1}/{len(pairs)} pairs")


results_df = pd.DataFrame(results)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

for label in ["same", "different"]:

    subset = results_df[
        results_df["label"].str.lower() == label
    ]

    print(f"\n{label.upper()} PAIRS: {len(subset)}")

    print(
        f"3-word median Jaccard : "
        f"{subset['jaccard_3'].median():.4f}"
    )

    print(
        f"5-word median Jaccard : "
        f"{subset['jaccard_5'].median():.4f}"
    )


# ---------------------------------------------------------
# THRESHOLD EXPERIMENT
# ---------------------------------------------------------

THRESHOLD = 0.50

print("\n" + "=" * 60)
print(f"THRESHOLD EXPERIMENT: {THRESHOLD}")
print("=" * 60)


for column in ["jaccard_3", "jaccard_5"]:

    predicted_same = results_df[column] >= THRESHOLD

    actual_same = (
        results_df["label"].str.lower() == "same"
    )

    false_positive = (
        predicted_same & ~actual_same
    ).sum()

    false_negative = (
        ~predicted_same & actual_same
    ).sum()

    print(f"\n{column}")

    print(f"False positives : {false_positive}")
    print(f"False negatives : {false_negative}")


# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------

output_file = os.path.join(
    RESULTS_DIR,
    "q2a_similarity_results.csv"
)

results_df.to_csv(
    output_file,
    index=False
)

print("\nResults saved to:")
print(output_file)

print("\n" + "=" * 60)
print("EXAMPLE PAIRS")
print("=" * 60)

# One SAME pair
same_example = results_df[results_df["label"].str.lower() == "same"].iloc[0]

# One DIFFERENT pair
different_example = results_df[
    results_df["label"].str.lower() == "different"
].iloc[0]


def show_example(row, label):
    id_a = row["id_a"]
    id_b = row["id_b"]

    notice_a = notice_lookup[id_a]
    notice_b = notice_lookup[id_b]

    print(f"\n--- {label} PAIR ---")
    print(f"Notice A ID: {id_a}")
    print(f"Notice A Title: {notice_a['title']}")

    print(f"\nNotice B ID: {id_b}")
    print(f"Notice B Title: {notice_b['title']}")

    print(f"\n3-word Jaccard: {row['jaccard_3']:.4f}")
    print(f"5-word Jaccard: {row['jaccard_5']:.4f}")


show_example(same_example, "SAME")
show_example(different_example, "DIFFERENT")

print("\nQ2(a) experiment completed successfully.")