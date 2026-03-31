# =============================================================================
# TKQ: Top-K Quantitative High Utility Itemset Mining
# Original authors: Mourad Nouioua et al., 2021
# =============================================================================

import math
import time
import heapq
from enum import Enum
from collections import defaultdict
import psutil
import os


# =============================================================================
# EnumCombination
# =============================================================================
class EnumCombination(Enum):
    COMBINEMIN = "COMBINEMIN"
    COMBINEMAX = "COMBINEMAX"
    COMBINEALL = "COMBINEALL"


# =============================================================================
# MemoryLogger (singleton)
# =============================================================================
class MemoryLogger:
    _instance = None

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def __init__(self):
        self._max_memory = 0.0

    def reset(self):
        self._max_memory = 0.0
    
    def checkMemory(self):
        process = psutil.Process(os.getpid())
        current_mb = process.memory_info().rss / 1024.0 / 1024.0

        if current_mb > self._max_memory:
            self._max_memory = current_mb

        return current_mb

    def getMaxMemory(self):
        return self._max_memory

# =============================================================================
# InfoTKQ
# =============================================================================
class InfoTKQ:
    def __init__(self):
        self.twu = 0
        self.utility = 0

    def __repr__(self):
        return f"(twu:{self.twu}, utility:{self.utility})"


# =============================================================================
# Qitem
# =============================================================================
class Qitem:
    def __init__(self, item=0, qte_min=0, qte_max=None):
        self.item = item
        self.qte_min = qte_min
        self.qte_max = qte_min if qte_max is None else qte_max

    def getItem(self):
        return self.item

    def getQteMin(self):
        return self.qte_min

    def getQteMax(self):
        return self.qte_max

    def setItem(self, i):
        self.item = i

    def setQteMin(self, q):
        self.qte_min = q

    def setQteMax(self, q):
        self.qte_max = q

    def copy(self, q):
        self.item = q.item
        self.qte_min = q.qte_min
        self.qte_max = q.qte_max

    def isRange(self):
        return self.qte_min != self.qte_max

    def __eq__(self, other):
        if not isinstance(other, Qitem):
            return False
        return self.item == other.item and self.qte_min == other.qte_min and self.qte_max == other.qte_max

    def __hash__(self):
        return hash((self.item, self.qte_min, self.qte_max))

    def __repr__(self):
        if not self.isRange():
            return f"({self.item},{self.qte_min})"
        else:
            return f"({self.item},{self.qte_min},{self.qte_max})"

    def __str__(self):
        return self.__repr__()


# =============================================================================
# QItemTrans
# =============================================================================
class QItemTrans:
    def __init__(self, tid, eu, ru):
        self.tid = tid
        self.eu = eu
        self.ru = ru

    def getTid(self):
        return self.tid

    def getEu(self):
        return self.eu

    def getRu(self):
        return self.ru

    def sum(self):
        return self.eu + self.ru

    def __repr__(self):
        return f"{self.tid} {self.eu}\t{self.ru}"


# =============================================================================
# Qitemset
# =============================================================================
class Qitemset:
    def __init__(self, *args):
        self.itemset = []
        self.utility = 0

        if len(args) == 0:
            pass
        elif len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], (int, float)):
            # (ArrayList<Qitem>, util)
            self.itemset = list(args[0])
            self.utility = args[1]
        elif len(args) == 2 and isinstance(args[0], Qitem) and isinstance(args[1], (int, float)):
            # (Qitem, util)
            self.itemset = [args[0]]
            self.utility = args[1]
        elif len(args) == 3 and isinstance(args[0], Qitem) and isinstance(args[1], Qitem):
            # (Qitem, Qitem, util)
            self.itemset = [args[0], args[1]]
            self.utility = args[2]
        elif len(args) == 4 and isinstance(args[0], (list, type(None))) and isinstance(args[1], int) and isinstance(args[2], Qitem) and isinstance(args[3], (int, float)):
            # (prefix[], length, Qitem x, util)
            prefix, length, x, util = args
            self.itemset = list(prefix[:length]) if prefix else []
            self.itemset.append(x)
            self.utility = util
        elif len(args) == 5 and isinstance(args[0], (list, type(None))) and isinstance(args[1], int) and isinstance(args[2], Qitem) and isinstance(args[3], Qitem):
            # (prefix[], length, Qitem x, Qitem y, util)
            prefix, length, x, y, util = args
            self.itemset = list(prefix[:length]) if prefix else []
            self.itemset.append(x)
            self.itemset.append(y)
            self.utility = util

    def __lt__(self, other):
        # For heapq (min-heap): lower utility = higher priority
        if self.utility != other.utility:
            return self.utility < other.utility
        return id(self) < id(other)

    def __repr__(self):
        return f"{self.itemset} #Util{self.utility}"

    def addQitem(self, q):
        self.itemset.append(q)

    def setUtility(self, utility):
        self.utility = utility


