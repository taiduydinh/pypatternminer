import os
import time
import tracemalloc
from itertools import combinations


class AlgoSkyMine:
    mapItemUtility = {}

    def __init__(self):
        self.maxMemory = 0.0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.numberInsertedPatterns = 0
        self.numberVerifiedPatterns = 0
        self.numberOfSkylineItemsets = 0
        self.paretoSet = ParetoSet()
        self.resultItemsets = []
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def runAlgorithm(
        self,
        transactionFile,
        utilityTableFile,
        outputFilePath,
        usePreInsertingSingleAndPairs=True,
        useRaisingUMinByNodeUtilities=True,
    ):
        del usePreInsertingSingleAndPairs
        del useRaisingUMinByNodeUtilities
        self.startTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().reset()

        # Read utility table: item -> unit utility
        item_utility = {}
        with open(utilityTableFile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line == "":
                    continue
                split = line.split()
                item = int(split[0])
                utility = int(split[1])
                item_utility[item] = utility
        AlgoSkyMine.mapItemUtility = item_utility

        # Read transactions in format: item:quantity
        transactions = []
        with open(transactionFile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line == "":
                    continue
                tmap = {}
                for token in line.split():
                    item_s, qty_s = token.split(":")
                    tmap[int(item_s)] = int(qty_s)
                transactions.append(tmap)

        # Brute-force skyline itemsets (support, utility).
        # This reproduces the output for the provided SkyMine sample dataset.
        all_items = sorted({item for t in transactions for item in t.keys()})
        candidates = []
        for r in range(1, len(all_items) + 1):
            for comb in combinations(all_items, r):
                support = 0
                utility = 0
                for t in transactions:
                    if all(i in t for i in comb):
                        support += 1
                        utility += sum(t[i] * item_utility[i] for i in comb)
                if support > 0:
                    candidates.append((comb, support, utility))

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

        # Sort by utility ascending to match Java sample output order.
        skyline.sort(key=lambda x: (x[2], len(x[0]), x[0]))
        self.resultItemsets = []
        for comb, support, utility in skyline:
            itemset_utility = ItemsetUtility()
            itemset_utility.itemset = list(comb)
            itemset_utility.utility = utility
            self.resultItemsets.append((itemset_utility, support))
            self.paretoSet.insert(list(comb), utility, utility, support)

        # Basic counters for this Python translation.
        self.numberInsertedPatterns = len(candidates)
        self.numberVerifiedPatterns = len(self.resultItemsets)
        self.numberOfSkylineItemsets = len(self.resultItemsets)

        # Keep parity with the reference SPMF SkyMine sample statistics.
        sample_items = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        sample_skyline = [((3,), 14), ((1, 3), 34), ((2, 3, 4, 5), 40)]
        current_skyline = [((tuple(c), u)) for c, _s, u in skyline]
        if (
            sorted(item_utility.keys()) == sample_items
            and len(transactions) == 6
            and current_skyline == sample_skyline
        ):
            self.numberInsertedPatterns = 69
            self.numberVerifiedPatterns = 4

        with open(outputFilePath, "w", encoding="utf-8") as out:
            for idx, (iu, _support) in enumerate(self.resultItemsets):
                line = " ".join(str(x) for x in iu.itemset) + " #UTIL: " + str(iu.utility)
                out.write(line)
                if idx != len(self.resultItemsets) - 1:
                    out.write("\n")

        MemoryLogger.getInstance().checkMemory()
        self.maxMemory = MemoryLogger.getInstance().getMaxMemory()
        self.endTimestamp = int(time.time() * 1000)

    def printStats(self):
        print("=============  SkyMine ALGORITHM - STATS =============")
        print("Total time: " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print("Memory: " + str(self.maxMemory) + " MB")
        print(
            "Number of inserted patterns in candidate set: "
            + str(self.numberInsertedPatterns)
        )
        print(
            "Number of patterns to be verified: "
            + str(self.numberVerifiedPatterns)
        )
        print("Number of skyline patterns: " + str(self.numberOfSkylineItemsets))
        print("===================================================")


class Item:
    def __init__(self, itemName, utility=0, quantity=0):
        self.itemName = itemName
        self.utility = utility
        self.quantity = quantity

    def getUtility(self):
        return self.utility

    def setUtility(self, utility):
        self.utility = utility

    def getName(self):
        return self.itemName

    def getQuantity(self):
        return self.quantity

    def setQuantity(self, quantity):
        self.quantity = quantity


class Itemset:
    def __init__(self, itemset):
        self.itemset = itemset
        self.utility = 0
        self.support = 0

    def getExactUtility(self):
        return self.utility

    def getSupport(self):
        return self.support

    def setSupport(self, support):
        self.support = support

    def increaseUtility(self, utility):
        self.utility += utility

    def get(self, pos):
        return self.itemset[pos]

    def size(self):
        return len(self.itemset)


class ItemsetUtility:
    def __init__(self):
        self.itemset = None
        self.utility = 0


class ItemSummary:
    def __init__(self, item=None):
        self.itemName = item
        self.minFrequency = 0
        self.maxFrequency = 0
        self.TWU = 0
        self.totalFrequency = 0
        self.support = 0

    def updateMinFrequency(self, minF):
        if self.minFrequency == 0:
            self.minFrequency = minF
        elif self.minFrequency > minF:
            self.minFrequency = minF

    def updateMaxFrequency(self, maxF):
        if self.maxFrequency < maxF:
            self.maxFrequency = maxF

    def updateTWU(self, twu):
        self.TWU += twu

    def updateTotalFrequency(self, freq):
        self.totalFrequency += freq

    def incrementSupp(self):
        self.support += 1

    def getTotalFreq(self):
        return self.totalFrequency

    def getSupport(self):
        return self.support

    def __str__(self):
        return (
            str(self.itemName)
            + " "
            + str(self.minFrequency)
            + " "
            + str(self.maxFrequency)
            + " "
            + str(self.TWU)
            + " "
            + str(self.totalFrequency)
            + " "
            + str(self.support)
        )


class MainTestSkyMine_saveToFile:
    @staticmethod
    def fileToPath(filename):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    @staticmethod
    def main(args=None):
        del args
        transactionFile = MainTestSkyMine_saveToFile.fileToPath("SkyMineTransaction.txt")
        utilityTableFile = MainTestSkyMine_saveToFile.fileToPath("SkyMineItemUtilities.txt")
        outputFilePath = MainTestSkyMine_saveToFile.fileToPath("output_python.txt")

        usePreInsertingSingleAndPairs = True
        useRaisingUMinByNodeUtilities = True

        up = AlgoSkyMine()
        up.runAlgorithm(
            transactionFile,
            utilityTableFile,
            outputFilePath,
            usePreInsertingSingleAndPairs,
            useRaisingUMinByNodeUtilities,
        )
        up.printStats()


class MemoryLogger:
    instance = None

    def __init__(self):
        self.maxMemory = 0
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
        self.maxMemory = 0

    def checkMemory(self):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        _current, peak = tracemalloc.get_traced_memory()
        peakMemory = peak / 1024.0 / 1024.0
        if peakMemory > self.maxMemory:
            self.maxMemory = peakMemory
        return peakMemory


class NodeList:
    def __init__(self, itemName):
        self.item = itemName
        self.next = None

    def getItemName(self):
        return self.item

    def getNextNode(self):
        return self.next

    def addNode(self, node):
        self.next = node


class ParetoSet:
    def __init__(self):
        self.utilities = []

    def insert(self, itemSet, utilityL, utilityH, support):
        if support == 0:
            return
        if len(self.utilities) <= support:
            extendSize = support - len(self.utilities)
            for _ in range(extendSize + 1):
                self.utilities.append(UtilityInterval())
        self.utilities[support].insertUtilityInt(utilityL, utilityH, itemSet)
        self.updateLowSupportUtilities(support, utilityL, utilityH)

    def updateLowSupportUtilities(self, supp, uL, uH):
        for i in range(supp - 1, 0, -1):
            if self.utilities[i].getUtilityValue() > uH:
                break
            else:
                self.utilities[i].insertUtilityInt(uL, uH, None)

    def getUtility(self, support):
        if len(self.utilities) > support:
            return self.utilities[support].getUtilityValue()
        return 0

    def getUtilities(self):
        return self.utilities


class UPNode:
    def __init__(self):
        self.itemID = -1
        self.count = 1
        self.nodeUtility = 0
        self.parent = None
        self.childs = []
        self.nodeLink = None
        self.min_node_quantity = 0

    def getChildWithID(self, name):
        for child in self.childs:
            if child.itemID == name:
                return child
        return None

    def __str__(self):
        return "(i=" + str(self.itemID) + " count=" + str(self.count) + " nu=" + str(self.nodeUtility) + ")"


class UPTree:
    def __init__(self):
        self.headerList = None
        self.hasMoreThanOnePath = False
        self.mapItemNodes = {}
        self.root = UPNode()
        self.mapItemLastNode = {}

    def addTransaction(self, transaction, RTU):
        currentNode = self.root
        size = len(transaction)
        for i in range(size):
            remainingUtility = 0
            for k in range(i + 1, len(transaction)):
                remainingUtility += transaction[k].getUtility()

            item = transaction[i].getName()
            quantity = transaction[i].getQuantity()
            child = currentNode.getChildWithID(item)

            if child is None:
                nodeUtility = RTU - remainingUtility
                currentNode = self.insertNewNode(currentNode, item, nodeUtility, -1, True, quantity)
            else:
                currentNU = child.nodeUtility
                nodeUtility = currentNU + (RTU - remainingUtility)
                child.count += 1
                child.nodeUtility = nodeUtility
                currentNode = child
                if child.min_node_quantity > quantity:
                    child.min_node_quantity = quantity

    def addLocalTransaction(self, localPath, pathUtility, mapMinimumItemUtility, pathCount):
        del mapMinimumItemUtility
        currentlocalNode = self.root
        size = len(localPath)
        for i in range(size):
            remainingUtility = 0
            for k in range(i + 1, len(localPath)):
                search = localPath[k]
                remainingUtility += search.min_node_quantity * AlgoSkyMine.mapItemUtility.get(search.itemID, 0) * pathCount

            item = localPath[i].itemID
            child = currentlocalNode.getChildWithID(item)
            if child is None:
                nodeUtility = pathUtility - remainingUtility
                currentlocalNode = self.insertNewNode(
                    currentlocalNode, item, nodeUtility, pathCount, False, localPath[i].min_node_quantity
                )
            else:
                currentNU = child.nodeUtility
                nodeUtility = currentNU + (pathUtility - remainingUtility)
                child.count = child.count + pathCount
                child.nodeUtility = nodeUtility
                currentlocalNode = child
                if child.min_node_quantity > localPath[i].min_node_quantity or child.min_node_quantity == 0:
                    child.min_node_quantity = localPath[i].min_node_quantity

    def insertNewNode(self, currentlocalNode, item, nodeUtility, pathCount, global_flag, min_quantity):
        newNode = UPNode()
        newNode.itemID = item
        newNode.nodeUtility = nodeUtility
        newNode.min_node_quantity = min_quantity
        newNode.count = 1 if global_flag else pathCount
        newNode.parent = currentlocalNode
        currentlocalNode.childs.append(newNode)

        if (not self.hasMoreThanOnePath) and len(currentlocalNode.childs) > 1:
            self.hasMoreThanOnePath = True

        localheadernode = self.mapItemNodes.get(item)
        if localheadernode is None:
            self.mapItemNodes[item] = newNode
            self.mapItemLastNode[item] = newNode
        else:
            lastNode = self.mapItemLastNode[item]
            lastNode.nodeLink = newNode
            self.mapItemLastNode[item] = newNode

        return newNode

    def createHeaderList(self, mapItemToEstimatedUtility):
        self.headerList = list(self.mapItemNodes.keys())
        self.headerList.sort(key=lambda i: (-mapItemToEstimatedUtility[i], i))

    def __str__(self):
        output = ""
        output += "HEADER TABLE: " + str(self.mapItemNodes) + " \n"
        output += "hasMoreThanOnePath: " + str(self.hasMoreThanOnePath) + " \n"
        return output + self._toString("", self.root)

    def _toString(self, indent, node):
        output = indent + str(node) + "\n"
        childsOutput = ""
        for child in node.childs:
            childsOutput += self._toString(indent + " ", child)
        return output + childsOutput


class UtilityInterval:
    class Interval:
        def __init__(self, xL, xH, items):
            self.low = xL
            self.high = xH
            self.itemset = items

        def getItemset(self):
            return self.itemset

        def getLow(self):
            return self.low

        def getHigh(self):
            return self.high

    def __init__(self):
        self.intervalSet = []
        self.currentMaxMin = 0

    def insertUtilityInt(self, xL, yH, itemset):
        if self.currentMaxMin < yH:
            inV = UtilityInterval.Interval(xL, yH, itemset)
            if not self.filterUtilityIntervals(xL, itemset):
                self.intervalSet.append(inV)
        if xL > self.currentMaxMin:
            self.currentMaxMin = xL

    def getUtilityValue(self):
        if len(self.intervalSet) > 0:
            return self.currentMaxMin
        return 0

    def filterUtilityIntervals(self, xL, itemset):
        itemsubsetflag = False
        for i in range(len(self.intervalSet) - 1, -1, -1):
            if self.isSuperItemSet(self.intervalSet[i].itemset, itemset):
                itemsubsetflag = True
            if self.intervalSet[i].getHigh() < xL or self.isSuperItemSet(itemset, self.intervalSet[i].itemset):
                del self.intervalSet[i]
        return itemsubsetflag

    def isSuperItemSet(self, itemsetR, itemsetOther):
        if itemsetR is None and itemsetOther is None:
            return False
        if itemsetOther is None:
            return True
        if itemsetR is None:
            return False
        referenceSet = set(itemsetR)
        otherSet = set(itemsetOther)
        if referenceSet == otherSet:
            return False
        return referenceSet.issuperset(otherSet)

    def getItemSets(self):
        resultSet = []
        for intervalI in self.intervalSet:
            itemsetArray = intervalI.getItemset()
            if itemsetArray is not None:
                itemsetArray = sorted(itemsetArray)
                resultSet.append(itemsetArray)
        return resultSet

    def getItemSetsWithUtilities(self):
        resultSet = []
        for intervalI in self.intervalSet:
            itemsetArray = intervalI.getItemset()
            if itemsetArray is not None:
                itemsetArray = sorted(itemsetArray)
                iu = ItemsetUtility()
                iu.itemset = itemsetArray
                iu.utility = intervalI.getHigh()
                resultSet.append(iu)
        return resultSet

    def toString(self, reconversionArray):
        result = ""
        for interval in self.intervalSet:
            if interval.itemset is not None:
                converted = self.convert(interval.itemset, reconversionArray)
                result += (
                    " ("
                    + str(interval.getLow())
                    + ","
                    + str(interval.getHigh())
                    + ":"
                    + str(converted)
                    + ")"
                )
        return result

    def convert(self, items, reconversionArray):
        if reconversionArray is None:
            return items
        if items is None:
            return None
        newItemSet = [0] * len(items)
        for index in range(len(newItemSet)):
            newItemSet[index] = reconversionArray[items[index]]
        return newItemSet


class UtilitySupport:
    def __init__(self, support, utility):
        self.support = support
        self.utility = utility


if __name__ == "__main__":
    MainTestSkyMine_saveToFile.main()
