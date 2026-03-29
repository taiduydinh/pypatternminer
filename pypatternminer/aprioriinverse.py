import math
import time
import os
import sys
import tracemalloc

# ------------------------------------------------------------
# MemoryLogger
# ------------------------------------------------------------
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0.0
        tracemalloc.start()

    @staticmethod
    def get_instance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self):
        self.max_memory = 0.0
        tracemalloc.reset_peak()

    def check_memory(self):
        current, peak = tracemalloc.get_traced_memory()
        peak_mb = peak / 1024 / 1024
        if peak_mb > self.max_memory:
            self.max_memory = peak_mb
        return peak_mb

    def get_max_memory(self):
        return round(self.max_memory, 2)


# ------------------------------------------------------------
# Itemset
# ------------------------------------------------------------
class Itemset:
    def __init__(self, items=None):
        self.itemset = items[:] if items else []
        self.support = 0

    def size(self):
        return len(self.itemset)

    def get(self, index):
        return self.itemset[index]

    def get_items(self):
        return self.itemset

    def get_absolute_support(self):
        return self.support

    def set_absolute_support(self, value):
        self.support = value

    def increase_transaction_count(self):
        self.support += 1

    def __str__(self):
        if not self.itemset:
            return "EMPTYSET"
        return " ".join(str(x) for x in self.itemset)


# ------------------------------------------------------------
# Itemsets
# ------------------------------------------------------------
class Itemsets:
    def __init__(self, name):
        self.name = name
        self.levels = [[]]
        self.itemsets_count = 0

    def add_itemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsets_count += 1

    def print_itemsets(self, nb_object):
        print(f" ------- {self.name} -------")
        pattern_count = 0
        for i, level in enumerate(self.levels):
            print(f"  L{i} ")
            for itemset in level:
                print(f"  pattern {pattern_count}: {itemset} #SUP: {itemset.get_absolute_support()}")
                pattern_count += 1
        print(" --------------------------------")


# ------------------------------------------------------------
# ArraysAlgos
# ------------------------------------------------------------
class ArraysAlgos:
    @staticmethod
    def same_as(itemset1, itemset2, pos_removed):
        j = 0
        for i in range(len(itemset1)):
            if j == pos_removed:
                j += 1
            if j >= len(itemset2):
                break
            if itemset1[i] == itemset2[j]:
                j += 1
            elif itemset1[i] > itemset2[j]:
                return 1
            else:
                return -1
        return 0


