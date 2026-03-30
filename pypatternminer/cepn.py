# cepn_all_in_one.py
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self) -> float:
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self) -> float:
        try:
            import tracemalloc

            if not tracemalloc.is_tracing():
                tracemalloc.start()
            current, _peak = tracemalloc.get_traced_memory()
            current_mb = current / 1024.0 / 1024.0
            if current_mb > self.maxMemory:
                self.maxMemory = current_mb
            return current_mb
        except Exception:
            return 0.0


class DataMapper:
    keyPair: Dict[str, int] = {}

    @staticmethod
    def mapKV(key: str) -> int:
        if key not in DataMapper.keyPair:
            DataMapper.keyPair[key] = len(DataMapper.keyPair)
        return DataMapper.keyPair[key]

    @staticmethod
    def getKey(value: int) -> str:
        for k, v in DataMapper.keyPair.items():
            if v == value:
                return k
        return "*-1*"


@dataclass
class Event:
    id: int
    cost: float

    def getId(self) -> int:
        return self.id

    def getCost(self) -> float:
        return self.cost


class EventSet:
    def __init__(self, event: Optional[int] = None):
        self.events: List[int] = []
        if event is not None:
            self.addEvent(event)

    def addEvent(self, event: int):
        self.events.append(event)

    def getEvents(self) -> List[int]:
        return self.events


@dataclass
class CostUtilityPair:
    cost: float
    utility: float

    def getCost(self) -> float:
        return self.cost

    def getUtility(self) -> float:
        return self.utility


class Pair:
    def __init__(self, cost: float = 0.0, totalLengthOfSeq: int = 0, indexOfNextEvent: int = 0):
        self.cost = cost
        self.totalLengthOfSeq = totalLengthOfSeq
        self.indexOfNextEvent = indexOfNextEvent

    def getTotalLengthOfSeq(self) -> int:
        return self.totalLengthOfSeq

    def getIndexOfNextEvent(self) -> int:
        return self.indexOfNextEvent

    def getCost(self) -> float:
        return self.cost


class PseudoSequence:
    def __init__(self, sequenceID: int, indexFirstItem: int, sequenceLength: int):
        self.sequenceID = sequenceID
        self.indexFirstItem = indexFirstItem
        self.sequenceLength = sequenceLength

    def getOriginalSequenceID(self) -> int:
        return self.sequenceID

    def getSequenceLength(self) -> int:
        return self.sequenceLength


class SequenceDatabase:
    def __init__(self):
        self.sequences: List[List[Event]] = []
        self.sequenceIdUtility: Dict[int, float] = {}
        self.eventOccurrenceCount = 0

    def loadFile(self, path: str):
        self.eventOccurrenceCount = 0
        self.sequences = []
        self.sequenceIdUtility = {}

        lineNumber = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                thisLine = line.strip("\n").strip("\r")
                if not thisLine:
                    continue
                if thisLine[0] in ("#", "%", "@"):
                    continue

                tokens = thisLine.split(" ")
                if len(tokens) < 2:
                    continue

                seq_util_token = tokens[-1]
                pos = seq_util_token.find(":")
                seqUtility = float(seq_util_token[pos + 1 :]) if pos != -1 else 0.0
                if lineNumber not in self.sequenceIdUtility:
                    self.sequenceIdUtility[lineNumber] = seqUtility
                    lineNumber += 1

                sequence: List[Event] = [None] * (len(tokens) - 1)  # type: ignore
                for i in range(len(tokens) - 1):
                    currentToken = tokens[i].strip()
                    if len(currentToken) != 0 and currentToken[0] != "-":
                        lb = currentToken.find("[")
                        rb = currentToken.find("]")
                        itemString = currentToken[:lb]
                        item = DataMapper.mapKV(itemString)
                        costString = currentToken[lb + 1 : rb]
                        cost = float(int(costString))
                        sequence[i] = Event(item, cost)
                    else:
                        current = int(currentToken)
                        sequence[i] = Event(current, -99.0)

                self.sequences.append(sequence)

    def size(self) -> int:
        return len(self.sequences)

    def getSequences(self) -> List[List[Event]]:
        return self.sequences

    def getSequenceUtility(self, sequenceId: int) -> float:
        return self.sequenceIdUtility[sequenceId]


