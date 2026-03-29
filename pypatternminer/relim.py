import time
import tracemalloc
from collections import defaultdict

def read_transactions(filename):
    """Read transactions from a file into a list of sets."""
    with open(filename, 'r') as file:
        transactions = [set(map(int, line.strip().split())) for line in file]
    return transactions

def get_support(transactions):
    """Calculate initial support for each item."""
    support = defaultdict(int)
    for transaction in transactions:
        for item in transaction:
            support[item] += 1
    return support

def relim(transactions, min_support_fraction):
    """Implements the RELIM algorithm to extract frequent itemsets."""
    total_transactions = len(transactions)
    min_support_count = min_support_fraction * total_transactions
    support = get_support(transactions)
    frequent_itemsets = {}

    def mine(transactions, prefix):
        local_support = defaultdict(int)
        for transaction in transactions:
            for item in transaction:
                local_support[item] += 1

        items = {item for item in local_support if local_support[item] >= min_support_count}

        for item in sorted(items, key=lambda x: local_support[x]):
            new_prefix = prefix + [item]
            itemset_support = local_support[item]
            frequent_itemsets[frozenset(new_prefix)] = itemset_support

            projected_transactions = [t - {item} for t in transactions if item in t]
            mine(projected_transactions, new_prefix)

    mine(transactions, [])
    return frequent_itemsets

def main():
    filename = 'contextPasquier99.txt'  # Adjust this to your file path
    transactions = read_transactions(filename)
    min_support_fraction = 0.40  # Minimum support as a fraction of total transactions

    tracemalloc.start()
    start_time = time.time()
    frequent_itemsets = relim(transactions, min_support_fraction)
    elapsed_time = time.time() - start_time
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print("========== RELIM - STATS ============")
    print(f" Number of frequent itemsets: {len(frequent_itemsets)}")
    print(f" Total time ~: {elapsed_time * 1000:.2f} ms")
    print(f" Max memory: {peak / 1024**2:.3f} MB")
    print("======================================")

    # Optionally print the itemsets and their supports
    for itemset, support in sorted(frequent_itemsets.items(), key=lambda x: (-len(x), x)):
        print(f"{' '.join(map(str, itemset))} #SUP: {support}")

if __name__ == "__main__":
    main()