# =============================================================================
# UtilityListTKQ
# =============================================================================
class UtilityListTKQ:
    def __init__(self, item_or_list=None, twu=0):
        self.items = []
        self.sumIutils = 0
        self.sumRutils = 0
        self.sumIutilsNonZero = 0
        self.twu = twu
        self.qItemTrans = []
        self.rangeOrNot = False

        if item_or_list is None:
            pass
        elif isinstance(item_or_list, Qitem):
            self.items = [item_or_list]
        elif isinstance(item_or_list, list):
            self.items = list(item_or_list)

    def addTWU(self, twu):
        self.twu += twu

    def setTWUtoZero(self):
        self.twu = 0

    def getSupport(self):
        return len(self.qItemTrans)

    def addTrans(self, qTid, twu=None):
        if qTid.getRu() != 0:
            self.sumIutilsNonZero += qTid.getEu()
        self.sumIutils += qTid.getEu()
        self.sumRutils += qTid.getRu()
        self.qItemTrans.append(qTid)
        if twu is not None:
            self.twu += twu

    def getSumIutils(self):
        return self.sumIutils

    def getSumRutils(self):
        return self.sumRutils

    def setSumIutils(self, s):
        self.sumIutils = s

    def setSumRutils(self, s):
        self.sumRutils = s

    def setRangeAsTrue(self):
        self.rangeOrNot = True

    def getTwu(self):
        return self.twu

    def isRange(self):
        return self.rangeOrNot

    def setTwu(self, twu):
        self.twu = twu

    def getItemsetName(self):
        return self.items

    def getSingleItemsetName(self):
        return self.items[0]

    def getQItemTrans(self):
        return self.qItemTrans

    def setQItemTrans(self, elements):
        self.qItemTrans = elements

    def QitemTransAdd(self, a, b):
        return QItemTrans(a.getTid(), a.getEu() + b.getEu(), a.getRu() + b.getRu())

    def getqItemTransLength(self):
        return len(self.qItemTrans) if self.qItemTrans else 0

    def __repr__(self):
        s = "\n=================================\n"
        s += str(self.items) + "\n"
        s += f"sumEU={self.sumIutils} sumRU={self.sumRutils} twu={self.twu}\n"
        for t in self.qItemTrans:
            s += str(t) + "\n"
        s += "=================================\n"
        return s


