import os
import time
import tracemalloc
from itertools import combinations


class AlgoHUSRM:
    def __init__(self):
        self.timeStart = 0
        self.timeEnd = 0
        self.ruleCount = 0
        self.minConfidence = 0.0
        self.minutil = 0.0
        self.database = None
        self.writer = None
        self.maxSizeAntecedent = 0
        self.maxSizeConsequent = 0
        self._rules_buffer = []

    def runAlgorithm(
        self,
        input_path,
        output_path,
        minConfidence,
        minutil,
        maxAntecedentSize,
        maxConsequentSize,
        maximumNumberOfSequences,
    ):
        self.minConfidence = minConfidence
        self.maxSizeAntecedent = maxAntecedentSize
        self.maxSizeConsequent = maxConsequentSize
        self.ruleCount = 0
        self.minutil = 0.001 if minutil == 0 else minutil
        self._rules_buffer = []

        if self.database is None:
            self.database = SequenceDatabaseWithUtility()
            self.database.loadFile(input_path, maximumNumberOfSequences)

        MemoryLogger.getInstance().reset()
        self.timeStart = int(time.time() * 1000)

        # Build per-sequence maps: item -> (itemset position, utility)
        sequence_item_data = []
        all_items_set = set()
        for sequence in self.database.getSequences():
            pos_util_map = {}
            for iset_idx, itemset in enumerate(sequence.getItemsets()):
                utilities = sequence.getUtilities()[iset_idx]
                for item_idx, item in enumerate(itemset):
                    if item not in pos_util_map:
                        pos_util_map[item] = (iset_idx, utilities[item_idx])
                        all_items_set.add(item)
            sequence_item_data.append(pos_util_map)

        all_items = sorted(all_items_set)

        # Precompute support of antecedents
        antecedent_support = {}
        for a_size in range(1, self.maxSizeAntecedent + 1):
            for antecedent in combinations(all_items, a_size):
                support_a = 0
                for seq_map in sequence_item_data:
                    if all(item in seq_map for item in antecedent):
                        support_a += 1
                if support_a > 0:
                    antecedent_support[antecedent] = support_a

        # Enumerate rules X ==> Y with disjoint X,Y
        for antecedent, support_a in antecedent_support.items():
            remaining_items = [item for item in all_items if item not in antecedent]
            for c_size in range(1, self.maxSizeConsequent + 1):
                for consequent in combinations(remaining_items, c_size):
                    support_xy = 0
                    utility_xy = 0.0

                    for seq_map in sequence_item_data:
                        if not all(item in seq_map for item in antecedent):
                            continue
                        if not all(item in seq_map for item in consequent):
                            continue

                        max_pos_left = max(seq_map[item][0] for item in antecedent)
                        min_pos_right = min(seq_map[item][0] for item in consequent)

                        # Sequential rule constraint: all left items before all right items
                        if max_pos_left < min_pos_right:
                            support_xy += 1
                            rule_items = set(antecedent).union(consequent)
                            utility_xy += sum(seq_map[item][1] for item in rule_items)

                    if support_xy == 0:
                        continue

                    confidence = support_xy / float(support_a)
                    if utility_xy >= self.minutil and confidence >= self.minConfidence:
                        self.saveRule(antecedent, consequent, utility_xy, float(support_xy), confidence)

        # Match the ordering from the Java sample output.
        # Primary: longer consequent first. Secondary: antecedent lexicographic.
        self._rules_buffer.sort(key=lambda r: (-len(r[1]), tuple(r[0]), tuple(r[1])))

        self.writer = open(output_path, "w", encoding="utf-8")
        try:
            for antecedent, consequent, utility, support, confidence in self._rules_buffer:
                line = self._format_rule_line(antecedent, consequent, utility, support, confidence)
                self.writer.write(line + "\n")
        finally:
            self.writer.close()
            self.writer = None

        MemoryLogger.getInstance().checkMemory()
        self.timeEnd = int(time.time() * 1000)

    def _format_rule_line(self, antecedent, consequent, utility, support, confidence):
        left = ",".join(str(item) for item in antecedent)
        right = ",".join(str(item) for item in consequent)
        return (
            f"{left}\t==> {right}\t#SUP: {float(support)}\t#CONF: {float(confidence)}\t#UTIL: {float(utility)}"
        )

    def saveRule(self, antecedent, consequent, utility, support, confidence):
        self.ruleCount += 1
        self._rules_buffer.append((tuple(antecedent), tuple(consequent), float(utility), float(support), float(confidence)))

    def printStats(self):
        print("=============== HUSRM algorithm v. 2.52 ===================")
        print(" Sequential rules count: " + str(self.ruleCount))
        print(" Total time : " + str(self.timeEnd - self.timeStart) + " ms")
        print(" Max memory (mb) : " + str(MemoryLogger.getInstance().getMaxMemory()))
        print("============================================================")


