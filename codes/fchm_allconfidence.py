#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FCHM_allconfidence (SPMF)
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse
import sys
import time
from typing import Dict, List, Optional


# ----------------------------------------------------------------------
# MemoryLogger (SPMF-like)
# ----------------------------------------------------------------------
class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self._max_memory_mb: float = 0.0

    @staticmethod
    def getInstance() -> "MemoryLogger":
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def getMaxMemory(self) -> float:
        return self._max_memory_mb

    def reset(self) -> None:
        self._max_memory_mb = 0.0

    def checkMemory(self) -> float:
        # Best-effort cross-platform memory measure (macOS/Linux).
        mem_mb = 0.0
        try:
            import resource  # Unix
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss = float(usage.ru_maxrss)
            if sys.platform == "darwin":
                mem_mb = rss / (1024.0 * 1024.0)  # bytes -> MB (macOS)
            else:
                mem_mb = rss / 1024.0  # KB -> MB (Linux)
        except Exception:
            mem_mb = self._max_memory_mb

        if mem_mb > self._max_memory_mb:
            self._max_memory_mb = mem_mb
        return mem_mb


# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------
@dataclass
class Element:
    tid: int
    iutils: int
    rutils: int


class UtilityList:
    def __init__(self, item: int) -> None:
        self.item: int = int(item)
        self.sumIutils: int = 0
        self.sumRutils: int = 0
        self.elements: List[Element] = []

    def addElement(self, element: Element) -> None:
        self.sumIutils += element.iutils
        self.sumRutils += element.rutils
        self.elements.append(element)

    def getSupport(self) -> int:
        return len(self.elements)

    def getUtils(self) -> int:
        return self.sumIutils


class UtilityListFCHM_all_confidence(UtilityList):
    def __init__(self, item: int) -> None:
        super().__init__(item)
        self.max_subset: int = 0  # support of the maximum subset

    def getAll_confidence(self) -> float:
        # Java: elements.size() / (double) max_subset
        if self.max_subset == 0:
            return 0.0
        return len(self.elements) / float(self.max_subset)


