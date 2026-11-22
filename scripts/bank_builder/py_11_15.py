"""Tasks EF-PY-011 through EF-PY-015."""

TASKS = [
    {
        "task_id": "EF-PY-011",
        "title": "Sliding-Window TCP Packet Reassembly Buffer",
        "language": "python",
        "difficulty": "medium",
        "category": "systems",
        "tags": ["networking", "tcp", "buffer", "packet-reassembly", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Sliding-Window TCP Packet Reassembly Buffer

Implement a TCP packet reassembly buffer that simulates the transport layer's receive window. It handles out-of-order, overlapping, duplicate, and fragmented byte segments.

## Requirements

Implement the class `PacketReassemblyBuffer`:

- `__init__(self, initial_seq: int = 0, window_size: int = 65535)`:
  Initializes reassembly buffer with the initial expected byte sequence number (`initial_seq >= 0`) and sliding window capacity (`window_size >= 1`).
- `receive_segment(self, seq: int, data: bytes) -> bytes`:
  Processes an incoming segment starting at byte sequence number `seq`.
  - Discards any data falling entirely before `expected_seq` or completely beyond the current window boundary `[expected_seq, expected_seq + window_size)`.
  - Trims overlapping slices that are already received or buffered.
  - If the segment fills the contiguous gap starting at `expected_seq`, returns all newly contiguous in-order bytes and advances `expected_seq`.
  - Otherwise, stores the out-of-order fragment in the buffer and returns `b""`.
- `expected_seq(self) -> int`:
  Returns the current next expected byte sequence number.
- `buffered_bytes_count(self) -> int`:
  Returns the total count of non-overlapping buffered bytes waiting for preceding gaps to be filled.
- `is_empty(self) -> bool`:
  Returns `True` if no out-of-order segments are currently buffered, `False` otherwise.
""",
        "starter_code": """class PacketReassemblyBuffer:
    def __init__(self, initial_seq: int = 0, window_size: int = 65535) -> None:
        \"\"\"Initialize TCP packet reassembly buffer with initial sequence number and window capacity.\"\"\"
        pass

    def receive_segment(self, seq: int, data: bytes) -> bytes:
        \"\"\"Receive segment, buffer out-of-order bytes, and return newly contiguous in-order bytes.\"\"\"
        pass

    def expected_seq(self) -> int:
        \"\"\"Return next expected sequence number.\"\"\"
        pass

    def buffered_bytes_count(self) -> int:
        \"\"\"Return count of out-of-order buffered bytes.\"\"\"
        pass

    def is_empty(self) -> bool:
        \"\"\"Return True if no out-of-order packets are held.\"\"\"
        pass
""",
        "canonical_solution": """class PacketReassemblyBuffer:
    def __init__(self, initial_seq: int = 0, window_size: int = 65535) -> None:
        if initial_seq < 0:
            raise ValueError("initial_seq must be non-negative")
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        self._expected_seq = initial_seq
        self._window_size = window_size
        self._buffer: dict[int, bytes] = {}

    def receive_segment(self, seq: int, data: bytes) -> bytes:
        if not data:
            return b""

        seg_end = seq + len(data)
        max_allowed = self._expected_seq + self._window_size

        # Completely before expected sequence or completely outside window
        if seg_end <= self._expected_seq or seq >= max_allowed:
            return b""

        # Trim left overlap (already received)
        if seq < self._expected_seq:
            offset = self._expected_seq - seq
            data = data[offset:]
            seq = self._expected_seq

        # Trim right overflow (beyond window)
        if seq + len(data) > max_allowed:
            excess = (seq + len(data)) - max_allowed
            data = data[:-excess]

        if not data:
            return b""

        # Store into buffer by merging overlapping slices
        self._merge_into_buffer(seq, data)

        # Check if contiguous stream is available from expected_seq
        delivered = bytearray()
        while self._expected_seq in self._buffer:
            chunk = self._buffer.pop(self._expected_seq)
            delivered.extend(chunk)
            self._expected_seq += len(chunk)

        return bytes(delivered)

    def _merge_into_buffer(self, seq: int, data: bytes) -> None:
        new_start = seq
        new_end = seq + len(data)
        new_bytes = bytearray(data)

        overlaps = []
        for s, d in self._buffer.items():
            e = s + len(d)
            if not (new_end < s or new_start > e):
                overlaps.append((s, d))

        for s, d in overlaps:
            e = s + len(d)
            del self._buffer[s]
            if s < new_start:
                prefix = d[:new_start - s]
                new_bytes = bytearray(prefix) + new_bytes
                new_start = s
            if e > new_end:
                suffix = d[new_end - s:]
                new_bytes.extend(suffix)
                new_end = e

        self._buffer[new_start] = bytes(new_bytes)

    def expected_seq(self) -> int:
        return self._expected_seq

    def buffered_bytes_count(self) -> int:
        return sum(len(d) for d in self._buffer.values())

    def is_empty(self) -> bool:
        return len(self._buffer) == 0
""",
        "visible_tests": """def test_in_order_packet_arrival():
    buf = PacketReassemblyBuffer(initial_seq=0)
    out1 = buf.receive_segment(0, b"Hello, ")
    out2 = buf.receive_segment(7, b"World!")
    assert out1 == b"Hello, "
    assert out2 == b"World!"
    assert buf.expected_seq() == 13
    assert buf.is_empty() is True


def test_out_of_order_reassembly():
    buf = PacketReassemblyBuffer(initial_seq=0)
    # Packet 2 arrives first
    assert buf.receive_segment(5, b"World") == b""
    assert buf.buffered_bytes_count() == 5
    assert buf.is_empty() is False

    # Packet 1 arrives second, unlocking contiguous stream
    assert buf.receive_segment(0, b"Hello") == b"HelloWorld"
    assert buf.expected_seq() == 10
    assert buf.is_empty() is True
""",
        "hidden_tests": """def test_duplicate_and_overlapping_packets():
    buf = PacketReassemblyBuffer(initial_seq=100)
    assert buf.receive_segment(100, b"ABC") == b"ABC"
    # Duplicate arrival of previous data
    assert buf.receive_segment(100, b"ABC") == b""
    # Overlapping packet covering partially delivered and new
    assert buf.receive_segment(102, b"CDEF") == b"DEF"
    assert buf.expected_seq() == 106


def test_packets_exceeding_window_dropped():
    buf = PacketReassemblyBuffer(initial_seq=0, window_size=10)
    # Segment starting at 12 is outside window [0, 10)
    assert buf.receive_segment(12, b"OUT_OF_BOUNDS") == b""
    assert buf.buffered_bytes_count() == 0


def test_multiple_gaps_filled_progressively():
    buf = PacketReassemblyBuffer(initial_seq=0)
    buf.receive_segment(20, b"FOUR")
    buf.receive_segment(10, b"12345")
    buf.receive_segment(15, b"THREE")
    assert buf.buffered_bytes_count() == 14

    # Fill hole 0..10
    out = buf.receive_segment(0, b"0123456789")
    assert out == b"012345678912345THREEFOUR"
    assert buf.expected_seq() == 24
    assert buf.is_empty() is True


def test_empty_segment():
    buf = PacketReassemblyBuffer(initial_seq=5)
    assert buf.receive_segment(5, b"") == b""
    assert buf.expected_seq() == 5


def test_scale_reverse_packet_stream():
    buf = PacketReassemblyBuffer(initial_seq=0, window_size=20000)
    chunk_size = 10
    num_chunks = 100

    # Deliver in reverse order: 99, 98, ..., 1
    for i in reversed(range(1, num_chunks)):
        seq = i * chunk_size
        data = f"{i:010d}".encode()
        assert buf.receive_segment(seq, data) == b""

    # Deliver chunk 0 to unlock all
    delivered = buf.receive_segment(0, f"{0:010d}".encode())
    assert len(delivered) == num_chunks * chunk_size
    assert buf.expected_seq() == num_chunks * chunk_size
    assert buf.is_empty() is True


def test_parameter_validation():
    import pytest
    with pytest.raises(ValueError):
        PacketReassemblyBuffer(initial_seq=-1)
    with pytest.raises(ValueError):
        PacketReassemblyBuffer(window_size=0)
""",
    },
    {
        "task_id": "EF-PY-012",
        "title": "Raft Log Compaction Buffer with Index Offsets",
        "language": "python",
        "difficulty": "hard",
        "category": "systems",
        "tags": ["raft", "consensus", "distributed-systems", "compaction", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Raft Log Compaction Buffer with Index Offsets

Implement a replicated log buffer for the Raft distributed consensus protocol that supports log compaction (snapshotting) with 1-based logical index offset mapping.

## Requirements

Implement the dataclass `LogEntry`:
- `index: int`: 1-based monotonic log index.
- `term: int`: Election term during which the entry was proposed.
- `command: Any`: Arbitrary state-machine payload.

Implement the class `RaftLogBuffer`:

- `__init__(self, initial_snapshot_index: int = 0, initial_snapshot_term: int = 0)`:
  Initializes log buffer with the last included snapshot index and term.
- `append(self, term: int, command: Any) -> LogEntry`:
  Appends a new entry with `index = self.last_index() + 1` and returns the created `LogEntry`.
- `truncate_after(self, index: int) -> None`:
  Removes all entries with `entry.index > index` to handle leader conflict resolution.
- `compact(self, snapshot_index: int, snapshot_term: int) -> bool`:
  Discards all buffered entries up to and including `snapshot_index`. Updates `last_included_index` and `last_included_term`.
  Returns `True` if compaction was applied, or `False` if `snapshot_index <= last_included_index`.
- `get_entry(self, index: int) -> LogEntry | None`:
  Returns the entry at logical `index`. Returns `None` if `index <= last_included_index` (already compacted) or `index > last_index()`.
- `get_entries_from(self, index: int) -> list[LogEntry]`:
  Returns all buffered entries from logical `index` onward. Returns empty list if `index > last_index()`.
  Raises `ValueError` if `index <= last_included_index` (compacted data requested).
- `last_index(self) -> int`:
  Returns the highest index stored in log or snapshot.
- `last_term(self) -> int`:
  Returns the term associated with `last_index()`.
- `first_available_index(self) -> int`:
  Returns `last_included_index + 1`.
""",
        "starter_code": """from dataclasses import dataclass
from typing import Any


@dataclass
class LogEntry:
    index: int
    term: int
    command: Any


class RaftLogBuffer:
    def __init__(self, initial_snapshot_index: int = 0, initial_snapshot_term: int = 0) -> None:
        \"\"\"Initialize log buffer with initial snapshot index and term.\"\"\"
        pass

    def append(self, term: int, command: Any) -> LogEntry:
        \"\"\"Append new entry to log.\"\"\"
        pass

    def truncate_after(self, index: int) -> None:
        \"\"\"Truncate all entries following index.\"\"\"
        pass

    def compact(self, snapshot_index: int, snapshot_term: int) -> bool:
        \"\"\"Discard entries up to snapshot_index.\"\"\"
        pass

    def get_entry(self, index: int) -> LogEntry | None:
        \"\"\"Retrieve entry by logical index.\"\"\"
        pass

    def get_entries_from(self, index: int) -> list[LogEntry]:
        \"\"\"Retrieve entries from index onwards.\"\"\"
        pass

    def last_index(self) -> int:
        \"\"\"Return highest index.\"\"\"
        pass

    def last_term(self) -> int:
        \"\"\"Return term of highest index.\"\"\"
        pass

    def first_available_index(self) -> int:
        \"\"\"Return lowest uncompacted logical index.\"\"\"
        pass
""",
        "canonical_solution": """from dataclasses import dataclass
from typing import Any


@dataclass
class LogEntry:
    index: int
    term: int
    command: Any


class RaftLogBuffer:
    def __init__(self, initial_snapshot_index: int = 0, initial_snapshot_term: int = 0) -> None:
        self._snapshot_index = initial_snapshot_index
        self._snapshot_term = initial_snapshot_term
        self._entries: list[LogEntry] = []

    def _to_physical(self, logical_index: int) -> int:
        return logical_index - (self._snapshot_index + 1)

    def append(self, term: int, command: Any) -> LogEntry:
        new_index = self.last_index() + 1
        entry = LogEntry(index=new_index, term=term, command=command)
        self._entries.append(entry)
        return entry

    def truncate_after(self, index: int) -> None:
        if index < self._snapshot_index:
            return
        phys_idx = self._to_physical(index)
        if phys_idx >= 0:
            self._entries = self._entries[:phys_idx + 1]

    def compact(self, snapshot_index: int, snapshot_term: int) -> bool:
        if snapshot_index <= self._snapshot_index:
            return False

        if snapshot_index >= self.last_index():
            self._entries.clear()
        else:
            phys_idx = self._to_physical(snapshot_index)
            self._entries = self._entries[phys_idx + 1:]

        self._snapshot_index = snapshot_index
        self._snapshot_term = snapshot_term
        return True

    def get_entry(self, index: int) -> LogEntry | None:
        if index <= self._snapshot_index or index > self.last_index():
            return None
        phys_idx = self._to_physical(index)
        if 0 <= phys_idx < len(self._entries):
            return self._entries[phys_idx]
        return None

    def get_entries_from(self, index: int) -> list[LogEntry]:
        if index <= self._snapshot_index:
            raise ValueError(f"Requested index {index} has been compacted (snapshot={self._snapshot_index})")
        if index > self.last_index():
            return []
        phys_idx = self._to_physical(index)
        return list(self._entries[phys_idx:])

    def last_index(self) -> int:
        if self._entries:
            return self._entries[-1].index
        return self._snapshot_index

    def last_term(self) -> int:
        if self._entries:
            return self._entries[-1].term
        return self._snapshot_term

    def first_available_index(self) -> int:
        return self._snapshot_index + 1
""",
        "visible_tests": """def test_raft_log_basic_append_get():
    buf = RaftLogBuffer()
    e1 = buf.append(term=1, command="SET x=10")
    e2 = buf.append(term=1, command="SET y=20")
    assert e1.index == 1
    assert e2.index == 2
    assert buf.last_index() == 2
    assert buf.last_term() == 1
    assert buf.get_entry(1) == e1
    assert buf.get_entry(2) == e2


def test_raft_log_compaction():
    buf = RaftLogBuffer()
    for i in range(1, 6):
        buf.append(term=1, command=f"cmd_{i}")

    assert buf.compact(snapshot_index=3, snapshot_term=1) is True
    assert buf.first_available_index() == 4
    assert buf.get_entry(2) is None  # compacted away
    assert buf.get_entry(4).command == "cmd_4"
    assert buf.last_index() == 5
""",
        "hidden_tests": """import pytest


def test_raft_log_truncation():
    buf = RaftLogBuffer()
    for i in range(1, 6):
        buf.append(term=1, command=f"op_{i}")

    buf.truncate_after(3)
    assert buf.last_index() == 3
    assert buf.get_entry(4) is None
    assert buf.get_entry(5) is None


def test_compact_entire_log():
    buf = RaftLogBuffer()
    for i in range(1, 4):
        buf.append(term=2, command=i)

    buf.compact(snapshot_index=3, snapshot_term=2)
    assert buf.last_index() == 3
    assert buf.last_term() == 2
    assert buf.first_available_index() == 4
    # Append after full compaction
    e = buf.append(term=3, command="new_cmd")
    assert e.index == 4
    assert buf.last_index() == 4


def test_get_entries_from_slices():
    buf = RaftLogBuffer()
    for i in range(1, 7):
        buf.append(term=1, command=i)

    entries = buf.get_entries_from(4)
    assert [e.index for e in entries] == [4, 5, 6]
    assert buf.get_entries_from(10) == []


def test_get_compacted_entries_raises_value_error():
    buf = RaftLogBuffer()
    buf.append(term=1, command="a")
    buf.append(term=1, command="b")
    buf.compact(snapshot_index=1, snapshot_term=1)

    with pytest.raises(ValueError):
        buf.get_entries_from(1)


def test_compaction_with_older_snapshot_rejected():
    buf = RaftLogBuffer(initial_snapshot_index=5, initial_snapshot_term=2)
    assert buf.compact(snapshot_index=3, snapshot_term=1) is False
    assert buf.compact(snapshot_index=5, snapshot_term=2) is False


def test_large_sequence_compaction_scale():
    buf = RaftLogBuffer()
    for i in range(1000):
        buf.append(term=i // 100 + 1, command=f"k_{i}")

    assert buf.last_index() == 1000
    buf.compact(snapshot_index=800, snapshot_term=8)
    assert buf.first_available_index() == 801
    assert buf.last_index() == 1000
    assert len(buf.get_entries_from(801)) == 200
""",
    },
    {
        "task_id": "EF-PY-013",
        "title": "Bellman-Ford Shortest Path with Negative Cycle Detection",
        "language": "python",
        "difficulty": "medium",
        "category": "algorithmic",
        "tags": ["graph", "shortest-path", "bellman-ford", "cycle-detection", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Bellman-Ford Shortest Path with Negative Cycle Detection

Implement the Bellman-Ford algorithm on directed weighted graphs supporting arbitrary real-valued weights, detecting reachable negative-weight cycles, and reconstructing negative cycle paths.

## Requirements

Implement the class `BellmanFordGraph`:

- `__init__(self, vertices: list[Any] | None = None)`:
  Initializes graph with optional vertex list.
- `add_edge(self, u: Any, v: Any, weight: float) -> None`:
  Adds a directed edge from `u` to `v` with given real weight. Adds vertices if not already present.
- `shortest_paths(self, source: Any) -> tuple[dict[Any, float], dict[Any, list[Any]]]`:
  Computes shortest paths from `source` to all reachable vertices.
  Returns `(distances, paths)` where:
  - `distances`: mapping from vertex to minimum distance (`float('inf')` if unreachable).
  - `paths`: mapping from vertex to the ordered list of vertices along the shortest path from `source` to that vertex (empty list for unreachable vertices, `[source]` for source itself).
  - If a negative-weight cycle is reachable from `source`, raises `ValueError("Negative weight cycle detected")`.
- `find_negative_cycle(self) -> list[Any] | None`:
  Finds any negative-weight cycle present anywhere in the graph.
  Returns the cycle as a list of vertices `[v1, v2, ..., vk, v1]` where the first and last vertex match, or `None` if no negative cycle exists.
""",
        "starter_code": """from typing import Any


class BellmanFordGraph:
    def __init__(self, vertices: list[Any] | None = None) -> None:
        \"\"\"Initialize graph.\"\"\"
        pass

    def add_edge(self, u: Any, v: Any, weight: float) -> None:
        \"\"\"Add directed weighted edge.\"\"\"
        pass

    def shortest_paths(self, source: Any) -> tuple[dict[Any, float], dict[Any, list[Any]]]:
        \"\"\"Compute shortest paths or raise ValueError if negative cycle reachable.\"\"\"
        pass

    def find_negative_cycle(self) -> list[Any] | None:
        \"\"\"Return vertices of any negative cycle or None.\"\"\"
        pass
""",
        "canonical_solution": """from typing import Any


class BellmanFordGraph:
    def __init__(self, vertices: list[Any] | None = None) -> None:
        self.vertices: set[Any] = set(vertices or [])
        self.edges: list[tuple[Any, Any, float]] = []

    def add_edge(self, u: Any, v: Any, weight: float) -> None:
        self.vertices.add(u)
        self.vertices.add(v)
        self.edges.append((u, v, float(weight)))

    def shortest_paths(self, source: Any) -> tuple[dict[Any, float], dict[Any, list[Any]]]:
        if source not in self.vertices:
            raise KeyError(f"Source vertex {source} not in graph")

        dist: dict[Any, float] = {v: float('inf') for v in self.vertices}
        pred: dict[Any, Any | None] = {v: None for v in self.vertices}
        dist[source] = 0.0

        num_v = len(self.vertices)
        for _ in range(num_v - 1):
            relaxed = False
            for u, v, w in self.edges:
                if dist[u] != float('inf') and dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    pred[v] = u
                    relaxed = True
            if not relaxed:
                break

        # Check for negative weight cycles reachable from source
        for u, v, w in self.edges:
            if dist[u] != float('inf') and dist[u] + w < dist[v]:
                raise ValueError("Negative weight cycle detected")

        paths: dict[Any, list[Any]] = {}
        for target in self.vertices:
            if dist[target] == float('inf'):
                paths[target] = []
            else:
                path: list[Any] = []
                curr: Any | None = target
                while curr is not None:
                    path.append(curr)
                    if curr == source:
                        break
                    curr = pred[curr]
                path.reverse()
                paths[target] = path

        return dist, paths

    def find_negative_cycle(self) -> list[Any] | None:
        dist: dict[Any, float] = {v: 0.0 for v in self.vertices}
        pred: dict[Any, Any | None] = {v: None for v in self.vertices}

        num_v = len(self.vertices)
        cycle_node: Any | None = None

        for i in range(num_v):
            cycle_node = None
            for u, v, w in self.edges:
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    pred[v] = u
                    cycle_node = v

        if cycle_node is None:
            return None

        # Trace back num_v times to guarantee entering the cycle
        for _ in range(num_v):
            cycle_node = pred[cycle_node]

        cycle: list[Any] = []
        curr = cycle_node
        while True:
            cycle.append(curr)
            if len(cycle) > 1 and curr == cycle_node:
                break
            curr = pred[curr]

        cycle.reverse()
        return cycle
""",
        "visible_tests": """def test_bellman_ford_simple_dag():
    g = BellmanFordGraph()
    g.add_edge("A", "B", 4)
    g.add_edge("A", "C", 2)
    g.add_edge("C", "B", 1)
    g.add_edge("B", "D", 5)

    dist, paths = g.shortest_paths("A")
    assert dist["A"] == 0
    assert dist["B"] == 3
    assert dist["C"] == 2
    assert dist["D"] == 8
    assert paths["B"] == ["A", "C", "B"]


def test_bellman_ford_negative_edge_without_cycle():
    g = BellmanFordGraph()
    g.add_edge("S", "A", 3)
    g.add_edge("A", "B", -2)
    g.add_edge("S", "B", 5)

    dist, paths = g.shortest_paths("S")
    assert dist["B"] == 1
    assert paths["B"] == ["S", "A", "B"]
""",
        "hidden_tests": """import pytest


def test_negative_cycle_reachable_raises_value_error():
    g = BellmanFordGraph()
    g.add_edge("S", "A", 1)
    g.add_edge("A", "B", 2)
    g.add_edge("B", "C", -6)
    g.add_edge("C", "A", 1)

    with pytest.raises(ValueError, match="Negative weight cycle detected"):
        g.shortest_paths("S")


def test_find_negative_cycle_vertices():
    g = BellmanFordGraph()
    g.add_edge(1, 2, 1)
    g.add_edge(2, 3, -5)
    g.add_edge(3, 1, 2)

    cycle = g.find_negative_cycle()
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert len(cycle) >= 3


def test_no_negative_cycle_returns_none():
    g = BellmanFordGraph()
    g.add_edge("X", "Y", 10)
    g.add_edge("Y", "Z", 20)
    assert g.find_negative_cycle() is None


def test_disconnected_vertices():
    g = BellmanFordGraph()
    g.add_edge("A", "B", 3)
    g.add_edge("C", "D", 4)

    dist, paths = g.shortest_paths("A")
    assert dist["A"] == 0
    assert dist["B"] == 3
    assert dist["C"] == float("inf")
    assert paths["C"] == []


def test_self_loop_negative_edge():
    g = BellmanFordGraph()
    g.add_edge("N", "N", -1.0)
    with pytest.raises(ValueError):
        g.shortest_paths("N")


def test_scale_graph():
    g = BellmanFordGraph()
    n = 100
    for i in range(n - 1):
        g.add_edge(i, i + 1, 1.0)
    dist, paths = g.shortest_paths(0)
    assert dist[n - 1] == float(n - 1)
    assert len(paths[n - 1]) == n
""",
    },
    {
        "task_id": "EF-PY-014",
        "title": "A* 2D Grid Pathfinding with Dynamic Obstacles",
        "language": "python",
        "difficulty": "medium",
        "category": "algorithmic",
        "tags": ["a-star", "pathfinding", "grid", "heuristics", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# A* 2D Grid Pathfinding with Dynamic Obstacles

Implement the A* pathfinding algorithm on a 2D integer grid supporting dynamic obstacle placement, diagonal movement toggling, and admissible heuristic estimates.

## Requirements

Implement the class `AStarGrid`:

- `__init__(self, width: int, height: int, allow_diagonal: bool = False)`:
  Initializes grid of size `width x height` (coordinates `0 <= x < width`, `0 <= y < height`).
  If `allow_diagonal` is `False`, allows 4-cardinal moves (cost 1.0).
  If `allow_diagonal` is `True`, allows 8-way moves (cardinal cost 1.0, diagonal cost $\\sqrt{2} \\approx 1.4142$).
- `set_obstacle(self, x: int, y: int, is_blocked: bool = True) -> None`:
  Marks `(x, y)` as an obstacle (`True`) or walkable space (`False`).
- `is_obstacle(self, x: int, y: int) -> bool`:
  Returns `True` if `(x, y)` is blocked, `False` otherwise.
- `find_path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]] | None`:
  Finds the optimal shortest path from `start` to `goal`.
  Returns the ordered list of coordinates `[(x0, y0), (x1, y1), ..., (xg, yg)]` including both `start` and `goal`.
  Returns `None` if no valid path exists or if `start` or `goal` is blocked/out of bounds.
  If `start == goal`, returns `[start]`.
""",
        "starter_code": """class AStarGrid:
    def __init__(self, width: int, height: int, allow_diagonal: bool = False) -> None:
        \"\"\"Initialize A* 2D grid.\"\"\"
        pass

    def set_obstacle(self, x: int, y: int, is_blocked: bool = True) -> None:
        \"\"\"Set or clear obstacle at coordinate.\"\"\"
        pass

    def is_obstacle(self, x: int, y: int) -> bool:
        \"\"\"Check if coordinate is an obstacle.\"\"\"
        pass

    def find_path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]] | None:
        \"\"\"Find shortest path using A* search.\"\"\"
        pass
""",
        "canonical_solution": """import heapq
import math


class AStarGrid:
    def __init__(self, width: int, height: int, allow_diagonal: bool = False) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("Width and height must be positive")
        self.width = width
        self.height = height
        self.allow_diagonal = allow_diagonal
        self.obstacles: set[tuple[int, int]] = set()

    def set_obstacle(self, x: int, y: int, is_blocked: bool = True) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError(f"Coordinate ({x}, {y}) out of bounds")
        if is_blocked:
            self.obstacles.add((x, y))
        else:
            self.obstacles.discard((x, y))

    def is_obstacle(self, x: int, y: int) -> bool:
        return (x, y) in self.obstacles

    def _heuristic(self, a: tuple[int, int], b: tuple[int, int]) -> float:
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        if self.allow_diagonal:
            # Octile distance
            return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)
        return float(dx + dy)

    def _neighbors(self, pos: tuple[int, int]) -> list[tuple[tuple[int, int], float]]:
        x, y = pos
        dirs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0)]
        if self.allow_diagonal:
            dirs.extend([(1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
                         (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))])

        res = []
        for dx, dy, cost in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if (nx, ny) not in self.obstacles:
                    res.append(((nx, ny), cost))
        return res

    def find_path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]] | None:
        if not (0 <= start[0] < self.width and 0 <= start[1] < self.height):
            return None
        if not (0 <= goal[0] < self.width and 0 <= goal[1] < self.height):
            return None
        if start in self.obstacles or goal in self.obstacles:
            return None
        if start == goal:
            return [start]

        open_set: list[tuple[float, float, tuple[int, int]]] = []
        heapq.heappush(open_set, (self._heuristic(start, goal), 0.0, start))

        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start: 0.0}

        while open_set:
            _, current_g, current = heapq.heappop(open_set)

            if current == goal:
                path = []
                curr: tuple[int, int] | None = goal
                while curr is not None:
                    path.append(curr)
                    curr = came_from.get(curr)
                path.reverse()
                return path

            if current_g > g_score.get(current, float('inf')):
                continue

            for neighbor, cost in self._neighbors(current):
                tentative_g = current_g + cost
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f, tentative_g, neighbor))

        return None
""",
        "visible_tests": """def test_astar_straight_line():
    grid = AStarGrid(width=5, height=5)
    path = grid.find_path((0, 0), (0, 3))
    assert path == [(0, 0), (0, 1), (0, 2), (0, 3)]


def test_astar_obstacle_detour():
    grid = AStarGrid(width=4, height=4)
    # Place wall at (1, 0), (1, 1), (1, 2)
    grid.set_obstacle(1, 0)
    grid.set_obstacle(1, 1)
    grid.set_obstacle(1, 2)

    path = grid.find_path((0, 0), (2, 0))
    assert path is not None
    # Must detour around (1, 3)
    assert (1, 3) in path
    assert path[0] == (0, 0)
    assert path[-1] == (2, 0)
""",
        "hidden_tests": """def test_astar_no_path_blocked():
    grid = AStarGrid(width=3, height=3)
    for y in range(3):
        grid.set_obstacle(1, y)
    assert grid.find_path((0, 0), (2, 2)) is None


def test_start_or_goal_is_obstacle():
    grid = AStarGrid(width=5, height=5)
    grid.set_obstacle(0, 0)
    assert grid.find_path((0, 0), (4, 4)) is None
    grid.set_obstacle(0, 0, False)
    grid.set_obstacle(4, 4)
    assert grid.find_path((0, 0), (4, 4)) is None


def test_start_equals_goal():
    grid = AStarGrid(width=5, height=5)
    assert grid.find_path((2, 2), (2, 2)) == [(2, 2)]


def test_diagonal_movement_efficiency():
    grid = AStarGrid(width=4, height=4, allow_diagonal=True)
    path = grid.find_path((0, 0), (3, 3))
    assert path == [(0, 0), (1, 1), (2, 2), (3, 3)]


def test_clear_obstacle():
    grid = AStarGrid(width=3, height=3)
    grid.set_obstacle(1, 1)
    assert grid.is_obstacle(1, 1) is True
    grid.set_obstacle(1, 1, is_blocked=False)
    assert grid.is_obstacle(1, 1) is False
    path = grid.find_path((0, 1), (2, 1))
    assert (1, 1) in path


def test_large_maze_scale():
    grid = AStarGrid(width=50, height=50)
    for x in range(1, 48):
        grid.set_obstacle(x, 25)
    # Gap at x=48
    path = grid.find_path((0, 0), (0, 49))
    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (0, 49)
""",
    },
    {
        "task_id": "EF-PY-015",
        "title": "Maximum Flow Edmonds-Karp Algorithm",
        "language": "python",
        "difficulty": "hard",
        "category": "algorithmic",
        "tags": ["max-flow", "edmonds-karp", "graph", "min-cut", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Maximum Flow Edmonds-Karp Algorithm

Implement the Edmonds-Karp algorithm (BFS-based implementation of Ford-Fulkerson) to compute maximum flow, edge flows, and the minimum cut in a directed capacitated network.

## Requirements

Implement the class `MaxFlowNetwork`:

- `__init__(self, vertices: list[Any] | None = None)`:
  Initializes network with optional vertex set.
- `add_edge(self, u: Any, v: Any, capacity: float) -> None`:
  Adds a directed capacity edge from `u` to `v` (`capacity >= 0`).
  If an edge already exists, adds to its existing capacity.
- `compute_max_flow(self, source: Any, sink: Any) -> float`:
  Computes and returns the maximum flow achievable from `source` to `sink`.
  Raises `ValueError` if `source == sink` or if either vertex is not in the network.
- `get_flow_on_edge(self, u: Any, v: Any) -> float`:
  Returns the net flow passing through edge `u -> v` after running `compute_max_flow`.
- `get_min_cut(self, source: Any, sink: Any) -> tuple[set[Any], set[Any]]`:
  Finds the minimum $s-t$ cut partition `(S, T)` where $source \\in S$ and $sink \\in T$, such that the capacity of edges from $S$ to $T$ equals the maximum flow.
""",
        "starter_code": """from typing import Any


class MaxFlowNetwork:
    def __init__(self, vertices: list[Any] | None = None) -> None:
        \"\"\"Initialize max flow capacity network.\"\"\"
        pass

    def add_edge(self, u: Any, v: Any, capacity: float) -> None:
        \"\"\"Add directed edge with capacity.\"\"\"
        pass

    def compute_max_flow(self, source: Any, sink: Any) -> float:
        \"\"\"Compute maximum flow from source to sink using Edmonds-Karp.\"\"\"
        pass

    def get_flow_on_edge(self, u: Any, v: Any) -> float:
        \"\"\"Return net flow on edge u -> v.\"\"\"
        pass

    def get_min_cut(self, source: Any, sink: Any) -> tuple[set[Any], set[Any]]:
        \"\"\"Return (S, T) vertex partition forming the min-cut.\"\"\"
        pass
""",
        "canonical_solution": """from collections import deque
from typing import Any


class MaxFlowNetwork:
    def __init__(self, vertices: list[Any] | None = None) -> None:
        self.vertices: set[Any] = set(vertices or [])
        self.capacity: dict[tuple[Any, Any], float] = {}
        self.flow: dict[tuple[Any, Any], float] = {}
        self.adj: dict[Any, set[Any]] = {}

    def add_edge(self, u: Any, v: Any, capacity: float) -> None:
        if capacity < 0:
            raise ValueError("Capacity cannot be negative")
        self.vertices.add(u)
        self.vertices.add(v)
        self.adj.setdefault(u, set()).add(v)
        self.adj.setdefault(v, set()).add(u)

        self.capacity[(u, v)] = self.capacity.get((u, v), 0.0) + float(capacity)
        self.capacity.setdefault((v, u), 0.0)
        self.flow.setdefault((u, v), 0.0)
        self.flow.setdefault((v, u), 0.0)

    def _bfs_find_path(self, source: Any, sink: Any, parent: dict[Any, Any]) -> float:
        parent.clear()
        queue = deque([source])
        parent[source] = source

        while queue:
            curr = queue.popleft()
            if curr == sink:
                break
            for nxt in self.adj.get(curr, set()):
                residual = self.capacity.get((curr, nxt), 0.0) - self.flow.get((curr, nxt), 0.0)
                if residual > 1e-9 and nxt not in parent:
                    parent[nxt] = curr
                    queue.append(nxt)

        if sink not in parent:
            return 0.0

        # Find bottleneck capacity along augmenting path
        bottleneck = float('inf')
        curr = sink
        while curr != source:
            prev = parent[curr]
            residual = self.capacity[(prev, curr)] - self.flow[(prev, curr)]
            bottleneck = min(bottleneck, residual)
            curr = prev

        return bottleneck

    def compute_max_flow(self, source: Any, sink: Any) -> float:
        if source == sink:
            raise ValueError("Source and sink cannot be identical")
        if source not in self.vertices or sink not in self.vertices:
            raise ValueError("Source or sink not in network")

        # Reset flows
        for edge in self.flow:
            self.flow[edge] = 0.0

        max_flow = 0.0
        parent: dict[Any, Any] = {}

        while True:
            push = self._bfs_find_path(source, sink, parent)
            if push <= 1e-9:
                break
            max_flow += push
            curr = sink
            while curr != source:
                prev = parent[curr]
                self.flow[(prev, curr)] += push
                self.flow[(curr, prev)] -= push
                curr = prev

        return max_flow

    def get_flow_on_edge(self, u: Any, v: Any) -> float:
        return max(0.0, self.flow.get((u, v), 0.0))

    def get_min_cut(self, source: Any, sink: Any) -> tuple[set[Any], set[Any]]:
        self.compute_max_flow(source, sink)
        visited = set()
        queue = deque([source])
        visited.add(source)

        while queue:
            curr = queue.popleft()
            for nxt in self.adj.get(curr, set()):
                residual = self.capacity.get((curr, nxt), 0.0) - self.flow.get((curr, nxt), 0.0)
                if residual > 1e-9 and nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)

        s_set = visited
        t_set = self.vertices - s_set
        return s_set, t_set
""",
        "visible_tests": """def test_max_flow_diamond_network():
    net = MaxFlowNetwork()
    net.add_edge("s", "u", 10)
    net.add_edge("s", "v", 5)
    net.add_edge("u", "v", 15)
    net.add_edge("u", "t", 10)
    net.add_edge("v", "t", 10)

    flow = net.compute_max_flow("s", "t")
    assert flow == 15.0


def test_min_cut_partition():
    net = MaxFlowNetwork()
    net.add_edge("s", "a", 3)
    net.add_edge("a", "t", 2)

    flow = net.compute_max_flow("s", "t")
    assert flow == 2.0
    s_set, t_set = net.get_min_cut("s", "t")
    assert "s" in s_set
    assert "t" in t_set
""",
        "hidden_tests": """import pytest


def test_identical_source_sink_raises():
    net = MaxFlowNetwork()
    net.add_edge("A", "B", 5)
    with pytest.raises(ValueError):
        net.compute_max_flow("A", "A")


def test_disconnected_source_sink():
    net = MaxFlowNetwork()
    net.add_edge("A", "B", 10)
    net.add_edge("C", "D", 10)
    assert net.compute_max_flow("A", "D") == 0.0


def test_multiple_parallel_paths():
    net = MaxFlowNetwork()
    net.add_edge("s", "a1", 10)
    net.add_edge("a1", "t", 10)
    net.add_edge("s", "a2", 20)
    net.add_edge("a2", "t", 20)
    net.add_edge("s", "a3", 30)
    net.add_edge("a3", "t", 30)
    assert net.compute_max_flow("s", "t") == 60.0


def test_flow_conservation():
    net = MaxFlowNetwork()
    net.add_edge("s", "1", 10)
    net.add_edge("s", "2", 10)
    net.add_edge("1", "3", 8)
    net.add_edge("2", "3", 8)
    net.add_edge("3", "t", 20)

    flow = net.compute_max_flow("s", "t")
    assert flow == 16.0
    # Inflow at 3 must equal outflow at 3
    inflow = net.get_flow_on_edge("1", "3") + net.get_flow_on_edge("2", "3")
    outflow = net.get_flow_on_edge("3", "t")
    assert inflow == outflow == 16.0


def test_edge_flow_tracking():
    net = MaxFlowNetwork()
    net.add_edge("A", "B", 5)
    net.add_edge("B", "C", 3)
    net.compute_max_flow("A", "C")
    assert net.get_flow_on_edge("A", "B") == 3.0
    assert net.get_flow_on_edge("B", "C") == 3.0


def test_scale_bipartite_matching():
    net = MaxFlowNetwork()
    n = 20
    # Left partition L0..L19, Right partition R0..R19
    for i in range(n):
        net.add_edge("source", f"L{i}", 1.0)
        net.add_edge(f"R{i}", "sink", 1.0)
        net.add_edge(f"L{i}", f"R{i}", 1.0)
    assert net.compute_max_flow("source", "sink") == 20.0
""",
    },
]