# ------------------------------------------------------------
# AlgoAprioriInverse
# ------------------------------------------------------------
class AlgoAprioriInverse:
    def __init__(self):
        self.k = 0
        self.total_candidate_count = 0
        self.start_timestamp = 0
        self.end_timestamp = 0
        self.itemset_count = 0
        self.database_size = 0
        self.minsup_relative = 0
        self.maxsup_relative = 0
        self.database = []
        self.patterns = None
        self.writer = None

    def run_algorithm(self, minsup, maxsup, input_path, output_path):
        self.start_timestamp = time.time()
        self.itemset_count = 0
        self.total_candidate_count = 0
        MemoryLogger.get_instance().reset()

        # -------------------------------
        # LOAD DATABASE
        # -------------------------------
        self.database = []
        item_count = {}

        with open(input_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ['#', '%', '@']:
                    continue
                transaction = [int(x) for x in line.split()]
                for item in transaction:
                    item_count[item] = item_count.get(item, 0) + 1
                self.database.append(transaction)

        self.database_size = len(self.database)
        self.minsup_relative = math.ceil(minsup * self.database_size)
        self.maxsup_relative = math.ceil(maxsup * self.database_size)

        print(f"[DEBUG] minsupRelative = {self.minsup_relative}, maxsupRelative = {self.maxsup_relative}, total transactions = {self.database_size}")

        # Output setup
        if output_path:
            self.writer = open(output_path, "w", encoding="utf-8")
            self.patterns = None
        else:
            self.writer = None
            self.patterns = Itemsets("SPORADIC ITEMSETS")

        # -------------------------------
        # FIND FREQUENT 1-ITEMSETS
        # -------------------------------
        frequent1 = [item for item, sup in item_count.items()
                     if sup >= self.minsup_relative and sup < self.maxsup_relative]
        frequent1.sort()

        for item in frequent1:
            self.save_itemset_to_file(item, item_count[item])

        if not frequent1:
            if self.writer:
                self.writer.close()
            return self.patterns

        self.total_candidate_count += len(frequent1)

        # -------------------------------
        # FIND LARGER ITEMSETS
        # -------------------------------
        k = 2
        level = None
        while True:
            MemoryLogger.get_instance().check_memory()
            if k == 2:
                candidates = self.generate_candidate2(frequent1)
            else:
                candidates = self.generate_candidate_size_k(level)
            self.total_candidate_count += len(candidates)

            # Count supports
            for transaction in self.database:
                for cand in candidates:
                    pos = 0
                    for item in transaction:
                        if item == cand.itemset[pos]:
                            pos += 1
                            if pos == len(cand.itemset):
                                cand.support += 1
                                break
                        elif item > cand.itemset[pos]:
                            break

            level = [cand for cand in candidates if cand.get_absolute_support() >= self.minsup_relative]
            for cand in level:
                self.save_itemset(cand)

            if not level:
                break
            k += 1

        self.end_timestamp = time.time()
        MemoryLogger.get_instance().check_memory()
        if self.writer:
            self.writer.close()
        return self.patterns

    def get_database_size(self):
        return self.database_size

    def generate_candidate2(self, frequent1):
        candidates = []
        for i in range(len(frequent1)):
            for j in range(i + 1, len(frequent1)):
                candidates.append(Itemset([frequent1[i], frequent1[j]]))
        return candidates

    def generate_candidate_size_k(self, level_k_1):
        candidates = []
        for i in range(len(level_k_1)):
            itemset1 = level_k_1[i].itemset
            for j in range(i + 1, len(level_k_1)):
                itemset2 = level_k_1[j].itemset
                valid = True
                for k in range(len(itemset1)):
                    if k == len(itemset1) - 1:
                        if itemset1[k] >= itemset2[k]:
                            valid = False
                            break
                    elif itemset1[k] < itemset2[k]:
                        valid = False
                        break
                    elif itemset1[k] > itemset2[k]:
                        valid = False
                        break
                if not valid:
                    continue
                new_itemset = itemset1[:] + [itemset2[-1]]
                if self.all_subsets_are_frequent(new_itemset, level_k_1):
                    candidates.append(Itemset(new_itemset))
        return candidates

    def all_subsets_are_frequent(self, candidate, level_k_1):
        for pos_removed in range(len(candidate)):
            first, last = 0, len(level_k_1) - 1
            found = False
            while first <= last:
                mid = (first + last) // 2
                comparison = ArraysAlgos.same_as(level_k_1[mid].get_items(), candidate, pos_removed)
                if comparison < 0:
                    first = mid + 1
                elif comparison > 0:
                    last = mid - 1
                else:
                    found = True
                    break
            if not found:
                return False
        return True

    def save_itemset(self, itemset):
        self.itemset_count += 1
        line = f"{itemset} #SUP: {itemset.get_absolute_support()}\n"
        if self.writer:
            self.writer.write(line)
        else:
            self.patterns.add_itemset(itemset, itemset.size())

    def save_itemset_to_file(self, item, support):
        self.itemset_count += 1
        line = f"{item} #SUP: {support}\n"
        if self.writer:
            self.writer.write(line)
        else:
            it = Itemset([item])
            it.set_absolute_support(support)
            self.patterns.add_itemset(it, 1)

    def print_stats(self):
        print("=============  APRIORI INVERSE - STATS =============")
        print(f" Candidates count : {self.total_candidate_count}")
        print(f" The algorithm stopped at size {self.k}, because there is no candidate")
        print(f" Sporadic itemsets count : {self.itemset_count}")
        print(f" Maximum memory usage : {MemoryLogger.get_instance().get_max_memory()} MB")
        print(f" Total time ~ {(self.end_timestamp - self.start_timestamp)*1000:.2f} ms")
        print("===================================================")


# ------------------------------------------------------------
# MAIN TEST
# ------------------------------------------------------------
def main():
    input_path = os.path.join(os.path.dirname(__file__), "contextInverse.txt")
    output_path = "aprioriinverse_outputs.txt"
    minsup = 0.4
    maxsup = 0.8

    print(f"[DEBUG] Using minsup = {minsup}, maxsup = {maxsup}")
    algo = AlgoAprioriInverse()
    algo.run_algorithm(minsup, maxsup, input_path, output_path)
    total_transactions = algo.get_database_size()
    print(f"[DEBUG] Total transactions in database = {total_transactions}")
    algo.print_stats()

    print("\n Mining complete! Output saved to:", output_path)
    print("=========================================")


if __name__ == "__main__":
    main()
