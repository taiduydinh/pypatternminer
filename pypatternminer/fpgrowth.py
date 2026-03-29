import math
import time

class MemoryLogger:
    _instance = None
    def __init__(self):
        self.max_memory = 0.0
        self._enabled = False
    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance
    def reset(self):
        self.max_memory = 0.0
        try:
            import tracemalloc
            tracemalloc.stop()
            tracemalloc.start()
            self._enabled = True
        except Exception:
            self._enabled = False
    def checkMemory(self):
        if self._enabled:
            import tracemalloc
            cur, peak = tracemalloc.get_traced_memory()
            mb = peak / 1024.0 / 1024.0
            if mb > self.max_memory:
                self.max_memory = mb
            return cur / 1024.0 / 1024.0
        return self.max_memory
    def getMaxMemory(self):
        return self.max_memory

class AbstractItemset:
    def size(self): raise NotImplementedError
    def __str__(self): raise NotImplementedError
    def print(self): print(str(self), end="")
    def getAbsoluteSupport(self): raise NotImplementedError
    def getRelativeSupport(self, nbObject): raise NotImplementedError
    def getRelativeSupportAsString(self, nbObject):
        val = self.getRelativeSupport(nbObject)
        s = f"{val:.5f}"
        return s.rstrip('0').rstrip('.') if '.' in s else s
    def contains(self, item): raise NotImplementedError

class AbstractOrderedItemset(AbstractItemset):
    def get(self, position): raise NotImplementedError
    def getLastItem(self): return self.get(self.size() - 1)
    def __str__(self):
        if self.size() == 0: return "EMPTYSET"
        return " ".join(str(self.get(i)) for i in range(self.size())) + " "
    def getRelativeSupport(self, nbObject):
        return float(self.getAbsoluteSupport()) / float(nbObject)
    def contains(self, item):
        for i in range(self.size()):
            gi = self.get(i)
            if gi == item: return True
            elif gi > item: return False
        return False
    def containsAll(self, itemset2):
        if self.size() < itemset2.size(): return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while not found and i < self.size():
                a = self.get(i)
                b = itemset2.get(j)
                if a == b: found = True
                elif a > b: return False
                i += 1
            if not found: return False
        return True
    def isEqualTo(self, itemset2):
        if self.size() != itemset2.size(): return False
        for i in range(itemset2.size()):
            if itemset2.get(i) != self.get(i): return False
        return True
    def isEqualToArray(self, arr):
        if self.size() != len(arr): return False
        for i in range(len(arr)):
            if arr[i] != self.get(i): return False
        return True
    def allTheSameExceptLastItemV2(self, itemset2):
        if itemset2.size() != self.size(): return False
        for i in range(self.size() - 1):
            if self.get(i) != itemset2.get(i): return False
        return True
    def allTheSameExceptLastItem(self, itemset2):
        if itemset2.size() != self.size(): return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if self.get(i) >= itemset2.get(i): return None
            else:
                if self.get(i) != itemset2.get(i): return None
        return itemset2.get(itemset2.size() - 1)

class Itemset(AbstractOrderedItemset):
    def __init__(self, items=None, support=0):
        if items is None: items = []
        self.itemset = list(items)
        self.support = int(support)
    def getItems(self): return self.itemset
    def size(self): return len(self.itemset)
    def get(self, position): return self.itemset[position]
    def getAbsoluteSupport(self): return self.support
    def setAbsoluteSupport(self, support): self.support = int(support)
    def __hash__(self): return hash(tuple(self.itemset))

class Itemsets:
    def __init__(self, name):
        self.levels = [[]]
        self.itemsetsCount = 0
        self.name = name
    def printItemsets(self, nbObject):
        print(" ------- " + self.name + " -------")
        patternCount = 0
        for levelCount, level in enumerate(self.levels):
            print("  L" + str(levelCount) + " ")
            for itemset in level:
                print("  pattern " + str(patternCount) + ":  ", end="")
                itemset.print()
                print("support :  " + str(itemset.getAbsoluteSupport()))
                patternCount += 1
        print(" --------------------------------")
    def addItemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1
    def getLevels(self): return self.levels
    def getItemsetsCount(self): return self.itemsetsCount
    def setName(self, newName): self.name = newName
    def decreaseItemsetCount(self): self.itemsetsCount -= 1

class ArraysAlgos:
    @staticmethod
    def intersectTwoSortedArrays(array1, array2):
        i, j = 0, 0
        out = []
        while i < len(array1) and j < len(array2):
            a, b = array1[i], array2[j]
            if a < b: i += 1
            elif b < a: j += 1
            else:
                out.append(a)
                i += 1
                j += 1
        return out

