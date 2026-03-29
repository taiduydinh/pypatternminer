"""
tkucep.py

Heuristically mining the top-k high-utility itemsets with cross-entropy
optimization.

Authors: Wei Song, Chuanlong Zheng, Chaomin Huang, and Lu Liu
"""

import os
import random
import time
from typing import List


# ===========================================================================
# MemoryLogger
# ===========================================================================

class MemoryLogger:
    """
    Records the maximum memory usage of an algorithm during a given execution.
    Implemented using the Singleton design pattern.
    """

    _instance = None

    def __init__(self):
        self._max_memory: float = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        """Return the only instance of this class (Singleton)."""
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self) -> float:
        """Return the maximum amount of memory used so far, in megabytes."""
        return self._max_memory

    def reset(self):
        """Reset the maximum memory recorded."""
        self._max_memory = 0.0

    def checkMemory(self) -> float:
        """
        Check current memory usage and update the maximum if higher.
        Returns current memory usage in megabytes.
        Works on both Windows and Unix/macOS.
        """
        import sys
        if sys.platform == "win32":
            # Windows: read from /proc equivalent via ctypes
            import ctypes
            import ctypes.wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD),
                    ("PageFaultCount", ctypes.wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(pmc)
            ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(pmc),
                pmc.cb
            )
            current_memory = pmc.WorkingSetSize / 1024.0 / 1024.0  # bytes -> MB
        else:
            import resource
            usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            current_memory = usage_kb / 1024.0  # KB -> MB

        if current_memory > self._max_memory:
            self._max_memory = current_memory
        return current_memory


# ===========================================================================
# Data classes
# ===========================================================================

class Pair:
    """Represents an item and its utility in a transaction."""

    def __init__(self):
        self.item: int = 0
        self.utility: int = 0


class HUI:
    """A high utility itemset."""

    def __init__(self, itemset: str, fitness: int):
        self.itemset = itemset
        self.fitness = fitness


class Particle:
    """
    Represents a sample/particle in the CE+ algorithm.
    Uses a Python list of bools instead of Java's BitSet.
    """

    def __init__(self, length: int = 0):
        self.X: List[bool] = [False] * length
        self.fitness: int = 0

    def copy_particle(self, other: "Particle"):
        """Copy another particle into this one."""
        self.X = other.X[:]
        self.fitness = other.fitness

    def get(self, index: int) -> bool:
        return self.X[index]

    def set(self, index: int):
        self.X[index] = True

    def clear(self, index: int):
        self.X[index] = False

    def cardinality(self) -> int:
        """Return the number of True bits (equivalent to BitSet.cardinality)."""
        return sum(self.X)

    def equals(self, other: "Particle") -> bool:
        return self.X == other.X

    def calculate_fitness(self, k: int, templist: List[int], database, twu_pattern: List[int]):
        """
        Calculate the fitness (utility) of this particle.

        :param k:           number of set bits
        :param templist:    list of transaction indices where this particle exists
        :param database:    the transaction database
        :param twu_pattern: the list of promising items
        """
        if k == 0:
            return
        fitness = 0
        for p in templist:
            i = 0
            temp = 0
            total = 0
            while i < len(twu_pattern):
                if self.X[i]:
                    for t in range(len(database[p])):
                        if database[p][t].item == twu_pattern[i]:
                            total += database[p][t].utility
                            i += 1
                            temp += 1
                            break
                    else:
                        i += 1
                else:
                    i += 1
            if temp == k:
                fitness += total
        self.fitness = fitness


class Item:
    """Represents an item with its transaction ID set (TIDS)."""

    def __init__(self, item: int, transaction_count: int):
        self.item = item
        self.TIDS: List[bool] = [False] * transaction_count


# ===========================================================================
# AlgoTKUCEP
# ===========================================================================

