#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python implementation of the CM-ClaSP algorithm for sequential pattern mining
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Iterable
import math
import argparse
import time


# ----------------------------------------------------------------------
# MemoryLogger (SPMF)
# ----------------------------------------------------------------------

class MemoryLogger:
    _instance = None

    def __init__(self) -> None:
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self.maxMemory = 0.0

    def checkMemory(self) -> float:
        # We do not have a direct portable equivalent without psutil.
        # Keep this as a no-op-ish estimate.
        # Still return 0.0 so stats do not crash.
        return 0.0

    def getMaxMemory(self) -> float:
        return self.maxMemory


# ----------------------------------------------------------------------
# Core data structures: Item, Position, Itemset, Sequence
# ----------------------------------------------------------------------

class Item:
    def __init__(self, id_: Any):
        self.id = id_

    def getId(self) -> Any:
        return self.id

    def __str__(self) -> str:
        return str(self.getId())

    def __repr__(self) -> str:
        return f"Item({self.id!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Item) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __lt__(self, other: "Item") -> bool:
        return self.id < other.id

    def compareTo(self, other: "Item") -> int:
        if self.id < other.id:
            return -1
        if self.id > other.id:
            return 1
        return 0


@dataclass(eq=True, frozen=True)
class Position:
    itemsetIndex: int
    itemIndex: int

    def getItemsetIndex(self) -> int:
        return self.itemsetIndex

    def getItemIndex(self) -> int:
        return self.itemIndex


class Itemset:
    def __init__(self) -> None:
        self.items: List[Item] = []
        self.timestamp: int = 0

    def addItem(self, value: Item) -> None:
        self.items.append(value)

    def removeItem(self, i: int) -> Item:
        return self.items.pop(i)

    def getItems(self) -> List[Item]:
        return self.items

    def get(self, index: int) -> Item:
        return self.items[index]

    def size(self) -> int:
        return len(self.items)

    def cloneItemSet(self) -> "Itemset":
        it = Itemset()
        it.timestamp = self.timestamp
        it.items.extend(self.items)
        return it

    def getTimestamp(self) -> int:
        return self.timestamp

    def setTimestamp(self, ts: int) -> None:
        self.timestamp = ts

    def __str__(self) -> str:
        return " ".join(str(x) for x in self.items) + (" " if self.items else "")


class Sequence:
    def __init__(self, id_: int) -> None:
        self.id = id_
        self.itemsets: List[Itemset] = []
        self.numberOfItems = 0

    def addItemset(self, itemset: Itemset) -> None:
        self.itemsets.append(itemset)
        self.numberOfItems += itemset.size()

    def addItem(self, indexItemset: int, item: Item) -> None:
        self.itemsets[indexItemset].addItem(item)
        self.numberOfItems += 1

    def remove(self, indexItemset: int, indexItem: Optional[int] = None) -> Any:
        if indexItem is None:
            itset = self.itemsets.pop(indexItemset)
            self.numberOfItems -= itset.size()
            return itset
        else:
            self.numberOfItems -= 1
            return self.itemsets[indexItemset].removeItem(indexItem)

    def cloneSequence(self) -> "Sequence":
        s = Sequence(self.getId())
        for it in self.itemsets:
            s.addItemset(it.cloneItemSet())
        return s

    def getId(self) -> int:
        return self.id

    def setID(self, id_: int) -> None:
        self.id = id_

    def getItemsets(self) -> List[Itemset]:
        return self.itemsets

    def get(self, index: int) -> Itemset:
        return self.itemsets[index]

    def size(self) -> int:
        return len(self.itemsets)

    def length(self) -> int:
        return self.numberOfItems

    def getTimeLength(self) -> int:
        return self.itemsets[-1].getTimestamp() - self.itemsets[0].getTimestamp()

    def __str__(self) -> str:
        out = []
        for it in self.itemsets:
            out.append("{t=" + str(it.getTimestamp()) + ", " + " ".join(str(x) for x in it.getItems()) + " }")
        return "".join(out) + "    "


# ----------------------------------------------------------------------
# Abstractions and creators
# ----------------------------------------------------------------------

class Abstraction_Generic:
    def toStringToFile(self) -> str:
        raise NotImplementedError

    def __str__(self) -> str:
        raise NotImplementedError

    def __lt__(self, other: "Abstraction_Generic") -> bool:
        return self.compareTo(other) < 0

    def compareTo(self, other: "Abstraction_Generic") -> int:
        raise NotImplementedError


class Abstraction_Qualitative(Abstraction_Generic):
    _pool: Dict[bool, "Abstraction_Qualitative"] = {}

    def __init__(self, equalRelation: bool) -> None:
        self._hasEqualRelation = equalRelation

    @staticmethod
    def create(hasEqualRelation: bool) -> "Abstraction_Qualitative":
        if not Abstraction_Qualitative._pool:
            Abstraction_Qualitative._pool[True] = Abstraction_Qualitative(True)
            Abstraction_Qualitative._pool[False] = Abstraction_Qualitative(False)
        return Abstraction_Qualitative._pool[hasEqualRelation]

    def hasEqualRelation(self) -> bool:
        return self._hasEqualRelation

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Abstraction_Qualitative) and self._hasEqualRelation == other._hasEqualRelation

    def __hash__(self) -> int:
        return 1 if self._hasEqualRelation else 0

    def compareTo(self, o: Abstraction_Generic) -> int:
        if not isinstance(o, Abstraction_Qualitative):
            raise TypeError("Cannot compare Abstraction_Qualitative with other abstraction")
        if self._hasEqualRelation == o._hasEqualRelation:
            return 0
        # Java: if (!hasEqualRelation) return -1 else 1
        return -1 if (not self._hasEqualRelation) else 1

    def __str__(self) -> str:
        # Java: if (!equal) append " ->"
        return "" if self._hasEqualRelation else " ->"

    def toStringToFile(self) -> str:
        # Java: if (!equal) append " -1"
        return "" if self._hasEqualRelation else " -1"


class AbstractionCreator:
    def createDefaultAbstraction(self) -> Abstraction_Generic:
        raise NotImplementedError

    def getSubpattern(self, extension: "Pattern", i: int) -> "Pattern":
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def isSubpattern(self, aThis: "Pattern", p: "Pattern", i: int, posiciones: List[int]) -> bool:
        raise NotImplementedError


