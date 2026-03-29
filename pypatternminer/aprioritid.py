import timeit
import math
import psutil


class Itemset:
    def __init__(self, items):
        self.itemset = items
        self.transactions_ids = set()

    def get_absolute_support(self):
        return len(self.transactions_ids)

    def get_items(self):
        return self.itemset

    def get(self, index):
        return self.itemset[index]

    def set_tids(self, listTransactionIds):
        self.transactions_ids = set(listTransactionIds)

    def size(self):
        return len(self.itemset)

    def get_transactions_ids(self):
        return self.transactions_ids

    def get_relative_support(self, nb_object):
        print(self.get_absolute_support())
        print(nb_object)
        return self.get_absolute_support() / nb_object

    def __str__(self):
        return " ".join(str(item) for item in self.itemset)


class Itemsets:
    def __init__(self, name):
        self.levels = [[]]
        self.itemsets_count = 0
        self.name = name

    def print_itemsets(self, nb_object):
        print(" ------- " + self.name + " -------")
        pattern_count = 0
        level_count = 0
        for level in self.levels:
            print("  L" + str(level_count) + " ")
            for itemset in level:
                itemset_str = str(itemset)
                print(f"  pattern {pattern_count}:  {itemset_str} support : {itemset.get_relative_support(nb_object)}")
                pattern_count += 1
            level_count += 1
        print(" --------------------------------")

    def add_itemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsets_count += 1

    def get_levels(self):
        return self.levels

    def get_itemsets_count(self):
        return self.itemsets_count


class TransactionDatabase:
    def __init__(self):
        self.items = set()
        self.transactions = []

    def add_transaction(self, transaction):
        self.transactions.append(transaction)
        self.items.update(transaction)

    def load_file(self, path):
        with open(path, "r") as file:
            for line in file:
                if line.strip() and not line.startswith("#") and not line.startswith("%") and not line.startswith("@"):
                    items = list(map(int, line.split()))
                    self.add_transaction(items)

    def print_database(self):
        print("===================  TRANSACTION DATABASE ===================")
        count = 0
        for itemset in self.transactions:
            print(f"{count}: ", end="")
            self.print_itemset(itemset)
            count += 1

    @staticmethod
    def print_itemset(itemset):
        print(" ".join(str(item) for item in itemset))

    def size(self):
        return len(self.transactions)

    def get_transactions(self):
        return self.transactions

    def get_items(self):
        return self.items


class AlgoAprioriTID:
    def __init__(self):
        self.k = 0
        self.map_item_tids = {}
        self.min_supp_relative = 0
        self.max_itemset_size = float('inf')
        self.start_timestamp = 0
        self.end_timestamp = 0
        self.writer = None
        self.patterns = None
        self.itemset_count = 0
        self.database_size = 0
        self.database = None
        self.empty_set_is_required = False
        self.show_transaction_identifiers = False

    def run_algorithm(self, database, output_file, min_supp):
        self.start_timestamp = timeit.default_timer()
        self.itemset_count = 0
        if output_file is None:
            self.writer = None
            self.patterns = Itemsets("FREQUENT ITEMSETS")
        else:
            self.patterns = None
            self.writer = open(output_file, 'w')

        self.map_item_tids = {}
        self.database_size = 0

        if database is not None:
            for transaction in database.get_transactions():
                for item in transaction:
                    tids = self.map_item_tids.get(item, set())
                    tids.add(self.database_size)
                    self.map_item_tids[item] = tids
                self.database_size += 1
        else:
            raise ValueError("Database is None.")

        if self.empty_set_is_required:
            self.patterns.add_itemset("", 0)

        self.min_supp_relative = math.ceil(min_supp * self.database_size)
        k = 1
        level = []

        items_to_delete = []

        for item, tids in self.map_item_tids.items():
            if len(tids) >= self.min_supp_relative and self.max_itemset_size >= 1:
                itemset = str(item)
                level.append(itemset)
                self.save_itemset(itemset, tids)
            else:
                items_to_delete.append(item)

        for item in items_to_delete:
            del self.map_item_tids[item]

        level.sort()

        k = 2
        while level and k <= self.max_itemset_size:
            level = self.generate_candidate_size_k(level)
            k += 1

        if self.writer:
            self.writer.close()

        self.end_timestamp = timeit.default_timer()

        return self.patterns

    def generate_candidate_size_k(self, level_k_1):
        candidates = []

        for i in range(len(level_k_1)):
            itemset1 = level_k_1[i]
            for j in range(i + 1, len(level_k_1)):
                itemset2 = level_k_1[j]
                if itemset1[:-1] == itemset2[:-1]:
                    new_itemset = itemset1 + " " + itemset2[-1]
                    candidate = str(new_itemset)
                    common_tids = self.get_common_tids(itemset1, itemset2)
                    if len(common_tids) >= self.min_supp_relative:
                        candidates.append(candidate)
                        self.save_itemset(candidate, common_tids)

        return candidates

    def get_common_tids(self, itemset1, itemset2):
        items1 = itemset1.split()
        items2 = itemset2.split()

        common_tids = set(self.map_item_tids[int(items1[0])])
        for item in items1[1:]:
            common_tids.intersection_update(self.map_item_tids[int(item)])
        for item in items2:
            common_tids.intersection_update(self.map_item_tids[int(item)])
        return common_tids

    def save_itemset(self, itemset, tids):
        self.itemset_count += 1
        if self.writer:
            self.writer.write(f"{itemset} #SUP: {len(tids)}")
            if self.show_transaction_identifiers:
                self.writer.write(" #TID:")
                for tid in tids:
                    self.writer.write(f" {tid}")
            self.writer.write("\n")
        else:
            itemset_obj = Itemset(list(map(int, itemset.split())))
            itemset_obj.set_tids(tids)
            self.patterns.add_itemset(itemset_obj, itemset_obj.size())

    def set_max_itemset_size(self, max_itemset_size):
        self.max_itemset_size = max_itemset_size

    def set_empty_set_is_required(self, empty_set_is_required):
        self.empty_set_is_required = empty_set_is_required

    def set_show_transaction_identifiers(self, show_transaction_identifiers):
        self.show_transaction_identifiers = show_transaction_identifiers

    def print_stats(self):
        elapsed_time = self.end_timestamp - self.start_timestamp
        print("=============  APRIORI TID v2.12 - STATS =============")
        print(" Transactions count from database :", self.database_size)
        print(" Frequent itemsets count :", self.itemset_count)
        print(" Maximum memory usage :", psutil.Process().memory_info().peak_wset / 1024 / 1024, "mb")
        print(" Total time ~", elapsed_time, "s")
        print("===================================================")


def main():
    input_file = "contextPasquier99.txt"
    algo = AlgoAprioriTID()

    db = TransactionDatabase()
    db.load_file(input_file)
    patterns = algo.run_algorithm(db, None, 0.4)

    # Print the statistics
    algo.print_stats()

    # Print the itemsets
    patterns.print_itemsets(algo.database_size)


if __name__ == "__main__":
    main()
