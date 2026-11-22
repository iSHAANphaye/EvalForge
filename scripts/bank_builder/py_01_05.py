"""Tasks EF-PY-001 through EF-PY-005."""

TASKS = [
    {
        "task_id": "EF-PY-001",
        "title": "Thread-Safe LRU Cache with TTL Expiration",
        "language": "python",
        "difficulty": "medium",
        "category": "concurrency",
        "tags": ["caching", "concurrency", "lru", "ttl", "thread-safety"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Thread-Safe LRU Cache with TTL Expiration

Implement a high-performance, thread-safe Least Recently Used (LRU) cache that supports per-item Time-To-Live (TTL) expiration.

## Requirements

Implement the class `ThreadSafeTTLCache` with the following interface:

- `__init__(self, capacity: int, default_ttl: float | None = None)`:
  Initializes cache with a maximum capacity (`capacity >= 1`) and an optional default TTL in seconds.
- `get(self, key: Any, default: Any = None) -> Any`:
  Retrieves the value for `key`. If the key exists and has not expired, returns the value and updates its LRU recency.
  If the key does not exist or has expired, it must be removed and `default` returned.
- `put(self, key: Any, value: Any, ttl: float | None = None) -> None`:
  Inserts or updates the `key` with `value` and an optional item-specific `ttl` in seconds (overriding `default_ttl`).
  If the key already exists, update its value and TTL and refresh recency.
  If capacity is reached, evict the least recently used, non-expired item.
- `delete(self, key: Any) -> bool`:
  Removes the key from the cache. Returns `True` if key was present and removed, `False` otherwise.
- `size(self) -> int`:
  Returns the count of non-expired keys currently in the cache.
- `cleanup(self) -> int`:
  Scans and purges all expired keys from the cache. Returns the number of keys purged.
- `clear(self) -> None`:
  Removes all keys from the cache.

## Concurrency
All operations must be thread-safe using a reentrant lock (`threading.RLock`) or standard lock (`threading.Lock`).
""",
        "starter_code": """import threading
import time
from typing import Any


class ThreadSafeTTLCache:
    def __init__(self, capacity: int, default_ttl: float | None = None) -> None:
        \"\"\"Initialize thread-safe LRU cache with capacity and optional default TTL.\"\"\"
        pass

    def get(self, key: Any, default: Any = None) -> Any:
        \"\"\"Retrieve value for key, updating recency if not expired.\"\"\"
        pass

    def put(self, key: Any, value: Any, ttl: float | None = None) -> None:
        \"\"\"Insert or update key with value and optional TTL.\"\"\"
        pass

    def delete(self, key: Any) -> bool:
        \"\"\"Delete key from cache. Return True if existed and deleted, else False.\"\"\"
        pass

    def size(self) -> int:
        \"\"\"Return number of active non-expired keys.\"\"\"
        pass

    def cleanup(self) -> int:
        \"\"\"Purge expired keys and return count of purged items.\"\"\"
        pass

    def clear(self) -> None:
        \"\"\"Purge all keys.\"\"\"
        pass
""",
        "canonical_solution": """from collections import OrderedDict
import threading
import time
from typing import Any


class ThreadSafeTTLCache:
    def __init__(self, capacity: int, default_ttl: float | None = None) -> None:
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")
        self._capacity = capacity
        self._default_ttl = default_ttl
        self._cache: OrderedDict[Any, tuple[Any, float | None]] = OrderedDict()
        self._lock = threading.RLock()

    def _is_expired(self, expiry: float | None, now: float) -> bool:
        return expiry is not None and now >= expiry

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            now = time.monotonic()
            if key not in self._cache:
                return default
            val, expiry = self._cache[key]
            if self._is_expired(expiry, now):
                del self._cache[key]
                return default
            self._cache.move_to_end(key)
            return val

    def put(self, key: Any, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            now = time.monotonic()
            effective_ttl = ttl if ttl is not None else self._default_ttl
            expiry = (now + effective_ttl) if effective_ttl is not None else None

            if key in self._cache:
                self._cache[key] = (value, expiry)
                self._cache.move_to_end(key)
                return

            # Check if any expired items can be evicted before enforcing LRU
            if len(self._cache) >= self._capacity:
                expired_keys = [k for k, (_, exp) in self._cache.items() if self._is_expired(exp, now)]
                if expired_keys:
                    for k in expired_keys:
                        del self._cache[k]

            if len(self._cache) >= self._capacity:
                self._cache.popitem(last=False)

            self._cache[key] = (value, expiry)

    def delete(self, key: Any) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def size(self) -> int:
        with self._lock:
            now = time.monotonic()
            return sum(1 for _, exp in self._cache.values() if not self._is_expired(exp, now))

    def cleanup(self) -> int:
        with self._lock:
            now = time.monotonic()
            expired = [k for k, (_, exp) in self._cache.items() if self._is_expired(exp, now)]
            for k in expired:
                del self._cache[k]
            return len(expired)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
""",
        "visible_tests": """def test_lru_basic_put_get():
    cache = ThreadSafeTTLCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") is None


def test_lru_eviction_order():
    cache = ThreadSafeTTLCache(capacity=2)
    cache.put("x", 10)
    cache.put("y", 20)
    cache.get("x")  # Mark x as recently used
    cache.put("z", 30)  # Should evict y
    assert cache.get("x") == 10
    assert cache.get("y") is None
    assert cache.get("z") == 30
""",
        "hidden_tests": """import concurrent.futures
import time


def test_ttl_expiration():
    cache = ThreadSafeTTLCache(capacity=5, default_ttl=0.05)
    cache.put("k1", "v1")
    assert cache.get("k1") == "v1"
    time.sleep(0.07)
    assert cache.get("k1") is None
    assert cache.size() == 0


def test_custom_item_ttl():
    cache = ThreadSafeTTLCache(capacity=5, default_ttl=10.0)
    cache.put("short", "fast", ttl=0.05)
    cache.put("long", "slow")
    time.sleep(0.07)
    assert cache.get("short") is None
    assert cache.get("long") == "slow"


def test_delete_and_clear():
    cache = ThreadSafeTTLCache(capacity=3)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.delete("a") is True
    assert cache.delete("a") is False
    assert cache.size() == 1
    cache.clear()
    assert cache.size() == 0


def test_cleanup_purges_expired():
    cache = ThreadSafeTTLCache(capacity=10)
    cache.put("exp1", 1, ttl=0.02)
    cache.put("exp2", 2, ttl=0.02)
    cache.put("keep", 3, ttl=5.0)
    time.sleep(0.04)
    purged = cache.cleanup()
    assert purged == 2
    assert cache.size() == 1
    assert cache.get("keep") == 3


def test_concurrent_access():
    cache = ThreadSafeTTLCache(capacity=50)

    def worker(worker_id: int):
        for i in range(100):
            cache.put(f"key_{worker_id}_{i}", i)
            val = cache.get(f"key_{worker_id}_{i}")
            assert val == i or val is None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, w) for w in range(8)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    assert cache.size() <= 50


def test_capacity_one():
    cache = ThreadSafeTTLCache(capacity=1)
    cache.put("first", 100)
    assert cache.get("first") == 100
    cache.put("second", 200)
    assert cache.get("first") is None
    assert cache.get("second") == 200
""",
    },
    {
        "task_id": "EF-PY-002",
        "title": "Async Token-Bucket Rate Limiter with Burst Capacity",
        "language": "python",
        "difficulty": "medium",
        "category": "concurrency",
        "tags": ["rate-limiter", "concurrency", "asyncio", "token-bucket", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Async Token-Bucket Rate Limiter with Burst Capacity

Implement an asynchronous token bucket rate limiter supporting burst traffic and asynchronous token acquisition.

## Requirements

Implement the class `AsyncTokenBucket`:

- `__init__(self, rate: float, capacity: float)`:
  Initializes limiter with a refill `rate` (tokens per second, `rate > 0`) and maximum burst `capacity` (`capacity > 0`).
  Initially, the bucket is completely full with `capacity` tokens.
- `try_acquire(self, tokens: float = 1.0) -> bool`:
  Non-blocking attempt to acquire `tokens`.
  If enough tokens are available, consumes them and returns `True`.
  Otherwise, returns `False` immediately without consuming tokens or sleeping.
- `async acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool`:
  Asynchronously waits until enough tokens accumulate to satisfy the request.
  If acquired before `timeout` seconds expire, consumes `tokens` and returns `True`.
  If `timeout` is reached before tokens become available, returns `False` without consuming tokens.
  If `timeout is None`, waits indefinitely until tokens become available.
- `available_tokens(self) -> float`:
  Returns the current number of available tokens after accounting for time elapsed since the last refill.
- `reset(self) -> None`:
  Resets the bucket to full capacity.
""",
        "starter_code": """import asyncio
import time


class AsyncTokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        \"\"\"Initialize token bucket with refill rate (per sec) and max burst capacity.\"\"\"
        pass

    def try_acquire(self, tokens: float = 1.0) -> bool:
        \"\"\"Non-blocking token acquisition attempt.\"\"\"
        pass

    async def acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool:
        \"\"\"Async acquisition waiting up to timeout seconds.\"\"\"
        pass

    def available_tokens(self) -> float:
        \"\"\"Return current tokens available.\"\"\"
        pass

    def reset(self) -> None:
        \"\"\"Reset bucket to full capacity.\"\"\"
        pass
""",
        "canonical_solution": """import asyncio
import time


class AsyncTokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0:
            raise ValueError("Rate must be positive")
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self._rate = float(rate)
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last_refill = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        if tokens <= 0:
            return True
        now = time.monotonic()
        self._refill(now)
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    async def acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool:
        if tokens <= 0:
            return True
        if tokens > self._capacity:
            return False

        deadline = (time.monotonic() + timeout) if timeout is not None else None

        while True:
            async with self._lock:
                now = time.monotonic()
                self._refill(now)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                needed = tokens - self._tokens
                wait_time = needed / self._rate

                if deadline is not None:
                    remaining = deadline - now
                    if remaining <= 0:
                        return False
                    wait_time = min(wait_time, remaining)

            # Sleep outside lock to allow other coroutines to execute
            await asyncio.sleep(min(wait_time, 0.05))

            if deadline is not None and time.monotonic() >= deadline:
                # One final attempt
                async with self._lock:
                    now = time.monotonic()
                    self._refill(now)
                    if self._tokens >= tokens:
                        self._tokens -= tokens
                        return True
                    return False

    def available_tokens(self) -> float:
        now = time.monotonic()
        self._refill(now)
        return self._tokens

    def reset(self) -> None:
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
""",
        "visible_tests": """import asyncio


async def test_burst_capacity_try_acquire():
    bucket = AsyncTokenBucket(rate=10.0, capacity=5.0)
    assert bucket.try_acquire(3.0) is True
    assert bucket.try_acquire(2.0) is True
    assert bucket.try_acquire(1.0) is False


async def test_async_acquire_immediate():
    bucket = AsyncTokenBucket(rate=10.0, capacity=10.0)
    res = await bucket.acquire(5.0)
    assert res is True
    assert bucket.available_tokens() <= 5.1
""",
        "hidden_tests": """import asyncio
import time


async def test_token_refill_over_time():
    bucket = AsyncTokenBucket(rate=20.0, capacity=5.0)
    assert bucket.try_acquire(5.0) is True
    assert bucket.try_acquire(1.0) is False
    await asyncio.sleep(0.12)
    # After ~0.12s, at least 2 tokens refilled
    assert bucket.try_acquire(2.0) is True


async def test_acquire_timeout_failure():
    bucket = AsyncTokenBucket(rate=2.0, capacity=5.0)
    assert bucket.try_acquire(5.0) is True
    # Bucket is empty. Needing 4 tokens requires 2.0s. Timeout 0.05s should fail.
    acquired = await bucket.acquire(4.0, timeout=0.05)
    assert acquired is False


async def test_acquire_waiting_success():
    bucket = AsyncTokenBucket(rate=50.0, capacity=10.0)
    assert bucket.try_acquire(10.0) is True
    # Needs 2 tokens => ~0.04s. Timeout 0.2s should succeed.
    start = time.monotonic()
    acquired = await bucket.acquire(2.0, timeout=0.2)
    elapsed = time.monotonic() - start
    assert acquired is True
    assert elapsed >= 0.03


async def test_exceed_capacity_rejected():
    bucket = AsyncTokenBucket(rate=100.0, capacity=10.0)
    assert await bucket.acquire(15.0) is False


async def test_reset_functionality():
    bucket = AsyncTokenBucket(rate=5.0, capacity=10.0)
    assert bucket.try_acquire(10.0) is True
    assert bucket.available_tokens() < 1.0
    bucket.reset()
    assert bucket.available_tokens() == 10.0
    assert bucket.try_acquire(10.0) is True


async def test_zero_or_negative_tokens():
    bucket = AsyncTokenBucket(rate=10.0, capacity=5.0)
    assert bucket.try_acquire(0.0) is True
    assert await bucket.acquire(0.0) is True
""",
    },
    {
        "task_id": "EF-PY-003",
        "title": "Consistent Hashing Ring with Virtual Nodes",
        "language": "python",
        "difficulty": "medium",
        "category": "systems",
        "tags": ["distributed-systems", "hashing", "consistent-hashing", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Consistent Hashing Ring with Virtual Nodes

Implement a consistent hashing ring with virtual nodes (vnodes) to achieve uniform distribution and minimal key remapping during cluster topology changes.

## Requirements

Implement the class `ConsistentHashRing`:

- `__init__(self, replicas: int = 100)`:
  Initializes the ring with `replicas` virtual nodes per physical node (`replicas >= 1`).
- `add_node(self, node: str) -> None`:
  Adds a physical node to the ring. Generates `replicas` virtual keys formatted as `f"{node}#{i}"` for `i` in `range(replicas)`.
  Computes the 32-bit integer MD5 hash of each virtual key and inserts it into the sorted ring.
  If the node is already present, does nothing.
- `remove_node(self, node: str) -> None`:
  Removes a physical node and all its virtual nodes from the ring.
  If the node does not exist, does nothing.
- `get_node(self, key: str) -> str | None`:
  Hashes `key` using the same MD5 hash function, and finds the first virtual node situated clockwise (equal or greater hash) on the ring.
  If the key's hash exceeds all virtual node hashes, wraps around to the first virtual node.
  Returns the physical node identifier associated with the matched virtual node.
  Returns `None` if the ring is empty.
- `get_nodes(self) -> list[str]`:
  Returns a sorted list of unique physical nodes currently registered on the ring.
""",
        "starter_code": """class ConsistentHashRing:
    def __init__(self, replicas: int = 100) -> None:
        \"\"\"Initialize ring with number of virtual node replicas.\"\"\"
        pass

    def add_node(self, node: str) -> None:
        \"\"\"Add physical node and its virtual nodes to the ring.\"\"\"
        pass

    def remove_node(self, node: str) -> None:
        \"\"\"Remove physical node and its virtual nodes.\"\"\"
        pass

    def get_node(self, key: str) -> str | None:
        \"\"\"Lookup physical node for given key clockwise.\"\"\"
        pass

    def get_nodes(self) -> list[str]:
        \"\"\"Return sorted list of all active physical nodes.\"\"\"
        pass
""",
        "canonical_solution": """import bisect
import hashlib


class ConsistentHashRing:
    def __init__(self, replicas: int = 100) -> None:
        if replicas < 1:
            raise ValueError("Replicas must be at least 1")
        self._replicas = replicas
        self._ring: dict[int, str] = {}
        self._sorted_keys: list[int] = []
        self._nodes: set[str] = set()

    def _hash(self, key: str) -> int:
        digest = hashlib.md5(key.encode("utf-8")).digest()
        # Use first 4 bytes as 32-bit big-endian unsigned integer
        return int.from_bytes(digest[:4], byteorder="big")

    def add_node(self, node: str) -> None:
        if node in self._nodes:
            return
        self._nodes.add(node)
        for i in range(self._replicas):
            vkey = f"{node}#{i}"
            h = self._hash(vkey)
            self._ring[h] = node
            bisect.insort(self._sorted_keys, h)

    def remove_node(self, node: str) -> None:
        if node not in self._nodes:
            return
        self._nodes.remove(node)
        for i in range(self._replicas):
            vkey = f"{node}#{i}"
            h = self._hash(vkey)
            if h in self._ring:
                del self._ring[h]
                idx = bisect.bisect_left(self._sorted_keys, h)
                if idx < len(self._sorted_keys) and self._sorted_keys[idx] == h:
                    del self._sorted_keys[idx]

    def get_node(self, key: str) -> str | None:
        if not self._sorted_keys:
            return None
        h = self._hash(key)
        idx = bisect.bisect_right(self._sorted_keys, h)
        if idx == len(self._sorted_keys):
            idx = 0
        return self._ring[self._sorted_keys[idx]]

    def get_nodes(self) -> list[str]:
        return sorted(self._nodes)
""",
        "visible_tests": """def test_consistent_hash_ring_basic():
    ring = ConsistentHashRing(replicas=50)
    ring.add_node("nodeA")
    ring.add_node("nodeB")
    ring.add_node("nodeC")

    node = ring.get_node("user_session_1234")
    assert node in {"nodeA", "nodeB", "nodeC"}
    assert ring.get_nodes() == ["nodeA", "nodeB", "nodeC"]


def test_consistent_hash_ring_empty():
    ring = ConsistentHashRing(replicas=10)
    assert ring.get_node("any_key") is None
    assert ring.get_nodes() == []
""",
        "hidden_tests": """def test_deterministic_mapping():
    ring = ConsistentHashRing(replicas=100)
    ring.add_node("alpha")
    ring.add_node("beta")
    ring.add_node("gamma")

    assignments = [ring.get_node(f"key_{i}") for i in range(100)]
    # Ensure repeated lookups produce identical node assignments
    assert assignments == [ring.get_node(f"key_{i}") for i in range(100)]


def test_remove_node_reassignment():
    ring = ConsistentHashRing(replicas=100)
    ring.add_node("node1")
    ring.add_node("node2")
    ring.add_node("node3")

    ring.remove_node("node2")
    assert "node2" not in ring.get_nodes()

    # No key should ever map to node2
    for i in range(200):
        assert ring.get_node(f"test_item_{i}") != "node2"


def test_single_node_ring():
    ring = ConsistentHashRing(replicas=25)
    ring.add_node("only_server")
    for i in range(50):
        assert ring.get_node(f"item_{i}") == "only_server"


def test_duplicate_add_remove_idempotent():
    ring = ConsistentHashRing(replicas=20)
    ring.add_node("nodeX")
    ring.add_node("nodeX")  # duplicate add
    assert ring.get_nodes() == ["nodeX"]
    ring.remove_node("nodeX")
    ring.remove_node("nodeX")  # duplicate remove
    assert ring.get_nodes() == []
    assert ring.get_node("item") is None


def test_fair_distribution():
    ring = ConsistentHashRing(replicas=150)
    for n in ["srv1", "srv2", "srv3"]:
        ring.add_node(n)

    counts = {"srv1": 0, "srv2": 0, "srv3": 0}
    for i in range(3000):
        srv = ring.get_node(f"sample_key_{i}")
        counts[srv] += 1

    # With 150 replicas, each server should receive roughly 33% (>= 15% and <= 50%)
    for srv, cnt in counts.items():
        assert cnt >= 450, f"{srv} received too few keys: {cnt}"
        assert cnt <= 1500, f"{srv} received too many keys: {cnt}"


def test_scale_ring():
    ring = ConsistentHashRing(replicas=50)
    for i in range(20):
        ring.add_node(f"node_{i:02d}")
    assert len(ring.get_nodes()) == 20
    for i in range(1000):
        assert ring.get_node(f"metric_{i}") is not None
""",
    },
    {
        "task_id": "EF-PY-004",
        "title": "Trie with Wildcard Prefix Search",
        "language": "python",
        "difficulty": "medium",
        "category": "data_structures",
        "tags": ["trie", "prefix-tree", "wildcard", "data_structures", "search"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Trie with Wildcard Prefix Search

Implement an efficient prefix tree (Trie) that supports exact word matching, prefix matching, and wildcard queries where the dot character (`'.'`) matches any single character.

## Requirements

Implement the class `WildcardTrie`:

- `insert(self, word: str) -> None`:
  Inserts `word` into the trie.
- `search(self, word: str) -> bool`:
  Returns `True` if `word` exists in the trie (exact match), `False` otherwise.
- `starts_with(self, prefix: str) -> bool`:
  Returns `True` if there is any word in the trie that starts with the given `prefix` (exact characters), `False` otherwise.
- `search_wildcard(self, pattern: str) -> list[str]`:
  Finds all complete words in the trie matching `pattern`, where `'.'` matches any single character.
  The length of matching words must equal the length of `pattern`.
  Returns a lexicographically sorted list of unique matching words.
- `prefix_wildcard(self, pattern: str) -> list[str]`:
  Finds all words in the trie that have a prefix matching `pattern` (where `'.'` matches any character).
  Returns a lexicographically sorted list of unique words.
""",
        "starter_code": """class WildcardTrie:
    def __init__(self) -> None:
        \"\"\"Initialize empty Wildcard Trie.\"\"\"
        pass

    def insert(self, word: str) -> None:
        \"\"\"Insert word into trie.\"\"\"
        pass

    def search(self, word: str) -> bool:
        \"\"\"Check if word exists in trie.\"\"\"
        pass

    def starts_with(self, prefix: str) -> bool:
        \"\"\"Check if any word starts with prefix.\"\"\"
        pass

    def search_wildcard(self, pattern: str) -> list[str]:
        \"\"\"Search for complete words matching wildcard pattern (. matches any char).\"\"\"
        pass

    def prefix_wildcard(self, pattern: str) -> list[str]:
        \"\"\"Search for words with prefix matching wildcard pattern.\"\"\"
        pass
""",
        "canonical_solution": """class _TrieNode:
    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.is_end: bool = False
        self.word: str | None = None


class WildcardTrie:
    def __init__(self) -> None:
        self.root = _TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = _TrieNode()
            node = node.children[char]
        node.is_end = True
        node.word = word

    def search(self, word: str) -> bool:
        node = self.root
        for char in word:
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_end

    def starts_with(self, prefix: str) -> bool:
        node = self.root
        for char in prefix:
            if char not in node.children:
                return False
            node = node.children[char]
        return True

    def search_wildcard(self, pattern: str) -> list[str]:
        results: list[str] = []

        def dfs(node: _TrieNode, idx: int) -> None:
            if idx == len(pattern):
                if node.is_end and node.word is not None:
                    results.append(node.word)
                return

            char = pattern[idx]
            if char == ".":
                for child in node.children.values():
                    dfs(child, idx + 1)
            else:
                if char in node.children:
                    dfs(node.children[char], idx + 1)

        dfs(self.root, 0)
        return sorted(results)

    def prefix_wildcard(self, pattern: str) -> list[str]:
        matching_nodes: list[_TrieNode] = []

        def dfs_pattern(node: _TrieNode, idx: int) -> None:
            if idx == len(pattern):
                matching_nodes.append(node)
                return

            char = pattern[idx]
            if char == ".":
                for child in node.children.values():
                    dfs_pattern(child, idx + 1)
            else:
                if char in node.children:
                    dfs_pattern(node.children[char], idx + 1)

        dfs_pattern(self.root, 0)

        results: list[str] = []

        def collect_words(node: _TrieNode) -> None:
            if node.is_end and node.word is not None:
                results.append(node.word)
            for child in node.children.values():
                collect_words(child)

        for n in matching_nodes:
            collect_words(n)

        return sorted(set(results))
""",
        "visible_tests": """def test_trie_insert_and_exact_search():
    trie = WildcardTrie()
    trie.insert("apple")
    trie.insert("app")
    assert trie.search("apple") is True
    assert trie.search("app") is True
    assert trie.search("appl") is False
    assert trie.starts_with("app") is True
    assert trie.starts_with("ban") is False


def test_trie_wildcard_search():
    trie = WildcardTrie()
    for w in ["cat", "bat", "rat", "bar", "car", "cattle"]:
        trie.insert(w)

    assert trie.search_wildcard(".at") == ["bat", "cat", "rat"]
    assert trie.search_wildcard("c.r") == ["car"]
    assert trie.search_wildcard("....") == []
""",
        "hidden_tests": """def test_prefix_wildcard_search():
    trie = WildcardTrie()
    words = ["flower", "flow", "flight", "flat", "blow", "blue"]
    for w in words:
        trie.insert(w)

    assert trie.prefix_wildcard("fl.") == ["flat", "flight", "flow", "flower"]
    assert trie.prefix_wildcard("bl..") == ["blow", "blue"]


def test_empty_string_and_single_char():
    trie = WildcardTrie()
    trie.insert("a")
    trie.insert("b")
    assert trie.search_wildcard(".") == ["a", "b"]
    assert trie.search("a") is True
    assert trie.search("c") is False


def test_all_wildcard_pattern():
    trie = WildcardTrie()
    words = ["cat", "dog", "fox", "ant", "bee"]
    for w in words:
        trie.insert(w)
    assert trie.search_wildcard("...") == sorted(words)


def test_no_matches_wildcard():
    trie = WildcardTrie()
    trie.insert("hello")
    trie.insert("world")
    assert trie.search_wildcard(".....z") == []
    assert trie.search_wildcard("z....") == []


def test_duplicate_insertions():
    trie = WildcardTrie()
    trie.insert("repeat")
    trie.insert("repeat")
    assert trie.search("repeat") is True
    assert trie.search_wildcard("re....") == ["repeat"]


def test_large_dictionary_scale():
    trie = WildcardTrie()
    for i in range(1000):
        trie.insert(f"item_{i:04d}")
    assert trie.search("item_0500") is True
    assert trie.search("item_9999") is False
    matches = trie.search_wildcard("item_00..")
    assert len(matches) == 100
""",
    },
    {
        "task_id": "EF-PY-005",
        "title": "B-Tree Index Node Split and Insertion",
        "language": "python",
        "difficulty": "hard",
        "category": "data_structures",
        "tags": ["b-tree", "database-index", "data_structures", "algorithmic"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 25,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# B-Tree Index Node Split and Insertion

Implement a self-balancing B-Tree index structure conforming to the classic Cormen-Leiserson-Rivest-Stein (CLRS) B-Tree algorithm with minimum degree $t$.

## Requirements

Implement the class `BTree`:

- `__init__(self, t: int = 3)`:
  Initializes B-Tree with minimum degree $t \ge 2$.
  Each node (except root) contains at least $t - 1$ keys, and at most $2t - 1$ keys.
  Each internal node contains at least $t$ children and at most $2t$ children.
- `insert(self, key: int, val: Any = None) -> None`:
  Inserts `(key, val)` into the B-Tree.
  If `key` already exists, update its associated value without duplicating the key.
  Maintains the B-Tree invariants by proactively splitting full nodes during downward traversal.
- `search(self, key: int) -> Any | None`:
  Returns the value associated with `key` if found, else `None`.
- `range_query(self, low: int, high: int) -> list[tuple[int, Any]]`:
  Returns an ordered list of `(key, value)` pairs such that `low <= key <= high`.
- `to_inorder_keys(self) -> list[int]`:
  Returns a list of all keys in the tree in ascending sorted order.
""",
        "starter_code": """from typing import Any


class BTree:
    def __init__(self, t: int = 3) -> None:
        \"\"\"Initialize B-Tree with minimum degree t.\"\"\"
        pass

    def insert(self, key: int, val: Any = None) -> None:
        \"\"\"Insert or update key-value pair.\"\"\"
        pass

    def search(self, key: int) -> Any | None:
        \"\"\"Search for key and return its value or None.\"\"\"
        pass

    def range_query(self, low: int, high: int) -> list[tuple[int, Any]]:
        \"\"\"Return sorted list of (key, val) within [low, high] inclusive.\"\"\"
        pass

    def to_inorder_keys(self) -> list[int]:
        \"\"\"Return all keys in ascending order.\"\"\"
        pass
""",
        "canonical_solution": """from typing import Any


class _BTreeNode:
    def __init__(self, is_leaf: bool = True) -> None:
        self.is_leaf = is_leaf
        self.keys: list[int] = []
        self.values: list[Any] = []
        self.children: list['_BTreeNode'] = []


class BTree:
    def __init__(self, t: int = 3) -> None:
        if t < 2:
            raise ValueError("Minimum degree t must be at least 2")
        self.t = t
        self.root = _BTreeNode(is_leaf=True)

    def search(self, key: int) -> Any | None:
        def _search(node: _BTreeNode, k: int) -> Any | None:
            i = 0
            while i < len(node.keys) and k > node.keys[i]:
                i += 1
            if i < len(node.keys) and node.keys[i] == k:
                return node.values[i]
            if node.is_leaf:
                return None
            return _search(node.children[i], k)

        return _search(self.root, key)

    def _split_child(self, parent: _BTreeNode, i: int) -> None:
        t = self.t
        full_child = parent.children[i]
        new_sibling = _BTreeNode(is_leaf=full_child.is_leaf)

        median_key = full_child.keys[t - 1]
        median_val = full_child.values[t - 1]

        new_sibling.keys = full_child.keys[t:]
        new_sibling.values = full_child.values[t:]
        full_child.keys = full_child.keys[: t - 1]
        full_child.values = full_child.values[: t - 1]

        if not full_child.is_leaf:
            new_sibling.children = full_child.children[t:]
            full_child.children = full_child.children[:t]

        parent.children.insert(i + 1, new_sibling)
        parent.keys.insert(i, median_key)
        parent.values.insert(i, median_val)

    def _insert_non_full(self, node: _BTreeNode, key: int, val: Any) -> None:
        i = len(node.keys) - 1

        if node.is_leaf:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            if i >= 0 and node.keys[i] == key:
                node.values[i] = val
                return
            node.keys.insert(i + 1, key)
            node.values.insert(i + 1, val)
        else:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            if i >= 0 and node.keys[i] == key:
                node.values[i] = val
                return
            i += 1
            if len(node.children[i].keys) == 2 * self.t - 1:
                self._split_child(node, i)
                if key > node.keys[i]:
                    i += 1
                elif key == node.keys[i]:
                    node.values[i] = val
                    return
            self._insert_non_full(node.children[i], key, val)

    def insert(self, key: int, val: Any = None) -> None:
        # Check if key already exists to update in place
        def _update_if_exists(node: _BTreeNode, k: int, v: Any) -> bool:
            i = 0
            while i < len(node.keys) and k > node.keys[i]:
                i += 1
            if i < len(node.keys) and node.keys[i] == k:
                node.values[i] = v
                return True
            if node.is_leaf:
                return False
            return _update_if_exists(node.children[i], k, v)

        if _update_if_exists(self.root, key, val):
            return

        r = self.root
        if len(r.keys) == 2 * self.t - 1:
            new_root = _BTreeNode(is_leaf=False)
            new_root.children.append(self.root)
            self._split_child(new_root, 0)
            self.root = new_root
            self._insert_non_full(new_root, key, val)
        else:
            self._insert_non_full(r, key, val)

    def to_inorder_keys(self) -> list[int]:
        keys: list[int] = []

        def _inorder(node: _BTreeNode) -> None:
            for i in range(len(node.keys)):
                if not node.is_leaf:
                    _inorder(node.children[i])
                keys.append(node.keys[i])
            if not node.is_leaf:
                _inorder(node.children[-1])

        _inorder(self.root)
        return keys

    def range_query(self, low: int, high: int) -> list[tuple[int, Any]]:
        results: list[tuple[int, Any]] = []

        def _traverse(node: _BTreeNode) -> None:
            for i in range(len(node.keys)):
                k = node.keys[i]
                v = node.values[i]
                if not node.is_leaf and k >= low:
                    _traverse(node.children[i])
                if low <= k <= high:
                    results.append((k, v))
                if k > high:
                    return
            if not node.is_leaf:
                _traverse(node.children[-1])

        _traverse(self.root)
        return sorted(results, key=lambda x: x[0])
""",
        "visible_tests": """def test_btree_basic_insert_search():
    tree = BTree(t=2)
    for k in [10, 20, 5, 6, 12, 30, 7, 17]:
        tree.insert(k, f"val_{k}")

    assert tree.search(10) == "val_10"
    assert tree.search(7) == "val_7"
    assert tree.search(999) is None
    assert tree.to_inorder_keys() == [5, 6, 7, 10, 12, 17, 20, 30]


def test_btree_range_query():
    tree = BTree(t=3)
    for i in range(1, 21):
        tree.insert(i, i * 10)

    res = tree.range_query(5, 10)
    expected = [(i, i * 10) for i in range(5, 11)]
    assert res == expected
""",
        "hidden_tests": """def test_root_split_multiple_levels():
    tree = BTree(t=2)  # max keys per node = 3
    for x in range(1, 32):
        tree.insert(x, x * 2)

    assert tree.to_inorder_keys() == list(range(1, 32))
    for x in range(1, 32):
        assert tree.search(x) == x * 2


def test_update_existing_key():
    tree = BTree(t=3)
    tree.insert(42, "original")
    assert tree.search(42) == "original"
    tree.insert(42, "updated")
    assert tree.search(42) == "updated"
    assert tree.to_inorder_keys() == [42]


def test_range_query_boundary_conditions():
    tree = BTree(t=2)
    tree.insert(10, "a")
    tree.insert(20, "b")
    tree.insert(30, "c")
    assert tree.range_query(0, 5) == []
    assert tree.range_query(10, 10) == [(10, "a")]
    assert tree.range_query(25, 40) == [(30, "c")]


def test_reverse_insertion_order():
    tree = BTree(t=3)
    for x in reversed(range(100)):
        tree.insert(x, x)
    assert tree.to_inorder_keys() == list(range(100))


def test_large_random_scale():
    import random
    rng = random.Random(42)
    tree = BTree(t=4)
    data = list(range(1000))
    rng.shuffle(data)

    for k in data:
        tree.insert(k, k)

    assert tree.to_inorder_keys() == list(range(1000))
    for k in [0, 499, 999]:
        assert tree.search(k) == k


def test_minimum_degree_parameter_validation():
    import pytest
    with pytest.raises(ValueError):
        BTree(t=1)
""",
    },
]
