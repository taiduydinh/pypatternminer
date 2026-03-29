from __future__ import annotations

import math
import time
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List, Optional, Set


class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.max_memory: float = 0.0

    @classmethod
    def get_instance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reset(self) -> None:
        self.max_memory = 0.0

    def check_memory(self) -> float:
        current_memory = 0.0
        try:
            import os
            import psutil

            process = psutil.Process(os.getpid())
            current_memory = process.memory_info().rss / 1024 / 1024
        except Exception:
            current_memory = 0.0
        if current_memory > self.max_memory:
            self.max_memory = current_memory
        return current_memory

    def get_max_memory(self) -> float:
        return self.max_memory


class Itemset:
    def __init__(self, *items: int) -> None:
        self.items: List[int] = list(items)

    def add_item(self, value: int) -> None:
        self.items.append(value)

    def get_items(self) -> List[int]:
        return self.items

    def get(self, index: int) -> int:
        return self.items[index]

    def __len__(self) -> int:
        return len(self.items)

    def __str__(self) -> str:
        return " ".join(str(item) for item in self.items) + " "

    def clone_item_set(self) -> "Itemset":
        clone = Itemset()
        clone.items.extend(self.items)
        return clone

    def contains_all(self, other: "Itemset") -> bool:
        i = 0
        for item in other.items:
            found = False
            while not found and i < len(self.items):
                if self.items[i] == item:
                    found = True
                elif self.items[i] > item:
                    return False
                i += 1
            if not found:
                return False
        return True


class Prefix:
    def __init__(self) -> None:
        self.itemsets: List[Itemset] = []

    def add_itemset(self, itemset: Itemset) -> None:
        self.itemsets.append(itemset)

    def clone_sequence(self) -> "Prefix":
        seq = Prefix()
        for itemset in self.itemsets:
            seq.add_itemset(itemset.clone_item_set())
        return seq

    def __str__(self) -> str:
        parts: List[str] = []
        for itemset in self.itemsets:
            for item in itemset.get_items():
                parts.append(str(item))
                parts.append(" ")
            parts.append("-1 ")
        return "".join(parts)

    def get_itemsets(self) -> List[Itemset]:
        return self.itemsets

    def get(self, index: int) -> Itemset:
        return self.itemsets[index]

    def size(self) -> int:
        return len(self.itemsets)

    def get_item_occurrences_total_count(self) -> int:
        return sum(len(i) for i in self.itemsets)

    def contains_item(self, item: int) -> bool:
        return any(item in i.get_items() for i in self.itemsets)


