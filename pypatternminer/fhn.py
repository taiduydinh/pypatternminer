#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse
import sys
import time
from typing import Dict, List, Optional, Set


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
        # Best-effort on macOS/Linux
        mem_mb = 0.0
        try:
            import resource  # Unix
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss = float(usage.ru_maxrss)
            if sys.platform == "darwin":
                mem_mb = rss / (1024.0 * 1024.0)  # bytes -> MB
            else:
                mem_mb = rss / 1024.0  # KB -> MB
        except Exception:
            mem_mb = self._max_memory_mb

        if mem_mb > self._max_memory_mb:
            self._max_memory_mb = mem_mb
        return mem_mb


# ----------------------------------------------------------------------
# Data structures
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Element:
    tid: int
    iutils: int
    rutils: int


@dataclass(frozen=True)
class ElementFHN:
    tid: int
    iutils: int     # positive part only
    inutils: int    # negative part only
    rutils: int     # remaining utility (computed like Java)

    # Java extends Element, but we keep explicit fields for clarity.


class UtilityList:
    def __init__(self, item: int) -> None:
        self.item: int = int(item)
        self.sumIutils: int = 0
        self.sumRutils: int = 0
        self.elements: List[Element] = []

    def addElement(self, e: Element) -> None:
        self.sumIutils += e.iutils
        self.sumRutils += e.rutils
        self.elements.append(e)

    def getSupport(self) -> int:
        return len(self.elements)

    def getUtils(self) -> int:
        return self.sumIutils


class UtilityListFHN(UtilityList):
    def __init__(self, item: int) -> None:
        super().__init__(item)
        self.sumINutils: int = 0
        # In Java, UtilityListFHN redeclares elements as List<ElementFHN>
        self.elements: List[ElementFHN] = []

    def addElementFHN(self, e: ElementFHN) -> None:
        self.sumIutils += e.iutils
        self.sumRutils += e.rutils
        self.sumINutils += e.inutils
        self.elements.append(e)


