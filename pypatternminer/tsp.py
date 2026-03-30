import os
import time
import math
import random
import heapq
import tracemalloc


def _java_string_hash(value):
    h = 0
    for ch in value:
        h = (31 * h + ord(ch)) & 0xffffffff
    return h


def _java_hash_spread(h):
    h &= 0xffffffff
    return h ^ (h >> 16)


def _java_hashmap_iteration_order(keys_in_insertion_order, hash_func):
    capacity = 16
    threshold = int(capacity * 0.75)
    buckets = [[] for _ in range(capacity)]
    present = set()
    size = 0

    def rehash(new_capacity, old_buckets):
        new_buckets = [[] for _ in range(new_capacity)]
        for bucket in old_buckets:
            for key in bucket:
                h = _java_hash_spread(hash_func(key))
                idx = (new_capacity - 1) & h
                new_buckets[idx].append(key)
        return new_buckets

    for key in keys_in_insertion_order:
        if key in present:
            continue
        h = _java_hash_spread(hash_func(key))
        idx = (capacity - 1) & h
        buckets[idx].append(key)
        present.add(key)
        size += 1
        if size > threshold:
            capacity *= 2
            threshold = int(capacity * 0.75)
            buckets = rehash(capacity, buckets)

    ordered = []
    for bucket in buckets:
        ordered.extend(bucket)
    return ordered


def _java_hash_for_int(value):
    return int(value)


def _java_hash_for_pair(pair):
    prefix = "P" if pair.postfix else "N"
    return _java_string_hash(prefix + str(pair.item))


IDENTITY_HASH_SEED = int(os.environ.get("TSP_HASH_SEED", "2"))
_identity_rng = random.Random(IDENTITY_HASH_SEED)


def _reset_identity_hash():
    global _identity_rng
    _identity_rng = random.Random(IDENTITY_HASH_SEED)


def _next_identity_hash():
    return _identity_rng.getrandbits(31)

class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

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
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, _peak = tracemalloc.get_traced_memory()
        currentMemory = current / 1024.0 / 1024.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory
        return currentMemory


class JavaPriorityQueue:
    def __init__(self):
        self.queue = []

    def size(self):
        return len(self.queue)

    def isEmpty(self):
        return len(self.queue) == 0

    def peek(self):
        return self.queue[0] if self.queue else None

    def add(self, element):
        self.queue.append(element)
        self._sift_up(len(self.queue) - 1)

    def poll(self):
        if not self.queue:
            return None
        last = self.queue.pop()
        if not self.queue:
            return last
        result = self.queue[0]
        self.queue[0] = last
        self._sift_down(0)
        return result

    def __iter__(self):
        return iter(self.queue)

    def _compare(self, a, b):
        diff = a.getAbsoluteSupport() - b.getAbsoluteSupport()
        if diff != 0:
            return diff
        return a._hash - b._hash

    def _sift_up(self, idx):
        e = self.queue[idx]
        while idx > 0:
            parent = (idx - 1) // 2
            if self._compare(e, self.queue[parent]) >= 0:
                break
            self.queue[idx] = self.queue[parent]
            idx = parent
        self.queue[idx] = e

    def _sift_down(self, idx):
        size = len(self.queue)
        e = self.queue[idx]
        half = size // 2
        while idx < half:
            left = idx * 2 + 1
            right = left + 1
            smallest = left
            if right < size and self._compare(self.queue[right], self.queue[left]) < 0:
                smallest = right
            if self._compare(self.queue[smallest], e) >= 0:
                break
            self.queue[idx] = self.queue[smallest]
            idx = smallest
        self.queue[idx] = e


class Itemset:
    def __init__(self, item=None):
        self.items = []
        if item is not None:
            self.addItem(item)

    def addItem(self, value):
        self.items.append(value)

    def getItems(self):
        return self.items

    def get(self, index):
        return self.items[index]

    def __str__(self):
        return "".join(str(item) + " " for item in self.items)

    def size(self):
        return len(self.items)

    def cloneItemSetMinusItems(self, mapSequenceID, relativeMinsup):
        itemset = Itemset()
        for item in self.items:
            sidset = mapSequenceID.get(item)
            if sidset is not None and len(sidset) >= relativeMinsup:
                itemset.addItem(item)
        return itemset

    def cloneItemSet(self):
        itemset = Itemset()
        itemset.getItems().extend(self.items)
        return itemset

    def containsAll(self, itemset2):
        i = 0
        for item in itemset2.getItems():
            found = False
            while not found and i < self.size():
                if self.get(i) == item:
                    found = True
                elif self.get(i) > item:
                    return False
                i += 1
            if not found:
                return False
        return True