class Bitmap:
    INTERSECTION_COUNT = 0

    def __init__(self, last_bit_index: int) -> None:
        self.bits: Set[int] = set()
        self.last_sid: int = -1
        self.first_itemset_id: int = -1
        self.support: int = 0
        self.sidsum: int = 0
        self.support_without_gap_total: int = 0
        self.last_bit_index = last_bit_index

    def register_bit(self, sid: int, tid: int, sequences_size: List[int]) -> None:
        pos = sequences_size[sid] + tid
        if pos not in self.bits:
            self.bits.add(pos)
            if sid != self.last_sid:
                self.support += 1
                self.sidsum += sid
            if self.first_itemset_id == -1 or tid < self.first_itemset_id:
                self.first_itemset_id = tid
            self.last_sid = sid

    def bit_to_sid(self, bit: int, sequences_size: List[int]) -> int:
        idx = bisect_right(sequences_size, bit) - 1
        if idx < 0:
            return 0
        return idx

    def get_support(self) -> int:
        return self.support

    def get_support_without_gap_total(self) -> int:
        return self.support_without_gap_total

    def last_bit_of_sid(self, sid: int, sequences_size: List[int]) -> int:
        if sid + 1 >= len(sequences_size):
            return self.last_bit_index
        return sequences_size[sid + 1] - 1

    def create_new_bitmap_s_step(self, bitmap_item: "Bitmap", sequences_size: List[int], last_bit_index: int, max_gap: int) -> "Bitmap":
        new_bitmap = Bitmap(last_bit_index)
        if max_gap == math.inf or max_gap == (1 << 31) - 1:
            bits_sorted = sorted(self.bits)
            idx = 0
            while idx < len(bits_sorted):
                bit_k = bits_sorted[idx]
                sid = self.bit_to_sid(bit_k, sequences_size)
                last_bit_of_sid = self.last_bit_of_sid(sid, sequences_size)
                match = False
                for bit in sorted(b for b in bitmap_item.bits if bit_k < b <= last_bit_of_sid):
                    new_bitmap.bits.add(bit)
                    tid = bit - sequences_size[sid]
                    if new_bitmap.first_itemset_id == -1 or tid < new_bitmap.first_itemset_id:
                        new_bitmap.first_itemset_id = tid
                    match = True
                if match:
                    if sid != new_bitmap.last_sid:
                        new_bitmap.support += 1
                        new_bitmap.support_without_gap_total += 1
                        new_bitmap.sidsum += sid
                        new_bitmap.last_sid = sid
                # skip to next sequence
                while idx < len(bits_sorted) and bits_sorted[idx] <= last_bit_of_sid:
                    idx += 1
        else:
            bits_sorted = sorted(self.bits)
            previous_sid = -1
            for bit_k in bits_sorted:
                sid = self.bit_to_sid(bit_k, sequences_size)
                last_bit_of_sid = self.last_bit_of_sid(sid, sequences_size)
                match = False
                match_without_gap = False
                for bit in sorted(b for b in bitmap_item.bits if bit_k < b <= last_bit_of_sid):
                    match_without_gap = True
                    if bit - bit_k > max_gap:
                        break
                    new_bitmap.bits.add(bit)
                    tid = bit - sequences_size[sid]
                    if new_bitmap.first_itemset_id == -1 or tid < new_bitmap.first_itemset_id:
                        new_bitmap.first_itemset_id = tid
                    match = True
                if match_without_gap and previous_sid != sid:
                    new_bitmap.support_without_gap_total += 1
                    previous_sid = sid
                if match:
                    if sid != new_bitmap.last_sid:
                        new_bitmap.support += 1
                        new_bitmap.sidsum += sid
                    new_bitmap.last_sid = sid
        return new_bitmap

    def create_new_bitmap_i_step(self, bitmap_item: "Bitmap", sequences_size: List[int], last_bit_index: int) -> "Bitmap":
        new_bitmap = Bitmap(last_bit_index)
        for bit in sorted(self.bits):
            if bit in bitmap_item.bits:
                new_bitmap.bits.add(bit)
                sid = self.bit_to_sid(bit, sequences_size)
                if sid != new_bitmap.last_sid:
                    new_bitmap.support += 1
                    new_bitmap.sidsum += sid
                new_bitmap.last_sid = sid
                tid = bit - sequences_size[sid]
                if new_bitmap.first_itemset_id == -1 or tid < new_bitmap.first_itemset_id:
                    new_bitmap.first_itemset_id = tid
        return new_bitmap

    def set_support(self, support: int) -> None:
        self.support = support

    def get_sids(self, sequences_size: List[int]) -> str:
        builder: List[str] = []
        last_sid_seen = -1
        for bit_k in sorted(self.bits):
            sid = self.bit_to_sid(bit_k, sequences_size)
            if sid != last_sid_seen:
                if last_sid_seen != -1:
                    builder.append(" ")
                builder.append(str(sid))
                last_sid_seen = sid
        return "".join(builder)


