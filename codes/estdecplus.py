# estdecplus.py

import math
import time
import os


# ============================================================
# MemoryLogger
# ============================================================

class MemoryLogger:
    """Equivalent to MemoryLogger.java"""

    _instance = None

    def __init__(self):
        self._max_memory = 0.0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self):
        self._max_memory = 0.0

    def check_memory(self) -> float:
        # Stubbed in Python – Java version reads heap memory.
        return 0.0

    def get_max_memory(self) -> float:
        return self._max_memory


# ============================================================
# CP-Tree node support classes
# ============================================================

class ParentNode:
    """Helper parent-link structure. Equivalent to Java ParentNode inside CPTreeNode."""

    def __init__(self, p_node: "CPTreeNode", p_ind: int):
        self.pNode = p_node
        self.pInd = p_ind


class CPTreeNode:
    """Equivalent to CPTreeNode.java"""

    def __init__(self, item: int = None, parent: "CPTreeNode" = None,
                 parent_ind: int = 0, count: float = 1.0):
        if item is None:
            # root / null constructor
            self.itemIDList: list[int] = []
            self.parents: list[ParentNode] = []
            self.counter1: float = 1.0
            self.counter2: float = 1.0
            self.children: list["CPTreeNode"] = []
        else:
            self.itemIDList = [item]
            self.parents = [ParentNode(parent, parent_ind)]
            self.counter1 = count
            self.counter2 = count
            self.children = []

    # ---- Java-style methods ----

    def getInnerIndexWithID(self, id_: int, parentNode: "CPTreeNode", parentInd: int) -> int:
        for i in range(parentInd + 1, len(self.itemIDList)):
            if (self.itemIDList[i] == id_ and
                    self.parents[i].pNode is parentNode and
                    self.parents[i].pInd == parentInd):
                return i
        return -1

    def getChildWithID(self, id_: int, q: int) -> "CPTreeNode | None":
        if not self.children:
            return None
        for child in self.children:
            if child.itemIDList[0] == id_ and child.parents[0].pInd == q:
                return child
        return None

    def getLevel(self, j: int) -> int:
        level = 0
        while True:
            level += 1
            if j != 0:
                j = self.parents[j].pInd
            else:
                return level

    def getLongestLevel(self) -> int:
        level = 1
        p = [0]
        while True:
            if not p:
                break
            level += 1
            p2: list[int] = []
            for j in range(1, len(self.itemIDList)):
                if self.parents[j].pInd in p:
                    p2.append(j)
            p = p2
        return level - 1

    def isLeafLevel(self, idx: int) -> bool:
        for i in range(idx + 1, len(self.itemIDList)):
            if self.parents[i].pNode is self and self.parents[i].pInd == idx:
                return False
        return True

    def update(self, d: float):
        self.counter1 = self.counter1 * d + 1.0

    def computeSupport(self, N: float, level: int) -> float:
        maxL = self.getLongestLevel()
        return self.estimateMergeCount(level, maxL) / N

    def estimateMergeCount(self, level: int, longestL: int) -> float:
        if level == 1:
            return self.counter1
        elif level == longestL:
            return self.counter2
        else:
            x = 0.0
            for l in range(1, longestL):
                x += 1.0 / l
            s = 0.0
            for l in range(1, level):
                s += 1.0 / l
            return self.counter1 - ((self.counter1 - self.counter2) * s / x)


# ============================================================
# CP-Tree
# ============================================================