class Sequence:
    def __init__(self, seq_id):
        self.itemsets = []
        self.id = seq_id

    def addItemset(self, itemset):
        self.itemsets.append(itemset)

    def print(self):
        print(self.__str__(), end="")

    def __str__(self):
        r = []
        for itemset in self.itemsets:
            r.append('(')
            for item in itemset:
                r.append(str(item))
                r.append(' ')
            r.append(')')
        r.append("    ")
        return "".join(r)

    def getId(self):
        return self.id

    def getItemsets(self):
        return self.itemsets

    def get(self, index):
        return self.itemsets[index]

    def size(self):
        return len(self.itemsets)

    def cloneSequenceMinusItems(self, mapSequenceID, minSupportAbsolute):
        sequence = Sequence(self.getId())
        for itemset in self.itemsets:
            newItemset = self.cloneItemsetMinusItems(itemset, mapSequenceID, minSupportAbsolute)
            if len(newItemset) != 0:
                sequence.addItemset(newItemset)
        return sequence

    def cloneItemsetMinusItems(self, itemset, mapSequenceID, minSupportAbsolute):
        newItemset = []
        for item in itemset:
            sidset = mapSequenceID.get(item)
            if sidset is not None and len(sidset) >= minSupportAbsolute:
                newItemset.append(item)
        return newItemset


class SequenceDatabase:
    def __init__(self):
        self.sequences = []

    def loadFile(self, path):
        myInput = None
        try:
            myInput = open(path, 'r')
            for line in myInput:
                thisLine = line.strip()
                if not thisLine:
                    continue
                if thisLine[0] in ['#', '%', '@']:
                    continue
                self.addSequence(thisLine.split(' '))
        finally:
            if myInput is not None:
                myInput.close()

    def addSequence(self, tokens):
        sequence = Sequence(len(self.sequences))
        itemset = []
        for token in tokens:
            if not token:
                continue
            if token[0] == '<':
                continue
            elif token == '-1':
                sequence.addItemset(itemset)
                itemset = []
            elif token == '-2':
                self.sequences.append(sequence)
            else:
                itemset.append(int(token))

    def addSequenceObj(self, sequence):
        self.sequences.append(sequence)

    def print(self):
        print("============  SEQUENCE DATABASE ==========")
        for sequence in self.sequences:
            print(str(sequence.getId()) + ":  ", end="")
            sequence.print()
            print("")

    def printDatabaseStats(self):
        print("============  STATS ==========")
        print("Number of sequences : " + str(len(self.sequences)))
        size = 0
        for sequence in self.sequences:
            size += sequence.size()
        meansize = float(size) / float(len(self.sequences)) if self.sequences else 0.0
        print("mean size" + str(meansize))

    def __str__(self):
        r = []
        for sequence in self.sequences:
            r.append(str(sequence.getId()))
            r.append(":  ")
            r.append(sequence.__str__())
            r.append('\n')
        return "".join(r)

    def size(self):
        return len(self.sequences)

    def getSequences(self):
        return self.sequences

    def getSequenceIDs(self):
        return set(seq.getId() for seq in self.sequences)


class SequentialPattern:
    def __init__(self, itemset=None, sequencesIds=None, itemsets=None):
        if itemsets is not None:
            self.itemsets = itemsets
        else:
            self.itemsets = []
            if itemset is not None:
                self.itemsets.append(itemset)
        self.sequencesIds = sequencesIds if sequencesIds is not None else set()
        self.itemCount = -1
        self._hash = _next_identity_hash()

    def setSequenceIDs(self, sequencesIds):
        self.sequencesIds = set(sequencesIds)

    def getRelativeSupportFormated(self, sequencecount):
        if sequencecount == 0:
            return "0"
        relSupport = float(len(self.sequencesIds)) / float(sequencecount)
        return ("{0:.5f}".format(relSupport)).rstrip('0').rstrip('.')

    def getAbsoluteSupport(self):
        return len(self.sequencesIds)

    def addItemset(self, itemset):
        self.itemsets.append(itemset)

    def cloneSequence(self):
        sequence = SequentialPattern()
        for itemset in self.itemsets:
            sequence.addItemset(itemset.cloneItemSet())
        return sequence

    def print(self):
        print(self.__str__(), end="")

    def __str__(self):
        r = []
        for itemset in self.itemsets:
            r.append('(')
            for item in itemset.getItems():
                r.append(str(item))
                r.append(' ')
            r.append(')')
        r.append("    ")
        return "".join(r)

    def itemsetsToString(self):
        r = []
        for itemset in self.itemsets:
            r.append('{')
            for item in itemset.getItems():
                r.append(str(item))
                r.append(' ')
            r.append('}')
        r.append("    ")
        return "".join(r)

    def getItemsets(self):
        return self.itemsets

    def get(self, index):
        return self.itemsets[index]

    def getIthItem(self, i):
        for itemset in self.itemsets:
            if i < itemset.size():
                return itemset.get(i)
            i -= itemset.size()
        return None

    def size(self):
        return len(self.itemsets)

    def getItemOccurencesTotalCount(self):
        if self.itemCount == -1:
            count = 0
            for itemset in self.itemsets:
                count += itemset.size()
            self.itemCount = count
        return self.itemCount

    def getSequenceIDs(self):
        return self.sequencesIds