class AlgoCMSPAM:
    def __init__(self) -> None:
        self.start_time = 0
        self.end_time = 0
        self.pattern_count = 0
        self.minsup = 0
        self.writer = None
        self.vertical_db: Dict[int, Bitmap] = {}
        self.sequences_size: List[int] = []
        self.last_bit_index = 0
        self.minimum_pattern_length = 0
        self.maximum_pattern_length = 1000
        self.must_appear_items: Optional[List[int]] = None
        self.cooc_map_after: Optional[Dict[int, Dict[int, int]]] = None
        self.cooc_map_equals: Optional[Dict[int, Dict[int, int]]] = None
        self.last_item_position_map: Optional[Dict[int, int]] = None
        self.use_cmap_pruning = True
        self.use_last_position_pruning = False
        self.max_gap = math.inf
        self.output_sequence_identifiers = False

    def run_algorithm(self, input_path: str, output_file_path: str, minsup_rel: float, output_sequence_identifiers: bool) -> None:
        self.output_sequence_identifiers = output_sequence_identifiers
        Bitmap.INTERSECTION_COUNT = 0
        self.pattern_count = 0
        MemoryLogger.get_instance().reset()
        self.start_time = int(time.time() * 1000)
        with open(output_file_path, "w", encoding="utf-8") as writer:
            self.writer = writer
            self._spam(input_path, minsup_rel)
        self.end_time = int(time.time() * 1000)

    def _spam(self, input_path: str, minsup_rel: float) -> None:
        self.vertical_db = {}
        in_memory_db: List[List[int]] = []
        self.sequences_size = []
        self.last_bit_index = 0

        # STEP 0
        with open(input_path, "r", encoding="utf-8") as reader:
            bit_index = 0
            for line in reader:
                if not line or line.startswith(('#', '%', '@')) or line.strip() == "":
                    continue
                # record the starting bit position for this sequence
                self.sequences_size.append(bit_index)

                tokens = line.strip().split()
                transaction_array = [int(tok) for tok in tokens]
                contains_must = False
                for item in transaction_array:
                    if item == -1:
                        bit_index += 1
                    if self.item_must_appear_in_patterns(item):
                        contains_must = True
                if contains_must:
                    in_memory_db.append(transaction_array)
            self.last_bit_index = bit_index - 1

        self.minsup = int(math.ceil(minsup_rel * len(self.sequences_size)))
        if self.minsup == 0:
            self.minsup = 1

        # STEP 1
        with open(input_path, "r", encoding="utf-8") as reader:
            sid = 0
            tid = 0
            for line in reader:
                if not line or line.startswith(('#', '%', '@')) or line.strip() == "":
                    continue
                for token in line.strip().split():
                    if token == "-1":
                        tid += 1
                    elif token == "-2":
                        sid += 1
                        tid = 0
                    else:
                        item = int(token)
                        bitmap_item = self.vertical_db.get(item)
                        if bitmap_item is None:
                            bitmap_item = Bitmap(self.last_bit_index)
                            self.vertical_db[item] = bitmap_item
                        bitmap_item.register_bit(sid, tid, self.sequences_size)

        # STEP 2
        frequent_items: List[int] = []
        filtered_db: Dict[int, Bitmap] = {}
        for item, bitmap in self.vertical_db.items():
            if bitmap.get_support() >= self.minsup:
                if self.minimum_pattern_length <= 1 <= self.maximum_pattern_length:
                    self.save_pattern_size1(item, bitmap)
                frequent_items.append(item)
                filtered_db[item] = bitmap
        self.vertical_db = filtered_db

        if self.maximum_pattern_length <= 1:
            return

        # STEP 3.1 create CMAP
        self.cooc_map_equals = {item: {} for item in frequent_items}
        self.cooc_map_after = {item: {} for item in frequent_items}
        if self.use_last_position_pruning:
            self.last_item_position_map = {}

        for transaction in in_memory_db:
            itemset_count = 0
            already_processed: Set[int] = set()
            equal_processed: Dict[int, Set[int]] = {}
            i = 0
            while i < len(transaction):
                item_i = transaction[i]
                equal_set = equal_processed.setdefault(item_i, set())
                if item_i < 0:
                    itemset_count += 1
                    i += 1
                    continue
                if self.use_last_position_pruning and self.last_item_position_map is not None:
                    last_val = self.last_item_position_map.get(item_i)
                    if last_val is None or last_val < itemset_count:
                        self.last_item_position_map[item_i] = itemset_count

                bitmap_of_item = self.vertical_db.get(item_i)
                if bitmap_of_item is None or bitmap_of_item.get_support() < self.minsup:
                    i += 1
                    continue

                already_processed_b: Set[int] = set()
                same_itemset = True
                j = i + 1
                while j < len(transaction):
                    item_j = transaction[j]
                    if item_j < 0:
                        same_itemset = False
                        j += 1
                        continue
                    bitmap_of_item_j = self.vertical_db.get(item_j)
                    if bitmap_of_item_j is None or bitmap_of_item_j.get_support() < self.minsup:
                        j += 1
                        continue
                    if same_itemset:
                        if item_j not in equal_set:
                            map_eq = self.cooc_map_equals.setdefault(item_i, {})
                            map_eq[item_j] = map_eq.get(item_j, 0) + 1
                            equal_set.add(item_j)
                    elif item_j not in already_processed_b:
                        if item_i in already_processed:
                            j += 1
                            continue
                        map_after = self.cooc_map_after.setdefault(item_i, {})
                        map_after[item_j] = map_after.get(item_j, 0) + 1
                        already_processed_b.add(item_j)
                    j += 1
                already_processed.add(item_i)
                i += 1

        # STEP 3 dfs
        for item, bitmap in self.vertical_db.items():
            prefix = Prefix()
            prefix.add_itemset(Itemset(item))
            self.dfs_pruning(prefix, bitmap, frequent_items, frequent_items, item, 2, item)

    def dfs_pruning(self, prefix: Prefix, prefix_bitmap: Bitmap, sn: List[int], in_items: List[int], has_to_be_greater_than_for_istep: int, m: int, last_appended_item: int) -> None:
        s_temp: List[int] = []
        s_temp_bitmaps: List[Bitmap] = []
        map_support_items_after = self.cooc_map_after.get(last_appended_item) if self.cooc_map_after else None

        for i in sn:
            if self.use_cmap_pruning:
                if map_support_items_after is None:
                    continue
                support = map_support_items_after.get(i, 0)
                if support < self.minsup:
                    continue
            Bitmap.INTERSECTION_COUNT += 1
            new_bitmap = prefix_bitmap.create_new_bitmap_s_step(self.vertical_db[i], self.sequences_size, self.last_bit_index, self.max_gap if self.max_gap != math.inf else (1 << 31) - 1)
            if new_bitmap.get_support_without_gap_total() >= self.minsup:
                s_temp.append(i)
                s_temp_bitmaps.append(new_bitmap)

        for item, new_bitmap in zip(s_temp, s_temp_bitmaps):
            prefix_s = prefix.clone_sequence()
            prefix_s.add_itemset(Itemset(item))
            if new_bitmap.get_support() >= self.minsup:
                if m >= self.minimum_pattern_length:
                    self.save_pattern(prefix_s, new_bitmap)
                if self.maximum_pattern_length > m:
                    self.dfs_pruning(prefix_s, new_bitmap, s_temp, s_temp, item, m + 1, item)

        map_support_items_equals = self.cooc_map_equals.get(last_appended_item) if self.cooc_map_equals else None
        i_temp: List[int] = []
        i_temp_bitmaps: List[Bitmap] = []

        for i in in_items:
            if i > has_to_be_greater_than_for_istep:
                if self.use_cmap_pruning:
                    if map_support_items_equals is None:
                        continue
                    support = map_support_items_equals.get(i, 0)
                    if support < self.minsup:
                        continue
                Bitmap.INTERSECTION_COUNT += 1
                new_bitmap = prefix_bitmap.create_new_bitmap_i_step(self.vertical_db[i], self.sequences_size, self.last_bit_index)
                if new_bitmap.get_support() >= self.minsup:
                    i_temp.append(i)
                    i_temp_bitmaps.append(new_bitmap)

        for item, new_bitmap in zip(i_temp, i_temp_bitmaps):
            prefix_i = prefix.clone_sequence()
            prefix_i.get_itemsets()[prefix_i.size() - 1].add_item(item)
            if m >= self.minimum_pattern_length:
                self.save_pattern(prefix_i, new_bitmap)
            if self.maximum_pattern_length > m:
                self.dfs_pruning(prefix_i, new_bitmap, s_temp, i_temp, item, m + 1, item)

        MemoryLogger.get_instance().check_memory()

    def save_pattern_size1(self, item: int, bitmap: Bitmap) -> None:
        if self.must_appear_items:
            if len(self.must_appear_items) > 1:
                return
            if item not in self.must_appear_items:
                return
        self.pattern_count += 1
        parts = [str(item), " -1 ", "#SUP: ", str(bitmap.get_support())]
        if self.output_sequence_identifiers:
            parts.extend([" #SID: ", bitmap.get_sids(self.sequences_size)])
        assert self.writer is not None
        self.writer.write("".join(parts) + "\n")

    def save_pattern(self, prefix: Prefix, bitmap: Bitmap) -> None:
        if self.must_appear_items:
            items_found: Set[int] = set()
            for itemset in prefix.get_itemsets():
                for item in itemset.get_items():
                    if self.item_must_appear_in_patterns(item):
                        items_found.add(item)
                        if len(items_found) == len(self.must_appear_items):
                            break
            if len(items_found) != len(self.must_appear_items):
                return
        self.pattern_count += 1
        parts: List[str] = []
        for itemset in prefix.get_itemsets():
            for item in itemset.get_items():
                parts.append(str(item))
                parts.append(" ")
            parts.append("-1 ")
        parts.extend(["#SUP: ", str(bitmap.get_support())])
        if self.output_sequence_identifiers:
            parts.extend([" #SID: ", bitmap.get_sids(self.sequences_size)])
        assert self.writer is not None
        self.writer.write("".join(parts) + "\n")

    def print_statistics(self) -> None:
        r = []
        r.append("=============  CM-SPAM - STATISTICS =============")
        r.append(f" Total time ~ {self.end_time - self.start_time} ms")
        r.append(f" Frequent sequences count : {self.pattern_count}")
        r.append(f" Max memory (mb) : {MemoryLogger.get_instance().get_max_memory()}")
        r.append(f" minsup {self.minsup}")
        r.append(f" Intersection count {Bitmap.INTERSECTION_COUNT}")
        r.append("===================================================")
        print("\n".join(r))

    def set_maximum_pattern_length(self, maximum_pattern_length: int) -> None:
        self.maximum_pattern_length = maximum_pattern_length

    def set_minimum_pattern_length(self, minimum_pattern_length: int) -> None:
        self.minimum_pattern_length = minimum_pattern_length

    def set_must_appear_items(self, must_appear_items: List[int]) -> None:
        if must_appear_items:
            self.must_appear_items = must_appear_items
        else:
            self.must_appear_items = None

    def item_must_appear_in_patterns(self, item: int) -> bool:
        return self.must_appear_items is None or item in self.must_appear_items

    def set_max_gap(self, max_gap: int) -> None:
        self.max_gap = max_gap if max_gap is not None else math.inf


class MainTestCMSPAMSaveToFile:
    @staticmethod
    def file_to_path(filename: str) -> str:
        base = Path(__file__).resolve().parent
        return str(base / filename)

    @staticmethod
    def main() -> None:
        input_file = MainTestCMSPAMSaveToFile.file_to_path("contextPrefixSpan.txt")
        output_file = Path(__file__).resolve().parent / "output_python.txt"

        algo = AlgoCMSPAM()
        output_sequence_identifiers = True
        algo.run_algorithm(input_file, str(output_file), 0.5, output_sequence_identifiers)
        algo.print_statistics()


if __name__ == "__main__":
    MainTestCMSPAMSaveToFile.main()