# ----------------------------------------------------------------------
# AlgoFHN (Python port)
# ----------------------------------------------------------------------
class AlgoFHN:
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

        # FHN specific
        self.negativeItems: Set[int] = set()

        self._writer = None

    # -----------------------------
    # Run algorithm
    # -----------------------------
    def runAlgorithm(self, input_path: str, output_path: str, minUtility: int) -> None:
        MemoryLogger.getInstance().reset()
        self.huiCount = 0
        self.candidateCount = 0

        self.mapFMAP = {}
        self.negativeItems = set()

        self.startTimestamp = int(time.time() * 1000)

        outp = Path(output_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        self._writer = open(outp, "w", encoding="utf-8", newline="\n")

        # 1) First pass: TWU + detect negative items
        self.mapItemToTWU = {}
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                parts = line.split(":")
                items = parts[0].split()
                tu = int(parts[1])
                utils = parts[2].split()

                for i in range(len(items)):
                    item = int(items[i])
                    util = int(utils[i])
                    if util < 0:
                        self.negativeItems.add(item)

                    self.mapItemToTWU[item] = self.mapItemToTWU.get(item, 0) + tu

        # 2) Build UtilityLists for promising items
        listOfUtilityLists: List[UtilityListFHN] = []
        mapItemToUL: Dict[int, UtilityListFHN] = {}

        for item, twu in self.mapItemToTWU.items():
            if twu >= minUtility:
                ul = UtilityListFHN(item)
                mapItemToUL[item] = ul
                listOfUtilityLists.append(ul)

        # Sort like Java compareItems:
        # - all non-negative items first, then negative items
        # - within group: TWU asc then lexical
        listOfUtilityLists.sort(key=lambda ul: (
            1 if ul.item in self.negativeItems else 0,
            self.mapItemToTWU[ul.item],
            ul.item
        ))

        # 3) Second pass: build UL elements + FMAP
        tid = 0
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                parts = line.split(":")
                items = parts[0].split()
                utils = parts[2].split()

                revised: List[tuple[int, int]] = []
                remainingUtility = 0
                newTWU = 0  # sum of *positive* utilities only (as Java does)

                for i in range(len(items)):
                    item = int(items[i])
                    util = int(utils[i])
                    if self.mapItemToTWU.get(item, 0) >= minUtility:
                        revised.append((item, util))
                        if item not in self.negativeItems:
                            remainingUtility += util
                            newTWU += util

                # sort revised by same compareItems order
                revised.sort(key=lambda p: (
                    1 if p[0] in self.negativeItems else 0,
                    self.mapItemToTWU[p[0]],
                    p[0]
                ))

                for i in range(len(revised)):
                    item, util = revised[i]

                    # Java:
                    # if(remainingUtility != 0) remainingUtility = remainingUtility - pair.utility;
                    if remainingUtility != 0:
                        remainingUtility -= util

                    ul = mapItemToUL[item]

                    # ElementFHN split
                    if util > 0:
                        e = ElementFHN(tid, util, 0, remainingUtility)
                    else:
                        e = ElementFHN(tid, 0, util, remainingUtility)
                    ul.addElementFHN(e)

                    # FMAP update only if remainingUtility != 0 (Java)
                    if remainingUtility != 0:
                        mp = self.mapFMAP.get(item)
                        if mp is None:
                            mp = {}
                            self.mapFMAP[item] = mp
                        for j in range(i + 1, len(revised)):
                            item_after, _ = revised[j]
                            prev = mp.get(item_after)
                            mp[item_after] = newTWU if prev is None else (prev + newTWU)

                tid += 1

        MemoryLogger.getInstance().checkMemory()

        # 4) Mine recursively
        self._fhn(self.itemsetBuffer, 0, None, listOfUtilityLists, minUtility)

        MemoryLogger.getInstance().checkMemory()

        self._writer.close()
        self._writer = None

        self.endTimestamp = int(time.time() * 1000)

    # -----------------------------
    # Binary search find by tid
    # -----------------------------
    def _findElementWithTID(self, ulist: UtilityListFHN, tid: int) -> Optional[ElementFHN]:
        lst = ulist.elements
        first, last = 0, len(lst) - 1
        while first <= last:
            mid = (first + last) >> 1
            mtid = lst[mid].tid
            if mtid < tid:
                first = mid + 1
            elif mtid > tid:
                last = mid - 1
            else:
                return lst[mid]
        return None

    # -----------------------------
    # Construct pXY
    # -----------------------------
    def _construct(self, P: Optional[UtilityListFHN], px: UtilityListFHN, py: UtilityListFHN, minUtility: int) -> Optional[UtilityListFHN]:
        pxy = UtilityListFHN(py.item)

        # LA-prune uses positive sums only (Java)
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
                eXY = ElementFHN(ex.tid, ex.iutils + ey.iutils, ex.inutils + ey.inutils, ey.rutils)
                pxy.addElementFHN(eXY)
            else:
                e = self._findElementWithTID(P, ex.tid)
                if e is not None:
                    eXY = ElementFHN(
                        ex.tid,
                        ex.iutils + ey.iutils - e.iutils,
                        ex.inutils + ey.inutils - e.inutils,
                        ey.rutils
                    )
                    pxy.addElementFHN(eXY)

        return pxy

    # -----------------------------
    # Recursive mining
    # -----------------------------
    def _fhn(self, prefix: List[int], prefixLength: int, pUL: Optional[UtilityListFHN], ULs: List[UtilityListFHN], minUtility: int) -> None:
        for i in range(len(ULs)):
            X = ULs[i]

            # HUI check: positive + negative
            if (X.sumIutils + X.sumINutils) >= minUtility:
                self._writeOut(prefix, prefixLength, X.item, X.sumIutils + X.sumINutils)

            # Prune uses positive + remaining only (Java)
            if (X.sumIutils + X.sumRutils) >= minUtility:
                exULs: List[UtilityListFHN] = []
                for j in range(i + 1, len(ULs)):
                    Y = ULs[j]

                    # EUCP pruning (FHM optimization)
                    mp = self.mapFMAP.get(X.item)
                    if mp is not None:
                        twuF = mp.get(Y.item)
                        if twuF is None or twuF < minUtility:
                            continue

                    self.candidateCount += 1

                    temp = self._construct(pUL, X, Y, minUtility)
                    if temp is not None:
                        exULs.append(temp)

                prefix[prefixLength] = X.item
                self._fhn(prefix, prefixLength + 1, X, exULs, minUtility)

        MemoryLogger.getInstance().checkMemory()

    # -----------------------------
    # Output
    # -----------------------------
    def _writeOut(self, prefix: List[int], prefixLength: int, item: int, utility: int) -> None:
        self.huiCount += 1
        parts: List[str] = []
        for i in range(prefixLength):
            parts.append(str(prefix[i]))
            parts.append(" ")
        parts.append(str(item))
        parts.append(" #UTIL: ")
        parts.append(str(utility))
        self._writer.write("".join(parts))
        self._writer.write("\n")

    # -----------------------------
    # Stats
    # -----------------------------
    def printStats(self) -> None:
        print("=============  FHN ALGORITHM v0.96r18 - STATS =============")
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
# Main (like MainTestFHN_saveToFile.java)
# - If you run with no args: default MainTest mode
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="FHN (single-file Python port)")
    parser.add_argument("-i", "--input", help="Input file (e.g., DB_NegativeUtility.txt)")
    parser.add_argument("-s", "--minutil", type=int, help="Min utility threshold (int)")
    parser.add_argument("-o", "--output", help="Output file path (e.g., Java/src/output_py.txt)")

    args = parser.parse_args()

    # Default: behave like Java MainTest if no args
    if not args.input and args.minutil is None and not args.output:
        print("No arguments provided. Running in default MainTest mode...\n")
        input_path = file_to_path("DB_NegativeUtility.txt")
        minutil = 30
        output_path = "output_py.txt"
    else:
        if not args.input or args.minutil is None or not args.output:
            parser.error("Provide -i, -s, -o OR run without arguments for default MainTest mode.")
        input_path = args.input
        minutil = int(args.minutil)
        output_path = args.output

    algo = AlgoFHN()
    algo.runAlgorithm(input_path, output_path, minutil)
    algo.printStats()


if __name__ == "__main__":
    main()
