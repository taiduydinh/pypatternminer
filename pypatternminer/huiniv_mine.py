#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse
import time
from typing import Dict, List, Optional, Set


# ----------------------------------------------------------------------
# MemoryLogger (simple, best-effort)
# ----------------------------------------------------------------------
class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self._max_mb: float = 0.0

    @staticmethod
    def getInstance() -> "MemoryLogger":
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self) -> None:
        self._max_mb = 0.0

    def getMaxMemory(self) -> float:
        return self._max_mb

    def checkMemory(self) -> float:
        mb = 0.0
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss = float(usage.ru_maxrss)
            # macOS reports bytes; Linux reports KB
            import sys
            if sys.platform == "darwin":
                mb = rss / (1024.0 * 1024.0)
            else:
                mb = rss / 1024.0
        except Exception:
            mb = self._max_mb

        if mb > self._max_mb:
            self._max_mb = mb
        return mb


# ----------------------------------------------------------------------
# Data structures (TP = Two-Phase)
# ----------------------------------------------------------------------
@dataclass
class ItemUtility:
    item: int
    utility: int


class TransactionTP:
    def __init__(self, items: List[ItemUtility], transaction_utility: int) -> None:
        self._items: List[ItemUtility] = items
        self._tu: int = transaction_utility

    def getItems(self) -> List[ItemUtility]:
        return self._items

    def getTransactionUtility(self) -> int:
        return self._tu

    def size(self) -> int:
        return len(self._items)

    def get(self, idx: int) -> ItemUtility:
        return self._items[idx]

    def getItemsUtilities(self) -> List[ItemUtility]:
        # Java code uses transaction.getItemsUtilities().get(i).utility
        # Here same list
        return self._items


class UtilityTransactionDatabaseTP:
    def __init__(self) -> None:
        self._transactions: List[TransactionTP] = []

    def loadFile(self, path: str) -> None:
        self._transactions = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                parts = line.split(":")
                items = parts[0].split()
                tu = int(parts[1])
                utils = parts[2].split()
                trans_items: List[ItemUtility] = []
                for i in range(len(items)):
                    trans_items.append(ItemUtility(int(items[i]), int(utils[i])))
                self._transactions.append(TransactionTP(trans_items, tu))

    def getTransactions(self) -> List[TransactionTP]:
        return self._transactions

    def size(self) -> int:
        return len(self._transactions)


class ItemsetTP:
    def __init__(self) -> None:
        self._items: List[int] = []
        self._tidset: Set[int] = set()
        self._utility: int = 0

    def addItem(self, item: int) -> None:
        self._items.append(int(item))

    def size(self) -> int:
        return len(self._items)

    def getItems(self) -> List[int]:
        return self._items

    def get(self, idx: int) -> int:
        return self._items[idx]

    def setTIDset(self, tids: Set[int]) -> None:
        self._tidset = set(tids)

    def getTIDset(self) -> Set[int]:
        return self._tidset

    def incrementUtility(self, u: int) -> None:
        self._utility += int(u)

    def getUtility(self) -> int:
        return self._utility

    def __str__(self) -> str:
        return " ".join(map(str, self._items))


class ItemsetsTP:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.levels: List[List[ItemsetTP]] = []  # index = k (size), store at k
        self._count: int = 0

    def addItemset(self, itemset: ItemsetTP, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self._count += 1

    def getLevels(self) -> List[List[ItemsetTP]]:
        return self.levels

    def getItemsetsCount(self) -> int:
        return self._count

    def decreaseCount(self) -> None:
        self._count -= 1

    def saveResultsToFile(self, output: str, transaction_count: int) -> None:
        # SPMF Two-Phase style typically: "i j k #UTIL: X"
        outp = Path(output)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, "w", encoding="utf-8", newline="\n") as w:
            for k in range(1, len(self.levels)):
                for it in self.levels[k]:
                    w.write(f"{it} #UTIL: {it.getUtility()}\n")


