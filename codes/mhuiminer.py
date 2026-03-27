
import time
from collections import defaultdict
import bisect

# -------------------------
# MemoryLogger (lightweight)
# -------------------------
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0

    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self):
        self.max_memory = 0

    def checkMemory(self):
        return 0


# -------------------------
# UtilityTuple
# -------------------------
class UtilityTuple:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


# -------------------------
# UtilityList
# -------------------------
class UtilityList:
    def __init__(self, itemID=None):
        self.itemID = itemID
        self.sumIutils = 0
        self.sumRutils = 0
        self.uLists = []

    def addTuple(self, t):
        self.sumIutils += t.iutils
        self.sumRutils += t.rutils
        self.uLists.append(t)


# -------------------------
# Item
# -------------------------
class Item:
    def __init__(self, itemID, utility):
        self.itemID = itemID
        self.utility = utility


# -------------------------
# Node (IHUP Tree)
# -------------------------
class Node:
    def __init__(self):
        self.itemID = -1
        self.count = 1
        self.parent = None
        self.childs = []
        self.nodeLink = None

    def getChildWithID(self, itemID):
        for c in self.childs:
            if c.itemID == itemID:
                return c
        return None


# -------------------------
# IHUPTreeMod
# -------------------------
class IHUPTreeMod:
    def __init__(self):
        self.headerList = []
        self.hasMoreThanOnePath = False
        self.mapItemNodes = {}
        self.mapItemLastNode = {}
        self.root = Node()

    def insertNewNode(self, parent, itemID):
        node = Node()
        node.itemID = itemID
        node.parent = parent
        parent.childs.append(node)

        if not self.hasMoreThanOnePath and len(parent.childs) > 1:
            self.hasMoreThanOnePath = True

        if itemID not in self.mapItemNodes:
            self.mapItemNodes[itemID] = node
            self.mapItemLastNode[itemID] = node
        else:
            last = self.mapItemLastNode[itemID]
            last.nodeLink = node
            self.mapItemLastNode[itemID] = node

        return node

    def addTransaction(self, transaction, tid):
        current = self.root
        for item in reversed(transaction):
            child = current.getChildWithID(item.itemID)
            if child is None:
                current = self.insertNewNode(current, item.itemID)
            else:
                child.count += 1
                current = child

    def addLocalTransaction(self, path):
        current = self.root
        for itemID in reversed(path):
            child = current.getChildWithID(itemID)
            if child is None:
                current = self.insertNewNode(current, itemID)
            else:
                child.count += 1
                current = child

    def createHeaderList(self, mapItemToTWU):
        self.headerList = list(self.mapItemNodes.keys())
        self.headerList.sort(key=lambda x: (-mapItemToTWU[x], x))


# -------------------------
# AlgoMHUIMiner
# -------------------------
class AlgoMHUIMiner:

    def __init__(self):
        self.mapItemToTWU = {}
        self.mapItemToUtilityList = {}
        self.huiCount = 0
        self.joinCount = 0

    def runAlgorithm(self, input_file, output_file, minUtility):
        self.minUtility = minUtility
        start = time.time()
        MemoryLogger.getInstance().reset()

        # ---- First DB Scan (TWU)
        self.mapItemToTWU = defaultdict(int)
        totalUtility = 0

        with open(input_file) as f:
            for line in f:
                if not line.strip() or line[0] in "#%@":
                    continue
                items, tu, _ = line.split(":")
                tu = int(tu)
                totalUtility += tu
                for it in map(int, items.split()):
                    self.mapItemToTWU[it] += tu

        # ---- Init Utility Lists
        for item, twu in self.mapItemToTWU.items():
            if twu >= minUtility:
                self.mapItemToUtilityList[item] = UtilityList(item)

        tree = IHUPTreeMod()

        # ---- Second DB Scan
        tid = 0
        with open(input_file) as f:
            for line in f:
                if not line.strip() or line[0] in "#%@":
                    continue
                items, _, utils = line.split(":")
                items = list(map(int, items.split()))
                utils = list(map(int, utils.split()))

                revised = []
                for i in range(len(items)):
                    if self.mapItemToTWU[items[i]] >= minUtility:
                        revised.append(Item(items[i], utils[i]))

                tid += 1
                revised.sort(key=lambda x: (self.mapItemToTWU[x.itemID], x.itemID))

                ru = 0
                for it in reversed(revised):
                    self.mapItemToUtilityList[it.itemID].addTuple(
                        UtilityTuple(tid, it.utility, ru)
                    )
                    ru += it.utility

                tree.addTransaction(revised, tid)

        tree.createHeaderList(self.mapItemToTWU)

        with open(output_file, "w") as out:
            for item in reversed(tree.headerList):
                ul = self.mapItemToUtilityList[item]
                if ul.sumIutils >= minUtility:
                    out.write(f"{item} #UTIL: {ul.sumIutils}\n")
                    self.huiCount += 1

                if ul.sumIutils + ul.sumRutils >= minUtility:
                    localTree = self.createLocalTree(tree, item)
                    if localTree.headerList:
                        self.mHUIMiner(localTree, [item], ul.uLists, out)

        end = time.time()
        print(f"Finished in {(end-start)*1000:.2f} ms")
        print("HUIs:", self.huiCount)

    def createLocalTree(self, tree, itemID):
        prefixPaths = []
        node = tree.mapItemNodes[itemID]

        while node:
            path = []
            parent = node.parent
            while parent and parent.itemID != -1:
                path.append(parent.itemID)
                parent = parent.parent
            if path:
                prefixPaths.append(path)
            node = node.nodeLink

        localTree = IHUPTreeMod()
        for p in prefixPaths:
            localTree.addLocalTransaction(p)
        localTree.createHeaderList(self.mapItemToTWU)
        return localTree

    def construct(self, pUL, xUL):
        pxUL = UtilityList()
        x_dict = {t.tid: t for t in xUL}

        for ep in pUL:
            if ep.tid in x_dict:
                ex = x_dict[ep.tid]
                pxUL.addTuple(UtilityTuple(ep.tid, ep.iutils + ex.iutils, ex.rutils))
        return pxUL

    def mHUIMiner(self, tree, prefix, pTuples, out):
        for item in reversed(tree.headerList):
            prefix.append(item)
            px = self.construct(pTuples, self.mapItemToUtilityList[item].uLists)
            self.joinCount += 1

            if px.sumIutils >= self.minUtility:
                out.write(" ".join(map(str, sorted(prefix))) + f" #UTIL: {px.sumIutils}\n")
                self.huiCount += 1

            if px.sumIutils + px.sumRutils >= self.minUtility:
                localTree = self.createLocalTree(tree, item)
                if localTree.headerList:
                    self.mHUIMiner(localTree, prefix, px.uLists, out)

            prefix.pop()


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    INPUT = "DB_Utility.txt"

    OUTPUT = "output_MHUIMiner.txt"
    MIN_UTILITY = 30 # Adjust as needed

    miner = AlgoMHUIMiner()
    miner.runAlgorithm(INPUT, OUTPUT, MIN_UTILITY)
