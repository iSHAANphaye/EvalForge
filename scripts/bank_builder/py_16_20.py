"""Tasks EF-PY-016 through EF-PY-020."""

TASKS = [
    {
        "task_id": "EF-PY-016",
        "title": "Interval Tree with Overlap Search and Merging",
        "language": "python",
        "difficulty": "medium",
        "category": "data_structures",
        "tags": ["interval-tree", "data_structures", "intervals", "geometric", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Interval Tree with Overlap Search and Merging

Implement an augmented binary search tree (Interval Tree) for efficient 1D interval storage, overlap querying, and interval union merging.

## Requirements

Implement the dataclass `Interval`:
- `low: float`
- `high: float`
- `data: Any = None`
- Two intervals `[l1, h1]` and `[l2, h2]` overlap if `max(l1, l2) <= min(h1, h2)`.

Implement the class `IntervalTree`:

- `insert(self, low: float, high: float, data: Any = None) -> None`:
  Inserts an interval `[low, high]` into the tree (`low <= high`).
- `search_overlaps(self, low: float, high: float) -> list[Interval]`:
  Finds all intervals in the tree that overlap with the query interval `[low, high]`.
  Returns a list of `Interval` objects sorted by `low` then `high`.
- `delete(self, low: float, high: float) -> bool`:
  Removes the first interval exactly matching `[low, high]`. Returns `True` if found and deleted, `False` otherwise.
- `merge_overlapping(self) -> list[Interval]`:
  Returns a merged list of contiguous/overlapping intervals covering the exact same set of points, sorted by `low`.
- `to_list(self) -> list[Interval]`:
  Returns all stored intervals sorted by `low` then `high`.
""",
        "starter_code": """from dataclasses import dataclass
from typing import Any


@dataclass
class Interval:
    low: float
    high: float
    data: Any = None


class IntervalTree:
    def __init__(self) -> None:
        \"\"\"Initialize empty Interval Tree.\"\"\"
        pass

    def insert(self, low: float, high: float, data: Any = None) -> None:
        \"\"\"Insert interval [low, high].\"\"\"
        pass

    def search_overlaps(self, low: float, high: float) -> list[Interval]:
        \"\"\"Return all intervals overlapping [low, high] sorted.\"\"\"
        pass

    def delete(self, low: float, high: float) -> bool:
        \"\"\"Delete matching interval [low, high].\"\"\"
        pass

    def merge_overlapping(self) -> list[Interval]:
        \"\"\"Merge all overlapping intervals into minimal disjoint intervals.\"\"\"
        pass

    def to_list(self) -> list[Interval]:
        \"\"\"Return all intervals sorted.\"\"\"
        pass
""",
        "canonical_solution": """from dataclasses import dataclass
from typing import Any


@dataclass
class Interval:
    low: float
    high: float
    data: Any = None


class _Node:
    def __init__(self, interval: Interval) -> None:
        self.interval = interval
        self.max_high = interval.high
        self.left: '_Node | None' = None
        self.right: '_Node | None' = None


class IntervalTree:
    def __init__(self) -> None:
        self.root: _Node | None = None

    def insert(self, low: float, high: float, data: Any = None) -> None:
        if low > high:
            raise ValueError(f"Invalid interval: low ({low}) > high ({high})")
        interval = Interval(float(low), float(high), data)
        self.root = self._insert(self.root, interval)

    def _insert(self, node: _Node | None, interval: Interval) -> _Node:
        if node is None:
            return _Node(interval)

        if interval.low < node.interval.low:
            node.left = self._insert(node.left, interval)
        else:
            node.right = self._insert(node.right, interval)

        node.max_high = max(
            node.interval.high,
            node.left.max_high if node.left else float('-inf'),
            node.right.max_high if node.right else float('-inf')
        )
        return node

    def search_overlaps(self, low: float, high: float) -> list[Interval]:
        results: list[Interval] = []

        def _search(node: _Node | None) -> None:
            if node is None:
                return
            if node.max_high < low:
                return

            if max(node.interval.low, low) <= min(node.interval.high, high):
                results.append(node.interval)

            if node.left and node.left.max_high >= low:
                _search(node.left)

            if node.interval.low <= high:
                _search(node.right)

        _search(self.root)
        return sorted(results, key=lambda x: (x.low, x.high))

    def to_list(self) -> list[Interval]:
        results: list[Interval] = []

        def _inorder(node: _Node | None) -> None:
            if node is None:
                return
            _inorder(node.left)
            results.append(node.interval)
            _inorder(node.right)

        _inorder(self.root)
        return sorted(results, key=lambda x: (x.low, x.high))

    def delete(self, low: float, high: float) -> bool:
        deleted = False

        def _delete(node: _Node | None) -> _Node | None:
            nonlocal deleted
            if node is None:
                return None

            if low == node.interval.low and high == node.interval.high and not deleted:
                deleted = True
                if node.left is None:
                    return node.right
                if node.right is None:
                    return node.left

                # Find in-order successor
                succ = node.right
                while succ.left is not None:
                    succ = succ.left
                node.interval = succ.interval
                node.right = _delete_exact(node.right, succ.interval.low, succ.interval.high)
            elif low < node.interval.low:
                node.left = _delete(node.left)
            else:
                node.right = _delete(node.right)

            node.max_high = max(
                node.interval.high,
                node.left.max_high if node.left else float('-inf'),
                node.right.max_high if node.right else float('-inf')
            )
            return node

        def _delete_exact(node: _Node | None, l: float, h: float) -> _Node | None:
            if node is None:
                return None
            if node.interval.low == l and node.interval.high == h:
                return node.right
            node.left = _delete_exact(node.left, l, h)
            node.max_high = max(
                node.interval.high,
                node.left.max_high if node.left else float('-inf'),
                node.right.max_high if node.right else float('-inf')
            )
            return node

        self.root = _delete(self.root)
        return deleted

    def merge_overlapping(self) -> list[Interval]:
        intervals = self.to_list()
        if not intervals:
            return []

        merged: list[Interval] = [Interval(intervals[0].low, intervals[0].high)]
        for current in intervals[1:]:
            prev = merged[-1]
            if current.low <= prev.high:
                prev.high = max(prev.high, current.high)
            else:
                merged.append(Interval(current.low, current.high))

        return merged
""",
        "visible_tests": """def test_interval_tree_insert_search():
    tree = IntervalTree()
    tree.insert(15, 20)
    tree.insert(10, 30)
    tree.insert(17, 19)
    tree.insert(5, 20)
    tree.insert(12, 15)
    tree.insert(30, 40)

    overlaps = tree.search_overlaps(6, 7)
    ranges = [(iv.low, iv.high) for iv in overlaps]
    assert (5.0, 20.0) in ranges
    assert (10.0, 30.0) not in ranges


def test_merge_overlapping_intervals():
    tree = IntervalTree()
    tree.insert(1, 3)
    tree.insert(2, 6)
    tree.insert(8, 10)
    tree.insert(15, 18)

    merged = tree.merge_overlapping()
    assert [(m.low, m.high) for m in merged] == [(1.0, 6.0), (8.0, 10.0), (15.0, 18.0)]
""",
        "hidden_tests": """import pytest


def test_single_point_overlap():
    tree = IntervalTree()
    tree.insert(10, 20)
    tree.insert(20, 30)
    overlaps = tree.search_overlaps(20, 20)
    assert len(overlaps) == 2


def test_delete_interval():
    tree = IntervalTree()
    tree.insert(10, 20)
    tree.insert(15, 25)
    assert tree.delete(10, 20) is True
    assert tree.delete(10, 20) is False
    assert [(iv.low, iv.high) for iv in tree.to_list()] == [(15.0, 25.0)]


def test_empty_tree_operations():
    tree = IntervalTree()
    assert tree.search_overlaps(0, 10) == []
    assert tree.merge_overlapping() == []
    assert tree.delete(1, 2) is False


def test_fully_contained_intervals():
    tree = IntervalTree()
    tree.insert(0, 100)
    tree.insert(20, 40)
    tree.insert(60, 80)
    merged = tree.merge_overlapping()
    assert len(merged) == 1
    assert (merged[0].low, merged[0].high) == (0.0, 100.0)


def test_invalid_interval_raises():
    tree = IntervalTree()
    with pytest.raises(ValueError):
        tree.insert(20, 10)


def test_scale_intervals():
    tree = IntervalTree()
    for i in range(100):
        tree.insert(i * 10, i * 10 + 5)
    assert len(tree.to_list()) == 100
    overlaps = tree.search_overlaps(24, 32)
    # Overlaps [20, 25] and [30, 35]
    assert len(overlaps) == 2
""",
    },
    {
        "task_id": "EF-PY-017",
        "title": "Work-Stealing Task Queue Simulator",
        "language": "python",
        "difficulty": "medium",
        "category": "concurrency",
        "tags": ["concurrency", "work-stealing", "deque", "thread-pool", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Work-Stealing Task Queue Simulator

Implement a thread-safe Chase-Lev work-stealing thread pool task scheduler.

## Operational Model

- Each worker thread owns a double-ended queue (deque).
- **Worker thread**: Pushes and pops tasks from the **bottom** of its own deque in LIFO order (cache locality).
- **Thief threads**: When a worker has no local tasks, it steals tasks from the **top** of other workers' deques in FIFO order (fairness).

## Requirements

Implement the class `WorkStealingPool`:

- `__init__(self, num_workers: int)`:
  Initializes pool with `num_workers >= 1` worker queues.
- `submit(self, worker_id: int, task: Any) -> None`:
  Pushes `task` to the bottom of `worker_id`'s deque.
- `worker_pop(self, worker_id: int) -> Any | None`:
  Pops a task from the bottom (LIFO) of `worker_id`'s deque. If empty, attempts to steal from any other worker.
  Returns `task`, or `None` if all queues are empty.
- `steal(self, victim_id: int) -> Any | None`:
  Steals a task from the top (FIFO) of `victim_id`'s deque. Returns `task`, or `None` if victim's deque is empty.
- `steal_any(self, thief_id: int) -> Any | None`:
  Attempts to steal from other workers in round-robin order `[(thief_id + 1) % N, (thief_id + 2) % N, ...]`.
  Returns the first successfully stolen task, or `None` if no tasks are available.
- `execute_all(self) -> list[tuple[int, Any]]`:
  Simulates execution of all pending tasks until the entire pool is depleted.
  Returns an ordered list of `(worker_id_who_executed, task)`.
""",
        "starter_code": """from typing import Any


class WorkStealingPool:
    def __init__(self, num_workers: int) -> None:
        \"\"\"Initialize work-stealing pool with num_workers deques.\"\"\"
        pass

    def submit(self, worker_id: int, task: Any) -> None:
        \"\"\"Submit task to worker's local deque.\"\"\"
        pass

    def worker_pop(self, worker_id: int) -> Any | None:
        \"\"\"Pop task LIFO or steal from another worker.\"\"\"
        pass

    def steal(self, victim_id: int) -> Any | None:
        \"\"\"Steal task FIFO from victim worker.\"\"\"
        pass

    def steal_any(self, thief_id: int) -> Any | None:
        \"\"\"Attempt to steal from any other worker.\"\"\"
        pass

    def execute_all(self) -> list[tuple[int, Any]]:
        \"\"\"Drain and execute all tasks across workers.\"\"\"
        pass
""",
        "canonical_solution": """from collections import deque
import threading
from typing import Any


class WorkStealingPool:
    def __init__(self, num_workers: int) -> None:
        if num_workers < 1:
            raise ValueError("num_workers must be at least 1")
        self.num_workers = num_workers
        self._queues: list[deque[Any]] = [deque() for _ in range(num_workers)]
        self._locks: list[threading.Lock] = [threading.Lock() for _ in range(num_workers)]

    def submit(self, worker_id: int, task: Any) -> None:
        if not (0 <= worker_id < self.num_workers):
            raise IndexError("worker_id out of range")
        with self._locks[worker_id]:
            self._queues[worker_id].append(task)  # append to bottom

    def worker_pop(self, worker_id: int) -> Any | None:
        if not (0 <= worker_id < self.num_workers):
            raise IndexError("worker_id out of range")

        # Try popping from bottom (LIFO)
        with self._locks[worker_id]:
            if self._queues[worker_id]:
                return self._queues[worker_id].pop()

        # If empty, attempt to steal from others
        return self.steal_any(worker_id)

    def steal(self, victim_id: int) -> Any | None:
        if not (0 <= victim_id < self.num_workers):
            raise IndexError("victim_id out of range")

        with self._locks[victim_id]:
            if self._queues[victim_id]:
                return self._queues[victim_id].popleft()  # steal from top (FIFO)
        return None

    def steal_any(self, thief_id: int) -> Any | None:
        for offset in range(1, self.num_workers):
            victim = (thief_id + offset) % self.num_workers
            stolen = self.steal(victim)
            if stolen is not None:
                return stolen
        return None

    def execute_all(self) -> list[tuple[int, Any]]:
        executed: list[tuple[int, Any]] = []
        active = True
        while active:
            active = False
            for wid in range(self.num_workers):
                task = self.worker_pop(wid)
                if task is not None:
                    executed.append((wid, task))
                    active = True
        return executed
""",
        "visible_tests": """def test_lifo_local_worker_order():
    pool = WorkStealingPool(num_workers=2)
    pool.submit(0, "task1")
    pool.submit(0, "task2")
    pool.submit(0, "task3")

    # Worker 0 should pop in LIFO order
    assert pool.worker_pop(0) == "task3"
    assert pool.worker_pop(0) == "task2"
    assert pool.worker_pop(0) == "task1"


def test_fifo_work_stealing():
    pool = WorkStealingPool(num_workers=2)
    pool.submit(0, "first")
    pool.submit(0, "second")

    # Worker 1 steals from Worker 0 in FIFO order
    assert pool.steal(0) == "first"
    # Worker 0 gets remaining task
    assert pool.worker_pop(0) == "second"
""",
        "hidden_tests": """def test_steal_any_round_robin():
    pool = WorkStealingPool(num_workers=4)
    pool.submit(2, "work_item")

    # Worker 0 steals from Worker 2
    task = pool.steal_any(0)
    assert task == "work_item"
    assert pool.steal_any(0) is None


def test_execute_all_drains_everything():
    pool = WorkStealingPool(num_workers=3)
    pool.submit(0, 100)
    pool.submit(0, 101)
    pool.submit(1, 200)

    results = pool.execute_all()
    tasks = [t for _, t in results]
    assert sorted(tasks) == [100, 101, 200]


def test_single_worker_pool():
    pool = WorkStealingPool(num_workers=1)
    pool.submit(0, "a")
    pool.submit(0, "b")
    assert pool.steal(0) == "a"
    assert pool.worker_pop(0) == "b"
    assert pool.worker_pop(0) is None


def test_empty_steal_returns_none():
    pool = WorkStealingPool(num_workers=2)
    assert pool.steal(0) is None
    assert pool.steal_any(1) is None
    assert pool.worker_pop(0) is None


def test_concurrent_stealing_threads():
    import concurrent.futures
    pool = WorkStealingPool(num_workers=4)
    for i in range(200):
        pool.submit(0, i)

    stolen_tasks = []

    def thief(tid: int):
        local = []
        while True:
            t = pool.worker_pop(tid)
            if t is None:
                break
            local.append(t)
        return local

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(thief, i) for i in range(4)]
        for f in concurrent.futures.as_completed(futures):
            stolen_tasks.extend(f.result())

    assert len(stolen_tasks) == 200
    assert sorted(stolen_tasks) == list(range(200))


def test_invalid_worker_id_raises():
    import pytest
    pool = WorkStealingPool(num_workers=2)
    with pytest.raises(IndexError):
        pool.submit(2, "invalid")
    with pytest.raises(IndexError):
        pool.worker_pop(5)
""",
    },
    {
        "task_id": "EF-PY-018",
        "title": "Binary Protocol Serializer with Varint and Checksum",
        "language": "python",
        "difficulty": "medium",
        "category": "systems",
        "tags": ["binary", "serialization", "varint", "crc32", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Binary Protocol Serializer with Varint and Checksum

Implement a compact binary frame serializer and deserializer with unsigned LEB128 Varint encoding, header flags, and CRC32 checksum verification.

## Frame Specification

`[Magic: 2 bytes] [MessageID: Varint] [Flags: 1 byte] [PayloadLength: Varint] [Payload: N bytes] [CRC32: 4 bytes BE]`

- **Magic bytes**: `0xEF, 0x01`
- **MessageID**: Unsigned integer encoded via variable-length LEB128.
- **Flags**: 1 byte (bitfield `0..255`).
- **PayloadLength**: Unsigned integer encoded via LEB128 representing byte length of payload.
- **Payload**: Raw byte buffer of length `PayloadLength`.
- **CRC32**: 4 bytes in big-endian network order computed over `Payload`.

## Requirements

Implement the class `BinaryProtocolCodec`:

- `encode_varint(value: int) -> bytes`:
  Encodes non-negative integer using LEB128 (7 data bits per byte, MSB indicates continuation).
- `decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]`:
  Decodes integer from `data` starting at `offset`. Returns `(decoded_value, new_offset)`.
- `encode_message(msg_id: int, flags: int, payload: bytes) -> bytes`:
  Packs message fields into compliant binary frame.
- `decode_message(frame: bytes) -> tuple[int, int, bytes]`:
  Validates magic bytes, decodes fields, and verifies CRC32 checksum.
  Returns `(msg_id, flags, payload)`.
  Raises `ValueError` if magic is invalid, frame is truncated, or CRC32 checksum fails.
""",
        "starter_code": """class BinaryProtocolCodec:
    @staticmethod
    def encode_varint(value: int) -> bytes:
        \"\"\"Encode unsigned integer using LEB128 varint.\"\"\"
        pass

    @staticmethod
    def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
        \"\"\"Decode LEB128 varint, returning (value, next_offset).\"\"\"
        pass

    @staticmethod
    def encode_message(msg_id: int, flags: int, payload: bytes) -> bytes:
        \"\"\"Pack frame with magic, varints, payload, and CRC32.\"\"\"
        pass

    @staticmethod
    def decode_message(frame: bytes) -> tuple[int, int, bytes]:
        \"\"\"Unpack frame and verify CRC32, returning (msg_id, flags, payload).\"\"\"
        pass
""",
        "canonical_solution": """import struct
import zlib


class BinaryProtocolCodec:
    MAGIC = bytes([0xEF, 0x01])

    @staticmethod
    def encode_varint(value: int) -> bytes:
        if value < 0:
            raise ValueError("Varint must be non-negative")
        out = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            if value > 0:
                out.append(byte | 0x80)
            else:
                out.append(byte)
                break
        return bytes(out)

    @staticmethod
    def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
        result = 0
        shift = 0
        i = offset
        n = len(data)

        while i < n:
            byte = data[i]
            i += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return result, i
            shift += 7
            if shift >= 64:
                raise ValueError("Varint overflow")

        raise ValueError("Unexpected EOF while decoding varint")

    @classmethod
    def encode_message(cls, msg_id: int, flags: int, payload: bytes) -> bytes:
        if not (0 <= flags <= 255):
            raise ValueError("Flags must fit in 1 byte (0..255)")

        buf = bytearray(cls.MAGIC)
        buf.extend(cls.encode_varint(msg_id))
        buf.append(flags)
        buf.extend(cls.encode_varint(len(payload)))
        buf.extend(payload)

        crc = zlib.crc32(payload) & 0xFFFFFFFF
        buf.extend(struct.pack(">I", crc))
        return bytes(buf)

    @classmethod
    def decode_message(cls, frame: bytes) -> tuple[int, int, bytes]:
        if len(frame) < 7:  # Min possible frame: 2 magic + 1 id + 1 flag + 1 len + 0 payload + 4 crc
            raise ValueError("Frame too short")

        if frame[:2] != cls.MAGIC:
            raise ValueError("Invalid magic bytes header")

        offset = 2
        msg_id, offset = cls.decode_varint(frame, offset)

        if offset >= len(frame):
            raise ValueError("Truncated frame at flags")
        flags = frame[offset]
        offset += 1

        payload_len, offset = cls.decode_varint(frame, offset)

        if offset + payload_len + 4 != len(frame):
            raise ValueError("Payload length mismatch with frame boundary")

        payload = frame[offset:offset + payload_len]
        offset += payload_len

        expected_crc = struct.unpack(">I", frame[offset:offset + 4])[0]
        actual_crc = zlib.crc32(payload) & 0xFFFFFFFF

        if expected_crc != actual_crc:
            raise ValueError(f"CRC32 mismatch: expected {expected_crc:#x}, got {actual_crc:#x}")

        return msg_id, flags, payload
""",
        "visible_tests": """def test_varint_roundtrip():
    codec = BinaryProtocolCodec
    for val in [0, 1, 127, 128, 300, 16384, 1000000]:
        encoded = codec.encode_varint(val)
        decoded, off = codec.decode_varint(encoded)
        assert decoded == val
        assert off == len(encoded)


def test_frame_encode_decode():
    codec = BinaryProtocolCodec
    msg_id = 42
    flags = 0x05
    payload = b"Sample JSON or binary payload"

    frame = codec.encode_message(msg_id, flags, payload)
    d_id, d_flags, d_payload = codec.decode_message(frame)
    assert d_id == msg_id
    assert d_flags == flags
    assert d_payload == payload
""",
        "hidden_tests": """import pytest


def test_corrupted_crc32_raises():
    codec = BinaryProtocolCodec
    frame = bytearray(codec.encode_message(10, 0, b"Secret Payload"))
    # Corrupt last byte of CRC
    frame[-1] ^= 0xFF
    with pytest.raises(ValueError, match="CRC32 mismatch"):
        codec.decode_message(bytes(frame))


def test_invalid_magic_raises():
    codec = BinaryProtocolCodec
    frame = bytearray(codec.encode_message(1, 0, b"data"))
    frame[0] = 0x00
    with pytest.raises(ValueError, match="Invalid magic"):
        codec.decode_message(bytes(frame))


def test_empty_payload():
    codec = BinaryProtocolCodec
    frame = codec.encode_message(100, 0xFF, b"")
    msg_id, flags, payload = codec.decode_message(frame)
    assert msg_id == 100
    assert flags == 0xFF
    assert payload == b""


def test_truncated_frame():
    codec = BinaryProtocolCodec
    frame = codec.encode_message(1, 0, b"some content")
    with pytest.raises(ValueError):
        codec.decode_message(frame[:5])


def test_large_payload_scale():
    codec = BinaryProtocolCodec
    large_payload = b"X" * 100000
    frame = codec.encode_message(99999, 12, large_payload)
    msg_id, flags, payload = codec.decode_message(frame)
    assert msg_id == 99999
    assert flags == 12
    assert payload == large_payload


def test_negative_varint_raises():
    codec = BinaryProtocolCodec
    with pytest.raises(ValueError):
        codec.encode_varint(-1)
""",
    },
    {
        "task_id": "EF-PY-019",
        "title": "Monotonic Stack for Sliding Window Maximum",
        "language": "python",
        "difficulty": "easy",
        "category": "algorithmic",
        "tags": ["monotonic-queue", "sliding-window", "deque", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Monotonic Queue for Sliding Window Maximum

Implement a Monotonic Queue data structure and use it to compute the sliding window maximum of an integer array in strictly $O(N)$ linear time.

## Requirements

Implement the class `MonotonicQueue`:
- `push(self, val: int) -> None`:
  Inserts `val`, ejecting all smaller elements from the back to maintain non-increasing order.
- `pop(self, val: int) -> None`:
  Pops `val` from the front if and only if the front element equals `val`.
- `max(self) -> int`:
  Returns the maximum element currently held in $O(1)$ time. Raises `IndexError` if queue is empty.
- `__len__(self) -> int`:
  Returns count of elements.

Implement the class `SlidingWindowMax`:
- `max_sliding_window(self, nums: list[int], k: int) -> list[int]`:
  Returns the maximum value across all sliding windows of size $k$.
  - If $k \\le 0$ or `nums` is empty, returns `[]`.
  - If $k \\ge \\text{len}(nums)$, returns `[max(nums)]`.
  - Runs in $O(N)$ time complexity.
""",
        "starter_code": """class MonotonicQueue:
    def __init__(self) -> None:
        \"\"\"Initialize Monotonic Queue.\"\"\"
        pass

    def push(self, val: int) -> None:
        \"\"\"Push value maintaining descending order.\"\"\"
        pass

    def pop(self, val: int) -> None:
        \"\"\"Pop value from front if equal.\"\"\"
        pass

    def max(self) -> int:
        \"\"\"Return current maximum in O(1).\"\"\"
        pass

    def __len__(self) -> int:
        \"\"\"Return queue length.\"\"\"
        pass


class SlidingWindowMax:
    def max_sliding_window(self, nums: list[int], k: int) -> list[int]:
        \"\"\"Compute sliding window maximum in O(N) time.\"\"\"
        pass
""",
        "canonical_solution": """from collections import deque


class MonotonicQueue:
    def __init__(self) -> None:
        self._deque: deque[int] = deque()

    def push(self, val: int) -> None:
        while self._deque and self._deque[-1] < val:
            self._deque.pop()
        self._deque.append(val)

    def pop(self, val: int) -> None:
        if self._deque and self._deque[0] == val:
            self._deque.popleft()

    def max(self) -> int:
        if not self._deque:
            raise IndexError("Queue is empty")
        return self._deque[0]

    def __len__(self) -> int:
        return len(self._deque)


class SlidingWindowMax:
    def max_sliding_window(self, nums: list[int], k: int) -> list[int]:
        if not nums or k <= 0:
            return []
        if k >= len(nums):
            return [max(nums)]

        mq = MonotonicQueue()
        res: list[int] = []

        for i in range(k):
            mq.push(nums[i])
        res.append(mq.max())

        for i in range(k, len(nums)):
            mq.pop(nums[i - k])
            mq.push(nums[i])
            res.append(mq.max())

        return res
""",
        "visible_tests": """def test_sliding_window_basic():
    sw = SlidingWindowMax()
    nums = [1, 3, -1, -3, 5, 3, 6, 7]
    assert sw.max_sliding_window(nums, k=3) == [3, 3, 5, 5, 6, 7]


def test_monotonic_queue_operations():
    mq = MonotonicQueue()
    mq.push(5)
    mq.push(2)
    mq.push(8)
    assert mq.max() == 8
    mq.pop(8)
    assert len(mq) == 0
""",
        "hidden_tests": """import pytest


def test_window_size_one():
    sw = SlidingWindowMax()
    nums = [4, 2, 7, 1]
    assert sw.max_sliding_window(nums, k=1) == [4, 2, 7, 1]


def test_window_size_equals_or_exceeds_length():
    sw = SlidingWindowMax()
    nums = [3, 1, 9, 2]
    assert sw.max_sliding_window(nums, k=4) == [9]
    assert sw.max_sliding_window(nums, k=10) == [9]


def test_empty_or_zero_window():
    sw = SlidingWindowMax()
    assert sw.max_sliding_window([], k=3) == []
    assert sw.max_sliding_window([1, 2], k=0) == []
    assert sw.max_sliding_window([1, 2], k=-1) == []


def test_strictly_decreasing_and_increasing():
    sw = SlidingWindowMax()
    assert sw.max_sliding_window([5, 4, 3, 2, 1], k=2) == [5, 4, 3, 2]
    assert sw.max_sliding_window([1, 2, 3, 4, 5], k=2) == [2, 3, 4, 5]


def test_empty_monotonic_queue_raises():
    mq = MonotonicQueue()
    with pytest.raises(IndexError):
        mq.max()


def test_large_scale_n_10000():
    sw = SlidingWindowMax()
    n = 10000
    nums = list(range(n))
    k = 50
    res = sw.max_sliding_window(nums, k=k)
    assert len(res) == n - k + 1
    assert res[0] == k - 1
    assert res[-1] == n - 1
""",
    },
    {
        "task_id": "EF-PY-020",
        "title": "Graph Cut Vertex and Bridge Detection via Tarjan's DFS",
        "language": "python",
        "difficulty": "medium",
        "category": "algorithmic",
        "tags": ["graph", "tarjan", "articulation-points", "bridges", "dfs", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Graph Cut Vertex and Bridge Detection via Tarjan's DFS

Implement Tarjan's Depth-First Search algorithm to find all articulation points (cut vertices) and bridges (cut edges) in an undirected graph.

## Definitions

- **Articulation Point (Cut Vertex)**: A vertex whose removal strictly increases the number of connected components in the graph.
- **Bridge (Cut Edge)**: An edge whose removal strictly increases the number of connected components.
- **Biconnected Graph**: A connected graph with $\ge 3$ vertices that has no articulation points.

## Requirements

Implement the class `TarjanBiconnected`:

- `__init__(self, num_vertices: int)`:
  Initializes graph with vertices `0` through `num_vertices - 1`.
- `add_edge(self, u: int, v: int) -> None`:
  Adds an undirected edge between `u` and `v` (`u != v`).
- `find_articulation_points(self) -> set[int]`:
  Returns the set of vertex indices that are articulation points.
- `find_bridges(self) -> list[tuple[int, int]]`:
  Returns the list of bridges formatted as canonical sorted tuples `(min(u, v), max(u, v))`, ordered lexicographically.
- `is_biconnected(self) -> bool`:
  Returns `True` if the graph has $\ge 3$ vertices, is fully connected, and contains zero articulation points.
""",
        "starter_code": """class TarjanBiconnected:
    def __init__(self, num_vertices: int) -> None:
        \"\"\"Initialize graph with num_vertices vertices (0..num_vertices-1).\"\"\"
        pass

    def add_edge(self, u: int, v: int) -> None:
        \"\"\"Add undirected edge between u and v.\"\"\"
        pass

    def find_articulation_points(self) -> set[int]:
        \"\"\"Return set of cut vertex indices.\"\"\"
        pass

    def find_bridges(self) -> list[tuple[int, int]]:
        \"\"\"Return sorted list of bridge edges (u, v) where u < v.\"\"\"
        pass

    def is_biconnected(self) -> bool:
        \"\"\"Return True if graph is connected and has no articulation points (N >= 3).\"\"\"
        pass
""",
        "canonical_solution": """class TarjanBiconnected:
    def __init__(self, num_vertices: int) -> None:
        if num_vertices < 0:
            raise ValueError("num_vertices cannot be negative")
        self.n = num_vertices
        self.adj: list[list[int]] = [[] for _ in range(num_vertices)]

    def add_edge(self, u: int, v: int) -> None:
        if u == v or not (0 <= u < self.n and 0 <= v < self.n):
            return
        self.adj[u].append(v)
        self.adj[v].append(u)

    def _dfs(self) -> tuple[set[int], list[tuple[int, int]], int]:
        tin = [-1] * self.n
        low = [-1] * self.n
        timer = 0
        art_points: set[int] = set()
        bridges: list[tuple[int, int]] = []
        components = 0

        def dfs_visit(v: int, p: int = -1) -> None:
            nonlocal timer
            tin[v] = low[v] = timer
            timer += 1
            children = 0

            for to in self.adj[v]:
                if to == p:
                    continue
                if tin[to] != -1:
                    low[v] = min(low[v], tin[to])
                else:
                    dfs_visit(to, v)
                    low[v] = min(low[v], low[to])
                    if low[to] >= tin[v] and p != -1:
                        art_points.add(v)
                    if low[to] > tin[v]:
                        bridges.append((min(v, to), max(v, to)))
                    children += 1

            if p == -1 and children > 1:
                art_points.add(v)

        for i in range(self.n):
            if tin[i] == -1:
                components += 1
                dfs_visit(i)

        bridges.sort()
        return art_points, bridges, components

    def find_articulation_points(self) -> set[int]:
        art_points, _, _ = self._dfs()
        return art_points

    def find_bridges(self) -> list[tuple[int, int]]:
        _, bridges, _ = self._dfs()
        return bridges

    def is_biconnected(self) -> bool:
        if self.n < 3:
            return False
        art_points, _, components = self._dfs()
        # Must be connected (single component) and have zero articulation points
        return components == 1 and len(art_points) == 0
""",
        "visible_tests": """def test_articulation_points_bowtie():
    # Bowtie graph: 0-1-2 and 2-3-4 connected at vertex 2
    g = TarjanBiconnected(5)
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 0)
    g.add_edge(2, 3)
    g.add_edge(3, 4)
    g.add_edge(4, 2)

    assert g.find_articulation_points() == {2}
    assert g.find_bridges() == []
    assert g.is_biconnected() is False


def test_bridges_simple():
    # 0 - 1 - 2
    g = TarjanBiconnected(3)
    g.add_edge(0, 1)
    g.add_edge(1, 2)

    assert g.find_articulation_points() == {1}
    assert g.find_bridges() == [(0, 1), (1, 2)]
""",
        "hidden_tests": """def test_cycle_graph_is_biconnected():
    # Triangle cycle 0-1-2-0
    g = TarjanBiconnected(3)
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 0)

    assert g.find_articulation_points() == set()
    assert g.find_bridges() == []
    assert g.is_biconnected() is True


def test_disconnected_components():
    g = TarjanBiconnected(4)
    g.add_edge(0, 1)
    g.add_edge(2, 3)
    assert g.is_biconnected() is False
    assert g.find_bridges() == [(0, 1), (2, 3)]


def test_star_graph():
    # Center vertex 0 connected to 1, 2, 3, 4
    g = TarjanBiconnected(5)
    for leaf in range(1, 5):
        g.add_edge(0, leaf)

    assert g.find_articulation_points() == {0}
    assert len(g.find_bridges()) == 4


def test_self_loop_and_duplicate_edges():
    g = TarjanBiconnected(3)
    g.add_edge(0, 0)  # self loop ignored
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    assert g.find_bridges() == [(0, 1), (1, 2)]


def test_scale_ring_lattice():
    n = 100
    g = TarjanBiconnected(n)
    for i in range(n):
        g.add_edge(i, (i + 1) % n)
        g.add_edge(i, (i + 2) % n)

    assert g.find_articulation_points() == set()
    assert g.find_bridges() == []
    assert g.is_biconnected() is True


def test_parameter_validation():
    import pytest
    with pytest.raises(ValueError):
        TarjanBiconnected(-1)
""",
    },
]
