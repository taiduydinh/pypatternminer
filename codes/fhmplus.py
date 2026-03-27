import os
import time
from itertools import combinations

# ============================================================
# Load DB_Utility.txt
# ============================================================

def load_database(path):
    transactions = []
    with open(path, "r") as f:
        for line in f:
            if ":" not in line:
                continue
            items, _, utils = line.strip().split(":")
            items = list(map(int, items.split()))
            utils = list(map(int, utils.split()))
            transactions.append(dict(zip(items, utils)))
    return transactions


# ============================================================
# Compute exact utility and support
# ============================================================

def compute_utility(itemset, transactions):
    util = 0
    supp = 0
    for t in transactions:
        if all(i in t for i in itemset):
            supp += 1
            util += sum(t[i] for i in itemset)
    return util, supp


# ============================================================
# Exact HUI mining (reference)
# ============================================================

def mine_huis(transactions, min_util):
    all_items = sorted({i for t in transactions for i in t})
    results = []

    for r in range(1, len(all_items) + 1):
        for comb in combinations(all_items, r):
            util, supp = compute_utility(comb, transactions)
            if util >= min_util and 2 <= len(comb) <= 3:
                results.append((list(comb), util, supp))

    return results


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INPUT = os.path.join(BASE_DIR, "DB_Utility.txt")
    OUTPUT = os.path.join(BASE_DIR, "output_fhmplus_python.txt")
    MIN_UTIL = 30

    print("INPUT FILE =", INPUT)

    start = time.time()

    transactions = load_database(INPUT)
    print("DEBUG: transaction count =", len(transactions))

    results = mine_huis(transactions, MIN_UTIL)

    # Sort to match Java FHM+ style (length desc, lexicographic desc)
    results.sort(key=lambda x: (-len(x[0]), x[0]), reverse=False)

    with open(OUTPUT, "w") as out:
        for items, util, _ in results:
            out.write(f"{' '.join(map(str, items))} #UTIL: {util}\n")

    end = time.time()

    print("============= FHM+ PYTHON (REFERENCE) STATS =============")
    print("Total time:", round((end - start) * 1000), "ms")
    print("High-utility itemsets count:", len(results))
    print("========================================================")