class AlgoTKUCEP:
    """
    Implementation of the TKU-CE+ algorithm for Top-K High-Utility
    Itemsets Mining.
    """

    SAMPLE_SIZE = 2000
    MAX_ITERATION = 2000

    def __init__(self):
        self.max_memory: float = 0.0
        self.start_timestamp: float = 0.0
        self.end_timestamp: float = 0.0
        self.actual_iterations: int = 0
        self.transaction_count: int = 0
        self.K: int = 0
        self.CUV: int = 0
        self.rho: float = 0.2
        self.SF: float = 0.2

        self.map_item_to_u: dict = {}
        self.map_item_to_twu: dict = {}
        self.twu_pattern: List[int] = []

        self.p: List[float] = []
        self.samples: List[Particle] = []
        self.hui_sets: List[HUI] = []
        self.database: List[List[Pair]] = []
        self.items: List[Item] = []
        self.top_k_hui_particle: List[Particle] = []

        self._output_path: str = ""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_algorithm(self, input_path: str, output_path: str, top_k: int):
        """
        Run the TKU-CE+ algorithm.

        :param input_path:  path to the input database file
        :param output_path: path to the output file
        :param top_k:       desired number of top-K HUIs
        """
        MemoryLogger.getInstance().reset()
        self.K = top_k
        self._output_path = output_path
        self.start_timestamp = time.time()

        self.map_item_to_u = {}
        self.map_item_to_twu = {}

        # ---- First scan: compute TWU of each item ----
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line or line[0] in ("#", "%", "@"):
                        continue
                    self.transaction_count += 1
                    parts = line.split(":")
                    item_strs = parts[0].split()
                    transaction_utility = int(parts[1])
                    utility_strs = parts[2].split()

                    for i, item_str in enumerate(item_strs):
                        item = int(item_str)
                        utility = int(utility_strs[i])
                        self.map_item_to_u[item] = self.map_item_to_u.get(item, 0) + utility
                        self.map_item_to_twu[item] = (
                            self.map_item_to_twu.get(item, 0) + transaction_utility
                        )
        except Exception as e:
            print(f"Error reading input file: {e}")

        # ---- Calculate Critical Utility Value ----
        self._calculate_cuv(self.map_item_to_u)

        self.twu_pattern = [
            item for item, twu in self.map_item_to_twu.items() if twu >= self.CUV
        ]
        self.p = [0.0] * len(self.twu_pattern)

        # ---- Second scan: build revised database ----
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line or line[0] in ("#", "%", "@"):
                        continue
                    parts = line.split(":")
                    item_strs = parts[0].split()
                    utility_strs = parts[2].split()

                    revised_transaction: List[Pair] = []
                    for i, item_str in enumerate(item_strs):
                        item = int(item_str)
                        if self.map_item_to_twu.get(item, 0) >= self.CUV:
                            pair = Pair()
                            pair.item = item
                            pair.utility = int(utility_strs[i])
                            revised_transaction.append(pair)
                    self.database.append(revised_transaction)
        except Exception as e:
            print(f"Error reading input file (2nd pass): {e}")

        # ---- Build Item objects with TIDS ----
        self.items = [Item(item, self.transaction_count) for item in self.twu_pattern]
        for i, transaction in enumerate(self.database):
            for item_obj in self.items:
                for pair in transaction:
                    if item_obj.item == pair.item:
                        item_obj.TIDS[i] = True

        MemoryLogger.getInstance().checkMemory()

        # ---- Main CE+ loop ----
        if len(self.twu_pattern) > 0:
            self._generate_sample(1.0)

            for _ in range(self.MAX_ITERATION):
                self.actual_iterations += 1
                self.samples.sort(key=lambda s: s.fitness, reverse=True)

                max_fit = self.samples[0].fitness
                min_fit = self.samples[int(self.rho * self.SAMPLE_SIZE) - 1].fitness
                max_min = max_fit - min_fit

                if max_min == 0:
                    break

                proportion = max_min / max_fit if max_fit != 0 else 0.0
                self._update((1 - self.SF) * proportion)

            self.end_timestamp = time.time()

            # ---- Collect top-K results ----
            for i in range(self.K):
                if i <= len(self.top_k_hui_particle) - 1:
                    self._insert(self.top_k_hui_particle[i])

        MemoryLogger.getInstance().checkMemory()
        self.max_memory = MemoryLogger.getInstance().getMaxMemory()
        self.end_timestamp = time.time()
        self._write_out()

    # ------------------------------------------------------------------
    # Critical Utility Value
    # ------------------------------------------------------------------

    def _calculate_cuv(self, utility_map: dict):
        """Calculate the critical utility value from individual item utilities."""
        if not utility_map:
            return
        values = sorted(utility_map.values(), reverse=True)
        s = min(len(values), self.K)
        self.CUV = values[s - 1]

    # ------------------------------------------------------------------
    # Sample generation
    # ------------------------------------------------------------------

    def _generate_sample(self, proportion: float):
        """Initialize the sample population."""
        n = len(self.twu_pattern)
        for i in range(int(proportion * self.SAMPLE_SIZE)):
            temp_particle = Particle(n)
            k = random.randint(1, n)
            j = 0
            while j < k:
                pos = random.randint(0, n - 1)
                if not temp_particle.X[pos]:
                    temp_particle.X[pos] = True
                    j += 1

            trans_list: List[int] = []
            self.is_rba_individual(temp_particle, trans_list)
            temp_particle.calculate_fitness(k, trans_list, self.database, self.twu_pattern)

            self.samples.insert(i, temp_particle)
            self._insert_top_list(self.samples[i])

    # ------------------------------------------------------------------
    # Update step
    # ------------------------------------------------------------------

    def _update(self, proportion: float):
        """Update the probability vector and sample set."""
        n = len(self.twu_pattern)
        num = [0] * n
        elite_count = int(self.rho * self.SAMPLE_SIZE)

        for i in range(elite_count):
            for j in range(n):
                if self.samples[i].X[j]:
                    num[j] += 1

        self.CUV = self.samples[elite_count - 1].fitness

        for i in range(n):
            self.p[i] = num[i] / (self.rho * self.SAMPLE_SIZE)

        for i in range(int(proportion * self.SAMPLE_SIZE)):
            temp_particle = Particle(n)
            self._update_particle(temp_particle)
            trans_list: List[int] = []
            if self.is_rba_individual(temp_particle, trans_list):
                k = temp_particle.cardinality()
                temp_particle.calculate_fitness(k, trans_list, self.database, self.twu_pattern)
                if temp_particle.fitness > self.CUV:
                    self.samples.insert(i, temp_particle)
                    self._insert_top_list(self.samples[i])

        self._generate_sample(self.SF)

    def _update_particle(self, temp: Particle):
        """Generate a particle guided by the probability vector."""
        for i in range(len(self.twu_pattern)):
            if random.random() < self.p[i]:
                temp.X[i] = True

    # ------------------------------------------------------------------
    # Top-K list management
    # ------------------------------------------------------------------

    def _insert_top_list(self, tmp: Particle):
        """Insert a particle into the sorted Top-K list."""
        temp = Particle(len(self.twu_pattern))
        temp.copy_particle(tmp)

        if not self.top_k_hui_particle:
            self.top_k_hui_particle.append(temp)
            return

        max_idx = 0
        min_idx = self.K - 1

        if len(self.top_k_hui_particle) < self.K:
            min_idx = len(self.top_k_hui_particle) - 1
            if temp.fitness < self.top_k_hui_particle[min_idx].fitness:
                self.top_k_hui_particle.append(temp)
                return
        else:
            if temp.fitness < self.top_k_hui_particle[min_idx].fitness:
                return

        # Binary search for insertion position
        mid = 0
        while max_idx <= min_idx:
            mid = (max_idx + min_idx) // 2
            if temp.fitness > self.top_k_hui_particle[mid].fitness:
                min_idx = mid - 1
            elif temp.fitness < self.top_k_hui_particle[mid].fitness:
                max_idx = mid + 1
            else:
                break

        mid_start = mid
        mid_end = mid

        if temp.fitness > self.top_k_hui_particle[mid].fitness:
            self.top_k_hui_particle.insert(mid, temp)
        elif temp.fitness < self.top_k_hui_particle[mid].fitness:
            self.top_k_hui_particle.insert(mid + 1, temp)
        else:
            if temp not in self.top_k_hui_particle:
                while mid_start >= 0 and self.top_k_hui_particle[mid_start].fitness == temp.fitness:
                    if (self.top_k_hui_particle[mid_start].equals(temp) or
                            self.top_k_hui_particle[mid_end].equals(temp)):
                        return
                    mid_start -= 1

                while (mid_end < len(self.top_k_hui_particle) and
                       self.top_k_hui_particle[mid_end].fitness == temp.fitness):
                    if self.top_k_hui_particle[mid_end].equals(temp):
                        return
                    mid_end += 1

                self.top_k_hui_particle.insert(mid, temp)

    # ------------------------------------------------------------------
    # RBA individual check
    # ------------------------------------------------------------------

    def is_rba_individual(self, temp_particle: Particle, temp_list: List[int]) -> bool:
        """
        Get the collection of transactions where the itemset exists.
        Auto-tunes the itemset if it is unreasonable.

        :return: True if the particle is a valid (non-empty) individual
        """
        selected_indices = [i for i in range(len(self.twu_pattern)) if temp_particle.X[i]]

        if not selected_indices:
            return False

        temp_bitset = self.items[selected_indices[0]].TIDS[:]
        mid_bitset = temp_bitset[:]

        for i in range(1, len(selected_indices)):
            new_bitset = [
                temp_bitset[t] and self.items[selected_indices[i]].TIDS[t]
                for t in range(self.transaction_count)
            ]
            if any(new_bitset):
                temp_bitset = new_bitset
                mid_bitset = new_bitset[:]
            else:
                temp_bitset = mid_bitset[:]
                temp_particle.X[selected_indices[i]] = False

        if not any(temp_bitset):
            return False

        for m in range(len(temp_bitset)):
            if temp_bitset[m]:
                temp_list.append(m)
        return True

    # ------------------------------------------------------------------
    # Insert into HUI sets
    # ------------------------------------------------------------------

    def _insert(self, temp_particle: Particle):
        """Insert a particle's itemset into hui_sets."""
        temp = " ".join(
            str(self.twu_pattern[i])
            for i in range(len(self.twu_pattern))
            if temp_particle.X[i]
        ) + " "

        if not self.hui_sets:
            self.hui_sets.append(HUI(temp, temp_particle.fitness))
        else:
            for hui in self.hui_sets:
                if temp == hui.itemset:
                    return
            self.hui_sets.append(HUI(temp, temp_particle.fitness))

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _write_out(self):
        """Write all discovered HUIs to the output file."""
        with open(self._output_path, "w", encoding="utf-8") as f:
            for hui in self.hui_sets:
                f.write(f"{hui.itemset}#UTIL:{hui.fitness}\n")

    def print_stats(self):
        """Print statistics about the latest execution."""
        elapsed_ms = int((self.end_timestamp - self.start_timestamp) * 1000)
        print("============ TKU-CE+ Algorithm v 2.52 ===========")
        print(f" Total time: {elapsed_ms} ms")
        print(f" Memory: {self.max_memory:.2f} MB")
        print(f" Actual iterations: {self.actual_iterations}")
        print(f" High-utility itemsets count: {len(self.hui_sets)}")
        print("=================================================")


# ===========================================================================
# Main
# ===========================================================================

def main():
    # Resolve paths relative to this script's location,
    # so files are found regardless of the working directory.
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Input file path
    input_path = os.path.join(base_dir, "DB_Utility.txt")

    # Output file path
    output_path = os.path.join(base_dir, "output_py.txt")

    # The number of top-k HUIs to discover
    k = 30

    tkucep = AlgoTKUCEP()
    tkucep.run_algorithm(input_path, output_path, k)
    tkucep.print_stats()


if __name__ == "__main__":
    main()