class FPNode:
    def __init__(self):
        self.itemID = -1
        self.counter = 1
        self.parent = None
        self.childs = []
        self.nodeLink = None
    def getChildWithID(self, id_):
        for c in self.childs:
            if c.itemID == id_: return c
        return None
    def toString(self, indent):
        s = []
        s.append(str(self.itemID))
        s.append(" (count=" + str(self.counter) + ")\n")
        newIndent = indent + "   "
        for ch in self.childs:
            s.append(newIndent + ch.toString(newIndent))
        return "".join(s)
    def __str__(self): return str(self.itemID)

class FPTree:
    def __init__(self):
        self.headerList = None
        self.mapItemNodes = {}
        self.mapItemLastNode = {}
        self.root = FPNode()
    def addTransaction(self, transaction):
        currentNode = self.root
        for item in transaction:
            child = currentNode.getChildWithID(item)
            if child is None:
                newNode = FPNode()
                newNode.itemID = item
                newNode.parent = currentNode
                currentNode.childs.append(newNode)
                currentNode = newNode
                self._fixNodeLinks(item, newNode)
            else:
                child.counter += 1
                currentNode = child
    def _fixNodeLinks(self, item, newNode):
        lastNode = self.mapItemLastNode.get(item)
        if lastNode is not None:
            lastNode.nodeLink = newNode
        self.mapItemLastNode[item] = newNode
        if self.mapItemNodes.get(item) is None:
            self.mapItemNodes[item] = newNode
    def addPrefixPath(self, prefixPath, mapSupportBeta, relativeMinsupp):
        pathCount = prefixPath[0].counter
        currentNode = self.root
        for i in range(len(prefixPath) - 1, 0, -1):
            pathItem = prefixPath[i]
            if mapSupportBeta.get(pathItem.itemID, 0) >= relativeMinsupp:
                child = currentNode.getChildWithID(pathItem.itemID)
                if child is None:
                    newNode = FPNode()
                    newNode.itemID = pathItem.itemID
                    newNode.parent = currentNode
                    newNode.counter = pathCount
                    currentNode.childs.append(newNode)
                    currentNode = newNode
                    self._fixNodeLinks(pathItem.itemID, newNode)
                else:
                    child.counter += pathCount
                    currentNode = child
    def createHeaderList(self, mapSupport):
        self.headerList = list(self.mapItemNodes.keys())
        self.headerList.sort(key=lambda id_: (-mapSupport[id_], id_))
    def __str__(self):
        temp = "F"
        temp += " HeaderList: " + str(self.headerList) + "\n"
        temp += self.root.toString("")
        return temp

