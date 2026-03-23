import time
import numpy as np
import tracemalloc

class Itemset:
    def __init__(self, items=None):
        self.items = items if items else []
        self.transaction_count = 0

    def add_item(self, item):
        self.items.append(item)

    def set_transaction_count(self, count):
        self.transaction_count = count

    def size(self):
        return len(self.items)

    def get(self, index):
        return self.items[index]

    def __eq__(self, other):
        return set(self.items) == set(other.items) and self.transaction_count == other.transaction_count

class Itemsets:
    def __init__(self, name):
        self.name = name
        self.levels = [[]]  # Initialize with L0 as an empty level

    def add_itemset(self, itemset, k):
        while len(self.levels) < k + 1:  # Adjust to ensure correct indexing
            self.levels.append([])
        self.levels[k].append(itemset)  # Adjusted to ensure correct level placement

    def get_itemsets_count(self):
        return sum(len(level) for level in self.levels)

    def print_itemsets(self):
        for level in self.levels:
            for itemset in level:
                print(f"{itemset.items} : {itemset.transaction_count}")

class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self):
        self.max_memory = 0

    def check_memory(self):
        self.max_memory = max(self.max_memory, self._current_memory_usage())

    def _current_memory_usage(self):
        # Placeholder for actual memory usage calculation
        return 0

class ArraysAlgos:
    @staticmethod
    def contains_all(transaction, itemset):
        return all(item in transaction for item in itemset)

class AlgoAprioriClose:
    def __init__(self):
        self.frequent_itemsets = Itemsets("FREQUENT ITEMSETS")
        self.start_timestamp = 0
        self.end_time = 0
        self.min_supp_relative = 0
        self.candidates_count = 0
        self.max_level = 0

    def run_algorithm(self, minsupp, database):
        self.start_timestamp = time.time()
        MemoryLogger.get_instance().reset()
        tracemalloc.start()

        self.min_supp_relative = int(np.ceil(minsupp * len(database)))

        itemset_counts = np.zeros(1000, dtype=int)  # assume max 1000 items
        for transaction in database:
            for item in transaction:
                itemset_counts[item] += 1

        level = []
        for i, count in enumerate(itemset_counts):
            if count >= self.min_supp_relative:
                itemset = Itemset([i])
                itemset.set_transaction_count(count)
                level.append(itemset)
                self.frequent_itemsets.add_itemset(itemset, 1)

        k = 1
        while level:
            self.max_level = k
            level_k = level
            level = []

            for i, itemset1 in enumerate(level_k):
                for j in range(i + 1, len(level_k)):
                    itemset2 = level_k[j]

                    # Generate new candidate by combining itemsets
                    new_itemset = sorted(set(itemset1.items) | set(itemset2.items))

                    if len(new_itemset) == k + 1:
                        new_itemset_obj = Itemset(new_itemset)

                        support = sum(1 for transaction in database if ArraysAlgos.contains_all(transaction, new_itemset))
                        self.candidates_count += 1  # Correctly count each candidate generated
                        if support >= self.min_supp_relative:
                            new_itemset_obj.set_transaction_count(support)
                            if new_itemset_obj not in level:
                                level.append(new_itemset_obj)
                                self.frequent_itemsets.add_itemset(new_itemset_obj, k + 1)

            k += 1

        # Ensure all levels are represented up to max_level + 1
        while len(self.frequent_itemsets.levels) < self.max_level + 1:
            self.frequent_itemsets.levels.append([])

        self.end_time = time.time()
        MemoryLogger.get_instance().check_memory()
        current, peak = tracemalloc.get_traced_memory()
        self.peak_memory = peak / 1024 / 1024  # Convert to MB
        tracemalloc.stop()
        return self.filter_closed_itemsets()

    def filter_closed_itemsets(self):
        closed_itemsets = Itemsets("CLOSED ITEMSETS")
        for level in self.frequent_itemsets.levels:
            for itemset in level:
                if itemset.size() == 0:
                    continue  # Skip empty itemsets
                is_closed = True
                for other_level in self.frequent_itemsets.levels:
                    for other_itemset in other_level:
                        if set(itemset.items).issubset(set(other_itemset.items)) and itemset.transaction_count == other_itemset.transaction_count and itemset.items != other_itemset.items:
                            is_closed = False
                            break
                    if not is_closed:
                        break
                if is_closed:
                    closed_itemsets.add_itemset(itemset, len(itemset.items))
        self.frequent_itemsets = closed_itemsets
        return closed_itemsets

    def print_stats(self):
        total_time = (self.end_time - self.start_timestamp) * 1000  # convert to ms
        print("=============  APRIORI - STATS =============")
        print(f" Candidates count : {self.candidates_count}")
        print(f" The algorithm stopped at size {self.max_level + 1}, because there is no candidate")
        print(f" Frequent closed itemsets count : {self.frequent_itemsets.get_itemsets_count()}")
        print(f" Maximum memory usage : {self.peak_memory} mb")
        print(f" Total time ~ {total_time:.2f} ms")
        print("===================================================")
        print(" ------- FREQUENT ITEMSETS -------")
        for k, level in enumerate(self.frequent_itemsets.levels):
            print(f"  L{k}")
            for i, itemset in enumerate(level):
                if itemset.size() > 0:  # Skip empty itemsets
                    print(f"  pattern {i}: ", " ".join(map(str, itemset.items)), "support : ", itemset.transaction_count)
        print(" --------------------------------")

# Read the context from contextPasquier99.txt file
context = []
with open('contextPasquier99.txt', 'r') as file:
    for line in file:
        transaction = list(map(int, line.strip().split()))
        context.append(transaction)

# Run the algorithm with the provided context and minimum support of 0.5
algo = AlgoAprioriClose()
closed_itemsets = algo.run_algorithm(0.5, context)
algo.print_stats()
