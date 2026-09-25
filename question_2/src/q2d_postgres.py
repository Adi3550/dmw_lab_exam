import psycopg2

print("=" * 60)
print("Q2(d) - INDEXED VS SEQUENTIAL SCAN")
print("=" * 60)

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="annapurna",
    user="annapurna",
    password="annapurna"
)

cur = conn.cursor()

# Make sure there is a known bucket with multiple rows.
cur.execute("""
SELECT band, bucket_key, COUNT(*) AS n
FROM tender_retrieval.lsh_bucket
GROUP BY band, bucket_key
ORDER BY n DESC
LIMIT 1;
""")

band, bucket_key, bucket_size = cur.fetchone()

print(f"\nTest bucket:")
print(f"Band       : {band}")
print(f"Bucket key : {bucket_key}")
print(f"Rows       : {bucket_size}")


# ------------------------------------------------------------
# INDEXED PLAN
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("INDEXED LOOKUP")
print("=" * 60)

cur.execute("""
EXPLAIN (ANALYZE, BUFFERS)
SELECT notice_id
FROM tender_retrieval.lsh_bucket
WHERE band = %s
  AND bucket_key = %s;
""", (band, bucket_key))

indexed_plan = cur.fetchall()

for row in indexed_plan:
    print(row[0])


# ------------------------------------------------------------
# FORCE SEQUENTIAL SCAN
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("FORCED SEQUENTIAL SCAN")
print("=" * 60)

cur.execute("SET enable_indexscan = off;")
cur.execute("SET enable_bitmapscan = off;")

cur.execute("""
EXPLAIN (ANALYZE, BUFFERS)
SELECT notice_id
FROM tender_retrieval.lsh_bucket
WHERE band = %s
  AND bucket_key = %s;
""", (band, bucket_key))

seq_plan = cur.fetchall()

for row in seq_plan:
    print(row[0])


# ------------------------------------------------------------
# ROW COUNT
# ------------------------------------------------------------

cur.execute("""
SELECT COUNT(*)
FROM tender_retrieval.lsh_bucket;
""")

total_rows = cur.fetchone()[0]

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

print(f"\nTotal LSH rows in PostgreSQL : {total_rows:,}")
print(f"Rows in selected bucket     : {bucket_size}")

print("""
The indexed plan uses the (band, bucket_key) index,
while the forced alternative examines the table without
using the index.
""")

cur.close()
conn.close()

print("\nQ2(d) comparison completed.")