class CPTree:
    """Equivalent to CPTree.java"""

    def __init__(self, decay: float, mins: float,
                 minSigValue: float, deltaValue: float, minMergeValue: float):
        self.N: float = 0.0
        self.d: float = decay
        self.delta: float = deltaValue
        self.patternCount: int = 0
        self.patterns: dict[tuple[int, ...], float] | None = None
        self.writer = None

        self.minsup: float = mins
        self.minsig: float = minSigValue
        self.minmerg: float = minMergeValue

        self.root: CPTreeNode = CPTreeNode()
        self.itemsetBuffer: list[int] = [0] * 500

    # ---------- Parameter handling ----------

    def setDecayRate(self, b: float, h: float):
        self.d = math.pow(b, -1.0 / h)

    def updateParams(self):
        self.N += 1.0

    # ---------- Phase 3: insertion ----------

    def insertItemset(self, transaction: list[int]):
        transaction2: list[int] = []

        for item in transaction:
            child = self.root.getChildWithID(item, -1)
            if child is None:
                self.root.children.append(CPTreeNode(item, self.root, -1, 1.0))
            elif child.counter1 / self.N >= self.minsig:
                transaction2.append(item)

        for ind, item in enumerate(transaction2):
            child = self.root.getChildWithID(item, -1)
            if child is not None:
                self.itemsetBuffer[0] = item
                self._insert_n_itemsets(child, 0, transaction2, ind + 1, 1)

    def _getCountOfItemset(self, itemset: list[int], length: int) -> float:
        if length == 0:
            return 0.0

        currentNode = self.root.getChildWithID(itemset[0], -1)
        if currentNode is None:
            return 0.0

        ind = 1
        parentInd = 0
        parentNode = currentNode
        l = 1

        while True:
            if ind >= length:
                break
            oldPInd = parentInd
            parentInd = currentNode.getInnerIndexWithID(
                itemset[ind], parentNode, parentInd
            )
            if parentInd != -1:
                ind += 1
                l += 1
                continue
            else:
                currentNode = currentNode.getChildWithID(itemset[ind], oldPInd)
                if currentNode is not None:
                    parentNode = currentNode
                    parentInd = 0
                    l = 1
                    ind += 1
                else:
                    return 0.0
        return currentNode.estimateMergeCount(l, currentNode.getLongestLevel())

    def _estimateCount(self, length: int) -> float:
        min_val = float("inf")
        for i in range(length):
            # skip position i
            itemset2 = self.itemsetBuffer[:i] + self.itemsetBuffer[i + 1:length]
            c = self._getCountOfItemset(itemset2, length - 1)
            if c == 0.0:
                return 0.0
            if c < min_val:
                min_val = c
        return min_val

    def _insert_n_itemsets(self, currentNode: CPTreeNode, PI: int,
                           transaction: list[int], ind: int, length: int):
        if ind >= len(transaction):
            return

        item = transaction[ind]
        self.itemsetBuffer[length] = item

        PI2 = currentNode.getInnerIndexWithID(item, currentNode, PI)

        if PI2 != -1:
            self._insert_n_itemsets(currentNode, PI2, transaction, ind + 1, length + 1)
        else:
            child = currentNode.getChildWithID(item, PI)
            if child is not None:
                self._insert_n_itemsets(child, 0, transaction, ind + 1, length + 1)
            else:
                if currentNode.counter1 / self.N >= self.minsig:
                    c = self._estimateCount(length + 1)
                    if c / self.N >= self.minsig:
                        child = CPTreeNode(item, currentNode, PI, c)
                        currentNode.children.append(child)
                        if ((currentNode.counter1 - child.counter2) / self.N) < self.delta \
                                and (child.counter2 / self.N) > self.minmerg:
                            self.merge(currentNode, child)

        self._insert_n_itemsets(currentNode, PI, transaction, ind + 1, length)

    # ---------- Tree maintenance ----------

    def forcePruning(self, currentNode: CPTreeNode):
        i = 0
        while i < len(currentNode.children):
            node = currentNode.children[i]
            if node.counter1 / self.N < self.minsig and currentNode.itemIDList is not None:
                currentNode.children.pop(i)
                i -= 1
            else:
                self.forcePruning(node)
            i += 1

    def merge(self, mp: CPTreeNode, m: CPTreeNode):
        l = len(mp.itemIDList)
        mp.itemIDList.extend(m.itemIDList)
        mp.parents.append(m.parents[0])

        for j in range(1, len(m.parents)):
            mp.parents.append(ParentNode(mp, l + m.parents[j].pInd))

        for mc in m.children:
            p = mc.parents[0]
            p.pNode = mp
            p.pInd = l + p.pInd
            mc.parents[0] = p
            mp.children.append(mc)

        if mp.counter2 > m.counter2:
            mp.counter2 = m.counter2

        mp.children.remove(m)

    def split(self, m: CPTreeNode):
        longestLevel = m.getLongestLevel()
        for j in range(1, len(m.itemIDList)):
            if m.isLeafLevel(j):
                m2 = CPTreeNode()
                m2.itemIDList.append(m.itemIDList[j])
                m2.parents.append(m.parents[j])
                m.itemIDList[j] = None
                m2.counter1 = m.estimateMergeCount(m.getLevel(j), longestLevel)
                m2.counter2 = m2.counter1

                k = len(m.children) - 1
                while k >= 0:
                    mc = m.children[k]
                    if mc.parents[0].pInd == j:
                        mc.parents[0] = ParentNode(m2, 0)
                        m.children.pop(k)
                        m2.children.append(mc)
                    k -= 1
                m.children.append(m2)

        k = len(m.itemIDList) - 1
        while k >= 0:
            if m.itemIDList[k] is None:
                m.itemIDList.pop(k)
                m.parents.pop(k)

                for y in range(1, len(m.parents)):
                    x = m.parents[y]
                    if x.pInd > k:
                        x.pInd -= 1
                        m.parents[y] = x

                for mx in m.children:
                    x = mx.parents[0]
                    if x.pInd > k:
                        x.pInd -= 1
                        mx.parents[0] = x
            k -= 1

        newLongest = m.getLongestLevel()
        m.counter2 = m.estimateMergeCount(newLongest, longestLevel)

    # ---------- Traversal & decay ----------

    def traverse(self, m: CPTreeNode, mp: CPTreeNode, q: int, transaction: list[int]):
        if q != -1 and m.parents[0].pInd != q and m.parents[0].pNode is not mp:
            return

        if m.itemIDList[0] not in transaction:
            return

        m.update(self.d)

        if m.counter1 / self.N < self.minsig:
            mp.children.remove(m)
            return
        else:
            leafCommonItemInds: list[int] = []
            levelParents: list[int] = []
            i = 1
            if m.isLeafLevel(0):
                leafCommonItemInds.append(0)
            else:
                levelParents.append(0)
                while True:
                    levelParents = self.FindLevelCommonItems(
                        m, levelParents, leafCommonItemInds, transaction
                    )
                    if len(levelParents) != 0:
                        i += 1
                    else:
                        break

            if i == m.getLongestLevel():
                m.counter2 = m.counter2 * self.d + 1.0

            if (mp.counter1 - m.counter2) / self.N < self.delta and m.counter2 / self.N >= self.minmerg:
                if mp is not self.root:
                    self.merge(mp, m)
            elif (m.counter1 - m.counter2) / self.N > self.delta and \
                    m.counter2 / self.N >= self.minmerg and len(m.itemIDList) > 1:
                self.split(m)

            for j in leafCommonItemInds:
                for mc in list(m.children):
                    self.traverse(mc, m, j, transaction)

    def FindLevelCommonItems(self, m: CPTreeNode, levelParents: list[int],
                             leafCommonItemInds: list[int], transaction: list[int]) -> list[int]:
        newParents: list[int] = []
        for k in range(levelParents[0] + 1, len(m.itemIDList)):
            if m.itemIDList[k] in transaction:
                pInd = m.parents[k].pInd
                if pInd in levelParents:
                    newParents.append(k)
                    if m.isLeafLevel(k):
                        leafCommonItemInds.append(k)
                else:
                    break
        return newParents

    # ---------- Pattern mining ----------

    def patternMining(self, currentNode: CPTreeNode, pattern: list[int]):
        if currentNode.itemIDList is not None and len(currentNode.itemIDList) > 0:
            itemsetList: list[list[int]] = []

            # first item
            first = currentNode.itemIDList[0]
            concatenation = pattern + [first]
            itemsetList.append(concatenation)

            s = currentNode.computeSupport(self.N, 1)
            if s >= self.minsup:
                self._save_itemset(concatenation, s)

            for i in range(1, len(currentNode.itemIDList)):
                PIn = currentNode.parents[i].pInd
                patternPIn = itemsetList[PIn]
                concatenation2 = patternPIn + [currentNode.itemIDList[i]]
                itemsetList.append(concatenation2)

                s = currentNode.computeSupport(self.N, currentNode.getLevel(i))
                if s >= self.minsup:
                    self._save_itemset(concatenation2, s)

            for node in currentNode.children:
                base_pattern = itemsetList[node.parents[0].pInd]
                self.patternMining(node, base_pattern)

    def _save_itemset(self, itemset: list[int], support: float):
        self.patternCount += 1
        if self.patterns is None:
            line = " ".join(str(x) for x in itemset) + " #SUP: " + repr(support)
            self.writer.write(line + "\n")
        else:
            self.patterns[tuple(itemset)] = support

    def patternMining_saveToMemory(self) -> dict[tuple[int, ...], float]:
        self.patterns = {}
        self.patternCount = 0
        for node in self.root.children:
            self.patternMining(node, [])
        return self.patterns

    def patternMining_saveToFile(self, outputPath: str):
        self.patterns = None
        self.patternCount = 0
        self.writer = open(outputPath, "w", encoding="utf-8")
        for node in self.root.children:
            self.patternMining(node, [])
        self.writer.close()

    # ---------- Misc ----------

    def nodeCount(self, currentNode: CPTreeNode) -> int:
        s = 1
        for child in currentNode.children:
            s += self.nodeCount(child)
        return s