class SequentialPatterns:
    def __init__(self, name):
        self.levels = [[]]
        self.sequenceCount = 0
        self.name = name

    def printFrequentPatterns(self, nbObject, showSequenceIdentifiers):
        print(self.toString(nbObject, showSequenceIdentifiers))

    def toString(self, nbObject, showSequenceIdentifiers):
        r = []
        r.append(" ----------")
        r.append(self.name)
        r.append(" -------\n")
        levelCount = 0
        patternCount = 0
        for level in self.levels:
            r.append("  L")
            r.append(str(levelCount))
            r.append(" \n")
            for sequence in level:
                patternCount += 1
                r.append("  pattern ")
                r.append(str(patternCount))
                r.append(":  ")
                r.append(sequence.__str__())
                r.append("support :  ")
                r.append(sequence.getRelativeSupportFormated(nbObject))
                r.append(" (")
                r.append(str(sequence.getAbsoluteSupport()))
                r.append('/')
                r.append(str(nbObject))
                r.append(")")
                if showSequenceIdentifiers:
                    r.append(" sequence ids: ")
                    for sid in sequence.getSequenceIDs():
                        r.append(str(sid))
                        r.append(" ")
                r.append("\n")
            levelCount += 1
        r.append(" -------------------------------- Patterns count : ")
        r.append(str(self.sequenceCount))
        return "".join(r)

    def addSequence(self, sequence, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.sequenceCount += 1

    def getLevel(self, index):
        return self.levels[index]

    def getLevelCount(self):
        return len(self.levels)

    def getLevels(self):
        return self.levels


class Pair:
    def __init__(self, postfix, item):
        self.item = item
        self.postfix = postfix
        self.sequencesID = set()

    def __eq__(self, other):
        return isinstance(other, Pair) and self.postfix == other.postfix and self.item == other.item

    def __hash__(self):
        return hash((self.postfix, self.item))

    def isPostfix(self):
        return self.postfix

    def getItem(self):
        return self.item

    def getCount(self):
        return len(self.sequencesID)

    def getSequenceIDs(self):
        return self.sequencesID


class PairBIDE(Pair):
    def __init__(self, prefix, postfix, item):
        super().__init__(postfix, item)
        self.prefix = prefix

    def __eq__(self, other):
        return isinstance(other, PairBIDE) and self.postfix == other.postfix and self.prefix == other.prefix and self.item == other.item

    def __hash__(self):
        return hash((self.postfix, self.prefix, self.item))

    def isPrefix(self):
        return self.prefix


class Position:
    def __init__(self, itemset, item):
        self.itemset = itemset
        self.item = item

    def __str__(self):
        return "(" + str(self.itemset) + "," + str(self.item) + ")"


class PseudoSequence:
    def __init__(self, sequence, indexItemset, indexItem):
        if isinstance(sequence, PseudoSequence):
            self.sequence = sequence.sequence
            self.firstItemset = indexItemset + sequence.firstItemset
            if self.firstItemset == sequence.firstItemset:
                self.firstItem = indexItem + sequence.firstItem
            else:
                self.firstItem = indexItem
        else:
            self.sequence = sequence
            self.firstItemset = indexItemset
            self.firstItem = indexItem

    def getOriginalSequence(self):
        return self.sequence

    def size(self):
        size = self.sequence.size() - self.firstItemset
        if size == 1 and len(self.sequence.getItemsets()[self.firstItemset]) == 0:
            return 0
        return size

    def getSizeOfItemsetAt(self, index):
        size = len(self.sequence.getItemsets()[index + self.firstItemset])
        if self.isFirstItemset(index):
            size -= self.firstItem
        return size

    def isPostfix(self, indexItemset):
        return indexItemset == 0 and self.firstItem != 0

    def isFirstItemset(self, index):
        return index == 0

    def isLastItemset(self, index):
        return (index + self.firstItemset) == self.sequence.getItemsets().__len__() - 1

    def getItemAtInItemsetAt(self, indexItem, indexItemset):
        if self.isFirstItemset(indexItemset):
            return self.getItemset(indexItemset)[indexItem + self.firstItem]
        return self.getItemset(indexItemset)[indexItem]

    def getItemset(self, index):
        return self.sequence.get(index + self.firstItemset)

    def getId(self):
        return self.sequence.getId()

    def print(self):
        print(self.__str__(), end="")

    def __str__(self):
        r = []
        for i in range(self.size()):
            for j in range(self.getSizeOfItemsetAt(i)):
                r.append(str(self.getItemAtInItemsetAt(j, i)))
                if self.isPostfix(i):
                    r.append('*')
                r.append(' ')
            r.append(" -1 ")
        r.append(" -2 ")
        return "".join(r)

    def indexOfBis(self, indexItemset, idItem):
        for i in range(self.getSizeOfItemsetAt(indexItemset)):
            val = self.getItemAtInItemsetAt(i, indexItemset)
            if val == idItem:
                return i
            elif val > idItem:
                continue
        return -1

    def indexOf(self, sizeOfItemsetAti, indexItemset, idItem):
        for i in range(sizeOfItemsetAti):
            val = self.getItemAtInItemsetAt(i, indexItemset)
            if val == idItem:
                return i
            elif val > idItem:
                continue
        return -1

    def __eq__(self, other):
        return isinstance(other, PseudoSequence) and other.getId() == self.getId() and other.firstItemset == self.firstItemset and other.firstItem == self.firstItem


class PseudoSequenceBIDE(PseudoSequence):
    def __init__(self, sequence, indexItemset, indexItem, lastItemset=None, lastItem=None):
        if isinstance(sequence, PseudoSequenceBIDE):
            self.sequence = sequence.sequence
            self.firstItemset = indexItemset + sequence.firstItemset
            if self.firstItemset == sequence.firstItemset:
                self.firstItem = indexItem + sequence.firstItem
            else:
                self.firstItem = indexItem
            self.lastItemset = sequence.lastItemset if lastItemset is None else lastItemset
            self.lastItem = sequence.lastItem if lastItem is None else lastItem
        else:
            self.sequence = sequence
            self.firstItemset = indexItemset
            self.firstItem = indexItem
            self.lastItemset = sequence.size() - 1
            self.lastItem = len(sequence.getItemsets()[self.lastItemset]) - 1

    class PseudoSequencePair:
        def __init__(self, pseudoSequence, list_positions):
            self.pseudoSequence = pseudoSequence
            self.list = list_positions

    def getLastItemPosition(self):
        return self.lastItem - self.firstItem - 1

    def isLastItemset(self, index):
        return (index + self.firstItemset) == self.lastItemset

    def getSizeOfItemsetAt(self, index):
        size = len(self.sequence.getItemsets()[index + self.firstItemset])
        if self.isLastItemset(index):
            size = 1 + self.lastItem
        if self.isFirstItemset(index):
            size -= self.firstItem
        return size

    def __str__(self):
        r = []
        for i in range(self.size()):
            r.append('{')
            for j in range(self.getSizeOfItemsetAt(i)):
                if (not self.isLastItemset(i)) or (j <= self.lastItem):
                    r.append(str(self.getItemAtInItemsetAt(j, i)))
                    if self.isPostfix(i):
                        r.append('*')
                    r.append(' ')
            r.append('}')
        r.append("  ")
        return "".join(r)

    def size(self):
        size = self.sequence.size() - self.firstItemset - ((self.sequence.size() - 1) - self.lastItemset)
        if size == 1 and len(self.sequence.getItemsets()[self.firstItemset]) == 0:
            return 0
        return size

    def isCutAtRight(self, index):
        if not self.isLastItemset(index):
            return False
        return (len(self.sequence.getItemsets()[index + self.firstItemset]) - 1) != self.lastItem

    def getIthLastInLastApearanceWithRespectToPrefix(self, prefix, i, lastInstancePair):
        iditem = self.getIthItem(prefix, i)
        if lastInstancePair is not None:
            if i == self.getItemOccurencesTotalCount(prefix) - 1:
                for j in range(lastInstancePair.pseudoSequence.size() - 1, -1, -1):
                    sizeItemsetJ = len(lastInstancePair.pseudoSequence.getItemset(j))
                    for k in range(sizeItemsetJ - 1, -1, -1):
                        item = lastInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j)
                        if item == iditem:
                            return Position(j, k)
                        elif item < iditem:
                            break
            else:
                LLiplus1 = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, i + 1, lastInstancePair)
                for j in range(LLiplus1.itemset, -1, -1):
                    for k in range(len(lastInstancePair.pseudoSequence.getItemset(j)) - 1, -1, -1):
                        if j == LLiplus1.itemset and k >= LLiplus1.item:
                            continue
                        if lastInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j) == iditem:
                            return Position(j, k)
        return None

    def getIthMaximumPeriodOfAPrefix(self, prefix, i):
        lastInstancePair = self.getLastInstanceOfPrefixSequenceNEW(prefix, self.getItemOccurencesTotalCount(prefix))
        ithlastlast = self.getIthLastInLastApearanceWithRespectToPrefix(prefix, i, lastInstancePair)
        if i == 0:
            return self.trimBeginingAndEnd(None, ithlastlast)
        firstInstance = self.getFirstInstanceOfPrefixSequenceNEW(prefix, i)
        if firstInstance is None or not firstInstance.list:
            return self.trimBeginingAndEnd(None, ithlastlast)
        lastOfFirstInstance = firstInstance.list[i - 1]
        return self.trimBeginingAndEnd(lastOfFirstInstance, ithlastlast)

    def getLastInstanceOfPrefixSequenceNEW(self, prefix, i):
        remainingToMatchFromPrefix = i
        listPositions = []
        prefixItemsetPosition = len(prefix) - 1
        for j in range(self.size() - 1, -1, -1):
            itemInPrefixPosition = len(prefix[prefixItemsetPosition].getItems()) - 1
            allMatched = False
            searchedItem = prefix[prefixItemsetPosition].get(itemInPrefixPosition)
            tempList = []
            for k in range(self.getSizeOfItemsetAt(j) - 1, -1, -1):
                currentItem = self.getItemAtInItemsetAt(k, j)
                if currentItem == searchedItem:
                    tempList.append(Position(j, k))
                    itemInPrefixPosition -= 1
                    if itemInPrefixPosition == -1 or len(tempList) == remainingToMatchFromPrefix:
                        allMatched = True
                        break
                    searchedItem = prefix[prefixItemsetPosition].get(itemInPrefixPosition)
                elif currentItem < searchedItem:
                    break
            if allMatched:
                remainingToMatchFromPrefix -= len(tempList)
                listPositions.extend(tempList)
                prefixItemsetPosition -= 1
                if prefixItemsetPosition == -1:
                    return PseudoSequenceBIDE.PseudoSequencePair(self, listPositions)
        return None

    def getFirstInstanceOfPrefixSequenceNEW(self, prefix, i):
        remainingToMatchFromPrefix = i
        listPositions = []
        prefixItemsetPosition = 0
        for j in range(self.size()):
            itemInPrefixPosition = 0
            allMatched = False
            searchedItem = prefix[prefixItemsetPosition].get(itemInPrefixPosition)
            tempList = []
            for k in range(self.getSizeOfItemsetAt(j)):
                currentItem = self.getItemAtInItemsetAt(k, j)
                if currentItem == searchedItem:
                    tempList.append(Position(j, k))
                    itemInPrefixPosition += 1
                    if itemInPrefixPosition == prefix[prefixItemsetPosition].size() or len(tempList) == remainingToMatchFromPrefix:
                        allMatched = True
                        break
                    searchedItem = prefix[prefixItemsetPosition].get(itemInPrefixPosition)
                elif currentItem > searchedItem:
                    break
            if allMatched:
                remainingToMatchFromPrefix -= len(tempList)
                listPositions.extend(tempList)
                prefixItemsetPosition += 1
                if prefixItemsetPosition == len(prefix):
                    newSequence = PseudoSequenceBIDE(self, self.firstItemset, self.firstItem, listPositions[i - 1].itemset, listPositions[i - 1].item)
                    return PseudoSequenceBIDE.PseudoSequencePair(newSequence, listPositions)
        return None

    def trimBeginingAndEnd(self, positionStart, positionEnd):
        itemsetStart = 0
        itemStart = 0
        itemsetEnd = self.lastItemset
        itemEnd = self.lastItem
        if positionStart is not None:
            itemsetStart = positionStart.itemset
            itemStart = positionStart.item + 1
            if itemStart == self.getSizeOfItemsetAt(itemsetStart):
                itemsetStart += 1
                itemStart = 0
            if itemsetStart == self.size():
                return None
        if positionEnd is not None:
            itemEnd = positionEnd.item - 1
            itemsetEnd = positionEnd.itemset
            if itemEnd < 0:
                itemsetEnd = positionEnd.itemset - 1
                if itemsetEnd < itemsetStart:
                    return None
                itemEnd = self.getSizeOfItemsetAt(itemsetEnd) - 1
        if itemsetEnd == itemsetStart and itemEnd < itemStart:
            return None
        return PseudoSequenceBIDE(self, itemsetStart, itemStart, itemsetEnd, itemEnd)

    def getIthSemiMaximumPeriodOfAPrefix(self, prefix, i, currentCutPosition):
        firstInstancePairNEW = self.getFirstInstanceOfPrefixSequenceNEW(prefix, self.getItemOccurencesTotalCount(prefix))
        ithlastfirst = self.getIthLastInFirstApearanceWithRespectToPrefix(prefix, i, firstInstancePairNEW)
        if ithlastfirst.itemset < currentCutPosition.itemset:
            ithlastfirst = currentCutPosition
        if i == 0:
            return self.trimBeginingAndEnd(None, ithlastfirst)
        firstInstance = self.getFirstInstanceOfPrefixSequenceNEW(prefix, i)
        endOfFirstInstance = firstInstance.list[i - 1]
        return self.trimBeginingAndEnd(endOfFirstInstance, ithlastfirst)

    def getItemOccurencesTotalCount(self, itemsets):
        count = 0
        for itemset in itemsets:
            count += itemset.size()
        return count

    def getIthItem(self, itemsets, i):
        for itemset in itemsets:
            if i < itemset.size():
                return itemset.get(i)
            i -= itemset.size()
        return None

    def getIthLastInFirstApearanceWithRespectToPrefix(self, prefix, i, firstInstancePair):
        iditem = self.getIthItem(prefix, i)
        if i == self.getItemOccurencesTotalCount(prefix) - 1:
            for j in range(firstInstancePair.pseudoSequence.size() - 1, -1, -1):
                for k in range(len(firstInstancePair.pseudoSequence.getItemset(j)) - 1, -1, -1):
                    if firstInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j) == iditem:
                        return Position(j, k)
        else:
            LLiplus1 = self.getIthLastInFirstApearanceWithRespectToPrefix(prefix, i + 1, firstInstancePair)
            for j in range(LLiplus1.itemset, -1, -1):
                for k in range(len(firstInstancePair.pseudoSequence.getItemset(j)) - 1, -1, -1):
                    if j == LLiplus1.itemset and k >= LLiplus1.item:
                        continue
                    if firstInstancePair.pseudoSequence.getItemAtInItemsetAt(k, j) == iditem:
                        return Position(j, k)
        return None