class AbstractionCreator_Qualitative(AbstractionCreator):
    _instance: Optional["AbstractionCreator_Qualitative"] = None

    @staticmethod
    def sclear() -> None:
        AbstractionCreator_Qualitative._instance = None

    @staticmethod
    def getInstance() -> "AbstractionCreator_Qualitative":
        if AbstractionCreator_Qualitative._instance is None:
            AbstractionCreator_Qualitative._instance = AbstractionCreator_Qualitative()
        return AbstractionCreator_Qualitative._instance

    def createDefaultAbstraction(self) -> Abstraction_Generic:
        return Abstraction_Qualitative.create(False)

    def crearAbstraccion(self, hasEqualRelation: bool) -> Abstraction_Generic:
        return Abstraction_Qualitative.create(hasEqualRelation)

    def getSubpattern(self, extension: "Pattern", index: int) -> "Pattern":
        pairCreator = ItemAbstractionPairCreator.getInstance()
        patternCreator = PatternCreator.getInstance()
        subElems: List[ItemAbstractionPair] = []
        abstraction: Optional[Abstraction_Generic] = None
        nextIndex = index + 1
        for i in range(extension.size()):
            if i != index:
                if i == nextIndex:
                    if abstraction is None:
                        abstraction = extension.getIthElement(i).getAbstraction()
                    subElems.append(pairCreator.getItemAbstractionPair(extension.getIthElement(i).getItem(), abstraction))
                else:
                    subElems.append(extension.getIthElement(i))
            else:
                if index == 0:
                    abstraction = self.createDefaultAbstraction()
                else:
                    absRemoved = extension.getIthElement(i).getAbstraction()
                    if isinstance(absRemoved, Abstraction_Qualitative) and (not absRemoved.hasEqualRelation()):
                        abstraction = self.crearAbstraccion(False)
        return patternCreator.createPattern(subElems)

    def clear(self) -> None:
        return

    def isSubpattern(self, shorter: "Pattern", larger: "Pattern", index: int, positions: List[int]) -> bool:
        # direct translation of Java method
        pair = shorter.getIthElement(index)
        itemPair = pair.getItem()
        absPair = pair.getAbstraction()
        previousAbs = shorter.getIthElement(index - 1).getAbstraction() if index > 0 else None

        cancelled = False
        while positions[index] < larger.size():
            if index == 0:
                pos = self.searchForFirstAppearance(larger, positions[index], itemPair)
            else:
                pos = self.findItemPositionInPattern(larger, itemPair, absPair, previousAbs,
                                                     positions[index], positions[index - 1])
            if pos is not None:
                positions[index] = pos
                if index + 1 < shorter.size():
                    positions[index + 1] = self.increasePosition(positions[index])
                    out = self.isSubpattern(shorter, larger, index + 1, positions)
                    if out:
                        positions.clear()
                        return True
                else:
                    positions.clear()
                    return True
            else:
                if index > 0:
                    positions[index - 1] = self.increaseItemset(larger, positions[index - 1])
                cancelled = True
                break

        if index > 0 and not cancelled:
            positions[index - 1] = self.increaseItemset(larger, positions[index - 1])
        return False

    def searchForFirstAppearance(self, p: "Pattern", beginning: int, itemPair: Item) -> Optional[int]:
        for i in range(beginning, p.size()):
            if p.getIthElement(i).getItem() == itemPair:
                return i
        return None

    def findItemPositionInPattern(self, p: "Pattern", itemPair: Item, currentAbs: Abstraction_Generic,
                                 previousAbs: Abstraction_Generic, currentPosition: int, previousPosition: int) -> Optional[int]:
        absq = currentAbs
        if isinstance(absq, Abstraction_Qualitative) and absq.hasEqualRelation():
            return self.searchForInTheSameItemset(p, itemPair, currentPosition)
        else:
            positionToSearchFor = currentPosition
            if not self.areInDifferentItemsets(p, previousPosition, currentPosition):
                positionToSearchFor = self.increaseItemset(p, currentPosition)
            return self.searchForFirstAppearance(p, positionToSearchFor, itemPair)

    def increasePosition(self, beginning: int) -> int:
        return beginning + 1

    def increaseItemset(self, p: "Pattern", beginning: int) -> int:
        for i in range(beginning + 1, p.size()):
            pair = p.getIthElement(i)
            absq = pair.getAbstraction()
            if isinstance(absq, Abstraction_Qualitative) and (not absq.hasEqualRelation()):
                return i
        return p.size()

    def searchForInTheSameItemset(self, pattern: "Pattern", itemPair: Item, beginning: int) -> Optional[int]:
        for i in range(beginning, pattern.size()):
            pair = pattern.getIthElement(i)
            absq = pair.getAbstraction()
            if isinstance(absq, Abstraction_Qualitative) and (not absq.hasEqualRelation()):
                return None
            if pair.getItem() == itemPair:
                return i
        return None

    def areInDifferentItemsets(self, pattern: "Pattern", p1: int, p2: int) -> bool:
        for i in range(p1 + 1, min(p2 + 1, pattern.size())):
            absq = pattern.getIthElement(i).getAbstraction()
            if isinstance(absq, Abstraction_Qualitative) and (not absq.hasEqualRelation()):
                return True
        return False


# ----------------------------------------------------------------------
# Pattern and related
# ----------------------------------------------------------------------

class ItemAbstractionPair:
    def __init__(self, item: Item, abstraction: Abstraction_Generic) -> None:
        self.item = item
        self.abstraction = abstraction

    def getItem(self) -> Item:
        return self.item

    def getAbstraction(self) -> Abstraction_Generic:
        return self.abstraction

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ItemAbstractionPair) and self.item == other.item and self.abstraction == other.abstraction

    def __hash__(self) -> int:
        return hash((self.item, self.abstraction))

    def compareTo(self, o: "ItemAbstractionPair") -> int:
        ic = self.item.compareTo(o.item)
        if ic == 0:
            return self.abstraction.compareTo(o.abstraction)
        return ic

    def __lt__(self, other: "ItemAbstractionPair") -> bool:
        return self.compareTo(other) < 0

    def __str__(self) -> str:
        if isinstance(self.abstraction, Abstraction_Qualitative):
            # Java: if qualitative => (abs + " " + item)
            return f"{self.abstraction}{' ' if str(self.abstraction) else ''}{self.item}"
        return f"{self.item}{self.abstraction} "

    def toStringToFile(self) -> str:
        if isinstance(self.abstraction, Abstraction_Qualitative):
            a = self.abstraction.toStringToFile()
            return f"{a}{' ' if a else ''}{self.item}"
        return f"{self.item}{self.abstraction} "


