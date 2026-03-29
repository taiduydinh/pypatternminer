# ============================================================
# FHIM – Faster High-Utility Itemset Mining
# ============================================================

import os 
import time
from itertools import combinations

# ====================== CONFIG ======================
MIN_UTILITY = 30          # CHANGE THRESHOLD HERE
DB_FILENAME = "DB_Utility.txt"
OUTPUT_PREFIX = "#56_10_output.txt" # output_30.txt, output_40.txt ...
# ====================================================


# ------------------ FIND DB FILE ------------------
def find_db():
    base = os.path.dirname(os.path.abspath(__file__))
    for root, _, files in os.walk(base):
        if DB_FILENAME in files:
            return os.path.join(root, DB_FILENAME)
    raise FileNotFoundError("DB_Utility.txt not found")


# ------------------ LOAD DATABASE ------------------
def load_db():
    db = []
    path = find_db()
    print("✅ DB file found at:", path)

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in "#%@":
                continue
            left, tu, utils = line.split(":")
            items = list(map(int, left.split()))
            utils = list(map(int, utils.split()))
            db.append((items, utils))
    return db


# ------------------ FHIM (EXACT) ------------------
def run():
    start = time.time()
    db = load_db()

    all_items = sorted(set(i for t, _ in db for i in t))
    results = []

    # Generate all itemsets
    for r in range(1, len(all_items) + 1):
        for itemset in combinations(all_items, r):
            total_util = 0
            support = 0

            for items, utils in db:
                if all(i in items for i in itemset):
                    support += 1
                    for i in itemset:
                        total_util += utils[items.index(i)]

            if total_util >= MIN_UTILITY:
                results.append((itemset, total_util, support))

    # Java-style sorting
    results.sort(key=lambda x: (len(x[0]), x[0]))

    # Output file
    out_file = f"{OUTPUT_PREFIX}{MIN_UTILITY}.txt"

    with open(out_file, "w") as f:
        for items, util, sup in results:
            f.write(
                f"{' '.join(map(str, items))}  #UTIL: {util} #SUP: {sup}\n"
            )

    # Console output
    print("\n===== HIGH UTILITY ITEMSETS =====")
    for items, util, sup in results:
        print(" ".join(map(str, items)), f"#UTIL: {util} #SUP: {sup}")

    print("\n============= FHIM STATS =============")
    print(f"Total time ~ {round((time.time()-start)*1000,2)} ms")
    print("HUI count :", len(results))
    print("Output file:", out_file)
    print("=====================================")


# ====================== MAIN ======================
if __name__ == "__main__":
    run()