class SequentialPattern:
    def __init__(self):
        self.eventsets: List[EventSet] = []
        self.sequenceIDS: List[int] = []
        self.averageCost: float = 0.0
        self.occupancy: float = 0.0
        self.tradeOff: float = 0.0
        self.utility: float = 0.0
        self.costUtilityPairs: Optional[List[CostUtilityPair]] = None

    def addEventset(self, eventSet: EventSet):
        self.eventsets.append(eventSet)

    def eventSetstoString(self) -> str:
        out: List[str] = []
        for es in self.eventsets:
            for ev in es.getEvents():
                out.append(f"{DataMapper.getKey(ev)} ")
            out.append("-1 ")
        out.append("-2")
        return "".join(out)

    def setCostUtilityPairs(self, pairs: List[CostUtilityPair]):
        self.costUtilityPairs = pairs

    def setAverageCost(self, avg: float):
        self.averageCost = avg

    def getAverageCost(self) -> float:
        return self.averageCost

    def setOccupancy(self, occ: float):
        self.occupancy = occ

    def getOccupancy(self) -> float:
        return self.occupancy

    def setSequencesIDs(self, sids: List[int]):
        self.sequenceIDS = sids

    def getSequencesIDs(self) -> List[int]:
        return self.sequenceIDS

    def getAbsoluteSupport(self) -> int:
        return len(self.sequenceIDS)

    def setUtility(self, u: float):
        self.utility = u

    def getUtility(self) -> float:
        return self.utility

    def setTradeOff(self, t: float):
        self.tradeOff = t

    def getTradeOff(self) -> float:
        return self.tradeOff


class SequentialPatterns:
    def __init__(self, name: str):
        self.levels: List[List[SequentialPattern]] = []
        self.sequenceCount: int = 0
        self.name = name
        self.levels.append([])

    def addSequence(self, sequence: SequentialPattern, k: int):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(sequence)
        self.sequenceCount += 1