class Pattern:
    def __init__(self, elements: Optional[List[ItemAbstractionPair]] = None) -> None:
        self.elements: List[ItemAbstractionPair] = elements if elements is not None else []
        self.appearingIn: Set[int] = set()

    def getSupport(self) -> int:
        return len(self.appearingIn)

    def clonePatron(self) -> "Pattern":
        return Pattern(list(self.elements))

    def getElements(self) -> List[ItemAbstractionPair]:
        return self.elements

    def setElements(self, elements: List[ItemAbstractionPair]) -> None:
        self.elements = elements

    def add(self, pair: ItemAbstractionPair) -> None:
        self.elements.append(pair)

    def size(self) -> int:
        return len(self.elements)

    def getIthElement(self, i: int) -> ItemAbstractionPair:
        return self.elements[i]

    def setAppearingIn(self, appearingIn: Set[int]) -> None:
        self.appearingIn = set(appearingIn)

    def getAppearingIn(self) -> Set[int]:
        return self.appearingIn

    def compareTo(self, o: "Pattern") -> int:
        return self.getIthElement(self.size() - 1).compareTo(o.getIthElement(o.size() - 1))

    def __lt__(self, other: "Pattern") -> bool:
        return self.compareTo(other) < 0

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Pattern) and self.compareTo(other) == 0

    def concatenate(self, pair: ItemAbstractionPair) -> "Pattern":
        r = self.clonePatron()
        r.add(pair)
        return r

    def concatenar(self, pattern: "Pattern") -> "Pattern":
        r = self.clonePatron()
        r.elements.extend(pattern.getElements())
        return r

    def isSubpattern(self, abstractionCreator: AbstractionCreator, p: "Pattern") -> bool:
        positions = [0 for _ in range(self.size())]
        return abstractionCreator.isSubpattern(self, p, 0, positions)

    def __str__(self) -> str:
        return "".join(str(e) for e in self.elements)

    # ----------------- IMPORTANT FIX: correct SPMF printing -----------------
    def toStringToFile(self, outputSequenceIdentifiers: bool) -> str:
        """
        Correct SPMF-style printing:
          item item ... -1 item item ... -1 #SUP: X [#SID: ...]
        Build itemsets based on Abstraction_Qualitative:
          equalRelation=True  => same itemset
          equalRelation=False => new itemset
        """
        if not self.elements:
            base = f"#SUP: {self.getSupport()}"
            if outputSequenceIdentifiers:
                base += " #SID:"
            return base

        itemsets: List[List[str]] = []
        current: List[str] = [str(self.elements[0].getItem().getId())]

        for pair in self.elements[1:]:
            abs_ = pair.getAbstraction()
            if isinstance(abs_, Abstraction_Qualitative) and abs_.hasEqualRelation():
                current.append(str(pair.getItem().getId()))
            else:
                itemsets.append(current)
                current = [str(pair.getItem().getId())]

        itemsets.append(current)

        tokens: List[str] = []
        for itset in itemsets:
            tokens.extend(itset)
            tokens.append("-1")

        tokens.append("#SUP:")
        tokens.append(str(self.getSupport()))

        if outputSequenceIdentifiers:
            tokens.append("#SID:")
            for sid in sorted(self.appearingIn):
                tokens.append(str(sid - 1))  # same as Java comment (BUG FIX in Java output)
        return " ".join(tokens)


# ----------------------------------------------------------------------
# Creators (singletons)
# ----------------------------------------------------------------------

class ItemAbstractionPairCreator:
    _instance: Optional["ItemAbstractionPairCreator"] = None

    @staticmethod
    def getInstance() -> "ItemAbstractionPairCreator":
        if ItemAbstractionPairCreator._instance is None:
            ItemAbstractionPairCreator._instance = ItemAbstractionPairCreator()
        return ItemAbstractionPairCreator._instance

    @staticmethod
    def sclear() -> None:
        ItemAbstractionPairCreator._instance = None

    def getItemAbstractionPair(self, item: Item, abstraction: Abstraction_Generic) -> ItemAbstractionPair:
        return ItemAbstractionPair(item, abstraction)

    def clear(self) -> None:
        return


class PatternCreator:
    _instance: Optional["PatternCreator"] = None

    @staticmethod
    def getInstance() -> "PatternCreator":
        if PatternCreator._instance is None:
            PatternCreator._instance = PatternCreator()
        return PatternCreator._instance

    @staticmethod
    def sclear() -> None:
        PatternCreator._instance = None

    def createPattern(self, elements: Optional[List[ItemAbstractionPair]] = None) -> Pattern:
        return Pattern(elements)

    def concatenate(self, p1: Optional[Pattern], pair: Optional[ItemAbstractionPair]) -> Optional[Pattern]:
        if p1 is None:
            if pair is None:
                return None
            return Pattern([pair])
        if pair is None:
            return p1
        return p1.concatenate(pair)


# ----------------------------------------------------------------------
# Trie
# ----------------------------------------------------------------------

class TrieNode:
    def __init__(self, pair: ItemAbstractionPair, child: Optional["Trie"] = None, alreadyExplored: bool = False) -> None:
        self.pair = pair
        self.child = child
        self.alreadyExplored = alreadyExplored

    def getChild(self) -> Optional["Trie"]:
        return self.child

    def setChild(self, child: Optional["Trie"]) -> None:
        self.child = child

    def getPair(self) -> ItemAbstractionPair:
        return self.pair

    def setPair(self, pair: Optional[ItemAbstractionPair]) -> None:
        # allow nulling
        self.pair = pair  # type: ignore

    def isAlreadyExplored(self) -> bool:
        return self.alreadyExplored

    def setAlreadyExplored(self, v: bool) -> None:
        self.alreadyExplored = v

    def compareTo(self, o: Any) -> int:
        if isinstance(o, TrieNode):
            return self.pair.compareTo(o.pair)
        if isinstance(o, ItemAbstractionPair):
            return self.pair.compareTo(o)
        if isinstance(o, Item):
            return self.pair.getItem().compareTo(o)
        raise RuntimeError("Invalid compare type")

    def __lt__(self, other: "TrieNode") -> bool:
        return self.compareTo(other) < 0

    def __str__(self) -> str:
        return "{%s}, [%s]" % (self.pair, "NULL" if self.child is None else self.child)


class Trie:
    intId = 1

    def __init__(self, nodes: Optional[List[TrieNode]] = None, idList: Optional["IDList"] = None) -> None:
        self.nodes: List[TrieNode] = nodes if nodes is not None else []
        # Tin insert: nodei for i-extensions
        self.nodei: List[TrieNode] = []
        self.idList: Optional[IDList] = idList
        self.appearingIn: Set[int] = set()
        self.support: int = -1
        self.sumSequencesIDs: int = -1
        self.id = Trie.intId
        Trie.intId += 1

    def mergeWithTrie(self, trieNode: TrieNode) -> None:
        self.nodes.append(trieNode)

    def mergeWithTrie_i(self, trieNode: TrieNode) -> None:
        self.nodei.append(trieNode)

    def levelSize(self) -> int:
        return len(self.nodes) if self.nodes is not None else 0

    def levelSize_i(self) -> int:
        return len(self.nodei) if self.nodei is not None else 0

    def getNodes(self) -> List[TrieNode]:
        return self.nodes

    def setNodes(self, nodes: List[TrieNode]) -> None:
        self.nodes = nodes

    def getNode(self, index: int) -> TrieNode:
        return self.nodes[index]

    def getIdList(self) -> Optional["IDList"]:
        return self.idList

    def setIdList(self, idList: Optional["IDList"]) -> None:
        self.idList = idList

    def getAppearingIn(self) -> Set[int]:
        return self.appearingIn

    def setAppearingIn(self, appearingIn: Set[int]) -> None:
        self.appearingIn = set(appearingIn)
        self.support = -1
        self.sumSequencesIDs = -1

    def getSupport(self) -> int:
        if self.support < 0:
            self.support = len(self.appearingIn)
        return self.support

    def getSumIdSequences(self) -> int:
        if self.sumSequencesIDs < 0:
            self.sumSequencesIDs = sum(self.appearingIn)
        return self.sumSequencesIDs

    def sort(self) -> None:
        self.nodes.sort()
        self.nodei.sort()

    def removeAll(self) -> None:
        # Tin correct: if levelSize() == 0 || levelSize_i() == 0 return;
        if self.levelSize() == 0 and self.levelSize_i() == 0:
            return
        for node in self.nodes:
            child = node.getChild()
            if child is not None:
                child.removeAll()
            node.setChild(None)
            node.setPair(None)
        for node in self.nodei:
            child = node.getChild()
            if child is not None:
                child.removeAll()
            node.setChild(None)
            node.setPair(None)
        self.setIdList(None)
        self.nodes.clear()
        self.nodei.clear()
        self.appearingIn.clear()
        self.idList = None

    def preorderTraversal(self, p: Optional[Pattern]) -> Optional[List[Tuple[Pattern, "Trie"]]]:
        result: List[Tuple[Pattern, Trie]] = []
        prefix = p

        if self.nodes is not None:
            for node in self.nodes:
                newPattern = PatternCreator.getInstance().concatenate(prefix, node.getPair())
                child = node.getChild()
                if newPattern is None or child is None:
                    continue
                result.append((newPattern, child))
                if child is not None:
                    sub = child.preorderTraversal(newPattern)
                    if sub:
                        result.extend(sub)

        if self.nodei is not None:
            for node in self.nodei:
                newPattern = PatternCreator.getInstance().concatenate(prefix, node.getPair())
                child = node.getChild()
                if newPattern is None or child is None:
                    continue
                result.append((newPattern, child))
                if child is not None:
                    sub = child.preorderTraversal(newPattern)
                    if sub:
                        result.extend(sub)

        return result if (self.nodes is not None or self.nodei is not None) else None

    def __str__(self) -> str:
        if self.nodes is None:
            return ""
        s = f"ID={self.id}["
        if self.nodes:
            s += ",".join(str(n.getPair()) for n in self.nodes)
        else:
            s += "NULL"
        s += "]"
        # Tin insert
        s += ", ["
        if self.nodei:
            s += ",".join(str(n.getPair()) for n in self.nodei)
        else:
            s += "NULL"
        s += "]"
        return s

    def __lt__(self, other: "Trie") -> bool:
        return self.id < other.id


