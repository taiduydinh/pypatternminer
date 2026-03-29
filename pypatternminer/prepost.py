import time
import psutil
from collections import defaultdict
from math import ceil

class TreeNode:
    def __init__(self, item, count=0):
        self.item = item
        self.count = count
        self.parent = None
        self.children = {}
        self.preorder = -1
        self.postorder = -1

class PrePostTree:
    def __init__(self):
        self.root = TreeNode(None)
        self.headers = defaultdict(list)
        self.item_counts = defaultdict(int)
        self.transactions = []
        self.preorder_counter = 0
        self.postorder_counter = 0

    def add_transaction(self, transaction):
        current_node = self.root
        sorted_items = sorted(transaction, key=lambda item: (-self.item_counts[item], item))
        for item in sorted_items:
            if item not in current_node.children:
                new_node = TreeNode(item)
                current_node.children[item] = new_node
                new_node.parent = current_node
                self.headers[item].append(new_node)
            current_node = current_node.children[item]
            current_node.count += 1

    def assign_prepost_numbers(self, node):
        node.preorder = self.preorder_counter
        self.preorder_counter += 1
        for child in node.children.values():
            self.assign_prepost_numbers(child)
        node.postorder = self.postorder_counter
        self.postorder_counter += 1

    def mine_patterns(self, min_support):
        patterns = []
        for item in sorted(self.headers.keys(), key=lambda x: -self.item_counts[x]):
            nodes = self.headers[item]
            support = sum(node.count for node in nodes)
            if support >= min_support:
                pattern = [item]
                patterns.append((pattern, support))
                conditional_base = []
                for node in nodes:
                    path = []
                    parent = node.parent
                    while parent.item is not None:
                        path.append(parent.item)
                        parent = parent.parent
                    for _ in range(node.count):
                        conditional_base.append(path)
                conditional_tree = PrePostTree()
                conditional_tree.item_counts = defaultdict(int, {k: v for k, v in self.item_counts.items() if k in {x for path in conditional_base for x in path}})
                conditional_tree.transactions = conditional_base
                for transaction in conditional_base:
                    conditional_tree.add_transaction(transaction)
                conditional_tree.assign_prepost_numbers(conditional_tree.root)
                sub_patterns = conditional_tree.mine_patterns(min_support)
                for sub_pattern, sub_support in sub_patterns:
                    patterns.append((pattern + sub_pattern, sub_support))
        return patterns

    def read_transactions(self, file_path):
        with open(file_path, 'r') as file:
            for line in file:
                transaction = set(map(int, line.strip().split()))
                self.transactions.append(transaction)
                for item in transaction:
                    self.item_counts[item] += 1

    def run_algorithm(self, file_path, min_support_ratio):
        self.read_transactions(file_path)
        min_support = ceil(min_support_ratio * len(self.transactions))
        print(f"Calculated min_support_count: {min_support}")

        for transaction in self.transactions:
            self.add_transaction(transaction)
        self.assign_prepost_numbers(self.root)

        start_time = time.time()
        patterns = self.mine_patterns(min_support)
        end_time = time.time()

        total_time = (end_time - start_time) * 1000  # in milliseconds
        max_memory = psutil.Process().memory_info().rss / (1024 ** 2)  # in MB

        with open("prepost_output.txt", "w") as f:
            for pattern, support in sorted(patterns, key=lambda x: (-len(x[0]), x[0])):
                f.write(f"{' '.join(map(str, sorted(pattern)))} #SUP: {support}\n")

        print("========== PrePost - STATS ============")
        print(f" Minsup = {min_support}")
        print(f" Number of transactions: {len(self.transactions)}")
        print(f" Number of frequent itemsets: {len(patterns)}")
        print(f" Total time ~: {total_time:.2f} ms")
        print(f" Max memory: {max_memory:.6f} MB")
        print("========================================")

# Usage
tree = PrePostTree()
tree.run_algorithm('contextPasquier99.txt', min_support_ratio=0.4)
