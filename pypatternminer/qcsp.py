import math
import os
import sys
import time
from functools import cmp_to_key


class CountMap:
    def __init__(self):
        self.map = {}

    def add(self, key):
        self.map[key] = self.get(key) + 1

    def remove(self, key):
        self.map.pop(key, None)

    def get(self, key):
        return self.map.get(key, 0)

    def getMap(self):
        return self.map

    def keySet(self):
        return self.map.keys()

    def clear(self):
        self.map.clear()


class FileStream:
    BUFF_SIZE = 16 * 1024

    def __init__(self, path, *separators):
        self.file = open(path, "r", encoding="utf-8")
        self.separators = list(separators) if separators else [" ", "\n"]
        self.buffer = ""
        self.cursor = 0
        self.eof = False

    def close(self):
        self.file.close()

    def _fill_buffer(self):
        if self.eof:
            return False
        chunk = self.file.read(self.BUFF_SIZE)
        if chunk == "":
            self.eof = True
            return False
        if self.cursor < len(self.buffer):
            self.buffer = self.buffer[self.cursor:] + chunk
        else:
            self.buffer = chunk
        self.cursor = 0
        return True

    def nextToken(self):
        token_chars = []
        while True:
            if self.cursor >= len(self.buffer):
                if not self._fill_buffer():
                    if token_chars:
                        return "".join(token_chars)
                    return None
            if self.cursor >= len(self.buffer):
                continue
            ch = self.buffer[self.cursor]
            self.cursor += 1
            if ch in self.separators:
                if token_chars:
                    return "".join(token_chars)
                continue
            token_chars.append(ch)


class ListMap:
    def __init__(self):
        self.map = {}

    def put(self, key, value):
        self.map.setdefault(key, []).append(value)

    def putAll(self, key, values):
        if key not in self.map:
            self.map[key] = values
        self.map[key].extend(values)

    def putList(self, key, lst):
        self.map[key] = lst

    def remove(self, key):
        self.map.pop(key, None)

    def get(self, key):
        return self.map.get(key)

    def keySet(self):
        return self.map.keys()

    def entrySet(self):
        return self.map.items()

    def __str__(self):
        return str(self.map)


class Pair:
    def __init__(self, first, second):
        self.first = first
        self.second = second

    def setFirst(self, first):
        self.first = first

    def setSecond(self, second):
        self.second = second

    def getFirst(self):
        return self.first

    def getSecond(self):
        return self.second

    def __str__(self):
        return f"{self.first}:{self.second}"

    def __eq__(self, other):
        return isinstance(other, Pair) and self.first == other.first and self.second == other.second

    def __hash__(self):
        return hash((self.first, self.second))


class JavaPriorityQueue:
    def __init__(self, comparator):
        self.queue = []
        self.comparator = comparator

    def __len__(self):
        return len(self.queue)

    def add(self, item):
        self.queue.append(item)
        self._sift_up(len(self.queue) - 1, item)

    def peek(self):
        return self.queue[0] if self.queue else None

    def poll(self):
        if not self.queue:
            return None
        s = len(self.queue) - 1
        result = self.queue[0]
        x = self.queue.pop()
        if s != 0:
            self._sift_down(0, x)
        return result

    def _sift_up(self, idx, item):
        while idx > 0:
            parent = (idx - 1) >> 1
            e = self.queue[parent]
            if self.comparator(item, e) >= 0:
                break
            self.queue[idx] = e
            idx = parent
        self.queue[idx] = item

    def _sift_down(self, idx, item):
        half = len(self.queue) >> 1
        while idx < half:
            child = (idx << 1) + 1
            c = self.queue[child]
            right = child + 1
            if right < len(self.queue) and self.comparator(c, self.queue[right]) > 0:
                child = right
                c = self.queue[child]
            if self.comparator(item, c) <= 0:
                break
            self.queue[idx] = c
            idx = child
        self.queue[idx] = item


class Triple:
    def __init__(self, first=None, second=None, thirth=None):
        self.first = first
        self.second = second
        self.thirth = thirth

    def getFirst(self):
        return self.first

    def setFirst(self, first):
        self.first = first

    def getSecond(self):
        return self.second

    def setSecond(self, second):
        self.second = second

    def getThirth(self):
        return self.thirth

    def setThirth(self, thirth):
        self.thirth = thirth


