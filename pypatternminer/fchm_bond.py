# fchm_bond_single_final.py


import os
import math
import time
from bisect import bisect_left


# -----------------------------
# MemoryLogger (SPMF-like)
# -----------------------------
class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0
        self.recordingMode = False
        self._writer = None

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        current = self._get_current_memory_mb()
        if current > self.maxMemory:
            self.maxMemory = current
        if self.recordingMode and self._writer is not None:
            try:
                self._writer.write(str(current) + "\n")
                self._writer.flush()
            except Exception:
                pass
        return current

    @staticmethod
    def _get_current_memory_mb():
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # macOS bytes, Linux KB heuristic
            if usage > 10_000_000:
                return usage / 1024.0 / 1024.0
            return usage / 1024.0
        except Exception:
            return 0.0


# -----------------------------
# BitSetSupport (int bitmask)
# -----------------------------
class BitSetSupport:
    """
    Java BitSetSupport equivalent:
      - bitset: emulated by Python int bitmask
      - support: cached cardinality
    """
    __slots__ = ("bitset", "support")

    def __init__(self):
        self.bitset = 0
        self.support = 0

    def getBitset(self):
        return self.bitset

    def set(self, tid):
        mask = 1 << tid
        if (self.bitset & mask) == 0:
            self.bitset |= mask
            self.support += 1

    def orClone(self, other):
        out = BitSetSupport()
        out.bitset = self.bitset | other.bitset
        # Compatible with older Python (no int.bit_count)
        out.support = bin(out.bitset).count("1")
        return out


# -----------------------------
# Element
# -----------------------------
class Element:
    __slots__ = ("tid", "iutils", "rutils")

    def __init__(self, tid, iutils, rutils):
        self.tid = tid
        self.iutils = iutils
        self.rutils = rutils


# -----------------------------
# UtilityList + UtilityListFCHM_bond
# -----------------------------
class UtilityList:
    __slots__ = ("item", "sumIutils", "sumRutils", "elements", "_tids")

    def __init__(self, item):
        self.item = item
        self.sumIutils = 0
        self.sumRutils = 0
        self.elements = []
        self._tids = []  # for binary search

    def addElement(self, element):
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)
        self._tids.append(element.tid)

    def getSupport(self):
        return len(self.elements)

    def getUtils(self):
        return self.sumIutils


class UtilityListFCHM_bond(UtilityList):
    __slots__ = ("bitsetDisjunctiveTIDs",)

    def __init__(self, item, bitsetDisjunctiveTIDs):
        super(UtilityListFCHM_bond, self).__init__(item)
        self.bitsetDisjunctiveTIDs = bitsetDisjunctiveTIDs

    def getBond(self):
        if self.bitsetDisjunctiveTIDs.support == 0:
            return 0.0
        return len(self.elements) / float(self.bitsetDisjunctiveTIDs.support)


# -----------------------------
# TwuSupportPair
# -----------------------------
class TwuSupportPair:
    __slots__ = ("support", "twu")

    def __init__(self):
        self.support = 0
        self.twu = 0