# ----------------------------------------------------------------------
# AlgoFCHM_all_confidence (Python port)
# ----------------------------------------------------------------------
class AlgoFCHM_all_confidence:
    BUFFERS_SIZE = 200

    def __init__(self) -> None:
        self.startTimestamp: int = 0
        self.endTimestamp: int = 0
        self.huiCount: int = 0
        self.candidateCount: int = 0

        self.mapItemToTWU: Dict[int, int] = {}
        self.mapFMAP: Dict[int, Dict[int, int]] = {}

        self.ENABLE_LA_PRUNE: bool = True
        self.DEBUG: bool = False

        self.itemsetBuffer: List[int] = [0] * self.BUFFERS_SIZE
        self._writer = None

    # -----------------------------
    # Run algorithm
    # -----------------------------
    def runAlgorithm(self, input_path: str, output_path: str, minUtility: int, minAllconfidence: float) -> None:
        MemoryLogger.getInstance().reset()
        self.huiCount = 0
        self.candidateCount = 0

        self.mapFMAP = {}
        self.startTimestamp = int(time.time() * 1000)

        outp = Path(output_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        self._writer = open(outp, "w", encoding="utf-8", newline="\n")

        # 1) First pass: TWU per item
        self.mapItemToTWU = {}
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                parts = line.split(":")
                items = parts[0].split()
                tu = int(parts[1])
                for s in items:
                    it = int(s)
                    self.mapItemToTWU[it] = self.mapItemToTWU.get(it, 0) + tu

        # 2) Create ULs for items with TWU >= minUtility
        ULs: List[UtilityListFCHM_all_confidence] = []
        mapItemToUL: Dict[int, UtilityListFCHM_all_confidence] = {}
        for it, twu in self.mapItemToTWU.items():
            if twu >= minUtility:
                ul = UtilityListFCHM_all_confidence(it)
                mapItemToUL[it] = ul
                ULs.append(ul)

        # Sort by TWU asc, then lexical
        ULs.sort(key=lambda ul: (self.mapItemToTWU[ul.item], ul.item))

        # 3) Second pass: build utility lists + FMAP
        # Java: tid starts at 0, element created with tid, then tid++ at end of transaction.
        tid = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue

                parts = line.split(":")
                items = parts[0].split()
                utils = parts[2].split()

                remainingUtility = 0
                newTWU = 0

                revised: List[tuple[int, int]] = []
                for i in range(len(items)):
                    item = int(items[i])
                    util = int(utils[i])
                    if self.mapItemToTWU.get(item, 0) >= minUtility:
                        revised.append((item, util))
                        remainingUtility += util
                        newTWU += util

                revised.sort(key=lambda p: (self.mapItemToTWU[p[0]], p[0]))

                for i in range(len(revised)):
                    item, util = revised[i]
                    remainingUtility -= util

                    ul = mapItemToUL[item]
                    ul.addElement(Element(tid, util, remainingUtility))

                    # FMAP updates (FHM optimization)
                    mp = self.mapFMAP.get(item)
                    if mp is None:
                        mp = {}
                        self.mapFMAP[item] = mp
                    for j in range(i + 1, len(revised)):
                        item_after, _ = revised[j]
                        prev = mp.get(item_after)
                        mp[item_after] = newTWU if prev is None else (prev + newTWU)

                tid += 1

        # 4) init max_subset for 1-itemsets
        for ul in ULs:
            ul.max_subset = len(ul.elements)

        MemoryLogger.getInstance().checkMemory()

        # 5) recursive mining
        self._fchm(self.itemsetBuffer, 0, None, ULs, minUtility, float(minAllconfidence))

        MemoryLogger.getInstance().checkMemory()

        self._writer.close()
        self._writer = None

        self.endTimestamp = int(time.time() * 1000)

    # -----------------------------
    # Helpers
    # -----------------------------
    def _compareItems(self, item1: int, item2: int) -> int:
        compare = self.mapItemToTWU[item1] - self.mapItemToTWU[item2]
        return (item1 - item2) if compare == 0 else compare

    def _findElementWithTID(self, ulist: UtilityListFCHM_all_confidence, tid: int) -> Optional[Element]:
        lst = ulist.elements
        first = 0
        last = len(lst) - 1
        while first <= last:
            middle = (first + last) >> 1
            mtid = lst[middle].tid
            if mtid < tid:
                first = middle + 1
            elif mtid > tid:
                last = middle - 1
            else:
                return lst[middle]
        return None

    def _construct(
        self,
        P: Optional[UtilityListFCHM_all_confidence],
        px: UtilityListFCHM_all_confidence,
        py: UtilityListFCHM_all_confidence,
        minUtility: int,
    ) -> Optional[UtilityListFCHM_all_confidence]:
        pxyUL = UtilityListFCHM_all_confidence(py.item)

        # LA-prune
        totalUtility = px.sumIutils + px.sumRutils

        for ex in px.elements:
            ey = self._findElementWithTID(py, ex.tid)
            if ey is None:
                if self.ENABLE_LA_PRUNE:
                    totalUtility -= (ex.iutils + ex.rutils)
                    if totalUtility < minUtility:
                        return None
                continue

            if P is None:
                eXY = Element(ex.tid, ex.iutils + ey.iutils, ey.rutils)
                pxyUL.addElement(eXY)
            else:
                e = self._findElementWithTID(P, ex.tid)
                if e is not None:
                    eXY = Element(ex.tid, ex.iutils + ey.iutils - e.iutils, ey.rutils)
                    pxyUL.addElement(eXY)

        # max subset support
        pxyUL.max_subset = px.max_subset if px.max_subset > py.max_subset else py.max_subset
        return pxyUL

    def _writeOut(self, prefix: List[int], prefixLength: int, item: int, utility: int, all_conf: float) -> None:
        self.huiCount += 1
        # Java formatting:
        # prefix items each with trailing space, then last item (no trailing space),
        # then " #UTIL: " + utility + " #ALLCONF: " + all_confidence
        parts: List[str] = []
        for i in range(prefixLength):
            parts.append(str(prefix[i]))
            parts.append(" ")
        parts.append(str(item))
        parts.append(" #UTIL: ")
        parts.append(str(utility))
        parts.append(" #ALLCONF: ")
        parts.append(str(all_conf))
        self._writer.write("".join(parts))
        self._writer.write("\n")

    # -----------------------------
    # Recursive mining
    # -----------------------------
    def _fchm(
        self,
        prefix: List[int],
        prefixLength: int,
        pUL: Optional[UtilityListFCHM_all_confidence],
        ULs: List[UtilityListFCHM_all_confidence],
        minUtility: int,
        minAll_confidence: float,
    ) -> None:
        for i in range(len(ULs)):
            X = ULs[i]

            if X.sumIutils >= minUtility:
                self._writeOut(prefix, prefixLength, X.item, X.sumIutils, X.getAll_confidence())

            if X.sumIutils + X.sumRutils >= minUtility:
                exULs: List[UtilityListFCHM_all_confidence] = []

                for j in range(i + 1, len(ULs)):
                    Y = ULs[j]

                    # FHM EUCP pruning using FMAP
                    mp = self.mapFMAP.get(X.item)
                    if mp is not None:
                        twuF = mp.get(Y.item)
                        if twuF is None or twuF < minUtility:
                            continue

                    self.candidateCount += 1

                    temp = self._construct(pUL, X, Y, minUtility)
                    if temp is not None and temp.getAll_confidence() >= minAll_confidence:
                        exULs.append(temp)

                prefix[prefixLength] = X.item
                self._fchm(prefix, prefixLength + 1, X, exULs, minUtility, minAll_confidence)

        MemoryLogger.getInstance().checkMemory()

    # -----------------------------
    # Stats
    # -----------------------------
    def printStats(self) -> None:
        print("=============  FHM ALGORITHM - SPMF 0.97e - STATS =============")
        print(f" Total time ~ {self.endTimestamp - self.startTimestamp} ms")
        print(f" Memory ~ {MemoryLogger.getInstance().getMaxMemory()} MB")
        print(f" High-utility itemsets count : {self.huiCount}")
        print(f" Candidate count : {self.candidateCount}")
        print("===================================================")


# ----------------------------------------------------------------------
# Helper: locate file like Java getResource()
# ----------------------------------------------------------------------
def file_to_path(filename: str) -> str:
    here = Path(__file__).resolve().parent
    candidates = [
        here / filename,
        here / "Java" / "src" / filename,
        Path.cwd() / filename,
        Path.cwd() / "Java" / "src" / filename,
    ]
    for p in candidates:
        if p.exists():
            return str(p.resolve())
    tried = "\n".join([f"- {c.resolve()}" for c in candidates])
    raise FileNotFoundError(f"Could not locate {filename}. Tried:\n{tried}")


# ----------------------------------------------------------------------
# Main (like Java MainTestFCHM_allconfidence.java)
# - If you run with no args: default MainTest mode (DB_Utility.txt, minutil=30, allconf=0.5)
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="FCHM_allconfidence (single-file Python port)")
    parser.add_argument("-i", "--input", help="Input utility DB file (e.g., DB_Utility.txt)")
    parser.add_argument("-s", "--support", type=int, help="Min utility threshold (int)")
    parser.add_argument("-o", "--output", help="Output file path (e.g., Java/src/output_py.txt)")
    parser.add_argument("-c", "--allconf", type=float, help="Min all-confidence threshold (double)")

    args = parser.parse_args()

    # Default: behave like Java MainTest if no args
    if not args.input and args.support is None and not args.output and args.allconf is None:
        print("No arguments provided. Running in default MainTest mode...\n")
        input_path = file_to_path("DB_Utility.txt")
        output_path = str((Path("Java") / "src" / "output_py.txt").resolve())
        minutil = 30
        min_allconf = 0.5
    else:
        if not args.input or args.support is None or not args.output or args.allconf is None:
            parser.error("Provide -i, -s, -o, -c OR run without arguments for default MainTest mode.")
        input_path = args.input
        output_path = args.output
        minutil = int(args.support)
        min_allconf = float(args.allconf)

    algo = AlgoFCHM_all_confidence()
    algo.runAlgorithm(input_path, output_path, minutil, min_allconf)
    algo.printStats()


if __name__ == "__main__":
    main()