# ----------------------------------------------------------------------
# AlgoHUINIVMine (Python port of your Java)
# ----------------------------------------------------------------------
class AlgoHUINIVMine:
    def __init__(self) -> None:
        self.highUtilityItemsets: Optional[ItemsetsTP] = None
        self.database: Optional[UtilityTransactionDatabaseTP] = None
        self.minUtility: int = 0

        self.startTimestamp: int = 0
        self.endTimestamp: int = 0
        self.candidatesCount: int = 0

        # HUINIV diff
        self.negativeItems: Set[int] = set()

    def runAlgorithm(self, database: UtilityTransactionDatabaseTP, minUtility: int) -> ItemsetsTP:
        self.database = database
        self.minUtility = int(minUtility)

        MemoryLogger.getInstance().reset()
        self.startTimestamp = int(time.time() * 1000)

        self.highUtilityItemsets = ItemsetsTP("HIGH UTILITY ITEMSETS")
        self.candidatesCount = 0
        self.negativeItems = set()

        # ---------------- PHASE 1: generate candidates ----------------
        candidatesSize1: List[ItemsetTP] = []

        mapItemTidsets: Dict[int, Set[int]] = {}
        mapItemTWU: Dict[int, int] = {}
        maxItem = -10**18

        # scan DB
        for tid in range(database.size()):
            transaction = database.getTransactions()[tid]
            for iu in transaction.getItems():
                item = iu.item
                util = iu.utility

                if util < 0:
                    self.negativeItems.add(item)

                if item > maxItem:
                    maxItem = item

                ts = mapItemTidsets.get(item)
                if ts is None:
                    ts = set()
                    mapItemTidsets[item] = ts
                ts.add(tid)

                mapItemTWU[item] = mapItemTWU.get(item, 0) + transaction.getTransactionUtility()

        # sort items inside each transaction by item id (like your Java comparator)
        for tr in database.getTransactions():
            tr.getItems().sort(key=lambda x: x.item)

        # create size-1 candidates with TWU >= minUtility
        for item in range(0, int(maxItem) + 1):
            est = mapItemTWU.get(item)
            if est is not None and est >= self.minUtility:
                it = ItemsetTP()
                it.addItem(item)
                it.setTIDset(mapItemTidsets[item])
                candidatesSize1.append(it)
                self.highUtilityItemsets.addItemset(it, it.size())

        # generate larger candidates
        currentLevel = candidatesSize1
        while True:
            before = self.highUtilityItemsets.getItemsetsCount()
            currentLevel = self.generateCandidateSizeK(currentLevel, self.highUtilityItemsets)
            after = self.highUtilityItemsets.getItemsetsCount()
            if before == after:
                break

        MemoryLogger.getInstance().checkMemory()
        self.candidatesCount = self.highUtilityItemsets.getItemsetsCount()

        # ---------------- PHASE 2: exact utility + filter ----------------
        for level in self.highUtilityItemsets.getLevels():
            if not level:
                continue
            i = 0
            while i < len(level):
                cand = level[i]

                # HUINIV diff: remove itemsets made only of negative items (len>=2 in comments, but Java checks always)
                if self.onlyContainsNegativeItems(cand.getItems()):
                    level.pop(i)
                    self.highUtilityItemsets.decreaseCount()
                    continue

                # compute exact utility by scanning all transactions (as Java does)
                for tr in database.getTransactions():
                    tu_cand = 0
                    matches = 0
                    cand_items = cand.getItems()

                    # Java does "candidate.getItems().contains(transaction.get(i).item)"
                    # We keep same simple contains (O(k)) for correctness
                    for it in tr.getItems():
                        if it.item in cand_items:
                            tu_cand += it.utility
                            matches += 1

                    if matches == cand.size():
                        cand.incrementUtility(tu_cand)

                if cand.getUtility() < self.minUtility:
                    level.pop(i)
                    self.highUtilityItemsets.decreaseCount()
                    continue

                i += 1

        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)
        return self.highUtilityItemsets

    def onlyContainsNegativeItems(self, items: List[int]) -> bool:
        for it in items:
            if it not in self.negativeItems:
                return False
        return True

    def generateCandidateSizeK(self, levelK_1: List[ItemsetTP], candidatesHTWUI: ItemsetsTP) -> List[ItemsetTP]:
        db = self.database
        assert db is not None

        for i in range(len(levelK_1)):
            itemset1 = levelK_1[i]
            for j in range(i + 1, len(levelK_1)):
                itemset2 = levelK_1[j]

                # lexical join test (same as Java)
                ok = True
                for k in range(itemset1.size()):
                    if k == itemset1.size() - 1:
                        if itemset1.getItems()[k] >= itemset2.get(k):
                            ok = False
                            break
                    else:
                        if itemset1.getItems()[k] < itemset2.get(k):
                            ok = False
                            break  # continue loop2 in Java
                        elif itemset1.getItems()[k] > itemset2.get(k):
                            ok = False
                            break  # continue loop1 in Java
                if not ok:
                    continue

                missing = itemset2.get(itemset2.size() - 1)

                # tidset intersection
                tidset = set()
                t2 = itemset2.getTIDset()
                for tid in itemset1.getTIDset():
                    if tid in t2:
                        tidset.add(tid)

                # compute TWU over tidset
                twu = 0
                for tid in tidset:
                    twu += db.getTransactions()[tid].getTransactionUtility()

                if twu >= self.minUtility:
                    cand = ItemsetTP()
                    for k in range(itemset1.size()):
                        cand.addItem(itemset1.get(k))
                    cand.addItem(missing)
                    cand.setTIDset(tidset)
                    candidatesHTWUI.addItemset(cand, cand.size())

        # return the last level
        levels = candidatesHTWUI.getLevels()
        return levels[len(levels) - 1] if levels else []

    def printStats(self) -> None:
        db = self.database
        assert db is not None and self.highUtilityItemsets is not None
        print("=============  HUINIV-MINE ALGORITHM - STATS =============")
        print(f" Transactions count from database : {db.size()}")
        print(f" Candidates count : {self.candidatesCount}")
        print(f" High-utility itemsets count : {self.highUtilityItemsets.getItemsetsCount()}")
        print(f" Total time ~ {self.endTimestamp - self.startTimestamp} ms")
        print("===================================================")


# ----------------------------------------------------------------------
# Helper: locate files like Java getResource()
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
# Main (like MainTestHUINIVMine_saveToFile.java)
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="HUINIV-Mine (single-file Python port)")
    parser.add_argument("-i", "--input", help="Input file (e.g., DB_NegativeUtility.txt)")
    parser.add_argument("-s", "--minutil", type=int, help="Min utility threshold (int)")
    parser.add_argument("-o", "--output", help="Output file path (e.g., Java/src/output_py.txt)")
    args = parser.parse_args()

    if not args.input and args.minutil is None and not args.output:
        print("No arguments provided. Running in default MainTest mode...\n")
        input_path = file_to_path("DB_NegativeUtility.txt")
        minutil = 30
        output_path = str((Path("output_py.txt").resolve()))
    else:
        if not args.input or args.minutil is None or not args.output:
            parser.error("Provide -i, -s, -o OR run without arguments for default MainTest mode.")
        input_path = args.input
        minutil = int(args.minutil)
        output_path = args.output

    db = UtilityTransactionDatabaseTP()
    db.loadFile(input_path)

    algo = AlgoHUINIVMine()
    itemsets = algo.runAlgorithm(db, minutil)
    itemsets.saveResultsToFile(output_path, db.size())
    algo.printStats()


if __name__ == "__main__":
    main()