# -----------------------------
# AlgoFCHM_bond
# -----------------------------
class AlgoFCHM_bond:
    BUFFERS_SIZE = 200

    def __init__(self):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.huiCount = 0
        self.candidateCount = 0

        self.mapItemToTWU = {}
        self.mapSMAP = {}

        self.DEBUG = False
        self.itemsetBuffer = [0] * self.BUFFERS_SIZE

        self.minBond = 0.0

        self.ENABLE_LA_PRUNE = True
        self.ENABLE_SLA_PRUNE = True
        self.ENABLE_FHM_PRUNING = True
        self.ENABLE_BOND_PAIR_PRUNING = True

        self.candidateEliminatedByLAPrune = 0
        self.candidateEliminatedBySLAPrune = 0
        self.candidateEliminatedByBondPruning = 0
        self.candidateEliminatedByFHMPruning = 0
        self.candidateEliminatedByACU2B = 0

        self._writer = None

    def runAlgorithm(self, input_path, output_path, minUtility, minBond):
        MemoryLogger.getInstance().reset()

        self.huiCount = 0
        self.candidateCount = 0
        self.candidateEliminatedByBondPruning = 0
        self.candidateEliminatedByFHMPruning = 0
        self.candidateEliminatedByLAPrune = 0
        self.candidateEliminatedBySLAPrune = 0
        self.candidateEliminatedByACU2B = 0

        self.itemsetBuffer = [0] * self.BUFFERS_SIZE
        self.mapSMAP = {}
        self.mapItemToTWU = {}
        self.minBond = float(minBond)

        self.startTimestamp = int(time.time() * 1000)
        self._writer = open(output_path, "w", encoding="utf-8")

        # PASS 1
        self._firstPassTWU(input_path)

        # init ULs for promising items
        listOfULs = []
        mapItemToUL = {}
        for item, twu in self.mapItemToTWU.items():
            if twu >= minUtility:
                ul = UtilityListFCHM_bond(item, BitSetSupport())
                mapItemToUL[item] = ul
                listOfULs.append(ul)

        # sort by TWU then lexical
        listOfULs.sort(key=lambda ul: (self.mapItemToTWU[ul.item], ul.item))

        # PASS 2
        self._secondPassBuildULsAndSMAP(input_path, mapItemToUL)

        MemoryLogger.getInstance().checkMemory()

        # mine
        self.fchm(self.itemsetBuffer, 0, None, listOfULs, minUtility)

        MemoryLogger.getInstance().checkMemory()
        self._writer.close()
        self._writer = None

        self.endTimestamp = int(time.time() * 1000)

    def _firstPassTWU(self, input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if (not line) or line[0] in "#%@":
                    continue
                split = line.split(":")
                items = [int(x) for x in split[0].split() if x]
                transactionUtility = int(split[1])
                for item in items:
                    self.mapItemToTWU[item] = self.mapItemToTWU.get(item, 0) + transactionUtility

    def _secondPassBuildULsAndSMAP(self, input_path, mapItemToUL):
        tid = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if (not line) or line[0] in "#%@":
                    continue

                split = line.split(":")
                items = [int(x) for x in split[0].split() if x]
                utilityValues = [int(x) for x in split[2].split() if x]

                revised = []
                remainingUtility = 0
                newTWU = 0

                for item, util in zip(items, utilityValues):
                    if item in mapItemToUL:
                        revised.append((item, util))
                        remainingUtility += util
                        newTWU += util

                revised.sort(key=lambda p: (self.mapItemToTWU[p[0]], p[0]))

                for i, (item_i, util_i) in enumerate(revised):
                    remainingUtility -= util_i

                    ul_i = mapItemToUL[item_i]
                    ul_i.bitsetDisjunctiveTIDs.set(tid)
                    ul_i.addElement(Element(tid, util_i, remainingUtility))

                    mapFMAPItem = self.mapSMAP.get(item_i)
                    if mapFMAPItem is None:
                        mapFMAPItem = {}
                        self.mapSMAP[item_i] = mapFMAPItem

                    for j in range(i + 1, len(revised)):
                        item_j = revised[j][0]
                        tsp = mapFMAPItem.get(item_j)
                        if tsp is None:
                            tsp = TwuSupportPair()
                            mapFMAPItem[item_j] = tsp
                        tsp.twu += newTWU
                        tsp.support += 1

                tid += 1

    def performOR(self, tidsetI, tidsetJ):
        return tidsetI.orClone(tidsetJ)

    def findElementWithTID(self, ulist, tid):
        tids = ulist._tids
        idx = bisect_left(tids, tid)
        if idx < len(tids) and tids[idx] == tid:
            return ulist.elements[idx]
        return None

    def writeOut(self, prefix, prefixLength, item, utility, bond):
        self.huiCount += 1
        parts = []
        for i in range(prefixLength):
            parts.append(str(prefix[i]))
        parts.append(str(item))
        # Match Java default double to-string closely
        line = " ".join(parts) + " #UTIL: " + str(utility) + " #BOND: " + str(bond)
        self._writer.write(line + "\n")

    def construct(self, P, px, py, minUtility, bitsetPXY):
        # SLA-prune
        maxdisjunctivesupport = float(bitsetPXY.support)
        pxsupport = float(len(px.elements))
        minSup = int(math.ceil(maxdisjunctivesupport * self.minBond))

        pxyUL = UtilityListFCHM_bond(py.item, bitsetPXY)

        # LA-prune
        totalUtility = px.sumIutils + px.sumRutils

        for ex in px.elements:
            ey = self.findElementWithTID(py, ex.tid)
            if ey is None:
                if self.ENABLE_LA_PRUNE:
                    totalUtility -= (ex.iutils + ex.rutils)
                    if totalUtility < minUtility:
                        self.candidateEliminatedByLAPrune += 1
                        return None

                if self.ENABLE_SLA_PRUNE:
                    pxsupport -= 1.0
                    if pxsupport < minSup:
                        self.candidateEliminatedBySLAPrune += 1
                        return None
                continue

            if P is None:
                pxyUL.addElement(Element(ex.tid, ex.iutils + ey.iutils, ey.rutils))
            else:
                e = self.findElementWithTID(P, ex.tid)
                if e is not None:
                    pxyUL.addElement(Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils))

        return pxyUL

    def fchm(self, prefix, prefixLength, pUL, ULs, minUtility):
        for i in range(len(ULs)):
            X = ULs[i]

            if X.sumIutils >= minUtility:
                self.writeOut(prefix, prefixLength, X.item, X.sumIutils, X.getBond())

            if X.sumIutils + X.sumRutils >= minUtility:
                exULs = []

                for j in range(i + 1, len(ULs)):
                    Y = ULs[j]

                    mapTWUF = self.mapSMAP.get(X.item)
                    min_consup = 0

                    if mapTWUF is not None:
                        twuF = mapTWUF.get(Y.item)
                        if twuF is not None:
                            if self.ENABLE_FHM_PRUNING and twuF.twu < minUtility:
                                self.candidateEliminatedByFHMPruning += 1
                                continue

                            if self.ENABLE_BOND_PAIR_PRUNING:
                                max_dissup = max(Y.bitsetDisjunctiveTIDs.support, X.bitsetDisjunctiveTIDs.support)

                                min_consup = twuF.support
                                if min_consup > len(X.elements):
                                    min_consup = len(X.elements)
                                if min_consup > len(Y.elements):
                                    min_consup = len(Y.elements)

                                if (min_consup / float(max_dissup)) < self.minBond:
                                    self.candidateEliminatedByBondPruning += 1
                                    continue

                    self.candidateCount += 1

                    # ACU2B optimization
                    bitsetPXY = self.performOR(X.bitsetDisjunctiveTIDs, Y.bitsetDisjunctiveTIDs)
                    if bitsetPXY.support == 0 or (min_consup / float(bitsetPXY.support)) < self.minBond:
                        self.candidateEliminatedByACU2B += 1
                        continue

                    temp = self.construct(pUL, X, Y, minUtility, bitsetPXY)
                    if temp is not None and temp.getBond() >= self.minBond:
                        exULs.append(temp)

                prefix[prefixLength] = X.item
                self.fchm(prefix, prefixLength + 1, X, exULs, minUtility)

        MemoryLogger.getInstance().checkMemory()

    def printStats(self):
        print("=============  FCHM ALGORITHM v0.96r18 - STATS =============")
        print(" Total time ~ " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Memory ~ " + str(MemoryLogger.getInstance().getMaxMemory()) + " MB")
        print(" Correlated High-utility itemset count : " + str(self.huiCount))
        print("   Candidate count : " + str(self.candidateCount))
        print("   Candidate eliminated by bond pruning: " + str(self.candidateEliminatedByBondPruning))
        print("   Candidate eliminated by FHM pruning: " + str(self.candidateEliminatedByFHMPruning))
        print("   List constructions stopped by SLAPrune: " + str(self.candidateEliminatedBySLAPrune))
        print("   List constructions stopped by LAPrune: " + str(self.candidateEliminatedByLAPrune))
        print(" utility_list eliminated by ACU2B:" + str(self.candidateEliminatedByACU2B))
        print("===================================================")


# -----------------------------
# Main (like MainTestFCHM_bond)
# -----------------------------
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(here, "DB_utility.txt")
    output_path = os.path.join(here, "output_py.txt")

    min_utility = 30
    minbond = 0.5

    algo = AlgoFCHM_bond()
    algo.runAlgorithm(input_path, output_path, min_utility, minbond)
    algo.printStats()


if __name__ == "__main__":
    main()