class AlgoCEPM:
    AVGCOST = " #AVGCOST: "
    TRADE = " #TRADE: "
    SUP = " #SUP: "
    UTIL = " #UTIL: "
    OCCUP = " #OCCUP: "

    class AlgorithmType:
        CEPB = "CEPB"
        CEPN = "CEPN"
        CORCEPB = "CORCEPB"

    def __init__(self):
        self.startTime = 0
        self.endTime = 0
        self.sequenceDatabase: Optional[SequenceDatabase] = None
        self.algorithmName: Optional[str] = None
        self.minimumSupport = 0
        self.maximumCost = 0.0
        self.minimumOccpuancy = 0.0
        self.patternCount = 0
        self.projectedDatabaseCount = 0
        self.consideredPatternCount = 0
        self.maximumPatternLength = 999
        self.patterns: Optional[SequentialPatterns] = None
        self.patternBuffer = [0] * 2000
        self.sequenceIdUtility: Dict[int, float] = {}
        self.useLowerBound = False
        self.sortByUtilityForCEPN = False
        self.outputLowestTradeOffForCEPN = False

    def setMaximumPatternLength(self, maximumPatternLength: int):
        self.maximumPatternLength = maximumPatternLength

    def setUseLowerBound(self, useLowerBound: bool):
        self.useLowerBound = useLowerBound

    def runAlgorithmCEPN(
        self,
        inputFile: str,
        outputFile: str,
        minsup: int,
        maxcost: float,
        minoccupancy: float,
        sortByUtilityForCEPN: bool,
        outputLowestTradeOffForCEPN: bool,
    ) -> SequentialPatterns:
        self.outputLowestTradeOffForCEPN = outputLowestTradeOffForCEPN
        self.sortByUtilityForCEPN = sortByUtilityForCEPN
        self.algorithmName = self.AlgorithmType.CEPN
        self.runAlgorithm(inputFile, outputFile, minsup, maxcost, minoccupancy)
        return self.patterns  # type: ignore

    def runAlgorithm(self, inputFile: str, outputFile: str, minsup: int, maxcost: float, minoccupancy: float):
        self.minimumSupport = minsup
        self.maximumCost = maxcost
        self.minimumOccpuancy = minoccupancy

        MemoryLogger.getInstance().reset()
        self.startTime = int(time.time() * 1000)

        self.sequenceDatabase = SequenceDatabase()
        self.sequenceDatabase.loadFile(inputFile)
        self.sequenceIdUtility = dict(self.sequenceDatabase.sequenceIdUtility)

        self.patterns = SequentialPatterns("SEQUENTIAL LOWER BOUND PATTERN MINING")

        mapSequenceID = self.findSequencesContainingItems()
        self.prefixSpanWithSingleItem(mapSequenceID)

        self.endTime = int(time.time() * 1000)

        if outputFile:
            self.writeResultsToFileCEPN(outputFile)

    def findSequencesContainingItems(self) -> Dict[int, Dict[int, Pair]]:
        assert self.sequenceDatabase is not None
        mapSequenceID: Dict[int, Dict[int, Pair]] = {}

        for i in range(self.sequenceDatabase.size()):
            sequence = self.sequenceDatabase.getSequences()[i]
            for token in sequence:
                if token.getId() >= 0:
                    if token.getId() not in mapSequenceID:
                        mapSequenceID[token.getId()] = {i: Pair(token.getCost(), len(sequence), i + 1)}
                    else:
                        if i not in mapSequenceID[token.getId()]:
                            mapSequenceID[token.getId()][i] = Pair(token.getCost(), len(sequence), i + 1)
        return mapSequenceID

    def prefixSpanWithSingleItem(self, mapSequenceID: Dict[int, Dict[int, Pair]]):
        assert self.sequenceDatabase is not None

        for i in range(self.sequenceDatabase.size()):
            sequence = self.sequenceDatabase.getSequences()[i]
            currentPosition = 0
            for token in sequence:
                if token.getId() >= 0:
                    isFrequent = len(mapSequenceID.get(token.getId(), {})) >= self.minimumSupport
                    if isFrequent:
                        sequence[currentPosition] = token
                        currentPosition += 1
                elif token.getId() == -2:
                    if currentPosition > 0:
                        sequence[currentPosition] = Event(-2, -99.0)
                    newSequence = sequence[: currentPosition + 1]
                    self.sequenceDatabase.getSequences()[i] = newSequence
                    break

        if self.algorithmName != self.AlgorithmType.CEPN:
            return

        for event, seqMap in mapSequenceID.items():
            self.consideredPatternCount += 1
            support = len(seqMap)
            if support < self.minimumSupport:
                continue

            averageCost = self.getAverageCostWithSingleEvent(seqMap)
            occupancy = self.getOccupancyWithSingleEvent(seqMap)

            if averageCost <= self.maximumCost and occupancy >= self.minimumOccpuancy:
                costUtilityPairs = self.getListOfCostUtility(seqMap)
                self.savePatternSingleEventCEPN(event, averageCost, occupancy, seqMap, costUtilityPairs)

            lowerSupportCost = self.getLowerBoundSingle(self.minimumSupport, seqMap)
            lowerBoundOfCost = lowerSupportCost / self.minimumSupport
            upperBoundOcc = self.getUpperBoundOccupancyWithSingleEvent(seqMap)

            if (lowerBoundOfCost <= self.maximumCost and upperBoundOcc >= self.minimumOccpuancy) or (not self.useLowerBound):
                self.patternBuffer[0] = event
                if self.maximumPatternLength > 1:
                    projected = self.buildProjectedDatabaseSingleItems(event, list(seqMap.keys()))
                    self.projectedDatabaseCount += 1
                    self.recursionSingleEvents(projected, 2, 0)

            MemoryLogger.getInstance().checkMemory()

    def getAverageCostWithSingleEvent(self, sequenceIdCost: Dict[int, Pair]) -> float:
        costOfPattern = 0.0
        for pair in sequenceIdCost.values():
            costOfPattern += pair.getCost()
        return costOfPattern / len(sequenceIdCost)

    def getLowerBoundSingle(self, minimumSupport: int, sequenceIdCost: Dict[int, Pair]) -> float:
        costs = [p.getCost() for p in sequenceIdCost.values()]
        costs.sort()
        return sum(costs[:minimumSupport])

    def getOccupancyWithSingleEvent(self, sequenceIDLength: Dict[int, Pair]) -> float:
        occupancy = 0.0
        for pair in sequenceIDLength.values():
            lengthOfSeq = pair.getTotalLengthOfSeq() - 1
            occupancy += (1.0 / lengthOfSeq)
        return occupancy / len(sequenceIDLength)

    def getUpperBoundOccupancyWithSingleEvent(self, sequenceIDLength: Dict[int, Pair]) -> float:
        upper_list: List[float] = []
        for pair in sequenceIDLength.values():
            l = pair.getTotalLengthOfSeq() - 1
            upper_list.append((1.0 + (l - pair.getIndexOfNextEvent())) / l)
        upper_list.sort(reverse=True)
        return sum(upper_list[: self.minimumSupport]) / self.minimumSupport

    def getListOfCostUtility(self, seqIdPair: Dict[int, Pair]) -> List[CostUtilityPair]:
        pairs: List[CostUtilityPair] = []
        for seqId, pair in seqIdPair.items():
            pairs.append(CostUtilityPair(pair.getCost(), self.sequenceIdUtility.get(seqId, 0.0)))
        return pairs

    def savePatternSingleEventCEPN(
        self,
        event: int,
        averageCost: float,
        occupancy: float,
        sequcenIdCost: Dict[int, Pair],
        costUtilityPairs: List[CostUtilityPair],
    ):
        self.patternCount += 1
        pattern = SequentialPattern()
        pattern.addEventset(EventSet(event))

        sequenceIDS = list(sequcenIdCost.keys())

        patternUtility = 0.0
        for seqId in sequcenIdCost.keys():
            patternUtility += self.sequenceIdUtility.get(seqId, 0.0)

        avgUtility = patternUtility / len(sequcenIdCost)
        if avgUtility == 0:
            avgUtility = 1.0

        pattern.setUtility(avgUtility)
        pattern.setTradeOff(averageCost / avgUtility)

        pattern.setCostUtilityPairs(costUtilityPairs)
        pattern.setAverageCost(averageCost)
        pattern.setSequencesIDs(sequenceIDS)
        pattern.setOccupancy(occupancy)

        assert self.patterns is not None
        self.patterns.addSequence(pattern, 1)

    def buildProjectedDatabaseSingleItems(self, event: int, sequenceIDs: List[int]) -> List[PseudoSequence]:
        assert self.sequenceDatabase is not None
        projected: List[PseudoSequence] = []
        for sequenceID in sequenceIDs:
            seq = self.sequenceDatabase.getSequences()[sequenceID]
            j = 0
            while seq[j].getId() != -2:
                if seq[j].getId() == event:
                    if seq[j + 1].getId() != -2:
                        projected.append(PseudoSequence(sequenceID, j + 1, len(seq)))
                    break
                j += 1
            MemoryLogger.getInstance().checkMemory()
        return projected

    def findAllFrequentPairsSingleEvents(self, sequences: List[PseudoSequence]) -> Dict[int, List[PseudoSequence]]:
        assert self.sequenceDatabase is not None
        mp: Dict[int, List[PseudoSequence]] = {}
        for ps in sequences:
            sequenceID = ps.getOriginalSequenceID()
            seq = self.sequenceDatabase.getSequences()[sequenceID]
            i = ps.indexFirstItem
            while seq[i].getId() != -2:
                token = seq[i].getId()
                if token >= 0:
                    lst = mp.get(token)
                    if lst is None:
                        lst = []
                        mp[token] = lst
                    ok = True
                    if len(lst) > 0:
                        ok = lst[-1].sequenceID != sequenceID
                    if ok:
                        lst.append(PseudoSequence(sequenceID, i + 1, len(seq)))
                MemoryLogger.getInstance().checkMemory()
                i += 1
        return mp

    def getLowerBoundMulti(self, lastBufferPosition: int, currentEvent: int, pseudoSequences: List[PseudoSequence]) -> float:
        assert self.sequenceDatabase is not None
        eventsBefore: List[int] = []
        for i in range(lastBufferPosition + 1):
            t = self.patternBuffer[i]
            if t >= 0:
                eventsBefore.append(t)
        eventsBefore.append(currentEvent)

        costs: List[float] = []
        for ps in pseudoSequences:
            seq = self.sequenceDatabase.getSequences()[ps.sequenceID]
            currentEventPos = ps.indexFirstItem - 1
            j = 0
            cost = 0.0
            for i in range(currentEventPos + 1):
                if seq[i].getId() == eventsBefore[j]:
                    cost += seq[i].getCost()
                    j += 1
            costs.append(cost)
        costs.sort()
        return sum(costs[: self.minimumSupport])

    def getAverageCostWithMulEvents(self, lastBufferPosition: int, pseudoSequences: List[PseudoSequence], currentEvent: int) -> float:
        assert self.sequenceDatabase is not None
        eventsBefore: List[int] = []
        for i in range(lastBufferPosition + 1):
            t = self.patternBuffer[i]
            if t >= 0:
                eventsBefore.append(t)
        eventsBefore.append(currentEvent)

        total = 0.0
        for ps in pseudoSequences:
            seq = self.sequenceDatabase.getSequences()[ps.sequenceID]
            currentEventPos = ps.indexFirstItem - 1
            j = 0
            for i in range(currentEventPos + 1):
                if seq[i].getId() == eventsBefore[j]:
                    total += seq[i].getCost()
                    j += 1
        return total / len(pseudoSequences)

    def getOccupancyWithMultipleEvents(self, pseudoSequenceList: List[PseudoSequence], patternLength: float) -> float:
        occ = 0.0
        for ps in pseudoSequenceList:
            l = ps.getSequenceLength() - 1
            occ += patternLength / l
        return occ / len(pseudoSequenceList)

    def setListOfCostUtility(self, lastBufferPosition: int, pseudoSequences: List[PseudoSequence]) -> List[CostUtilityPair]:
        assert self.sequenceDatabase is not None
        eventsBefore: List[int] = []
        for i in range(lastBufferPosition + 1):
            t = self.patternBuffer[i]
            if t >= 0:
                eventsBefore.append(t)

        pairs: List[CostUtilityPair] = []
        for ps in pseudoSequences:
            seq = self.sequenceDatabase.getSequences()[ps.sequenceID]
            currentEventPos = ps.indexFirstItem - 1
            j = 0
            cost = 0.0
            for i in range(currentEventPos + 1):
                if seq[i].getId() == eventsBefore[j]:
                    cost += seq[i].getCost()
                    j += 1
            pairs.append(CostUtilityPair(cost, self.sequenceIdUtility.get(ps.sequenceID, 0.0)))
        return pairs

    def savePatternMultiCEPN(
        self,
        lastBufferPosition: int,
        pseudoSequences: List[PseudoSequence],
        averageCost: float,
        occupancy: float,
        costUtilityPairs: List[CostUtilityPair],
    ):
        self.patternCount += 1
        pattern = SequentialPattern()

        currentEventset = EventSet()
        eventsetCount = 0
        for i in range(lastBufferPosition + 1):
            t = self.patternBuffer[i]
            if t >= 0:
                currentEventset.addEvent(t)
            elif t == -1:
                pattern.addEventset(currentEventset)
                currentEventset = EventSet()
                eventsetCount += 1
        pattern.addEventset(currentEventset)
        eventsetCount += 1

        seqIDs = [ps.sequenceID for ps in pseudoSequences]

        patternUtility = 0.0
        for ps in pseudoSequences:
            patternUtility += self.sequenceIdUtility.get(ps.sequenceID, 0.0)
        avgU = patternUtility / len(pseudoSequences)
        if avgU == 0:
            avgU = 1.0

        pattern.setUtility(avgU)
        pattern.setTradeOff(averageCost / avgU)

        pattern.setCostUtilityPairs(costUtilityPairs)
        pattern.setSequencesIDs(seqIDs)
        pattern.setAverageCost(averageCost)
        pattern.setOccupancy(occupancy)

        assert self.patterns is not None
        self.patterns.addSequence(pattern, eventsetCount)

    def recursionSingleEvents(self, database: List[PseudoSequence], k: int, lastBufferPositionOfPattern: int):
        eventsPseudoSequence = self.findAllFrequentPairsSingleEvents(database)

        for event, psList in eventsPseudoSequence.items():
            self.consideredPatternCount += 1
            support = len(psList)
            if support < self.minimumSupport:
                continue

            self.patternBuffer[lastBufferPositionOfPattern + 1] = -1
            self.patternBuffer[lastBufferPositionOfPattern + 2] = event

            lowerSupportCost = self.getLowerBoundMulti(lastBufferPositionOfPattern, event, psList)
            lowerBoundOfCost = lowerSupportCost / self.minimumSupport

            averageCost = self.getAverageCostWithMulEvents(lastBufferPositionOfPattern, psList, event)
            occupancy = self.getOccupancyWithMultipleEvents(psList, k)

            if averageCost <= self.maximumCost and occupancy >= self.minimumOccpuancy:
                cu = self.setListOfCostUtility(lastBufferPositionOfPattern + 2, psList)
                self.savePatternMultiCEPN(lastBufferPositionOfPattern + 2, psList, averageCost, occupancy, cu)

            if (lowerBoundOfCost <= self.maximumCost and occupancy >= self.minimumOccpuancy) or (not self.useLowerBound):
                if k < self.maximumPatternLength:
                    self.projectedDatabaseCount += 1
                    self.recursionSingleEvents(psList, k + 1, lastBufferPositionOfPattern + 2)

            MemoryLogger.getInstance().checkMemory()

    def sortByUtility(self, patterns: SequentialPatterns) -> List[Tuple[float, List[SequentialPattern]]]:
        bucket: Dict[float, List[SequentialPattern]] = {}
        for level in patterns.levels:
            for p in level:
                u = p.getUtility()
                bucket.setdefault(u, []).append(p)
        return sorted(bucket.items(), key=lambda x: x[0], reverse=True)

    def writeResultsToFileCEPN(self, outputFile: str):
        assert self.patterns is not None

        def fmt3(x: float) -> str:
            return f"{x:.3f}"

        d = os.path.dirname(outputFile)
        if d:
            os.makedirs(d, exist_ok=True)

        with open(outputFile, "w", encoding="utf-8") as writer:
            if self.sortByUtilityForCEPN:
                grouped = self.sortByUtility(self.patterns)
                for _util, plist in grouped:
                    for pattern in plist:
                        writer.write(pattern.eventSetstoString())
                        writer.write(self.UTIL + fmt3(pattern.getUtility()))
                        writer.write(self.SUP + str(pattern.getAbsoluteSupport()))
                        writer.write(self.TRADE + fmt3(pattern.getTradeOff()))
                        writer.write(self.OCCUP + fmt3(pattern.getOccupancy()))
                        writer.write(self.AVGCOST + fmt3(pattern.getAverageCost()))
                        writer.write("\n")
            else:
                for level in self.patterns.levels:
                    for pattern in level:
                        writer.write(pattern.eventSetstoString())
                        writer.write(self.UTIL + fmt3(pattern.getUtility()))
                        writer.write(self.SUP + str(pattern.getAbsoluteSupport()))
                        writer.write(self.TRADE + fmt3(pattern.getTradeOff()))
                        writer.write(self.AVGCOST + fmt3(pattern.getAverageCost()))
                        writer.write(self.OCCUP + fmt3(pattern.getOccupancy()))
                        writer.write("\n")

    def printStatistics(self):
        r = []
        r.append(f"=============  {self.algorithmName} 2.42 STATISTICS =============")
        r.append(f" Pattern count : {self.patternCount}")
        r.append(f" Total time : {self.endTime - self.startTime} ms")
        r.append(f" Max memory (mb) : {MemoryLogger.getInstance().getMaxMemory():.3f}")
        r.append("===================================================")
        print("\n".join(r))


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_input = os.path.join(script_dir, "example_CEPN.txt")
    default_output = os.path.join(script_dir, "cepn_output.txt")

    input_path = default_input
    output_path = default_output

    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]

    minsup = 2
    maxcost = 50.0
    minoccupancy = 0.1
    sortByUtility = True
    outputLowestTradeOff = False

    algo = AlgoCEPM()
    algo.setMaximumPatternLength(100)
    algo.setUseLowerBound(True)

    algo.runAlgorithmCEPN(
        input_path,
        output_path,
        minsup,
        maxcost,
        minoccupancy,
        sortByUtility,
        outputLowestTradeOff,
    )

    algo.printStatistics()
    print("CEPN finished")
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()