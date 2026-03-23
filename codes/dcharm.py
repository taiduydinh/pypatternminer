# ==============================================================
# dcharm.py
# Single-file Python implementation of DCharm (Closed Itemset Mining)
# Inspired by SPMF AlgoDCharm_Bitset
# ==============================================================

import time
from collections import defaultdict


# ==============================================================
# Itemset class
# ==============================================================

class Itemset:
    def __init__(self, items):
        self.items = list(items)
        self.support = 0

    def set_absolute_support(self, support):
        self.support = support

    def get_absolute_support(self):
        return self.support

    def contains_all(self, other):
        return set(self.items).issuperset(set(other.items))

    def __str__(self):
        return " ".join(map(str, self.items))


# ==============================================================
# HashTable for closure checking
# ==============================================================

class HashTable:
    def __init__(self, size):
        self.table = [None] * size

    def hash_code(self, tidset):
        h = sum(tidset)
        if h < 0:
            h = -h
        return h % len(self.table)

    def contains_superset_of(self, itemset, hashcode):
        bucket = self.table[hashcode]
        if bucket is None:
            return False

        for existing in bucket:
            if (existing.get_absolute_support() == itemset.get_absolute_support()
                    and existing.contains_all(itemset)):
                return True
        return False

    def put(self, itemset, hashcode):
        if self.table[hashcode] is None:
            self.table[hashcode] = []
        self.table[hashcode].append(itemset)


# ==============================================================
# BitSetSupport (Python set version)
# ==============================================================

class BitSetSupport:
    def __init__(self, tidset=None):
        self.tidset = set() if tidset is None else set(tidset)
        self.support = len(self.tidset)


# ==============================================================
# DCharm Algorithm (tidset-based closed mining)
# ==============================================================

class AlgoDCharm:

    def __init__(self):
        self.minsup_relative = 0
        self.database = None
        self.hash = None
        self.writer = None
        self.itemset_count = 0
        self.start_time = 0
        self.end_time = 0

    # ----------------------------------------------------------
    # Run algorithm
    # ----------------------------------------------------------

    def run_algorithm(self, input_file, output_file, minsup, hash_table_size=10000):

        self.start_time = time.time()

        print("Loading database...")
        self.database = self.load_spmf_file(input_file)

        self.minsup_relative = int(minsup * len(self.database) + 0.9999)

        self.hash = HashTable(hash_table_size)
        self.writer = open(output_file, "w")
        self.itemset_count = 0

        # First scan
        map_item_tidset = self.calculate_support_single_items()

        # Keep frequent items
        frequent_items = [
            item for item, tid in map_item_tidset.items()
            if tid.support >= self.minsup_relative
        ]

        # Sort by increasing support
        frequent_items.sort(key=lambda x: map_item_tidset[x].support)

        # Main loop
        for i, item_x in enumerate(frequent_items):

            tidset_x = map_item_tidset[item_x]
            prefix = [item_x]

            eq_items = []
            eq_tidsets = []

            for item_j in frequent_items[i + 1:]:

                tidset_j = map_item_tidset[item_j]
                new_tidset = BitSetSupport(
                    tidset_x.tidset & tidset_j.tidset
                )

                if new_tidset.support >= self.minsup_relative:
                    eq_items.append([item_j])
                    eq_tidsets.append(new_tidset)

            if eq_items:
                self.process_equivalence_class(prefix, eq_items, eq_tidsets)

            self.save(prefix, tidset_x)

        self.writer.close()
        self.end_time = time.time()

    # ----------------------------------------------------------
    # Load SPMF file
    # ----------------------------------------------------------

    def load_spmf_file(self, filepath):

        database = []

        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#") \
                        or line.startswith("%") \
                        or line.startswith("@"):
                    continue

                transaction = list(map(int, line.split()))
                database.append(transaction)

        return database

    # ----------------------------------------------------------
    # First pass
    # ----------------------------------------------------------

    def calculate_support_single_items(self):

        map_item_tidset = defaultdict(BitSetSupport)

        for tid, transaction in enumerate(self.database):
            for item in transaction:
                map_item_tidset[item].tidset.add(tid)

        for item in map_item_tidset:
            map_item_tidset[item].support = len(map_item_tidset[item].tidset)

        return map_item_tidset

    # ----------------------------------------------------------
    # Recursive equivalence processing
    # ----------------------------------------------------------

    def process_equivalence_class(self, prefix, itemsets, tidsets):

        for i in range(len(itemsets)):

            itemset_i = itemsets[i]
            tidset_i = tidsets[i]

            new_prefix = prefix + itemset_i

            new_eq_items = []
            new_eq_tidsets = []

            for j in range(i + 1, len(itemsets)):

                itemset_j = itemsets[j]
                tidset_j = tidsets[j]

                new_tidset = BitSetSupport(
                    tidset_i.tidset & tidset_j.tidset
                )

                if new_tidset.support >= self.minsup_relative:
                    new_eq_items.append(itemset_j)
                    new_eq_tidsets.append(new_tidset)

            if new_eq_items:
                self.process_equivalence_class(new_prefix, new_eq_items, new_eq_tidsets)

            self.save(new_prefix, tidset_i)

    # ----------------------------------------------------------
    # Save with closure checking
    # ----------------------------------------------------------

    def save(self, itemset, tidset):

        sorted_items = sorted(itemset)

        itemset_obj = Itemset(sorted_items)
        itemset_obj.set_absolute_support(tidset.support)

        hashcode = self.hash.hash_code(tidset.tidset)

        if not self.hash.contains_superset_of(itemset_obj, hashcode):

            self.itemset_count += 1

            line = " ".join(map(str, sorted_items))
            line += f" #SUP: {tidset.support}\n"
            self.writer.write(line)

            self.hash.put(itemset_obj, hashcode)

    # ----------------------------------------------------------
    # Print stats
    # ----------------------------------------------------------

    def print_stats(self):
        print("============= DCHARM (Python) STATS =============")
        print("Transactions:", len(self.database))
        print("Closed itemsets:", self.itemset_count)
        print("Time:", round(self.end_time - self.start_time, 4), "seconds")
        print("=================================================")


# ==============================================================
# MAIN (Equivalent to Java MainTestDCharm_bitset_saveToMemory)
# ==============================================================

if __name__ == "__main__":

    input_file = "contextPasquier99.txt"
    output_file = "dcharm_outputs.txt"
    minsup = 0.7

    algo = AlgoDCharm()
    algo.run_algorithm(input_file, output_file, minsup)

    algo.print_stats()

    print("Output saved to:", output_file)