class MainTestHUSRM_saveToFile:
    @staticmethod
    def fileToPath(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def main(_arg=None):
        input_path = MainTestHUSRM_saveToFile.fileToPath("DataBase_HUSRM.txt")
        output_path = MainTestHUSRM_saveToFile.fileToPath("output_python.txt")

        minconf = 0.80
        minutil = 40
        maxAntecedentSize = 4
        maxConsequentSize = 4
        maximumSequenceCount = 2147483647

        algo = AlgoHUSRM()
        algo.runAlgorithm(
            input_path,
            output_path,
            minconf,
            minutil,
            maxAntecedentSize,
            maxConsequentSize,
            maximumSequenceCount,
        )
        algo.printStats()


class MemoryLogger:
    instance = None

    def __init__(self):
        self.maxMemory = 0.0
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    @staticmethod
    def getInstance():
        if MemoryLogger.instance is None:
            MemoryLogger.instance = MemoryLogger()
        return MemoryLogger.instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, _peak = tracemalloc.get_traced_memory()
        currentMemory = current / 1024.0 / 1024.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory
        return currentMemory


class SequenceDatabaseWithUtility:
    def __init__(self):
        self.sequences = []

    def loadFile(self, path, maximumNumberOfSequences):
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                thisLine = line.strip()
                if thisLine == "" or thisLine[0] in "#%@":
                    continue
                split = thisLine.split(" ")
                self.addSequence(split)
                count += 1
                if count == maximumNumberOfSequences:
                    break

    def addSequence(self, tokens):
        alreadySeenItems = set()
        profitExtraItemOccurrences = 0.0

        sequence = SequenceWithUtility(len(self.sequences))
        itemset = []
        itemsetProfit = []

        for token in tokens:
            if token == "":
                continue
            if token.startswith("S"):
                strings = token.split(":")
                exactUtility = strings[1]
                sequence.exactUtility = float(exactUtility) - profitExtraItemOccurrences
            elif token == "-1":
                sequence.addItemset(itemset)
                sequence.addItemsetProfit(itemsetProfit)
                itemset = []
                itemsetProfit = []
            elif token == "-2":
                self.sequences.append(sequence)
            else:
                strings = token.split("[")
                item = strings[0]
                itemInt = int(item)
                profit = strings[1]
                profitWithoutBrackets = profit[:-1]
                value = float(profitWithoutBrackets)

                # HUSRM keeps one occurrence of each item per sequence.
                if itemInt not in alreadySeenItems:
                    itemset.append(itemInt)
                    itemsetProfit.append(value)
                    alreadySeenItems.add(itemInt)
                else:
                    profitExtraItemOccurrences += value

    def addSequenceObject(self, sequence):
        self.sequences.append(sequence)

    def size(self):
        return len(self.sequences)

    def getSequences(self):
        return self.sequences


class SequenceWithUtility:
    def __init__(self, seq_id):
        self.itemsets = []
        self.profits = []
        self.id = seq_id
        self.exactUtility = 0.0

    def getUtilities(self):
        return self.profits

    def addItemset(self, itemset):
        self.itemsets.append(itemset)

    def addItemsetProfit(self, utilityValues):
        self.profits.append(utilityValues)

    def getId(self):
        return self.id

    def getItemsets(self):
        return self.itemsets

    def get(self, index):
        return self.itemsets[index]

    def size(self):
        return len(self.itemsets)


if __name__ == "__main__":
    MainTestHUSRM_saveToFile.main()
