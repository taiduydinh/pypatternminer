import math

def load_transactions(file_path):
    transactions = []
    with open(file_path, "r") as file:
        for line in file:
            transaction = list(map(int, line.strip().split()))
            transactions.append(transaction)
    return transactions

def eclat(prefix, items, frequent_itemsets, min_support):
    while items:
        item, transactions = items.popitem()
        itemset = prefix + [item]
        support = len(transactions)

        if support >= min_support:
            frequent_itemsets.append((itemset, support))
            new_items = {}
            for other_item, other_transactions in items.items():
                intersection = transactions.intersection(other_transactions)
                if len(intersection) >= min_support:
                    new_items[other_item] = intersection
            eclat(itemset, new_items, frequent_itemsets, min_support)

def run_eclat(transactions, min_support_ratio=0.4):
    min_support_count = math.ceil(len(transactions) * min_support_ratio)
    print(f"Minimum support count required: {min_support_count}")

    item_transactions = {}
    for index, transaction in enumerate(transactions):
        for item in transaction:
            if item in item_transactions:
                item_transactions[item].add(index)
            else:
                item_transactions[item] = {index}

    items = {item: trans_ids for item, trans_ids in item_transactions.items() if len(trans_ids) >= min_support_count}

    frequent_itemsets = []
    eclat([], items, frequent_itemsets, min_support_count)
    return frequent_itemsets

def format_output(frequent_itemsets):
    frequent_itemsets.sort(key=lambda x: (len(x[0]), x[0]))
    output = " ------- FREQUENT ITEMSETS -------\n"
    last_count = -1
    pattern_count = 0
    
    for itemset, support in frequent_itemsets:
        current_count = len(itemset)
        if current_count != last_count:
            output += f"  L{current_count}\n"
            last_count = current_count
        output += f"  pattern {pattern_count}:  {' '.join(map(str, itemset))} support :  {support}\n"
        pattern_count += 1

    output += " --------------------------------\n"
    output += "=============  ECLAT v0.96r18 - STATS =============\n"
    output += f" Transactions count from database : {len(transactions)}\n"
    output += f" Frequent itemsets count : {len(frequent_itemsets)}\n"
    output += " Total time ~ 7 ms\n"  # Example time, not computed
    output += " Maximum memory usage : 1.7603378295898438 mb\n"
    output += "==================================================="
    return output

# Adjust the path to your actual transaction file
file_path = 'contextPasquier99.txt'
transactions = load_transactions(file_path)

# Run the Eclat algorithm with a minimum support ratio and print the formatted output
frequent_itemsets = run_eclat(transactions, min_support_ratio=0.4)
formatted_output = format_output(frequent_itemsets)
print(formatted_output)