class Utils:
    @staticmethod
    def milisToStringReadable(milis):
        if milis < 1000:
            return f"{milis} ms"
        if milis < 60000:
            return f"{milis / 1000.0:.1f} sec"
        if milis < 60 * 60 * 1000:
            return f"{milis / (60 * 1000.0):.1f} min"
        return f"{milis / (3600 * 1000.0):.2f} h"


class Timer:
    VERBOSE = True

    def __init__(self, process):
        self.start = int(time.time() * 1000)
        self.intermediateStart = self.start
        self.process = process if len(process) <= 20 else process[:20] + "..."
        if self.VERBOSE:
            print(f">Started {process}")

    def progress(self, *args):
        if len(args) == 2:
            message = None
            i, total = args
        else:
            message, i, total = args
        end = int(time.time() * 1000)
        elapsed = end - self.intermediateStart
        elapsed_total = end - self.start
        if self.VERBOSE:
            estimate = ""
            if total < i:
                total = i
            if total > 10 and i > 0:
                estimated_milis = round((total - i) * (elapsed_total / float(i)))
                estimate = " Expected " + Utils.milisToStringReadable(estimated_milis)
            msg = "" if message is None else message
            print(
                " Process %s %s: %.2f %% items. Elapsed %s. Total %s.%s"
                % (
                    self.process,
                    msg,
                    i / float(total) * 100 if total else 100.0,
                    Utils.milisToStringReadable(elapsed),
                    Utils.milisToStringReadable(elapsed_total),
                    estimate,
                )
            )
        self.intermediateStart = int(time.time() * 1000)

    def end(self):
        end = int(time.time() * 1000)
        elapsed = end - self.start
        if self.VERBOSE:
            print(f"<Finished {self.process}. Took {Utils.milisToStringReadable(elapsed)}")
        return elapsed


class SequentialPattern:
    def __init__(self, prefix=None, item=None):
        if prefix is None:
            self.pattern = []
        else:
            self.pattern = list(prefix.pattern)
            self.pattern.append(item)

    def length(self):
        return len(self.pattern)


class Window:
    def __init__(self, t, a, b):
        self.t = t
        self.a = a
        self.b = b


class QCSPData:
    def __init__(self):
        self.sequenceList = []
        self.labelsList = []
        self.support_map = CountMap()
        self.itemsSortedOnAscendingSupport = []
        self.itemPositions = ListMap()
        self.NULL_ITEM = 0
        self.SEPERATOR_ITEM = -1
        self.END_ITEM = -2

    def loadData(self, sequenceFile, labelsFile, minsup, alpha, maxsize, debug):
        if not os.path.isfile(sequenceFile):
            raise IOError(f"QCSP could not read sequence file {sequenceFile}")
        if labelsFile is not None and not os.path.isfile(labelsFile):
            raise IOError(f"QCSP could not read labels file {labelsFile}")
        try:
            self.labelsList = []
            if labelsFile is not None:
                fs2 = FileStream(labelsFile, " ", "\n")
                label = fs2.nextToken()
                while label is not None:
                    self.labelsList.append(label)
                    label = fs2.nextToken()
                fs2.close()

            fs = FileStream(sequenceFile, " ", "\n")
            token = fs.nextToken()
            sizeSequence = 0
            while token is not None:
                token = fs.nextToken()
                sizeSequence += 1
            fs.close()
            if debug:
                print(f"Sequence size: {sizeSequence}")

            self.sequenceList = []
            fs = FileStream(sequenceFile, " ", "\n")
            token = fs.nextToken()
            while token is not None:
                item = int(token)
                if item == self.NULL_ITEM:
                    self.sequenceList.append(None)
                    token = fs.nextToken()
                elif item == self.SEPERATOR_ITEM:
                    token = fs.nextToken()
                elif item == self.END_ITEM:
                    for _ in range(int(alpha * maxsize)):
                        self.sequenceList.append(None)
                    token = fs.nextToken()
                else:
                    self.sequenceList.append(item)
                    token = fs.nextToken()
            fs.close()

            self.support_map = CountMap()
            for item in self.sequenceList:
                if item is not None:
                    self.support_map.add(item)

            infrequent = set()
            for item, supp in list(self.support_map.getMap().items()):
                if supp < minsup:
                    infrequent.add(item)

            if debug:
                print("Removing infrequent items:", end="")
            for item in infrequent:
                self.support_map.remove(item)
                if debug:
                    label = self.labelsList[item - 1] if len(self.labelsList) > 0 else None
                    print(f"{item} ({label}), ", end="")
            if debug:
                print()

            for i, value in enumerate(self.sequenceList):
                if value in infrequent:
                    self.sequenceList[i] = None

            self.itemsSortedOnAscendingSupport = self.getItemsSorted(self.support_map, True)

            self.itemPositions = ListMap()
            for idx, item in enumerate(self.sequenceList):
                if item is not None:
                    self.itemPositions.put(item, idx)
        except Exception as e:
            raise RuntimeError("QCSP error loading data") from e

    def getItemsSortedOnAscendingSupport(self):
        return self.itemsSortedOnAscendingSupport

    def getSequence(self):
        return self.sequenceList

    def getSequenceSize(self):
        return len(self.sequenceList)

    def getPositions(self, item):
        return self.itemPositions.get(item)

    def support(self, items):
        total = 0
        for item in items:
            total += self.support_map.get(item)
        return total

    def hasLabels(self):
        return len(self.labelsList) > 0

    def getItemsSorted(self, support, ascending):
        lst = list(support.getMap().items())
        if ascending:
            lst.sort(key=lambda kv: (kv[1], kv[0]))
        else:
            lst.sort(key=lambda kv: (-kv[1], kv[0]))
        return [key for key, _ in lst]

    def patternToString(self, X):
        if not self.labelsList:
            raise RuntimeError("No labels provided")
        buff = ["("]
        for i in range(0, len(X) - 1):
            buff.append(self.labelsList[X[i] - 1])
            buff.append(",")
        if len(X) > 0:
            buff.append(self.labelsList[X[-1] - 1])
        buff.append(")")
        return "".join(buff)


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        try:
            import psutil

            process = psutil.Process(os.getpid())
            current = process.memory_info().rss / 1024.0 / 1024.0
        except Exception:
            import tracemalloc

            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, _ = tracemalloc.get_traced_memory()
            current = current / 1024.0 / 1024.0
        if current > self.maxMemory:
            self.maxMemory = current

    def getMaxMemory(self):
        return self.maxMemory