# =============================================================================
# AlgoTKQ
# =============================================================================
class AlgoTKQ:
    BUFFERS_SIZE = 200
    DEBUG_MODE = True

    def __init__(self):
        self.outputFile = None
        self.inputDatabase = None
        self.mapItemToTwu = {}        # Qitem -> int
        self.mapItemToProfit = {}     # int -> int
        self.mapTransactionToUtility = {}  # int -> int
        self.mapFMAP = {}             # Qitem -> {Qitem -> InfoTKQ}
        self.realUtility = {}         # Qitem -> long
        self.CUD = {}                 # str -> long
        self.minUtil = 0
        self.coefficient = 1
        self.combiningMethod = None
        self.kPatterns = []           # min-heap of Qitemset
        self.k = 0
        self.maxMemory = 0
        self.startTime = 0
        self.endTime = 0
        self.HUQIcount = 0
        self.countConstruct = 0
        self.currentQitem = None
        self.itemsetBuffer = None
        self.inserted2Itemsets = set()  # BUG FIX 2026

    def runAlgorithm(self, topk, inputData, inputProfit, coef, combinationmethod, output):
        import gc
        gc.collect()

        MemoryLogger.getInstance().reset()
        self.startTime = time.time()

        self.k = topk
        self.coefficient = coef
        self.combiningMethod = combinationmethod
        self.outputFile = output
        self.itemsetBuffer = [None] * self.BUFFERS_SIZE
        self.mapItemToProfit = {}
        self.mapTransactionToUtility = {}

        qitemNameList = []
        mapItemToUtilityList = {}

        if self.DEBUG_MODE:
            print("1. Build Initial Q-Utility Lists")
        self._buildInitialQUtilityLists(inputData, inputProfit, qitemNameList, mapItemToUtilityList)
        MemoryLogger.getInstance().checkMemory()

        if self.DEBUG_MODE:
            print("2. Find Initial High Utility Range Q-items")
        candidateList = []
        hwQUI = []
        self._findInitialRHUQIs(qitemNameList, mapItemToUtilityList, candidateList, hwQUI)
        MemoryLogger.getInstance().checkMemory()

        if self.DEBUG_MODE:
            print("3. Recursive Mining Procedure")
        self._miner(self.itemsetBuffer, 0, None, mapItemToUtilityList, qitemNameList, hwQUI)
        MemoryLogger.getInstance().checkMemory()

        self.endTime = time.time()
        if self.DEBUG_MODE:
            print(f"4. Finished mining. The final internal minUtil value is: {self.minUtil}")

        self._writeResultTofile(output)

    # ------------------------------------------------------------------
    # insert helpers
    # ------------------------------------------------------------------
    def _insert_single(self, item, utility):
        """Insert a single Qitem."""
        temp = Qitemset(item, utility)
        print("ADDHERE2" + str(temp))
        heapq.heappush(self.kPatterns, temp)
        if len(self.kPatterns) > self.k:
            if utility >= self.minUtil:
                while len(self.kPatterns) > self.k:
                    heapq.heappop(self.kPatterns)
            self.minUtil = self.kPatterns[0].utility

    def _insert_prefix_item(self, prefix, length, item, utility):
        """Insert prefix + one Qitem."""
        temp = Qitemset(prefix, length, item, utility)
        heapq.heappush(self.kPatterns, temp)
        if len(self.kPatterns) > self.k:
            if utility >= self.minUtil:
                while len(self.kPatterns) > self.k:
                    heapq.heappop(self.kPatterns)
            self.minUtil = self.kPatterns[0].utility

    def _insert_prefix_two_items(self, prefix, length, item1, item2, utility):
        """Insert prefix + two Qitems (with BUG FIX 2026 dedup for 2-itemsets)."""
        if length == 0:
            key = str(item1) + "_" + str(item2)
            if key in self.inserted2Itemsets:
                return
            self.inserted2Itemsets.add(key)

        temp = Qitemset(prefix, length, item1, item2, utility)
        heapq.heappush(self.kPatterns, temp)
        if len(self.kPatterns) > self.k:
            if utility >= self.minUtil:
                while len(self.kPatterns) > self.k:
                    heapq.heappop(self.kPatterns)
            self.minUtil = self.kPatterns[0].utility

    def _insertCUD(self, item1, item2, utility):
        """Insert a 2-itemset from CUD (BUG FIX 2026: record to avoid duplicates)."""
        key = str(item1) + "_" + str(item2)
        self.inserted2Itemsets.add(key)

        temp = Qitemset(item1, item2, utility)
        heapq.heappush(self.kPatterns, temp)
        if len(self.kPatterns) > self.k:
            if utility >= self.minUtil:
                while len(self.kPatterns) > self.k:
                    heapq.heappop(self.kPatterns)
            self.minUtil = self.kPatterns[0].utility

    def _insertIn(self, ktopls, value):
        """Insert value into a min-heap of size k."""
        if len(ktopls) < self.k:
            heapq.heappush(ktopls, value)
        elif value > ktopls[0]:
            heapq.heappush(ktopls, value)
            while len(ktopls) > self.k:
                heapq.heappop(ktopls)

    # ------------------------------------------------------------------
    # Write results
    # ------------------------------------------------------------------
    def _writeResultTofile(self, output):
        with open(output, 'w') as f:
            for pattern in self.kPatterns:
                buf = ""
                for qi in pattern.itemset:
                    buf += str(qi) + " "
                buf += "#UTIL: " + str(pattern.utility)
                f.write(buf + "\n")

    # ------------------------------------------------------------------
    # Build initial utility lists
    # ------------------------------------------------------------------
    def _buildInitialQUtilityLists(self, inputData, inputProfit, qitemNameList, mapItemToUtilityList):
        # 1. Build mapItemToProfit
        with open(inputProfit, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(", ")
                if len(parts) >= 2:
                    profit = int(parts[1])
                    if profit == 0:
                        profit = 1
                    item = int(parts[0])
                    self.mapItemToProfit[item] = profit

        # 2. Build mapItemToTwu
        self.mapItemToTwu = {}
        tid = 0
        self.currentQitem = Qitem(0, 0)

        with open(inputData, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            tid += 1
            itemInfo = line.split(" ")
            transactionU = 0
            for token in itemInfo:
                comma = token.index(',')
                item_id = int(token[:comma])
                qty = int(token[comma+1:])
                transactionU += qty * self.mapItemToProfit[item_id]

            for token in itemInfo:
                comma = token.index(',')
                item_id = int(token[:comma])
                qty = int(token[comma+1:])
                Q = Qitem(item_id, qty, qty)
                if Q not in self.mapItemToTwu:
                    self.mapItemToTwu[Q] = transactionU
                else:
                    self.mapItemToTwu[Q] += transactionU
                utility = Q.getQteMin() * self.mapItemToProfit[Q.getItem()]
                real = self.realUtility.get(Q, 0)
                self.realUtility[Q] = real + utility

        # 3. Apply RIU raising
        if self.DEBUG_MODE:
            print("===============================================")
            print(f" minutil is {self.minUtil}")
        self._raisingThresholdRIU(self.realUtility, self.k)
        if self.DEBUG_MODE:
            print(f"after RIU minUtil is {self.minUtil}")

        # 4. Build mapItemToUtilityList
        for item, twu_val in self.mapItemToTwu.items():
            if twu_val >= math.floor(self.minUtil / self.coefficient):
                ul = UtilityListTKQ(item, 0)
                mapItemToUtilityList[item] = ul
                qitemNameList.append(item)

        MemoryLogger.getInstance().checkMemory()

        # 5. Build MapFMAP
        self.mapFMAP = {}
        ktopls = []
        tid = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue
            tid += 1
            itemInfo = line.split(" ")
            remainingUtility = 0
            newTWU = 0
            revisedTransaction = []

            for token in itemInfo:
                comma = token.index(',')
                item_id = int(token[:comma])
                qty = int(token[comma+1:])
                Q = Qitem(item_id, qty, qty)
                if Q in mapItemToUtilityList:
                    revisedTransaction.append(Q)
                    remainingUtility += Q.getQteMin() * self.mapItemToProfit[Q.getItem()]
                    newTWU += Q.getQteMin() * self.mapItemToProfit[Q.getItem()]
                self.mapTransactionToUtility[tid] = newTWU

            revisedTransaction.sort(key=lambda q: self._compareQItems_key(q))
            self._insertIn(ktopls, remainingUtility)

            for i, current_q in enumerate(revisedTransaction):
                remainingUtility -= current_q.getQteMin() * self.mapItemToProfit[current_q.getItem()]
                utilityListOfItem = mapItemToUtilityList[current_q]
                element = QItemTrans(
                    tid,
                    current_q.getQteMin() * self.mapItemToProfit[current_q.getItem()],
                    remainingUtility
                )
                utilityListOfItem.addTrans(element)
                utilityListOfItem.addTWU(self.mapTransactionToUtility[tid])

                if current_q not in self.mapFMAP:
                    self.mapFMAP[current_q] = {}
                mapFMAPItem = self.mapFMAP[current_q]

                for j in range(i + 1, len(revisedTransaction)):
                    qAfter = revisedTransaction[j]
                    infoItem = mapFMAPItem.get(qAfter)
                    if infoItem is None:
                        infoItem = InfoTKQ()
                    infoItem.twu += newTWU
                    infoItem.utility += (
                        current_q.getQteMin() * self.mapItemToProfit[current_q.getItem()]
                        + qAfter.getQteMin() * self.mapItemToProfit[qAfter.getItem()]
                    )
                    mapFMAPItem[qAfter] = infoItem

        MemoryLogger.getInstance().checkMemory()

        # 6. Apply CUD raising
        if self.DEBUG_MODE:
            print("===================================================")
            print(f" before CUD kpatterns is ... minutil is {self.minUtil}")
        self._raisingThresholdCUDOptimize2()
        if self.DEBUG_MODE:
            print(f"after CUD minUtil is {self.minUtil}")

        # 7. Sort qitemNameList
        qitemNameList.sort(key=lambda q: self._compareQItems_key(q))
        MemoryLogger.getInstance().checkMemory()

    # ------------------------------------------------------------------
    # CUD raising
    # ------------------------------------------------------------------
    def _raisingThresholdCUDOptimize2(self):
        for q1, inner in self.mapFMAP.items():
            for q2, info in inner.items():
                value = info.utility
                if value >= self.minUtil:
                    self.CUD[str(q1) + "_" + str(q2)] = info.utility
                    self._insertCUD(q1, q2, info.utility)

    # ------------------------------------------------------------------
    # RIU raising
    # ------------------------------------------------------------------
    def _raisingThresholdRIU(self, map_data, k):
        sorted_list = sorted(map_data.items(), key=lambda kv: kv[1], reverse=True)
        if len(sorted_list) >= k and k > 0:
            self.minUtil = sorted_list[k - 1][1]
        for qitem, utility in sorted_list:
            self._insert_single(qitem, utility)

    # ------------------------------------------------------------------
    # Find initial RHUQIs
    # ------------------------------------------------------------------
    def _findInitialRHUQIs(self, qitemNameList, mapItemToUtilityList, candidateList, hwQUI):
        for qi in qitemNameList:
            utility = mapItemToUtilityList[qi].getSumIutils()
            if utility >= self.minUtil:
                hwQUI.append(qi)
                self.HUQIcount += 1
            else:
                if (self.combiningMethod != EnumCombination.COMBINEMAX
                        and utility >= math.floor(self.minUtil / self.coefficient)) or \
                   (self.combiningMethod == EnumCombination.COMBINEMAX
                        and utility >= math.floor(self.minUtil / 2)):
                    candidateList.append(qi)
                if utility + mapItemToUtilityList[qi].getSumRutils() >= self.minUtil:
                    hwQUI.append(qi)

        MemoryLogger.getInstance().checkMemory()
        self._combineMethod(None, 0, candidateList, qitemNameList, mapItemToUtilityList, hwQUI)

    # ------------------------------------------------------------------
    # combineMethod dispatcher
    # ------------------------------------------------------------------
    def _combineMethod(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        if len(candidateList) > 2:
            candidateList.sort(key=lambda q: self._compareCandidateItems_key(q))
            if self.combiningMethod == EnumCombination.COMBINEALL:
                self._combineAll(prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI)
            elif self.combiningMethod == EnumCombination.COMBINEMIN:
                self._combineMin(prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI)
            elif self.combiningMethod == EnumCombination.COMBINEMAX:
                self._combineMax(prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI)
            MemoryLogger.getInstance().checkMemory()
        return qItemNameList

    # ------------------------------------------------------------------
    # combineAll
    # ------------------------------------------------------------------
    def _combineAll(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        # Prune non-necessary candidates
        s = 1
        while s < len(candidateList) - 1:
            prev = candidateList[s - 1]
            curr = candidateList[s]
            nxt = candidateList[s + 1]
            if ((curr.getQteMin() == prev.getQteMax() + 1 and curr.getItem() == prev.getItem()) or
                    (curr.getQteMax() == nxt.getQteMin() - 1 and curr.getItem() == nxt.getItem())):
                s += 1
            else:
                candidateList.pop(s)

        if len(candidateList) > 2:
            last = candidateList[-1]
            second_last = candidateList[-2]
            if last.getQteMin() != second_last.getQteMax() + 1 or second_last.getItem() != last.getItem():
                candidateList.pop()

        mapRangeToUtilityList = {}
        for i in range(len(candidateList)):
            currentItem = candidateList[i].getItem()
            mapRangeToUtilityList.clear()
            count = 1
            for j in range(i + 1, len(candidateList)):
                nextItem = candidateList[j].getItem()
                if currentItem != nextItem:
                    break
                if j == i + 1:
                    if candidateList[j].getQteMin() != candidateList[i].getQteMax() + 1:
                        break
                    res = self._constructForCombine(
                        mapItemToUtilityList[candidateList[i]],
                        mapItemToUtilityList[candidateList[j]]
                    )
                    count += 1
                    if count > self.coefficient:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        self.HUQIcount += 1
                        if prefixLength == 0:
                            self._insert_prefix_item(None, 0, res.getSingleItemsetName(), res.getSumIutils())
                        else:
                            self._insert_prefix_item(prefix, prefixLength, res.getSingleItemsetName(), res.getSumIutils())
                        hwQUI.append(res.getSingleItemsetName())
                        mapItemToUtilityList[res.getSingleItemsetName()] = res
                        site = qItemNameList.index(candidateList[j])
                        qItemNameList.insert(site, res.getSingleItemsetName())
                else:
                    if candidateList[j].getQteMin() != candidateList[j - 1].getQteMax() + 1:
                        break
                    qItem1 = Qitem(currentItem, candidateList[i].getQteMin(), candidateList[j - 1].getQteMax())
                    ulQitem1 = mapRangeToUtilityList.get(qItem1)
                    res = self._constructForCombine(ulQitem1, mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        self.HUQIcount += 1
                        if prefixLength == 0:
                            self._insert_prefix_item(None, 0, res.getSingleItemsetName(), res.getSumIutils())
                        else:
                            self._insert_prefix_item(prefix, prefixLength, res.getSingleItemsetName(), res.getSumIutils())
                        hwQUI.append(res.getSingleItemsetName())
                        mapItemToUtilityList[res.getSingleItemsetName()] = res
                        site = qItemNameList.index(candidateList[j])
                        qItemNameList.insert(site, res.getSingleItemsetName())
        MemoryLogger.getInstance().checkMemory()

    # ------------------------------------------------------------------
    # combineMin
    # ------------------------------------------------------------------
    def _combineMin(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        # Prune
        s = 1
        while s < len(candidateList) - 1:
            prev = candidateList[s - 1]
            curr = candidateList[s]
            nxt = candidateList[s + 1]
            if ((curr.getQteMin() == prev.getQteMax() + 1 and curr.getItem() == prev.getItem()) or
                    (curr.getQteMax() == nxt.getQteMin() - 1 and curr.getItem() == nxt.getItem())):
                s += 1
            else:
                candidateList.pop(s)

        if len(candidateList) > 2:
            last = candidateList[-1]
            second_last = candidateList[-2]
            if last.getQteMin() != second_last.getQteMax() + 1 or second_last.getItem() != last.getItem():
                candidateList.pop()

        temporaryArrayList = []
        temporaryMap = {}
        mapRangeToUtilityList = {}

        for i in range(len(candidateList)):
            currentItem = candidateList[i].getItem()
            mapRangeToUtilityList.clear()
            count = 1
            for j in range(i + 1, len(candidateList)):
                nextItem = candidateList[j].getItem()
                if currentItem != nextItem:
                    break
                if j == i + 1:
                    if candidateList[j].getQteMin() != candidateList[i].getQteMax() + 1:
                        break
                    res = self._constructForCombine(
                        mapItemToUtilityList[candidateList[i]],
                        mapItemToUtilityList[candidateList[j]]
                    )
                    count += 1
                    if count > self.coefficient:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        name = res.getSingleItemsetName()
                        if (not temporaryArrayList or
                                name.getItem() != temporaryArrayList[-1].getItem() or
                                name.getQteMax() > temporaryArrayList[-1].getQteMax()):
                            temporaryArrayList.append(name)
                            temporaryMap[name] = res
                        else:
                            old = temporaryArrayList[-1]
                            del temporaryMap[old]
                            temporaryArrayList[-1] = name
                            temporaryMap[name] = res
                        break
                else:
                    if candidateList[j].getQteMin() != candidateList[j - 1].getQteMax() + 1:
                        break
                    qItem1 = Qitem(currentItem, candidateList[i].getQteMin(), candidateList[j - 1].getQteMax())
                    ulQitem1 = mapRangeToUtilityList.get(qItem1)
                    res = self._constructForCombine(ulQitem1, mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count > self.coefficient:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                    if res.getSumIutils() > self.minUtil:
                        name = res.getSingleItemsetName()
                        if (not temporaryArrayList or
                                name.getItem() != temporaryArrayList[-1].getItem() or
                                name.getQteMax() > temporaryArrayList[-1].getQteMax()):
                            temporaryArrayList.append(name)
                            temporaryMap[name] = res
                        else:
                            old = temporaryArrayList[-1]
                            del temporaryMap[old]
                            temporaryArrayList[-1] = name
                            temporaryMap[name] = res
                        break

        for currentQitem in temporaryArrayList:
            mapItemToUtilityList[currentQitem] = temporaryMap[currentQitem]
            self._insert_prefix_item(prefix, prefixLength, currentQitem, temporaryMap[currentQitem].getSumIutils())
            self.HUQIcount += 1
            hwQUI.append(currentQitem)
            q = Qitem(currentQitem.getItem(), currentQitem.getQteMax())
            site = qItemNameList.index(q)
            qItemNameList.insert(site, currentQitem)

        temporaryArrayList.clear()
        temporaryMap.clear()
        MemoryLogger.getInstance().checkMemory()

    # ------------------------------------------------------------------
    # combineMax
    # ------------------------------------------------------------------
    def _combineMax(self, prefix, prefixLength, candidateList, qItemNameList, mapItemToUtilityList, hwQUI):
        # Prune
        s = 1
        while s < len(candidateList) - 1:
            prev = candidateList[s - 1]
            curr = candidateList[s]
            nxt = candidateList[s + 1]
            if ((curr.getQteMin() == prev.getQteMax() + 1 and curr.getItem() == prev.getItem()) or
                    (curr.getQteMax() == nxt.getQteMin() - 1 and curr.getItem() == nxt.getItem())):
                s += 1
            else:
                candidateList.pop(s)

        if len(candidateList) > 2:
            last = candidateList[-1]
            second_last = candidateList[-2]
            if last.getQteMin() != second_last.getQteMax() + 1 or second_last.getItem() != last.getItem():
                candidateList.pop()

        temporaryArrayList = []
        temporaryMap = {}
        mapRangeToUtilityList = {}
        count = 1

        for i in range(len(candidateList)):
            res = UtilityListTKQ()
            currentItem = candidateList[i].getItem()
            mapRangeToUtilityList.clear()
            count = 1
            for j in range(i + 1, len(candidateList)):
                nextItem = candidateList[j].getItem()
                if currentItem != nextItem:
                    break
                if j == i + 1:
                    if candidateList[j].getQteMin() != candidateList[i].getQteMax() + 1:
                        break
                    res = self._constructForCombine(
                        mapItemToUtilityList[candidateList[i]],
                        mapItemToUtilityList[candidateList[j]]
                    )
                    count += 1
                    if count > self.coefficient - 1:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res
                else:
                    if candidateList[j].getQteMin() != candidateList[j - 1].getQteMax() + 1:
                        break
                    qItem1 = Qitem(currentItem, candidateList[i].getQteMin(), candidateList[j - 1].getQteMax())
                    ulQitem1 = mapRangeToUtilityList.get(qItem1)
                    res = self._constructForCombine(ulQitem1, mapItemToUtilityList[candidateList[j]])
                    count += 1
                    if count >= self.coefficient:
                        break
                    mapRangeToUtilityList[res.getSingleItemsetName()] = res

            if res.getSumIutils() > self.minUtil:
                name = res.getSingleItemsetName()
                if (not temporaryMap or
                        name.getItem() != temporaryArrayList[-1].getItem() or
                        name.getQteMax() > temporaryArrayList[-1].getQteMax()):
                    temporaryMap[name] = res
                    temporaryArrayList.append(name)

        for currentQitem in temporaryArrayList:
            mapItemToUtilityList[currentQitem] = temporaryMap[currentQitem]
            self._insert_prefix_item(prefix, prefixLength, currentQitem, temporaryMap[currentQitem].getSumIutils())
            self.HUQIcount += 1
            hwQUI.append(currentQitem)
            q = Qitem(currentQitem.getItem(), currentQitem.getQteMax())
            site = qItemNameList.index(q)
            qItemNameList.insert(site, currentQitem)

        temporaryArrayList.clear()
        temporaryMap.clear()
        MemoryLogger.getInstance().checkMemory()

    # ------------------------------------------------------------------
    # constructForCombine
    # ------------------------------------------------------------------
    def _constructForCombine(self, ulQitem1, ulQitem2):
        name1 = ulQitem1.getSingleItemsetName()
        name2 = ulQitem2.getSingleItemsetName()
        result = UtilityListTKQ(Qitem(name1.getItem(), name1.getQteMin(), name2.getQteMax()))

        temp1 = ulQitem1.getQItemTrans()
        temp2 = ulQitem2.getQItemTrans()
        mainlist = []

        result.setSumIutils(ulQitem1.getSumIutils() + ulQitem2.getSumIutils())
        result.setSumRutils(ulQitem1.getSumRutils() + ulQitem2.getSumRutils())
        result.setTwu(ulQitem1.getTwu() + ulQitem2.getTwu())

        i, j = 0, 0
        while i < len(temp1) and j < len(temp2):
            t1 = temp1[i].getTid()
            t2 = temp2[j].getTid()
            if t1 > t2:
                mainlist.append(temp2[j])
                j += 1
            else:
                mainlist.append(temp1[i])
                i += 1
        while j < len(temp2):
            mainlist.append(temp2[j])
            j += 1
        while i < len(temp1):
            mainlist.append(temp1[i])
            i += 1

        result.setQItemTrans(mainlist)
        MemoryLogger.getInstance().checkMemory()
        return result

    # ------------------------------------------------------------------
    # constructForJoin
    # ------------------------------------------------------------------
    def _constructForJoin(self, ul1, ul2, ul0):
        if ul1.getSingleItemsetName().getItem() == ul2.getSingleItemsetName().getItem():
            return None

        qT1 = ul1.getQItemTrans()
        qT2 = ul2.getQItemTrans()
        res = UtilityListTKQ(ul2.getItemsetName())

        if ul0 is None:
            i, j = 0, 0
            while i < len(qT1) and j < len(qT2):
                tid1 = qT1[i].getTid()
                tid2 = qT2[j].getTid()
                if tid1 == tid2:
                    eu1 = qT1[i].getEu()
                    eu2 = qT2[j].getEu()
                    if qT1[i].getRu() >= qT2[j].getRu():
                        temp = QItemTrans(tid1, eu1 + eu2, qT2[j].getRu())
                        res.addTrans(temp, self.mapTransactionToUtility.get(tid1, 0))
                    i += 1
                    j += 1
                elif tid1 > tid2:
                    j += 1
                else:
                    i += 1
        else:
            preQT = ul0.getQItemTrans()
            i, j, k = 0, 0, 0
            while i < len(qT1) and j < len(qT2):
                tid1 = qT1[i].getTid()
                tid2 = qT2[j].getTid()
                if tid1 == tid2:
                    eu1 = qT1[i].getEu()
                    eu2 = qT2[j].getEu()
                    while preQT[k].getTid() != tid1:
                        k += 1
                    preEU = preQT[k].getEu()
                    if qT1[i].getRu() >= qT2[j].getRu():
                        temp = QItemTrans(tid1, eu1 + eu2 - preEU, qT2[j].getRu())
                        res.addTrans(temp, self.mapTransactionToUtility.get(tid1, 0))
                    i += 1
                    j += 1
                elif tid1 > tid2:
                    j += 1
                else:
                    i += 1

        MemoryLogger.getInstance().checkMemory()
        if res.getQItemTrans():
            return res
        return None

    # ------------------------------------------------------------------
    # Main miner
    # ------------------------------------------------------------------
    def _miner(self, prefix, prefixLength, prefixUL, ULs, qItemNameList, hwQUI):
        t2 = [0] * self.coefficient
        nextNameList = []

        for i in range(len(qItemNameList)):
            nextNameList.clear()
            nextHWQUI = []
            candidateList = []
            nextHUL = {}
            candidateHUL = {}

            if qItemNameList[i] not in hwQUI:
                continue

            if qItemNameList[i].isRange():
                for ii in range(qItemNameList[i].getQteMin(), qItemNameList[i].getQteMax() + 1):
                    idx = ii - qItemNameList[i].getQteMin()
                    search = Qitem(qItemNameList[i].getItem(), ii)
                    t2[idx] = qItemNameList.index(search) if search in qItemNameList else -1

            for j in range(i + 1, len(qItemNameList)):
                if qItemNameList[j].isRange():
                    continue
                if qItemNameList[i].isRange() and j == i + 1:
                    continue

                afterUL = None

                mapTWUF = self.mapFMAP.get(qItemNameList[i])
                if mapTWUF is not None:
                    twuF = mapTWUF.get(qItemNameList[j])
                    if twuF is None or twuF.twu < math.floor(self.minUtil / self.coefficient):
                        continue
                    else:
                        afterUL = self._constructForJoin(
                            ULs[qItemNameList[i]], ULs[qItemNameList[j]], prefixUL
                        )
                        self.countConstruct += 1
                        if afterUL is None or afterUL.getTwu() < math.floor(self.minUtil / self.coefficient):
                            continue
                else:
                    sumtwu = 0
                    for ii in range(qItemNameList[i].getQteMin(), qItemNameList[i].getQteMax() + 1):
                        idx = ii - qItemNameList[i].getQteMin()
                        a = min(t2[idx], j)
                        b = max(t2[idx], j)
                        if a < 0 or b >= len(qItemNameList):
                            continue
                        fmap_a = self.mapFMAP.get(qItemNameList[a])
                        if fmap_a is not None:
                            info = fmap_a.get(qItemNameList[b])
                            if info is not None:
                                sumtwu += info.twu
                    if sumtwu == 0 or sumtwu < math.floor(self.minUtil / self.coefficient):
                        continue
                    else:
                        afterUL = self._constructForJoin(
                            ULs[qItemNameList[i]], ULs[qItemNameList[j]], prefixUL
                        )
                        self.countConstruct += 1
                        if afterUL is None or afterUL.getTwu() < math.floor(self.minUtil / self.coefficient):
                            continue

                if afterUL is not None and afterUL.getTwu() >= math.floor(self.minUtil / self.coefficient):
                    nextNameList.append(afterUL.getSingleItemsetName())
                    nextHUL[afterUL.getSingleItemsetName()] = afterUL
                    if afterUL.getSumIutils() >= self.minUtil:
                        self._insert_prefix_two_items(
                            prefix, prefixLength,
                            qItemNameList[i], qItemNameList[j],
                            afterUL.getSumIutils()
                        )
                        self.HUQIcount += 1
                        nextHWQUI.append(afterUL.getSingleItemsetName())
                    else:
                        if (self.combiningMethod != EnumCombination.COMBINEMAX
                                and afterUL.getSumIutils() >= math.floor(self.minUtil / self.coefficient)) or \
                           (self.combiningMethod == EnumCombination.COMBINEMAX
                                and afterUL.getSumIutils() >= math.floor(self.minUtil / 2)):
                            candidateList.append(afterUL.getSingleItemsetName())
                            candidateHUL[afterUL.getSingleItemsetName()] = afterUL
                        if afterUL.getSumIutils() + afterUL.getSumRutils() >= self.minUtil:
                            nextHWQUI.append(afterUL.getSingleItemsetName())

            if candidateList:
                nextNameList = self._combineMethod(
                    prefix, prefixLength, candidateList, nextNameList, nextHUL, nextHWQUI
                )
                candidateHUL.clear()
                candidateList.clear()

            MemoryLogger.getInstance().checkMemory()

            if len(nextNameList) >= 1:
                self.itemsetBuffer[prefixLength] = qItemNameList[i]
                self._miner(
                    self.itemsetBuffer, prefixLength + 1,
                    ULs[qItemNameList[i]], nextHUL,
                    nextNameList, nextHWQUI
                )

    # ------------------------------------------------------------------
    # Comparators
    # ------------------------------------------------------------------
    def _compareQItems_key(self, q):
        val = q.getQteMin() * self.mapItemToProfit.get(q.getItem(), 0)
        return (-val, q.getItem())

    def _compareCandidateItems_key(self, q):
        return (q.getItem(), q.getQteMin(), q.getQteMax())

    # ------------------------------------------------------------------
    # Print statistics
    # ------------------------------------------------------------------
    def printStatistics(self):
        print("============= TKQ v 2.52 Statistical results===============")
        if self.DEBUG_MODE:
            print(f"K: {self.k} coefficient: {self.coefficient}")
        print(f"HUQIcount:{self.HUQIcount}")
        print(f"Runtime: {(self.endTime - self.startTime):.3f} (s)")
        print(f"Memory usage: {MemoryLogger.getInstance().getMaxMemory():.4f} (Mb)")
        if self.DEBUG_MODE:
            print(f"Join operation count: {self.countConstruct}")
        print("================================================")


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))

    input_profit = os.path.join(script_dir, "dbHUQI_p.txt")
    input_db     = os.path.join(script_dir, "dbHUQI.txt")
    output       = os.path.join(script_dir, "output_py.txt")

    k    = 15
    coef = 3
    combination_method = EnumCombination.COMBINEALL

    algo = AlgoTKQ()
    algo.runAlgorithm(k, input_db, input_profit, coef, combination_method, output)
    algo.printStatistics()