# ----------------------------------------------------------------------
# IDList interfaces and implementations
# ----------------------------------------------------------------------

class IDList:
    def join(self, idList: "IDList", equals: bool, minSupport: int) -> "IDList":
        raise NotImplementedError

    def getSupport(self) -> int:
        raise NotImplementedError

    def setAppearingInTrie(self, trie: Trie) -> None:
        raise NotImplementedError

    def setAppearingInPattern(self, pattern: Pattern) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def appearingInMap(self) -> Dict[int, List[Position]]:
        raise NotImplementedError

    def getTotalElementsAfterPrefixes(self) -> int:
        raise NotImplementedError

    def setTotalElementsAfterPrefixes(self, i: int) -> None:
        raise NotImplementedError

    def SetOriginalSequenceLengths(self, m: Dict[int, int]) -> None:
        raise NotImplementedError


class IDListStandard_Map(IDList):
    originalSizeOfSequences: Dict[int, int] = {}

    def __init__(self, sequencePositionsEntries: Optional[Dict[int, List[Position]]] = None) -> None:
        self.sequencePositionsEntries: Dict[int, List[Position]] = sequencePositionsEntries if sequencePositionsEntries is not None else {}
        self.sequences: Set[int] = set(self.sequencePositionsEntries.keys())
        self.totalElementsAfterPrefixes: int = 0

    @staticmethod
    def sclear() -> None:
        IDListStandard_Map.originalSizeOfSequences.clear()

    def getSequencePositionsEntries(self) -> Dict[int, List[Position]]:
        return self.sequencePositionsEntries

    def addAppearance(self, sequence: int, positionItem: Position) -> None:
        eids = self.sequencePositionsEntries.get(sequence)
        if eids is None:
            eids = []
        if positionItem not in eids:
            eids.append(positionItem)
            self.sequencePositionsEntries[sequence] = eids
            self.sequences.add(sequence)

    def addAppearancesInSequence(self, sid: int, itemsets: List[Position]) -> None:
        existing = self.sequencePositionsEntries.get(sid)
        if existing is None:
            existing = itemsets
        self.sequencePositionsEntries[sid] = existing
        self.sequences.add(sid)

    def getSupport(self) -> int:
        return len(self.sequences)

    def getTotalElementsAfterPrefixes(self) -> int:
        return self.totalElementsAfterPrefixes

    def setTotalElementsAfterPrefixes(self, i: int) -> None:
        self.totalElementsAfterPrefixes = i

    def SetOriginalSequenceLengths(self, m: Dict[int, int]) -> None:
        IDListStandard_Map.originalSizeOfSequences = m

    def setAppearingInTrie(self, trie: Trie) -> None:
        trie.setAppearingIn(set(self.sequences))

    def setAppearingInPattern(self, pattern: Pattern) -> None:
        pattern.setAppearingIn(set(self.sequences))

    def appearingInMap(self) -> Dict[int, List[Position]]:
        return self.sequencePositionsEntries

    def clear(self) -> None:
        self.sequencePositionsEntries.clear()
        self.sequences.clear()

    def __str__(self) -> str:
        out = []
        for sid, positions in self.sequencePositionsEntries.items():
            out.append("\t%d {%s}\n" % (sid, ",".join(str(p.getItemsetIndex()) for p in positions)))
        return "".join(out)

    def join(self, idList: IDList, equals: bool, minSupport: int) -> IDList:
        idStandard = idList  # expected IDListStandard_Map
        if not isinstance(idStandard, IDListStandard_Map):
            raise TypeError("This implementation only supports joining with IDListStandard_Map")

        # Tin modifies: use min size for capacity (not needed in python, but keep logic)
        _size = min(len(idStandard.getSequencePositionsEntries()), len(self.getSequencePositionsEntries()))
        intersection: Dict[int, List[Position]] = {}

        newSequences: Set[int] = set()
        newTotalElementsAfterPrefixes = [0]

        for sid, posListOther in idStandard.getSequencePositionsEntries().items():
            if equals:
                posAppear = self._equalOperation(sid, posListOther, newTotalElementsAfterPrefixes)
            else:
                posAppear = self._laterOperation(sid, posListOther, newTotalElementsAfterPrefixes)
            if posAppear is not None:
                intersection[sid] = posAppear
                newSequences.add(sid)

        out = IDListStandard_Map(intersection)
        out.sequences = newSequences
        out.setTotalElementsAfterPrefixes(newTotalElementsAfterPrefixes[0])
        return out

    def _laterOperation(self, sid: int, positionAppearancesInSequence: List[Position], dif: List[int]) -> Optional[List[Position]]:
        myList = self.sequencePositionsEntries.get(sid)
        if not myList:
            return None

        result: List[Position] = []
        index = -1
        for i in range(len(positionAppearancesInSequence)):
            eid = positionAppearancesInSequence[i].getItemsetIndex()
            if myList[0].getItemsetIndex() < eid:
                index = i
                break

        if index >= 0:
            for i in range(index, len(positionAppearancesInSequence)):
                pos = positionAppearancesInSequence[i]
                result.append(pos)
                if i == index:
                    dif[0] += (IDListStandard_Map.originalSizeOfSequences.get(sid, 0) - pos.getItemIndex())

        return result if result else None

    def _equalOperation(self, key: int, posOther: List[Position], dif: List[int]) -> Optional[List[Position]]:
        myList = self.sequencePositionsEntries.get(key)
        if not myList:
            return None

        result: List[Position] = []
        beginningIndex = 0

        if len(myList) <= len(posOther):
            listToExplore = myList
            listToSearch = posOther
        else:
            listToExplore = posOther
            listToSearch = myList

        # Tin modifies:
        twoFirstEventsEqual = False

        for eid in listToExplore:
            for i in range(beginningIndex, len(listToSearch)):
                current = listToSearch[i]
                comparison = (current.getItemsetIndex() > eid.getItemsetIndex()) - (current.getItemsetIndex() < eid.getItemsetIndex())
                if comparison >= 0:
                    if comparison == 0:
                        if eid.getItemIndex() > current.getItemIndex():
                            result.append(eid)
                            if not twoFirstEventsEqual:
                                dif[0] += (IDListStandard_Map.originalSizeOfSequences.get(key, 0) - eid.getItemIndex())
                        else:
                            result.append(current)
                            if not twoFirstEventsEqual:
                                dif[0] += (IDListStandard_Map.originalSizeOfSequences.get(key, 0) - current.getItemIndex())
                        twoFirstEventsEqual = True
                        beginningIndex = i + 1
                    break

        return result if result else None