# ============================================================
# Algo_estDecPlus
# ============================================================

class Algo_estDecPlus:
    """Equivalent to Algo_estDecPlus.java"""

    def __init__(self, mins: float, d: float,
                 minSigValue: float, deltaValue: float, minMergeValue: float):
        MemoryLogger.get_instance().reset()
        self.tree = CPTree(d, mins, minSigValue, deltaValue, minMergeValue)
        self.transactionCount: int = 0
        self.miningTime: float = 0.0
        self.sumTransactionInsertionTime: float = 0.0

    def setDecayRate(self, b: float, h: float):
        self.tree.setDecayRate(b, h)

    def processTransaction(self, transaction: list[int]):
        start = time.time() * 1000.0
        self.tree.updateParams()

        for child in list(self.tree.root.children):
            self.tree.traverse(child, self.tree.root, -1, transaction)

        self.tree.insertItemset(transaction)

        self.transactionCount += 1
        if self.transactionCount % 1000 == 0:
            self.tree.forcePruning(self.tree.root)
        self.tree.forcePruning(self.tree.root)

        end = time.time() * 1000.0
        self.sumTransactionInsertionTime += (end - start)

    def processTransactionFromFile(self, inputPath: str):
        with open(inputPath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                transaction = [int(x) for x in line.split()]
                self.processTransaction(transaction)

    def performMining_saveResultToFile(self, outputPath: str):
        start = time.time() * 1000.0
        self.tree.patternMining_saveToFile(outputPath)
        self.miningTime = time.time() * 1000.0 - start
        MemoryLogger.get_instance().check_memory()

    def performMining_saveResultToMemory(self) -> dict[tuple[int, ...], float]:
        MemoryLogger.get_instance().check_memory()
        start = time.time() * 1000.0
        patterns = self.tree.patternMining_saveToMemory()
        self.miningTime = time.time() * 1000.0 - start
        MemoryLogger.get_instance().check_memory()
        return patterns

    def printStats(self):
        print("===========  estDecPlus - STATS ===========")
        print(" Number of nodes :", self.tree.nodeCount(self.tree.root))
        print(" Frequent itemsets count :", self.tree.patternCount)
        print(" Maximum memory usage :", MemoryLogger.get_instance().get_max_memory(), "mb")
        print(" Number of transactions:", self.transactionCount)
        print(" Total insertion time ~", self.sumTransactionInsertionTime)
        if self.transactionCount > 0:
            print(" Insertion time per transaction ~",
                  self.sumTransactionInsertionTime / float(self.transactionCount), "ms")
        print(" Mining time ~", self.miningTime, "ms")
        print("============================================")


# ============================================================
# Main-style helpers
# ============================================================

def run_from_file(input_file: str, output_file: str):
    mins = 0.6
    minsig = 0.3 * mins
    minmerge = 0.1
    delta = 0.001
    d = 1.0

    algo = Algo_estDecPlus(mins, d, minsig, delta, minmerge)
    algo.processTransactionFromFile(input_file)
    algo.performMining_saveResultToFile(output_file)
    algo.printStats()
    result = algo.performMining_saveResultToMemory()
    algo.printStats()
    print("Itemsets found:")
    for items, sup in result.items():
        print(" ".join(map(str, items)), "#SUP:", sup)


# ============================================================
# CLI entry point – safe file paths
# ============================================================

if __name__ == "__main__":
    BASE = os.path.dirname(os.path.abspath(__file__))

    input_path = os.path.join(BASE, "contextPasquier99.txt")
    output_path = os.path.join(BASE, "estdecplus_outputs.txt")

    run_from_file(input_path, output_path)