class AlgoFPGrowth:
    def __init__(self):
        self.startTimestamp = 0
        self.endTime = 0
        self.transactionCount = 0
        self.itemsetCount = 0
        self.minSupportRelative = 0
        self.writer = None
        self.patterns = None
        self.BUFFERS_SIZE = 2000
        self.itemsetBuffer = None
        self.fpNodeTempBuffer = None
        self.itemsetOutputBuffer = None
        self.maxPatternLength = 1000
        self.minPatternLength = 0
    def runAlgorithm(self, input_path, output_path, minsupp):
        self.startTimestamp = int(time.time() * 1000)
        self.itemsetCount = 0
        MemoryLogger.getInstance().reset()
        MemoryLogger.getInstance().checkMemory()
        if output_path is None:
            self.writer = None
            self.patterns = Itemsets("FREQUENT ITEMSETS")
        else:
            self.patterns = None
            self.writer = open(output_path, "w", encoding="utf-8")
            self.itemsetOutputBuffer = [0] * self.BUFFERS_SIZE
        mapSupport = self._scanDatabaseToDetermineFrequencyOfSingleItems(input_path)
        self.minSupportRelative = int(math.ceil(minsupp * self.transactionCount))

        # helpful debug:
        print(f"[DEBUG] transactions={self.transactionCount}, minsupRelative={self.minSupportRelative}")

        self._buildInitialTreeAndMine(input_path, mapSupport)
        if self.writer is not None:
            self.writer.close()
        self.endTime = int(time.time() * 1000)
        MemoryLogger.getInstance().checkMemory()
        return self.patterns
    def _buildInitialTreeAndMine(self, input_path, mapSupport):
        tree = FPTree()
        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line or (line[0] in "#%@"):
                    continue
                tokens = line.split()
                transaction = []
                for tok in tokens:
                    it = int(tok)
                    if mapSupport.get(it, 0) >= self.minSupportRelative:
                        transaction.append(it)
                transaction.sort(key=lambda it: (-mapSupport[it], it))
                tree.addTransaction(transaction)
        tree.createHeaderList(mapSupport)
        if tree.headerList and len(tree.headerList) > 0:
            self.itemsetBuffer = [0] * self.BUFFERS_SIZE
            self.fpNodeTempBuffer = [None] * self.BUFFERS_SIZE
            self._fpgrowth(tree, self.itemsetBuffer, 0, self.transactionCount, mapSupport)
    def _fpgrowth(self, tree, prefix, prefixLength, prefixSupport, mapSupport):
        if prefixLength == self.maxPatternLength: return
        singlePath = True
        position = 0
        if len(tree.root.childs) > 1:
            singlePath = False
        else:
            if len(tree.root.childs) == 1:
                currentNode = tree.root.childs[0]
                while True:
                    if len(currentNode.childs) > 1:
                        singlePath = False
                        break
                    self.fpNodeTempBuffer[position] = currentNode
                    position += 1
                    if len(currentNode.childs) == 0:
                        break
                    currentNode = currentNode.childs[0]
        if singlePath:
            self._saveAllCombinationsOfPrefixPath(self.fpNodeTempBuffer, position, prefix, prefixLength)
        else:
            for i in range(len(tree.headerList) - 1, -1, -1):
                item = tree.headerList[i]
                support = mapSupport[item]
                prefix[prefixLength] = item
                betaSupport = prefixSupport if prefixSupport < support else support
                self._saveItemset(prefix, prefixLength + 1, betaSupport)
                if prefixLength + 1 < self.maxPatternLength:
                    prefixPaths = []
                    path = tree.mapItemNodes.get(item)
                    mapSupportBeta = {}
                    while path is not None:
                        if path.parent.itemID != -1:
                            prefixPath = []
                            prefixPath.append(path)
                            pathCount = path.counter
                            parent = path.parent
                            while parent.itemID != -1:
                                prefixPath.append(parent)
                                if parent.itemID not in mapSupportBeta:
                                    mapSupportBeta[parent.itemID] = pathCount
                                else:
                                    mapSupportBeta[parent.itemID] += pathCount
                                parent = parent.parent
                            prefixPaths.append(prefixPath)
                        path = path.nodeLink
                    treeBeta = FPTree()
                    for prefixPath in prefixPaths:
                        treeBeta.addPrefixPath(prefixPath, mapSupportBeta, self.minSupportRelative)
                    if len(treeBeta.root.childs) > 0:
                        treeBeta.createHeaderList(mapSupportBeta)
                        self._fpgrowth(treeBeta, prefix, prefixLength + 1, betaSupport, mapSupportBeta)
    def _saveAllCombinationsOfPrefixPath(self, fpNodeTempBuffer, position, prefix, prefixLength):
        support = 0
        maxv = 1 << position
        i = 1
        while i < maxv:
            newPrefixLength = prefixLength
            j = 0
            while j < position:
                isSet = i & (1 << j)
                if isSet > 0:
                    if newPrefixLength == self.maxPatternLength:
                        newPrefixLength = None
                        break
                    prefix[newPrefixLength] = fpNodeTempBuffer[j].itemID
                    newPrefixLength += 1
                    support = fpNodeTempBuffer[j].counter
                j += 1
            if newPrefixLength is not None:
                self._saveItemset(prefix, newPrefixLength, support)
            i += 1
    def _scanDatabaseToDetermineFrequencyOfSingleItems(self, input_path):
        mapSupport = {}
        self.transactionCount = 0
        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line or (line[0] in "#%@"):
                    continue
                for tok in line.split():
                    it = int(tok)
                    mapSupport[it] = mapSupport.get(it, 0) + 1
                self.transactionCount += 1
        return mapSupport
    def _saveItemset(self, itemset, itemsetLength, support):
        if itemsetLength < self.minPatternLength: return
        self.itemsetCount += 1
        if self.writer is not None:
            buf = list(itemset[:itemsetLength])
            buf[:itemsetLength] = sorted(buf[:itemsetLength])
            s = " ".join(str(x) for x in buf[:itemsetLength]) + f" #SUP: {support}"
            self.writer.write(s + "\n")
        else:
            arr = list(itemset[:itemsetLength])
            arr.sort()
            obj = Itemset(arr)
            obj.setAbsoluteSupport(support)
            self.patterns.addItemset(obj, itemsetLength)
    def printStats(self):
        print("=============  FP-GROWTH 2.42 - STATS =============")
        temps = self.endTime - self.startTimestamp
        print(" Transactions count from database : " + str(self.transactionCount))
        print(" Max memory usage: " + str(MemoryLogger.getInstance().getMaxMemory()) + " mb ")
        print(" Frequent itemsets count : " + str(self.itemsetCount))
        print(" Total time ~ " + str(temps) + " ms")
        print("===================================================")
    def getDatabaseSize(self): return self.transactionCount
    def setMaximumPatternLength(self, length): self.maxPatternLength = int(length)
    def setMinimumPatternLength(self, length): self.minPatternLength = int(length)

if __name__ == "__main__":
    input_path = "contextPasquier99.txt"   # make sure this path exists relative to where you run the script
    output_path = "fp_growth_output.txt"
    minsup = 0.4  # try 0.2 if you still get no patterns

    algo = AlgoFPGrowth()
    algo.runAlgorithm(input_path, output_path, minsup)
    algo.printStats()
    print("\n✅ Output saved to:", output_path)