class IdListCreator:
    def create(self) -> IDList:
        raise NotImplementedError

    def addAppearance(self, idlist: IDList, sequence: int, timestamp: int, item: int) -> None:
        raise NotImplementedError

    def addAppearancesInSequence(self, idlist: IDList, sequence: int, itemsets: List[Position]) -> None:
        raise NotImplementedError

    def initializeMaps(self, frequentItems: Dict[Item, TrieNode],
                       projectingDistanceMap: Dict[Item, Dict[int, List[int]]],
                       sequenceSize: Dict[int, int],
                       itemsetSequenceSize: Dict[int, List[int]]) -> None:
        raise NotImplementedError

    def updateProjectionDistance(self, projectingDistanceMap: Dict[Item, Dict[int, List[int]]],
                                 item: Item, id_: int, size: int, i: int) -> None:
        raise NotImplementedError


class IdListCreatorStandard_Map(IdListCreator):
    _instance: Optional["IdListCreatorStandard_Map"] = None

    @staticmethod
    def clear() -> None:
        IdListCreatorStandard_Map._instance = None

    @staticmethod
    def getInstance() -> "IdListCreatorStandard_Map":
        if IdListCreatorStandard_Map._instance is None:
            IdListCreatorStandard_Map._instance = IdListCreatorStandard_Map()
        return IdListCreatorStandard_Map._instance

    def create(self) -> IDList:
        return IDListStandard_Map({})

    def addAppearance(self, idlist: IDList, sequence: int, timestamp: int, item: int) -> None:
        if not isinstance(idlist, IDListStandard_Map):
            raise TypeError("Expected IDListStandard_Map")
        idlist.addAppearance(sequence, Position(timestamp, item))

    def addAppearancesInSequence(self, idlist: IDList, sequence: int, itemsets: List[Position]) -> None:
        if not isinstance(idlist, IDListStandard_Map):
            raise TypeError("Expected IDListStandard_Map")
        idlist.addAppearancesInSequence(sequence, itemsets)

    def initializeMaps(self, frequentItems: Dict[Item, TrieNode],
                       projectingDistance: Dict[Item, Dict[int, List[int]]],
                       sequenceSize: Dict[int, int],
                       itemsetSequenceSize: Dict[int, List[int]]) -> None:
        for it in list(frequentItems.keys()):
            node = frequentItems[it]
            seqMap = projectingDistance.get(it, {})
            totalProjected = 0
            for sid, elementsProjected in seqMap.items():
                # Tin modifies: only use elementsProjected[0]
                if elementsProjected:
                    totalProjected += sequenceSize.get(sid, 0) - elementsProjected[0]
            if node.getChild() is not None and node.getChild().getIdList() is not None:
                node.getChild().getIdList().setTotalElementsAfterPrefixes(totalProjected)

        # store original sizes globally
        dummy = IDListStandard_Map()
        dummy.SetOriginalSequenceLengths(sequenceSize)

    def updateProjectionDistance(self, projectingDistance: Dict[Item, Dict[int, List[int]]],
                                 item: Item, id_: int, itemsetCount: int, itemsCount: int) -> None:
        associated = projectingDistance.get(item)
        if associated is None:
            associated = {}
            projectingDistance[item] = associated
        lst = associated.get(id_)
        if lst is None:
            lst = []
            associated[id_] = lst
        lst.append(itemsCount)


# ----------------------------------------------------------------------
# Sequences container and Saver
# ----------------------------------------------------------------------

