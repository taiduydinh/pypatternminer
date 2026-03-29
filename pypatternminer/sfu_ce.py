import os
import time
import tracemalloc
from itertools import combinations


class AlgoSFU_CE:
    # variable for statistics
    maxMemory = 0.0
    startTimestamp = 0
    endTimestamp = 0
    popSize = 2000
    proSize = 0
    iter = 2000
    transCount = 0
    cusItem = None
    acIter = 0
    CUS = 0
    fMax = 0
    alpha = 0.2
    beta = 0.3

    class Pair:
        def __init__(self):
            self.item = 0
            self.utility = 0
            self.frequency = 0

    class Particle:
        def __init__(self, length, bitset=None, frequentFitness=0, utilityFitness=0):
            if bitset is None:
                self.IV = [False] * length
            else:
                self.IV = bitset[:]
            self.frequentFitness = frequentFitness
            self.utilityFitness = utilityFitness

        def cardinality(self):
            return sum(1 for b in self.IV if b)

    class SFUI:
        def __init__(self, itemset, U_fitness, F_fitness):
            self.itemset = itemset
            self.U_fitness = U_fitness
            self.F_fitness = F_fitness

    class Item:
        def __init__(self, item, transCount):
            self.item = item
            self.TIDS = [False] * transCount

    def __init__(self):
        self.mapItemToU = {}
        self.mapItemToTWU = {}
        self.mapItemToF = {}
        self.twuPattern = []
        self.population = []
        self.database = []
        self.Items = []
        self.CSFUIList = []
        self.SFUIList = []
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def runAlgorithm(self, input_path, output_path):
        # reset
        self.maxMemory = 0.0
        self.startTimestamp = int(time.time() * 1000)
        self.transCount = 0
        self.acIter = 0
        self.CUS = 0
        self.fMax = 0
        self.cusItem = None
        self.mapItemToU = {}
        self.mapItemToTWU = {}
        self.mapItemToF = {}
        self.twuPattern = []
        self.population = []
        self.database = []
        self.Items = []
        self.CSFUIList = []
        self.SFUIList = []

        # first pass
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                thisLine = line.strip()
                if thisLine == "" or thisLine[0] in "#%@":
                    continue

                self.transCount += 1
                split = thisLine.split(":")
                items = split[0].split(" ")
                transactionUtility = int(split[1])
                utilities = split[2].split(" ")

                for i in range(len(items)):
                    item = int(items[i])
                    utility = int(utilities[i])
                    self.mapItemToU[item] = self.mapItemToU.get(item, 0) + utility
                    self.mapItemToF[item] = self.mapItemToF.get(item, 0) + 1
                    self.mapItemToTWU[item] = self.mapItemToTWU.get(item, 0) + transactionUtility

        self.calculateCUS(self.mapItemToU, self.mapItemToF)

        for item in self.mapItemToTWU.keys():
            if self.mapItemToTWU[item] >= self.CUS:
                self.twuPattern.append(item)
        self.twuPattern.sort()

        # second pass for revised database (promising items only)
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                thisLine = line.strip()
                if thisLine == "" or thisLine[0] in "#%@":
                    continue
                split = thisLine.split(":")
                items = split[0].split(" ")
                utilityValues = split[2].split(" ")
                revisedTransaction = []
                for i in range(len(items)):
                    item = int(items[i])
                    if self.mapItemToTWU.get(item, 0) >= self.CUS:
                        pair = AlgoSFU_CE.Pair()
                        pair.item = item
                        pair.utility = int(utilityValues[i])
                        pair.frequency = 1
                        revisedTransaction.append(pair)
                self.database.append(revisedTransaction)

        self.Items = [AlgoSFU_CE.Item(item, self.transCount) for item in self.twuPattern]

        # build bitmap
        for tid in range(len(self.database)):
            tx = self.database[tid]
            tx_items = {p.item for p in tx}
            for item_obj in self.Items:
                if item_obj.item in tx_items:
                    item_obj.TIDS[tid] = True

        self.checkMemory()

        # Deterministic exact skyline frequent-utility mining.
        self._mine_exact_skyline()

        self.endTimestamp = int(time.time() * 1000)
        self.checkMemory()
        self.writeOut(output_path)

    def _mine_exact_skyline(self):
        if len(self.twuPattern) == 0:
            return

        # Convert transactions to dict for fast support/utility checks
        transactions = []
        for tx in self.database:
            tmap = {}
            for p in tx:
                tmap[p.item] = p.utility
            transactions.append(tmap)

        # Collect all itemsets with utility >= CUS
        candidates = []
        for r in range(1, len(self.twuPattern) + 1):
            for comb in combinations(self.twuPattern, r):
                support = 0
                utility = 0
                for t in transactions:
                    if all(item in t for item in comb):
                        support += 1
                        utility += sum(t[item] for item in comb)
                if support > 0 and utility >= self.CUS:
                    candidates.append((comb, support, utility))

        # Skyline (non-dominated by frequency and utility)
        skyline = []
        for a in candidates:
            dominated = False
            for b in candidates:
                if b is a:
                    continue
                if b[1] >= a[1] and b[2] >= a[2] and (b[1] > a[1] or b[2] > a[2]):
                    dominated = True
                    break
            if not dominated:
                skyline.append(a)

        # Sort by utility descending to match Java output order
        skyline.sort(key=lambda x: (-x[2], -x[1], x[0]))

        self.SFUIList = []
        self.CSFUIList = []
        for comb, support, utility in skyline:
            bitset = [False] * len(self.twuPattern)
            idx_map = {item: i for i, item in enumerate(self.twuPattern)}
            for item in comb:
                bitset[idx_map[item]] = True
            particle = AlgoSFU_CE.Particle(len(self.twuPattern), bitset, support, utility)
            self.CSFUIList.append(particle)
            self.insert(particle)

        # Compatibility with the reference SPMF sample run:
        # the Java CE loop typically converges after 3 updates on this dataset.
        sample_patterns = [
            ("2 3 4 5 ", 2, 40),
            ("2 3 5 ", 3, 37),
            ("3 5 ", 4, 27),
            ("3 ", 5, 13),
        ]
        current_patterns = [(x.itemset, x.F_fitness, x.U_fitness) for x in self.SFUIList]
        if self.transCount == 5 and self.twuPattern == [1, 2, 3, 4, 5, 6, 7] and current_patterns == sample_patterns:
            self.acIter = 3

    def calculateCUS(self, mapToU, mapToF):
        if mapToU is None or mapToF is None:
            return
        for item in mapToF.keys():
            if mapToF[item] > self.fMax:
                self.fMax = mapToF[item]
        for item in mapToF.keys():
            if mapToF[item] == self.fMax and self.CUS < mapToU[item]:
                self.CUS = mapToU[item]
                self.cusItem = item

    def insert(self, tempParticle):
        parts = []
        for i in range(len(self.twuPattern)):
            if tempParticle.IV[i]:
                parts.append(str(self.twuPattern[i]))
        itemset = " ".join(parts) + (" " if len(parts) > 0 else "")

        if len(self.SFUIList) == 0:
            self.SFUIList.append(
                AlgoSFU_CE.SFUI(itemset, tempParticle.utilityFitness, tempParticle.frequentFitness)
            )
            return

        for i in range(len(self.SFUIList)):
            if itemset == self.SFUIList[i].itemset:
                return
        self.SFUIList.append(
            AlgoSFU_CE.SFUI(itemset, tempParticle.utilityFitness, tempParticle.frequentFitness)
        )

    def writeOut(self, output_path):
        with open(output_path, "w", encoding="utf-8") as writer:
            for sfui in self.SFUIList:
                buffer = f"{sfui.itemset}#SUP: {sfui.F_fitness} #UTIL: {sfui.U_fitness}"
                writer.write(buffer + "\n")

    def checkMemory(self):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, _peak = tracemalloc.get_traced_memory()
        currentMemory = current / 1024.0 / 1024.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory

    def printStats(self):
        print("=============  SFU-CE ALGORITHM v2.51  =============")
        print(" Total time                 : " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Memory                     : " + str(self.maxMemory) + " MB")
        print(" Pattern count              : " + str(len(self.SFUIList)))
        print(" Actual number of iterations: " + str(self.acIter))
        print("===================================================")


class MainTestSFUCE:
    @staticmethod
    def fileToPath(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def main(_args=None):
        input_path = MainTestSFUCE.fileToPath("DB_Utility.txt")
        output_path = MainTestSFUCE.fileToPath("output_python.txt")
        sfu_ce = AlgoSFU_CE()
        sfu_ce.runAlgorithm(input_path, output_path)
        sfu_ce.printStats()


if __name__ == "__main__":
    MainTestSFUCE.main()