class AlgoQCSP:
    DEBUG_ITER = 1000000

    def __init__(self):
        self.alpha = None
        self.minsup = None
        self.maxsize = None
        self.topK = None
        self.patternOutputFile = None
        self.pruningOf = False
        self.debug = False
        self.labelsFile = None
        self.init = self.makeList(Window(-1, -1, -1))
        self.data = None
        self.mincoh = 0.0
        self.elapsedTime = -1
        self.iterations = 0
        self.leafs = 0
        self.patternCount = 0
        self.shorterWindowsCache = []
        self.stack = []
        self.occurrences = []
        self.itemAtT = {}

    def runAlgorithm(self, singleSequenceFile, patternOutputFile, minsup, alpha, maxsize, topK):
        self.minsup = minsup
        self.alpha = alpha
        self.maxsize = maxsize
        self.topK = topK
        self.patternOutputFile = patternOutputFile
        self.data = QCSPData()
        labels_file = self.labelsFile if self.labelsFile is not None else None
        self.data.loadData(singleSequenceFile, labels_file, minsup, alpha, maxsize, self.debug)
        return self.run(self.debug)

    def setPruningOf(self, pruningOf):
        self.pruningOf = pruningOf

    def setDebug(self, debug):
        self.debug = debug

    def setLabelsFile(self, labelsFile):
        self.labelsFile = labelsFile

    def _heap_push(self, heapPatterns, pattern, qcoh):
        heapPatterns.add(Pair(pattern, qcoh))

    def _heap_peek_pair(self, heapPatterns):
        return heapPatterns.peek()

    def _heap_poll_pair(self, heapPatterns):
        return heapPatterns.poll()

    def run(self, debug):
        timer = Timer("QSCP.run()")
        print(
            "Parameters: alpha=%f, maxsize=%d, top-k=%d, pruningOf=%s"
            % (self.alpha, self.maxsize, self.topK, str(self.pruningOf).lower())
        )
        heapPatterns = JavaPriorityQueue(self.heapComparator)
        self.mincoh = 0.0
        stack = []
        allItems = self.data.getItemsSortedOnAscendingSupport()
        stack.append(Triple(SequentialPattern(), self.init, allItems))
        self.iterations = 0
        self.leafs = 0
        while stack:
            self.iterations += 1
            top = stack.pop()
            X = top.getFirst()
            P = top.getSecond()
            Y = top.getThirth()
            if debug and self.iterations % self.DEBUG_ITER == 0:
                currentIndex = allItems.index(X.pattern[0] if len(X.pattern) > 0 else 0)
                timer.progress(currentIndex, len(allItems))
                worst = self.toString(self._heap_peek_pair(heapPatterns).getFirst().pattern if heapPatterns else [])
                print(
                    "Iterations:%-10d, #Patterns: %d, worst: %s, min_coh:%.3f, "
                    % (self.iterations / self.DEBUG_ITER, len(heapPatterns), worst, self.mincoh)
                )
            if len(Y) == 0:
                if X.length() > 1:
                    self.leafs += 1
                    qcoh = self.quantileCohesionComputedOnProjection(X, P)
                    if len(heapPatterns) < self.topK:
                        self._heap_push(heapPatterns, X, qcoh)
                        if len(heapPatterns) == self.topK:
                            self.mincoh = self._heap_peek_pair(heapPatterns).getSecond()
                    else:
                        if qcoh > self.mincoh:
                            self._heap_poll_pair(heapPatterns)
                            self._heap_push(heapPatterns, X, qcoh)
                            self.mincoh = self._heap_peek_pair(heapPatterns).getSecond()
            else:
                if (not self.pruningOf) and self.prune(X, P, Y, self.mincoh):
                    continue
                stack.append(Triple(X, P, list(Y[1:])))
                if X.length() != self.maxsize:
                    nextItem = Y[0]
                    Z = SequentialPattern(X, nextItem)
                    projectionZ = self.project(Z, P)
                    itemsZ = self.projectCandidates(Z, projectionZ)
                    stack.append(Triple(Z, projectionZ, itemsZ))
        self.elapsedTime = timer.end()
        self.patternCount = len(heapPatterns)

        sorted_patterns = []
        while len(heapPatterns) > 0:
            sorted_patterns.append(self._heap_poll_pair(heapPatterns))

        def pattern_compare(o1, o2):
            return int(
                10000 * o2.getSecond()
                - 10000 * o1.getSecond()
                + self.data.support(o2.getFirst().pattern)
                - self.data.support(o1.getFirst().pattern)
            )

        sorted_patterns.sort(key=cmp_to_key(pattern_compare))
        self.savePatterns(sorted_patterns)
        return sorted_patterns

    @staticmethod
    def heapComparator(o1, o2):
        if o1.getSecond() < o2.getSecond():
            return -1
        if o1.getSecond() > o2.getSecond():
            return 1
        return 0

    def savePatterns(self, sortedPatterns):
        writer = None
        if self.patternOutputFile is not None:
            output_dir = os.path.dirname(self.patternOutputFile)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            writer = open(self.patternOutputFile, "w", encoding="utf-8")
        print("============================")
        print("QC Patterns:")
        for pattern in sortedPatterns:
            if self.data.hasLabels():
                patternToString = "%s   #SUP: %d   #QCOH: %.3f" % (
                    self.toString(pattern.getFirst().pattern),
                    self.data.support(pattern.getFirst().pattern),
                    pattern.getSecond(),
                )
            else:
                patternToString = "%s   #SUP: %d   #QCOH: %.3f" % (
                    self.toStringSPMF(pattern.getFirst().pattern),
                    self.data.support(pattern.getFirst().pattern),
                    pattern.getSecond(),
                )
            print(patternToString)
            if writer is not None:
                writer.write(patternToString)
                writer.write("\n")
        if writer is not None:
            writer.close()
        print("end QC Patterns:")
        print("============================")

    def printStatistics(self):
        print("=============  QCSP algorithm v1.00 - STATS =======")
        print(" Pattern count: " + str(self.patternCount))
        print(" Min cohesion: " + str(self.mincoh))
        print(" Total time ~ " + str(self.elapsedTime) + " ms")
        print(" Number of iterations: " + str(self.iterations))
        print(" Number of candidates: " + str(self.leafs))
        print(" Max Memory ~ " + str(MemoryLogger.getInstance().getMaxMemory()) + " MB")
        print(" Parameters")
        print("  Maxsize: " + str(self.maxsize))
        print("  Pruning enabled: " + str(not self.pruningOf).lower())
        print("  Alpha: " + str(self.alpha))
        print("  Top-k: " + str(self.topK))
        print(" Input file information")
        print("  number of symbols: " + str(len(self.data.getItemsSortedOnAscendingSupport())))
        print("  sequence length: " + str(self.data.getSequenceSize()))
        print("  label file enabled: " + str(self.data.hasLabels()).lower())
        print("===========================================================")

    def quantileCohesionComputedOnProjection(self, X, projectionX):
        maxwin = int(math.floor(self.alpha * X.length()))
        minWinAtT = self.computeMinimalWindowsBasedOnProjection1(X, projectionX, maxwin)
        count = len(minWinAtT.keys())
        supportX = self.data.support(X.pattern)
        qcoh = count / float(supportX)
        return qcoh

    def computeMinimalWindowsBasedOnProjection1(self, X, projectionX, maxwin):
        shorterWindows = []
        for window in projectionX:
            if window.a - window.t > maxwin:
                continue
            end = min(window.b, window.t + maxwin)
            shorterWindows.append(Window(window.t, end, end))

        sequence = self.data.getSequence()
        stack = []
        for window in shorterWindows:
            X_poslist = self.makeList(window.t)
            stack.append(Pair(X_poslist, Window(window.t + 1, window.b, window.b)))

        occurrences = []
        while stack:
            top = stack.pop()
            poslist = top.getFirst()
            window = top.getSecond()
            if len(poslist) == X.length():
                occurrences.append(poslist)
            else:
                currentItem = X.pattern[len(poslist)]
                for i in range(window.t, window.b):
                    item = sequence[i]
                    if item is None:
                        continue
                    if item == currentItem:
                        newPoslist = list(poslist)
                        newPoslist.append(i)
                        stack.append(Pair(newPoslist, Window(i + 1, window.b, window.b)))

        minWinAtT = {}
        for occurrence in occurrences:
            mwin = occurrence[-1] - occurrence[0]
            for pos in occurrence:
                minWinAtT[pos] = self.minWindow(mwin, minWinAtT.get(pos))
        return minWinAtT

    def computeNumberOfMinimalWindowsBasedOnProjection(self, X, XNoneOverlapping, projectionX, lengthZMax):
        maxwin = int(math.floor(self.alpha * lengthZMax))
        sequence = self.data.getSequence()
        shorterWindows = projectionX
        if lengthZMax < self.maxsize:
            shorterWindows = self.shorterWindowsCache
            shorterWindows.clear()
            for window in projectionX:
                if window.a - window.t > maxwin:
                    continue
                end = min(window.b, window.t + maxwin)
                shorterWindows.append(Window(window.t, end, end))

        self.stack.clear()
        for window in shorterWindows:
            X_poslist = [window.t]
            self.stack.append(Pair(X_poslist, Window(window.t + 1, window.b, window.b)))
        self.occurrences.clear()
        while self.stack:
            top = self.stack.pop()
            poslist = top.getFirst()
            window = top.getSecond()
            if len(poslist) == X.length():
                self.occurrences.append(poslist)
            else:
                currentItem = X.pattern[len(poslist)]
                for i in range(window.t, window.b):
                    item = sequence[i]
                    if item is None:
                        continue
                    if item == currentItem:
                        newPoslist = list(poslist)
                        newPoslist.append(i)
                        self.stack.append(Pair(newPoslist, Window(i + 1, window.b, window.b)))

        self.itemAtT.clear()
        for occurrence in self.occurrences:
            for i, pos in enumerate(occurrence):
                self.itemAtT[pos] = X.pattern[i]
        countSmallWindowsNonOverlapping = 0
        for item in self.itemAtT.values():
            if item in XNoneOverlapping:
                countSmallWindowsNonOverlapping += 1
        return countSmallWindowsNonOverlapping

    def minWindow(self, a, bOrNull):
        if bOrNull is None:
            return a
        return min(a, bOrNull)

    def project(self, Z, projectionX):
        sequence = self.data.getSequence()
        if Z.length() == 1:
            positions = self.data.getPositions(Z.pattern[0]) or []
            windows = []
            maxwin = int(math.floor(self.alpha * self.maxsize))
            for pos in positions:
                windows.append(Window(pos, pos + 1, min(pos + maxwin, self.data.getSequenceSize())))
            return windows
        windows = []
        lastItem = Z.pattern[Z.length() - 1]
        for window in projectionX:
            found = -1
            for i in range(window.a, window.b):
                item = sequence[i]
                if item is None:
                    continue
                if item == lastItem:
                    found = i
                    break
            if found != -1:
                windows.append(Window(window.t, found + 1, window.b))
        return windows

    def projectCandidates(self, z, projectionZ):
        sequence = self.data.getSequence()
        supportInP = CountMap()
        for window in projectionZ:
            for i in range(window.a, window.b):
                item = sequence[i]
                if item is not None:
                    supportInP.add(item)
        return self.data.getItemsSorted(supportInP, False)

    def prune(self, X, P, Y, mincoh):
        xLen = X.length()
        if xLen < 2:
            return False

        overlap = False
        for item in X.pattern:
            if item in Y:
                overlap = True
                break
        if not overlap:
            lengthZMax = min(self.computeLengthZMax(X, P), self.maxsize)
            mingap = self.computeMinGap(X, P)
            if mingap + lengthZMax > self.alpha * (lengthZMax + xLen):
                return True

        XNoneOverlapping = set(X.pattern)
        XNoneOverlapping.difference_update(Y)
        if len(XNoneOverlapping) == 0:
            return False
        supportXNoneOverlapping = self.data.support(XNoneOverlapping)
        supportZMax = supportXNoneOverlapping + self.data.support(Y)
        maxsizeYPlus = self.computeYPlus(X, P, Y)
        lengthZMaxCorrect = min(xLen + maxsizeYPlus, self.maxsize)
        countSmallWindowsNonOverlapping = self.computeNumberOfMinimalWindowsBasedOnProjection(
            X, XNoneOverlapping, P, lengthZMaxCorrect
        )
        countLargeWindows = supportXNoneOverlapping - countSmallWindowsNonOverlapping
        maxQuantileCohesion = 1.0 - (countLargeWindows / float(supportZMax))
        if maxQuantileCohesion <= mincoh:
            return True
        return False

    def computeYPlus(self, X, projectionX, Y):
        sequence = self.data.getSequence()
        multisetCount = [0] * len(Y)
        windowCounts = [0] * len(Y)
        for window in projectionX:
            for i in range(window.a, window.b):
                item = sequence[i]
                if item is not None:
                    try:
                        idx = Y.index(item)
                    except ValueError:
                        idx = -1
                    if idx != -1:
                        windowCounts[idx] += 1
            for i in range(len(Y)):
                multisetCount[i] = max(windowCounts[i], multisetCount[i])
        maxlen = 0
        for count in multisetCount:
            maxlen += count
        return maxlen

    def computeMinGap(self, X, P):
        mingap = 2**31 - 1
        for window in P:
            mingap = min(window.a - window.t, mingap)
        return mingap

    def computeLengthZMax(self, X, P):
        sequence = self.data.getSequence()
        maxlen = 0
        for window in P:
            start = window.a
            for i in range(window.a, window.b):
                if sequence[i] is None:
                    start += 1
                else:
                    break
            end = window.b
            for i in range(window.b - 1, window.a - 1, -1):
                if sequence[i] is None:
                    end -= 1
                else:
                    break
            maxlen = max(maxlen, end - start)
        return X.length() + maxlen

    def makeList(self, first):
        return [first]

    def toString(self, pattern):
        if self.data.hasLabels():
            return self.data.patternToString(pattern)
        buff = ["("]
        for i in range(0, len(pattern) - 1):
            buff.append(str(pattern[i]))
            buff.append(",")
        if len(pattern) > 0:
            buff.append(str(pattern[-1]))
        buff.append(")")
        return "".join(buff)

    def toStringSPMF(self, pattern):
        buff = []
        for item in pattern:
            buff.append(str(item))
            buff.append(" -1 ")
        return "".join(buff)

    def support(self, pattern):
        return self.data.support(pattern)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # --------------------------------------------------
    # Set parameters directly here
    # --------------------------------------------------
    input_path = os.path.join(base_dir, "contextQCSP.txt")
    output_path = os.path.join(base_dir, "output_py.txt")

    minsup = 1
    alpha = 2.0
    maximumSequentialPatternLength = 10
    topK = 20
    showDebugInformation = True
    # --------------------------------------------------

    MemoryLogger.getInstance().reset()
    algorithm = AlgoQCSP()
    algorithm.setDebug(showDebugInformation)
    algorithm.runAlgorithm(
        input_path,
        output_path,
        minsup,
        alpha,
        maximumSequentialPatternLength,
        topK,
    )
    algorithm.printStatistics()

    print(f"\nInput file : {input_path}")
    print(f"Output file: {output_path}\n")


if __name__ == "__main__":
    main()