class Sequences:
    def __init__(self, name: str) -> None:
        self.levels: List[List[Pattern]] = [[]]
        self.numberOfFrequentSequences = 0
        self.name = name

    def addSequence(self, sequence: Pattern, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.numberOfFrequentSequences += 1

    def sort(self) -> None:
        for level in self.levels:
            level.sort(key=lambda p: [e.getItem().getId() for e in p.getElements()])

    def clear(self) -> None:
        for level in self.levels:
            level.clear()
        self.levels.clear()

    def toStringToFile(self, outputSequenceIdentifiers: bool) -> str:
        r = []
        levelCount = 0
        for level in self.levels:
            r.append(f"\n***Level {levelCount}***\n\n")
            for seq in level:
                r.append(seq.toStringToFile(outputSequenceIdentifiers))
                r.append("\n")
            levelCount += 1
        return "".join(r)


class Saver:
    def savePattern(self, p: Pattern) -> None:
        raise NotImplementedError

    def finish(self) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def print(self) -> str:
        raise NotImplementedError


class SaverIntoMemory(Saver):
    def __init__(self, outputSequenceIdentifiers: bool, name: str = "FREQUENT SEQUENTIAL PATTERNS") -> None:
        self.patterns = Sequences(name)
        self.outputSequenceIdentifiers = outputSequenceIdentifiers

    def savePattern(self, p: Pattern) -> None:
        self.patterns.addSequence(p, p.size())

    def finish(self) -> None:
        self.patterns.sort()

    def clear(self) -> None:
        self.patterns.clear()

    def print(self) -> str:
        return self.patterns.toStringToFile(self.outputSequenceIdentifiers)


class SaverIntoFile(Saver):
    def __init__(self, outputFilePath: str, outputSequenceIdentifiers: bool) -> None:
        self.path = outputFilePath
        self.outputSequenceIdentifiers = outputSequenceIdentifiers
        self._fh = open(outputFilePath, "w", encoding="utf-8")

    def savePattern(self, p: Pattern) -> None:
        self._fh.write(p.toStringToFile(self.outputSequenceIdentifiers))
        self._fh.write("\n")

    def finish(self) -> None:
        if self._fh:
            self._fh.close()

    def clear(self) -> None:
        self._fh = None  # type: ignore

    def print(self) -> str:
        return f"Content at file {self.path}"


# ----------------------------------------------------------------------
# SequenceDatabase
# ----------------------------------------------------------------------

class ItemFactory:
    def __init__(self) -> None:
        self.pool: Dict[Any, Item] = {}

    def getItem(self, key: Any) -> Item:
        it = self.pool.get(key)
        if it is None:
            it = Item(key)
            self.pool[key] = it
        return it


class SequenceDatabase:
    def __init__(self, abstractionCreator: AbstractionCreator, idListCreator: IdListCreator) -> None:
        self.abstractionCreator = abstractionCreator
        self.idListCreator = idListCreator

        # IMPORTANT: don't call this "frequentItems" because we need method frequent_items()
        self.frequent_items_map: Dict[Item, TrieNode] = {}
        self.sequences: List[Sequence] = []
        self.itemFactory = ItemFactory()
        self.nSequences = 1

        self.sequencesLengths: Dict[int, int] = {}
        self.sequenceItemsetSize: Dict[int, List[int]] = {}
        self.projectingDistance: Dict[Item, Dict[int, List[int]]] = {}

    def loadFile(self, path: str, minSupport: float) -> float:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line[0] in ("#", "%", "@"):
                    continue
                self.addSequence(line.split())

        support_abs = int(math.ceil(minSupport * len(self.sequences)))

        itemsToRemove: List[Item] = []
        for it, node in self.frequent_items_map.items():
            child = node.getChild()
            if child is None or child.getIdList() is None:
                itemsToRemove.append(it)
                continue
            if child.getIdList().getSupport() < support_abs:
                itemsToRemove.append(it)
            else:
                # set appearingIn using idlist sequences
                child.getIdList().setAppearingInTrie(child)

        for it in itemsToRemove:
            self.frequent_items_map.pop(it, None)

        self.reduceDatabase(set(self.frequent_items_map.keys()))
        self.idListCreator.initializeMaps(self.frequent_items_map, self.projectingDistance,
                                         self.sequencesLengths, self.sequenceItemsetSize)
        return float(support_abs)

    def addSequence(self, tokens: List[str]) -> None:
        pairCreator = ItemAbstractionPairCreator.getInstance()
        timestamp = -1

        seq = Sequence(len(self.sequences))
        itemset = Itemset()
        seq.setID(self.nSequences)

        sizeItemsetsList: List[int] = []

        for tok in tokens:
            if tok and tok[0] == "<":  # timestamp
                val = tok[1:-1]
                timestamp = int(val)
                itemset.setTimestamp(timestamp)
            elif tok == "-1":
                timestamp = itemset.getTimestamp() + 1
                seq.addItemset(itemset)
                itemset = Itemset()
                itemset.setTimestamp(timestamp)
                sizeItemsetsList.append(seq.length())
            elif tok == "-2":
                self.sequences.append(seq)
                self.nSequences += 1
                self.sequencesLengths[seq.getId()] = seq.length()
                self.sequenceItemsetSize[seq.getId()] = sizeItemsetsList
            else:
                # ignore "id(value)" format as Java did (no handling)
                if "(" in tok:
                    continue
                item = self.itemFactory.getItem(int(tok))
                node = self.frequent_items_map.get(item)
                if node is None:
                    idlist = self.idListCreator.create()
                    childTrie = Trie(None, idlist)
                    node = TrieNode(pairCreator.getItemAbstractionPair(item, self.abstractionCreator.createDefaultAbstraction()),
                                    childTrie)
                    self.frequent_items_map[item] = node

                idlist = node.getChild().getIdList()  # type: ignore
                if timestamp < 0:
                    timestamp = 1
                    itemset.setTimestamp(timestamp)
                itemset.addItem(item)
                # item position: seq.length() + itemset.size()
                self.idListCreator.addAppearance(idlist, seq.getId(), int(timestamp), seq.length() + itemset.size())
                self.idListCreator.updateProjectionDistance(self.projectingDistance, item, seq.getId(), seq.size(),
                                                           seq.length() + itemset.size())

    def reduceDatabase(self, frequentSet: Set[Item]) -> None:
        k = 0
        while k < len(self.sequences):
            seq = self.sequences[k]
            i = 0
            while i < seq.size():
                itset = seq.get(i)
                j = 0
                while j < itset.size():
                    it = itset.get(j)
                    if it not in frequentSet:
                        seq.remove(i, j)
                        continue
                    j += 1
                if itset.size() == 0:
                    seq.remove(i)
                    continue
                i += 1
            if seq.size() == 0:
                self.sequences.pop(k)
                continue
            k += 1

    def frequent_items(self) -> Trie:
        t = Trie()
        t.setNodes(list(self.frequent_items_map.values()))
        t.sort()
        return t

    def getSequences(self) -> List[Sequence]:
        return self.sequences

    def clear(self) -> None:
        self.sequences.clear()
        self.frequent_items_map.clear()
        self.projectingDistance.clear()
        self.sequenceItemsetSize.clear()
        self.sequencesLengths.clear()


# ----------------------------------------------------------------------
# FrequentPatternEnumeration_ClaSP (main recursion)
# ----------------------------------------------------------------------

class FrequentPatternEnumeration_ClaSP:
    def __init__(self, abstractionCreator: AbstractionCreator, minSupAbsolute: float,
                 saver: Saver, findClosedPatterns: bool, executePruningMethods: bool) -> None:
        self.joinCount = 0
        self.abstractionCreator = abstractionCreator
        self.minSupAbsolute = minSupAbsolute
        self.saver = saver
        self.matchingMap: Dict[int, Dict[int, List[Tuple[Pattern, Trie]]]] = {}
        self.findClosedPatterns = findClosedPatterns
        self.executePruningMethods = executePruningMethods
        self.numberOfFrequentPatterns = 0
        self.numberOfFrequentClosedPatterns = 0

        # Tin inserts:
        self.firstSequenceExtensions: List[TrieNode] = []

    def getFrequentPatterns(self) -> int:
        return self.numberOfFrequentPatterns

    def getFrequentClosedPatterns(self) -> int:
        return self.numberOfFrequentClosedPatterns

    def dfsPruning(self, patron: Pattern, trie: Trie, verbose: bool,
                   coocMapAfter: Dict[int, Dict[int, int]],
                   coocMapEquals: Dict[int, Dict[int, int]]) -> None:
        tam = trie.levelSize()
        self.firstSequenceExtensions = trie.getNodes()
        for i in range(tam):
            eq = trie.getNode(i)
            self.exploreChildren(Pattern([eq.getPair()]), eq,
                                 trie.getNodes(), trie.getNodes(),
                                 i + 1, coocMapAfter, coocMapEquals,
                                 eq.getPair().getItem())

    def exploreChildren(self, pattern: Pattern, currentNode: TrieNode,
                        sequenceExtensions: List[TrieNode], itemsetsExtensions: List[TrieNode],
                        beginning: int,
                        coocMapAfter: Dict[int, Dict[int, int]],
                        coocMapEquals: Dict[int, Dict[int, int]],
                        lastAppendedItem: Item) -> None:

        currentTrie = currentNode.getChild()
        if currentTrie is None or currentTrie.getIdList() is None:
            return

        isAvoidable = False
        if self.findClosedPatterns and self.executePruningMethods:
            isAvoidable = self.isAvoidable(pattern, currentTrie)

        self.numberOfFrequentPatterns += 1

        new_sequenceExtension: List[TrieNode] = []
        new_itemsetExtension: List[TrieNode] = []
        newPatterns: List[Pattern] = []
        newNodesToExtends: List[TrieNode] = []

        clone = pattern.clonePatron()

        # s-extensions
        if not isAvoidable:
            for node in sequenceExtensions:
                if coocMapAfter is not None:
                    m = coocMapAfter.get(int(lastAppendedItem.getId()))
                    if m is None:
                        continue
                    co = m.get(int(node.getPair().getItem().getId()))
                    if co is None or co < self.minSupAbsolute:
                        continue

                extension = Pattern(list(clone.getElements()))
                newPair = node.getPair()
                extension.add(newPair)

                self.joinCount += 1
                newIdList = currentTrie.getIdList().join(node.getChild().getIdList(), False, int(self.minSupAbsolute))  # type: ignore

                if newIdList.getSupport() >= self.minSupAbsolute:
                    newTrie = Trie(None, newIdList)
                    newIdList.setAppearingInTrie(newTrie)
                    newTrieNode = TrieNode(newPair, newTrie)
                    currentTrie.mergeWithTrie(newTrieNode)

                    newPatterns.append(extension)
                    newNodesToExtends.append(newTrieNode)
                    new_sequenceExtension.append(newTrieNode)

            for i in range(len(new_sequenceExtension)):
                newPattern = newPatterns[i]
                nodeToExtend = newNodesToExtends.pop(0)
                last = newPattern.getIthElement(newPattern.size() - 1).getItem()
                self.exploreChildren(newPattern, nodeToExtend,
                                     new_sequenceExtension, new_sequenceExtension,
                                     i + 1, coocMapAfter, coocMapEquals, last)

        newPatterns.clear()
        newNodesToExtends.clear()

        # i-extensions (equal relation)
        for k in range(beginning, len(itemsetsExtensions)):
            eq = itemsetsExtensions[k]

            if coocMapEquals is not None:
                m = coocMapEquals.get(int(lastAppendedItem.getId()))
                if m is None:
                    continue
                co = m.get(int(eq.getPair().getItem().getId()))
                if co is None or co < self.minSupAbsolute:
                    continue

            extension = Pattern(list(clone.getElements()))
            newPair = ItemAbstractionPairCreator.getInstance().getItemAbstractionPair(
                eq.getPair().getItem(),
                AbstractionCreator_Qualitative.getInstance().crearAbstraccion(True)
            )
            extension.add(newPair)

            self.joinCount += 1
            newIdList = currentTrie.getIdList().join(eq.getChild().getIdList(), True, int(self.minSupAbsolute))  # type: ignore

            if newIdList.getSupport() >= self.minSupAbsolute:
                newTrie = Trie(None, newIdList)
                newIdList.setAppearingInTrie(newTrie)
                newTrieNode = TrieNode(newPair, newTrie)

                # Tin inserts: i-extensions go to nodei
                currentTrie.mergeWithTrie_i(newTrieNode)

                newPatterns.append(extension)
                newNodesToExtends.append(newTrieNode)
                new_itemsetExtension.append(newTrieNode)

        for i in range(len(new_itemsetExtension)):
            newPattern = newPatterns[i]
            nodeToExtend = newNodesToExtends.pop(0)
            last = newPattern.getIthElement(newPattern.size() - 1).getItem()

            # Tin inserts: if avoidable reset sequence extension
            if isAvoidable:
                new_sequenceExtension = self.firstSequenceExtensions

            self.exploreChildren(newPattern, nodeToExtend,
                                 new_sequenceExtension, new_itemsetExtension,
                                 i + 1, coocMapAfter, coocMapEquals, last)

            # free idlist like Java
            if nodeToExtend.getChild() is not None:
                nodeToExtend.getChild().setIdList(None)

    # ---------------- pruning support ----------------

    def isAvoidable(self, prefix: Pattern, trie: Trie) -> bool:
        support = trie.getSupport()
        idList = trie.getIdList()
        if idList is None:
            return False

        key1 = trie.getSumIdSequences()
        prefixSize = prefix.size()
        key2 = self.key2(idList, trie)

        newEntry = (prefix, trie)

        associatedMap = self.matchingMap.get(key1)
        if associatedMap is None:
            associatedMap = {}
            associatedMap[key2] = [newEntry]
            self.matchingMap[key1] = associatedMap
            return False

        associatedList = associatedMap.get(key2)
        if associatedList is None:
            associatedMap[key2] = [newEntry]
            return False

        superPattern = 0
        i = 0
        while i < len(associatedList):
            p, t = associatedList[i]
            if support == t.getSupport():
                pSize = p.size()
                if pSize != prefixSize:
                    if prefixSize < pSize:
                        if prefix.isSubpattern(self.abstractionCreator, p):
                            trie.setNodes(t.getNodes())
                            return True
                    else:
                        if p.isSubpattern(self.abstractionCreator, prefix):
                            superPattern += 1
                            trie.setNodes(t.getNodes())
                            associatedList.pop(i)
                            continue
            i += 1

        associatedList.append(newEntry)
        if superPattern > 0:
            return True
        return False

    def key2(self, idlist: IDList, t: Trie) -> int:
        # key_standardAndSupport
        return idlist.getTotalElementsAfterPrefixes() + t.getSupport()

    def removeNonClosedPatterns(self, frequentPatterns: List[Tuple[Pattern, Trie]], keepPatterns: bool) -> None:
        self.numberOfFrequentClosedPatterns = 0

        totalPatterns: Dict[int, List[Pattern]] = {}
        for p, t in frequentPatterns:
            p.setAppearingIn(t.getAppearingIn())
            totalPatterns.setdefault(t.getSumIdSequences(), []).append(p)

        for lst in totalPatterns.values():
            i = 0
            while i < len(lst):
                j = i + 1
                while j < len(lst):
                    p1 = lst[i]
                    p2 = lst[j]
                    if len(p1.getAppearingIn()) == len(p2.getAppearingIn()):
                        if p1.size() != p2.size():
                            if p1.size() < p2.size():
                                if p1.isSubpattern(self.abstractionCreator, p2):
                                    lst.pop(i)
                                    i -= 1
                                    break
                            else:
                                if p2.isSubpattern(self.abstractionCreator, p1):
                                    lst.pop(j)
                                    j -= 1
                    j += 1
                i += 1

        for lst in totalPatterns.values():
            self.numberOfFrequentClosedPatterns += len(lst)
            if keepPatterns:
                for p in lst:
                    self.saver.savePattern(p)

    def clear(self) -> None:
        self.matchingMap.clear()


# ----------------------------------------------------------------------
# AlgoCM_ClaSP
# ----------------------------------------------------------------------

class AlgoCM_ClaSP:
    def __init__(self, supportAbs: float, abstractionCreator: AbstractionCreator,
                 findClosedPatterns: bool, executePruningMethods: bool) -> None:
        self.minSupAbsolute = supportAbs
        self.abstractionCreator = abstractionCreator
        self.findClosedPatterns = findClosedPatterns
        self.executePruningMethods = executePruningMethods
        self.saver: Optional[Saver] = None

        self.overallStart = 0.0
        self.overallEnd = 0.0
        self.mainMethodStart = 0.0
        self.mainMethodEnd = 0.0
        self.postProcessingStart = 0.0
        self.postProcessingEnd = 0.0

        self.FrequentAtomsTrie: Optional[Trie] = None
        self.numberOfFrequentPatterns = 0
        self.numberOfFrequentClosedPatterns = 0
        self.joinCount = 0

    def runAlgorithm(self, database: SequenceDatabase, keepPatterns: bool, verbose: bool,
                     outputFilePath: Optional[str], outputSequenceIdentifiers: bool) -> None:
        if outputFilePath is None:
            self.saver = SaverIntoMemory(outputSequenceIdentifiers)
        else:
            self.saver = SaverIntoFile(outputFilePath, outputSequenceIdentifiers)

        MemoryLogger.getInstance().reset()
        self.overallStart = time.time()

        self.claSP(database, self.minSupAbsolute, keepPatterns, verbose,
                   self.findClosedPatterns, self.executePruningMethods)

        self.overallEnd = time.time()
        self.saver.finish()  # type: ignore

    def claSP(self, database: SequenceDatabase, minSupAbsolute: float,
              keepPatterns: bool, verbose: bool,
              findClosedPatterns: bool, executePruningMethods: bool) -> None:

        # FIX: call method frequent_items(), not a dict
        self.FrequentAtomsTrie = database.frequent_items()

        coocMapAfter: Dict[int, Dict[int, int]] = {}
        coocMapEquals: Dict[int, Dict[int, int]] = {}

        for seq in database.getSequences():
            alreadySeenA: Set[int] = set()
            alreadySeenB_equals: Dict[int, Set[int]] = {}

            for i in range(len(seq.getItemsets())):
                itemsetA = seq.get(i)
                for j in range(itemsetA.size()):
                    itemA = int(itemsetA.get(j).getId())

                    alreadyDoneForItemA = itemA in alreadySeenA
                    equalSet = alreadySeenB_equals.get(itemA)
                    if equalSet is None:
                        equalSet = set()
                        alreadySeenB_equals[itemA] = equalSet

                    mapEq = coocMapEquals.get(itemA)
                    mapAfter = None if alreadyDoneForItemA else coocMapAfter.get(itemA)

                    # equals in same itemset
                    for k in range(j + 1, itemsetA.size()):
                        itemB = int(itemsetA.get(k).getId())
                        if itemB not in equalSet:
                            if mapEq is None:
                                mapEq = {}
                                coocMapEquals[itemA] = mapEq
                            mapEq[itemB] = mapEq.get(itemB, 0) + 1
                            equalSet.add(itemB)

                    # after in later itemsets (unique per itemB)
                    if not alreadyDoneForItemA:
                        alreadySeenB_after: Set[int] = set()
                        for k in range(i + 1, len(seq.getItemsets())):
                            itemsetB = seq.get(k)
                            for m in range(itemsetB.size()):
                                itemB = int(itemsetB.get(m).getId())
                                if itemB in alreadySeenB_after:
                                    continue
                                if mapAfter is None:
                                    mapAfter = {}
                                    coocMapAfter[itemA] = mapAfter
                                mapAfter[itemB] = mapAfter.get(itemB, 0) + 1
                                alreadySeenB_after.add(itemB)
                        alreadySeenA.add(itemA)

        database.clear()

        fpe = FrequentPatternEnumeration_ClaSP(self.abstractionCreator, minSupAbsolute,
                                              self.saver, findClosedPatterns, executePruningMethods)  # type: ignore

        self.mainMethodStart = time.time()
        fpe.dfsPruning(Pattern(), self.FrequentAtomsTrie, verbose, coocMapAfter, coocMapEquals)  # type: ignore
        self.mainMethodEnd = time.time()

        self.numberOfFrequentPatterns = fpe.getFrequentPatterns()
        MemoryLogger.getInstance().checkMemory()

        if verbose:
            print(f"ClaSP: main part {(self.mainMethodEnd - self.mainMethodStart):.3f}s, patterns {self.numberOfFrequentPatterns}")

        if findClosedPatterns:
            outputPatternsFromMain = self.FrequentAtomsTrie.preorderTraversal(None)  # type: ignore
            self.postProcessingStart = time.time()
            fpe.removeNonClosedPatterns(outputPatternsFromMain or [], keepPatterns)
            self.postProcessingEnd = time.time()
            self.numberOfFrequentClosedPatterns = fpe.getFrequentClosedPatterns()
            if verbose:
                print(f"ClaSP: post part {(self.postProcessingEnd - self.postProcessingStart):.3f}s, closed {self.numberOfFrequentClosedPatterns}")
        else:
            if keepPatterns:
                outputPatternsFromMain = self.FrequentAtomsTrie.preorderTraversal(None)  # type: ignore
                for p, _t in (outputPatternsFromMain or []):
                    self.saver.savePattern(p)  # type: ignore

        self.numberOfFrequentPatterns = fpe.getFrequentPatterns()
        self.joinCount = fpe.joinCount
        fpe.clear()
        MemoryLogger.getInstance().checkMemory()

    def printStatistics(self) -> str:
        r = []
        r.append("=============  Algorithm - STATISTICS =============\n")
        r.append(f" Total time ~ {int(self.getRunningTime())} ms\n")
        r.append(f" Frequent closed sequences count : {self.numberOfFrequentClosedPatterns}\n")
        r.append(f" Join count : {self.joinCount}\n")
        r.append(f" Max memory (mb):{MemoryLogger.getInstance().getMaxMemory()}\n")
        r.append(self.saver.print() if self.saver else "")
        r.append("\n===================================================\n")
        return "".join(r)

    def getNumberOfFrequentPatterns(self) -> int:
        return self.numberOfFrequentPatterns

    def getNumberOfFrequentClosedPatterns(self) -> int:
        return self.numberOfFrequentClosedPatterns

    def getRunningTime(self) -> float:
        return (self.overallEnd - self.overallStart) * 1000.0

    def clear(self) -> None:
        if self.FrequentAtomsTrie:
            self.FrequentAtomsTrie.removeAll()
        self.abstractionCreator = None  # type: ignore

    def getFrequentAtomsTrie(self) -> Optional[Trie]:
        return self.FrequentAtomsTrie


# ----------------------------------------------------------------------
# Path helpers + main
# ----------------------------------------------------------------------

def file_to_path(filename: str) -> str:
    """
    Look for the file next to cmclasp.py first, then try Java/src/cmclasp/.
    """
    here = Path(__file__).resolve().parent

    p1 = here / filename
    if p1.exists():
        return str(p1)

    p2 = Path("Java") / "src" / "cmclasp" / filename
    if p2.exists():
        return str(p2.resolve())

    raise FileNotFoundError(
        f"Could not locate {filename}. Tried:\n- {p1}\n- {p2.resolve()}"
    )


def main() -> None:
    # --------------------------------------------------
    # Set parameters directly here
    # --------------------------------------------------
    input_path = file_to_path("contextPrefixSpan.txt")
    output_path = Path(__file__).resolve().parent / "output_py.txt"

    support = 0.5
    keepPatterns = True
    verbose = True
    findClosedPatterns = True
    executePruningMethods = True
    outputSequenceIdentifiers = False
    # --------------------------------------------------

    output_path.parent.mkdir(parents=True, exist_ok=True)

    abstractionCreator = AbstractionCreator_Qualitative.getInstance()
    idListCreator = IdListCreatorStandard_Map.getInstance()

    db = SequenceDatabase(abstractionCreator, idListCreator)
    minsup_abs = db.loadFile(input_path, support)

    algo = AlgoCM_ClaSP(minsup_abs, abstractionCreator, findClosedPatterns, executePruningMethods)
    algo.runAlgorithm(db, keepPatterns, verbose, str(output_path), outputSequenceIdentifiers)

    print("Minsup (relative) :", support)
    print(algo.getNumberOfFrequentPatterns(), "patterns found.")
    print("Input file :", Path(input_path).resolve())
    print("Output file:", output_path.resolve())
    if verbose and keepPatterns:
        print(algo.printStatistics())


if __name__ == "__main__":
    main()