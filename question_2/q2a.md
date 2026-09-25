============================================================
Q2(a) - SIMILARITY EXPERIMENT
============================================================

Loading labelled pairs...
Labelled pairs loaded: 900

Columns:
['notice_id_a', 'notice_id_b', 'label', 'adjudicated_by', 'adjudicated_on']

Label distribution:
label
different    621
same         279
Name: count, dtype: int64

Searching for notice files...
Notice files found: 8

Loading notices...
  Reading part-000.csv
  Reading part-001.csv
  Reading part-002.csv
  Reading part-003.csv
  Reading part-004.csv
  Reading part-005.csv
  Reading part-006.csv
  Reading part-007.csv

Total notices loaded: 12000

Notice columns:
['notice_id', 'portal_id', 'published_at', 'title', 'body', 'estimated_value', 'closing_date']

Calculating Jaccard similarities...
  Processed 100/900 pairs
  Processed 200/900 pairs
  Processed 300/900 pairs
  Processed 400/900 pairs
  Processed 500/900 pairs
  Processed 600/900 pairs
  Processed 700/900 pairs
  Processed 800/900 pairs
  Processed 900/900 pairs

============================================================
RESULTS
============================================================

SAME PAIRS: 279
3-word median Jaccard : 0.6522
5-word median Jaccard : 0.6434

DIFFERENT PAIRS: 621
3-word median Jaccard : 0.2848
5-word median Jaccard : 0.1974

============================================================
THRESHOLD EXPERIMENT: 0.5
============================================================

jaccard_3
False positives : 24
False negatives : 80

jaccard_5
False positives : 1
False negatives : 83

Results saved to:
C:\Users\ub02-glab-002\Desktop\question_2\results\q2a_similarity_results.csv

============================================================
EXAMPLE PAIRS
============================================================

--- SAME PAIR ---
Notice A ID: N010018
Notice A Title: Supply and installation of the check dam on the Sone near Banaskantha

Notice B ID: N010020
Notice B Title: Tender Notice: Corrigendum - Supply and installation of the check dam on the Sone near Banaskantha

3-word Jaccard: 0.2503
5-word Jaccard: 0.2233

--- DIFFERENT PAIR ---
Notice A ID: N007876
Notice A Title: NIT for Annual maintenance contract for CCTV surveillance infrastructure for Shivamogga city

Notice B ID: N008565
Notice B Title: e-Tender - Upgradation of solar street lighting in Karur municipal area - Karur

3-word Jaccard: 0.2201
5-word Jaccard: 0.1423

Q2(a) experiment completed successfully.