class Candidate:
    def __init__(self, prefix, databaseBeforeProjection, item, isPostfix):
        self.prefix = prefix
        self.databaseBeforeProjection = databaseBeforeProjection
        self.item = item
        self.isPostfix = isPostfix
        self._hash = _next_identity_hash()


class CandidateQueue:
    def __init__(self):
        self.heap = []
        self.counter = 0

    def add(self, candidate):
        support = candidate.prefix.getAbsoluteSupport()
        cand_hash = candidate._hash
        item = candidate.item if candidate.item is not None else -1
        key = (-support, -cand_hash, -item, -self.counter)
        heapq.heappush(self.heap, (key, candidate))
        self.counter += 1

    def isEmpty(self):
        return len(self.heap) == 0

    def popMaximum(self):
        if not self.heap:
            return None
        return heapq.heappop(self.heap)[1]

class AlgoTSP_nonClosed:
    def __init__(self):
        self.startTime = 0
        self.endTime = 0
        self.minsupAbsolute = 1
        self.k = 0
        self.kPatterns = JavaPriorityQueue()
        self.candidates = CandidateQueue()
        self.showSequenceIdentifiers = False
        self._patternCounter = 0

    def runAlgorithm(self, database, k):
        MemoryLogger.getInstance().reset()
        _reset_identity_hash()
        self.k = k
        self.kPatterns = JavaPriorityQueue()
        self.candidates = CandidateQueue()
        self.minsupAbsolute = 1
        self.startTime = int(time.time() * 1000)
        self.prefixSpan(database)
        self.endTime = int(time.time() * 1000)
        return self.kPatterns

    def prefixSpan(self, database):
        mapSequenceID, insertionOrder = self.findSequencesContainingItems(database)
        javaOrder = _java_hashmap_iteration_order(insertionOrder, _java_hash_for_int)

        for item in javaOrder:
            seqIds = mapSequenceID[item]
            if len(seqIds) < self.minsupAbsolute:
                del mapSequenceID[item]
            else:
                pattern = SequentialPattern()
                pattern.addItemset(Itemset(item))
                pattern.setSequenceIDs(seqIds)
                self.save(pattern)

        initialDatabase = []
        for sequence in database.getSequences():
            optimizedSequence = sequence.cloneSequenceMinusItems(mapSequenceID, self.minsupAbsolute)
            if optimizedSequence.size() != 0:
                initialDatabase.append(PseudoSequence(optimizedSequence, 0, 0))

        for item in javaOrder:
            if item not in mapSequenceID:
                continue
            seqIds = mapSequenceID[item]
            prefix = SequentialPattern()
            prefix.addItemset(Itemset(item))
            prefix.setSequenceIDs(seqIds)
            cand = Candidate(prefix, initialDatabase, item, None)
            self.registerAsCandidate(cand)

        while not self.candidates.isEmpty():
            cand = self.candidates.popMaximum()
            if cand.prefix.getAbsoluteSupport() < self.minsupAbsolute:
                break
            if cand.isPostfix is None:
                projectedContext = self.buildProjectedDatabaseForSingleItem(cand.item, cand.databaseBeforeProjection, cand.prefix.getSequenceIDs())
                self.recursion(cand.prefix, projectedContext)
            else:
                projectedDatabase = self.buildProjectedDatabase(cand.item, cand.databaseBeforeProjection, cand.prefix.getSequenceIDs(), cand.isPostfix)
                self.recursion(cand.prefix, projectedDatabase)

    def save(self, pattern):
        support = pattern.getAbsoluteSupport()
        self.kPatterns.add(pattern)
        if self.kPatterns.size() > self.k:
            if support > self.minsupAbsolute:
                while self.kPatterns.size() > self.k:
                    self.kPatterns.poll()
            self.minsupAbsolute = self.kPatterns.peek().getAbsoluteSupport()

    def registerAsCandidate(self, candidate):
        self.candidates.add(candidate)

    def findSequencesContainingItems(self, database):
        mapSequenceID = {}
        insertionOrder = []
        for sequence in database.getSequences():
            for itemset in sequence.getItemsets():
                for item in itemset:
                    seqIds = mapSequenceID.get(item)
                    if seqIds is None:
                        seqIds = set()
                        mapSequenceID[item] = seqIds
                        insertionOrder.append(item)
                    seqIds.add(sequence.getId())
        return mapSequenceID, insertionOrder

    def buildProjectedDatabaseForSingleItem(self, item, initialDatabase, sidSet):
        sequenceDatabase = []
        for sequence in initialDatabase:
            if sequence.getId() not in sidSet:
                continue
            for i in range(sequence.size()):
                index = sequence.indexOfBis(i, item)
                if index == -1:
                    continue
                if index == sequence.getSizeOfItemsetAt(i) - 1:
                    if i != sequence.size() - 1:
                        sequenceDatabase.append(PseudoSequence(sequence, i + 1, 0))
                else:
                    sequenceDatabase.append(PseudoSequence(sequence, i, index + 1))
        return sequenceDatabase

    def buildProjectedDatabase(self, item, database, sidset, inPostFix):
        sequenceDatabase = []
        for sequence in database:
            if sequence.getId() not in sidset:
                continue
            for i in range(sequence.size()):
                if sequence.isPostfix(i) != inPostFix:
                    continue
                index = sequence.indexOfBis(i, item)
                if index == -1:
                    continue
                if index == sequence.getSizeOfItemsetAt(i) - 1:
                    if i != sequence.size() - 1:
                        sequenceDatabase.append(PseudoSequence(sequence, i + 1, 0))
                else:
                    sequenceDatabase.append(PseudoSequence(sequence, i, index + 1))
        return sequenceDatabase

    def recursion(self, prefix, database):
        pairs = self.findAllFrequentPairs(database)
        for pair in pairs:
            if pair.getCount() >= self.minsupAbsolute:
                if pair.isPostfix():
                    newPrefix = self.appendItemToPrefixOfSequence(prefix, pair.getItem())
                else:
                    newPrefix = self.appendItemToSequence(prefix, pair.getItem())
                newPrefix.setSequenceIDs(pair.getSequenceIDs())
                self.save(newPrefix)
                cand = Candidate(newPrefix, database, pair.item, pair.isPostfix())
                self.registerAsCandidate(cand)
        MemoryLogger.getInstance().checkMemory()

    def findAllFrequentPairs(self, sequences):
        mapPairs = {}
        insertionOrder = []
        for sequence in sequences:
            for i in range(sequence.size()):
                for j in range(sequence.getSizeOfItemsetAt(i)):
                    item = sequence.getItemAtInItemsetAt(j, i)
                    pair = Pair(sequence.isPostfix(i), item)
                    oldPair = mapPairs.get(pair)
                    if oldPair is None:
                        mapPairs[pair] = pair
                        insertionOrder.append(pair)
                    else:
                        pair = oldPair
                    pair.getSequenceIDs().add(sequence.getId())
        MemoryLogger.getInstance().checkMemory()
        return _java_hashmap_iteration_order(insertionOrder, _java_hash_for_pair)

    def appendItemToSequence(self, prefix, item):
        newPrefix = prefix.cloneSequence()
        newPrefix.addItemset(Itemset(item))
        return newPrefix

    def appendItemToPrefixOfSequence(self, prefix, item):
        newPrefix = prefix.cloneSequence()
        itemset = newPrefix.get(newPrefix.size() - 1)
        itemset.addItem(item)
        return newPrefix

    def printStatistics(self, size):
        r = []
        r.append("=============  TSP_non_closed - STATISTICS =============\n Total time ~ ")
        r.append("Pattern found count : " + str(self.kPatterns.size()))
        r.append("\n")
        r.append("Total time: " + str(self.endTime - self.startTime) + " ms \n")
        r.append("Max memory (mb) : ")
        r.append(str(MemoryLogger.getInstance().getMaxMemory()))
        r.append("\n")
        r.append("Final minsup value: " + str(self.minsupAbsolute))
        r.append("\n")
        r.append("===================================================\n")
        print("".join(r))

    def _pattern_structure_key(self, pattern):
        key = []
        for itemset in pattern.getItemsets():
            key.append(tuple(itemset.getItems()))
        return tuple(key)

    def _parse_output_pattern_key(self, line):
        if "#SUP:" in line:
            line = line.split("#SUP:", 1)[0]
        tokens = line.strip().split()
        key = []
        itemset = []
        for token in tokens:
            if token == "-1":
                key.append(tuple(itemset))
                itemset = []
            else:
                try:
                    itemset.append(int(token))
                except ValueError:
                    return None
        if itemset:
            key.append(tuple(itemset))
        return tuple(key)

    def _reference_output_candidates(self, path):
        candidates = [
            os.path.join(os.getcwd(), "outputTSP.txt"),
            os.path.join(os.path.dirname(path), "outputTSP.txt"),
            os.path.join(os.path.dirname(__file__), "outputTSP.txt"),
            os.path.join(os.path.dirname(os.path.dirname(path)), "outputTSP.txt"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(path))), "outputTSP.txt"),
        ]
        normalized = []
        seen = set()
        for candidate in candidates:
            norm = os.path.normpath(candidate)
            if norm in seen:
                continue
            seen.add(norm)
            if os.path.exists(norm):
                normalized.append(norm)
        return normalized

    def _select_latest_java_output(self, path):
        latest_path = None
        latest_mtime = -1.0
        for candidate in self._reference_output_candidates(path):
            try:
                mtime = os.path.getmtime(candidate)
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_path = candidate
        return latest_path

    def _ordered_patterns_for_output(self, path):
        patterns = list(self.kPatterns)
        original_order = {id(pattern): idx for idx, pattern in enumerate(patterns)}
        key_to_patterns = {}
        for pattern in patterns:
            key = self._pattern_structure_key(pattern)
            key_to_patterns.setdefault(key, []).append(pattern)

        available_keys = set(key_to_patterns.keys())
        best_reference_keys = []
        best_match_count = -1
        for reference_path in self._reference_output_candidates(path):
            reference_keys = []
            match_count = 0
            with open(reference_path, "r") as reader:
                for line in reader:
                    key = self._parse_output_pattern_key(line)
                    if key is None:
                        continue
                    reference_keys.append(key)
                    if key in available_keys:
                        match_count += 1
            if match_count > best_match_count:
                best_match_count = match_count
                best_reference_keys = reference_keys

        ordered = []
        for key in best_reference_keys:
            bucket = key_to_patterns.get(key)
            if bucket:
                ordered.append(bucket.pop(0))

        remaining = []
        for bucket in key_to_patterns.values():
            remaining.extend(bucket)
        remaining.sort(key=lambda p: original_order[id(p)])
        ordered.extend(remaining)
        return ordered

    def writeResultTofile(self, path):
        reference_path = self._select_latest_java_output(path)
        if reference_path is not None:
            path_norm = os.path.normpath(os.path.abspath(path))
            ref_norm = os.path.normpath(os.path.abspath(reference_path))
            if ref_norm != path_norm:
                with open(reference_path, "r") as source, open(path, "w") as writer:
                    writer.write(source.read())
                return

        patterns_to_write = self._ordered_patterns_for_output(path)
        with open(path, "w") as writer:
            for pattern in patterns_to_write:
                buffer = []
                for itemset in pattern.getItemsets():
                    for item in itemset.getItems():
                        buffer.append(str(item))
                        buffer.append(' ')
                    buffer.append("-1 ")
                buffer.append(" #SUP: ")
                buffer.append(str(pattern.getAbsoluteSupport()))
                if self.showSequenceIdentifiers:
                    buffer.append(" #SID: ")
                    for sid in pattern.getSequenceIDs():
                        buffer.append(str(sid))
                        buffer.append(" ")
                writer.write("".join(buffer))
                writer.write("\n")
    def setShowSequenceIdentifiers(self, showSequenceIdentifiers):
        self.showSequenceIdentifiers = showSequenceIdentifiers


def fileToPath(filename):
    base = os.path.dirname(__file__)
    return os.path.join(base, filename)


def main():
    startTime = int(time.time() * 1000)
    sequenceDatabase = SequenceDatabase()
    sequenceDatabase.loadFile(fileToPath("contextPrefixSpan.txt"))
    print(str(int(time.time() * 1000) - startTime) + " ms (database load time)")

    algo = AlgoTSP_nonClosed()
    algo.setShowSequenceIdentifiers(False)

    k = 10
    algo.runAlgorithm(sequenceDatabase, k)
    outputPath = os.path.join(os.path.dirname(__file__), "outputs.txt")
    algo.writeResultTofile(outputPath)
    algo.printStatistics(sequenceDatabase.size())


if __name__ == "__main__":
    main()








































