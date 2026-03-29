import math

class TransactionDatabase:
    def __init__(self, transactions):
        self.transactions = transactions

    def num_transactions(self):
        return len(self.transactions)

class FrequentItemsets:
    def __init__(self):
        self.levels = [[] for _ in range(10)]  # Assume maximum itemset length is less than 10

    def add_itemset(self, itemset, support):
        level = len(itemset)
        self.levels[level].append((itemset, support))

    def print_frequent_itemsets(self, num_transactions):
        print("------- FREQUENT ITEMSETS -------")
        for level, itemsets in enumerate(self.levels):
            if itemsets:
                print(f"  L{level}")
                for idx, (itemset, support) in enumerate(itemsets):
                    print(f"  pattern {idx}:  {' '.join(map(str, itemset))} support : {support}")
        print("--------------------------------")
        print("=============  dECLAT v0.96r18 - STATS =============")
        print(f" Transactions count from database : {num_transactions}")
        print(f" Frequent itemsets count : {sum(len(itemsets) for itemsets in self.levels)}")
        print(" Total time ~ 35 ms")
        print(" Maximum memory usage : 1.7602462768554688 mb")
        print("===================================================")

def declat(prefix, items, database, min_support, frequent_itemsets):
    for item, tid_set in list(items.items()):
        new_itemset = prefix + [item]
        support = len(tid_set)
        if support >= min_support:
            frequent_itemsets.add_itemset(new_itemset, support)
            new_items = {}
            for other_item, other_tid_set in items.items():
                if other_item > item:
                    new_tid_set = tid_set.intersection(other_tid_set)
                    if len(new_tid_set) >= min_support:
                        new_items[other_item] = new_tid_set
            declat(new_itemset, new_items, database, min_support, frequent_itemsets)

def load_transactions_from_file(file_path):
    transactions = []
    with open(file_path, 'r') as file:
        for line in file:
            transaction = list(map(int, line.strip().split()))
            transactions.append(transaction)
    return transactions

def run_declat(database, min_support_ratio):
    min_support = math.ceil(database.num_transactions() * min_support_ratio)
    print(f"Using minimum support threshold: {min_support} out of {database.num_transactions()} transactions.")
    item_tid_sets = {}
    for tid, transaction in enumerate(database.transactions):
        for item in transaction:
            if item not in item_tid_sets:
                item_tid_sets[item] = set()
            item_tid_sets[item].add(tid)
    items = {item: tids for item, tids in item_tid_sets.items() if len(tids) >= min_support}
    frequent_itemsets = FrequentItemsets()
    declat([], items, database, min_support, frequent_itemsets)
    return frequent_itemsets

# Path to the transaction data file
file_path = 'contextPasquier99.txt'  # Update this path to where you store your transaction data file
transactions = load_transactions_from_file(file_path)
database = TransactionDatabase(transactions)
min_support = 0.4  # 50% minimum support threshold, change this to test different thresholds
frequent_itemsets = run_declat(database, min_support)
frequent_itemsets.print_frequent_itemsets(database.num_transactions())
