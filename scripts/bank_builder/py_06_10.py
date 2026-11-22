"""Tasks EF-PY-006 through EF-PY-010."""

TASKS = [
    {
        "task_id": "EF-PY-006",
        "title": "Disjoint Set Union with Path Compression and Rank",
        "language": "python",
        "difficulty": "easy",
        "category": "data_structures",
        "tags": ["union-find", "disjoint-set", "graphs", "data_structures", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Disjoint Set Union with Path Compression and Rank

Implement a generic Disjoint Set Union (DSU / Union-Find) data structure supporting near-constant time amortized operations using path compression and union by rank.

## Requirements

Implement the class `DisjointSet`:

- `make_set(self, x: Any) -> None`:
  Adds a new element `x` as an independent set of size 1. If `x` already exists, does nothing.
- `find(self, x: Any) -> Any`:
  Finds the representative (root) of the set containing `x`, applying two-pass or recursive path compression.
  Raises `KeyError` if `x` has not been added via `make_set`.
- `union(self, x: Any, y: Any) -> bool`:
  Unites the sets containing elements `x` and `y` using union by rank.
  If the root ranks are equal, increments the rank of the new root.
  Updates the component size accordingly.
  Returns `True` if two disjoint sets were united, or `False` if `x` and `y` were already in the same set.
  Raises `KeyError` if either `x` or `y` is not registered.
- `connected(self, x: Any, y: Any) -> bool`:
  Returns `True` if `x` and `y` share the same representative, `False` otherwise.
  Raises `KeyError` if either element is not registered.
- `get_component_size(self, x: Any) -> int`:
  Returns the total number of elements in the component containing `x`.
- `count_components(self) -> int`:
  Returns the total number of distinct disjoint sets (connected components).
""",
        "starter_code": """from typing import Any


class DisjointSet:
    def __init__(self) -> None:
        \"\"\"Initialize empty Disjoint Set.\"\"\"
        pass

    def make_set(self, x: Any) -> None:
        \"\"\"Create a new set for element x.\"\"\"
        pass

    def find(self, x: Any) -> Any:
        \"\"\"Find representative of set containing x with path compression.\"\"\"
        pass

    def union(self, x: Any, y: Any) -> bool:
        \"\"\"Union sets containing x and y by rank.\"\"\"
        pass

    def connected(self, x: Any, y: Any) -> bool:
        \"\"\"Return True if x and y are in same set.\"\"\"
        pass

    def get_component_size(self, x: Any) -> int:
        \"\"\"Return size of component containing x.\"\"\"
        pass

    def count_components(self) -> int:
        \"\"\"Return number of disjoint components.\"\"\"
        pass
""",
        "canonical_solution": """from typing import Any


class DisjointSet:
    def __init__(self) -> None:
        self._parent: dict[Any, Any] = {}
        self._rank: dict[Any, int] = {}
        self._size: dict[Any, int] = {}
        self._num_components: int = 0

    def make_set(self, x: Any) -> None:
        if x in self._parent:
            return
        self._parent[x] = x
        self._rank[x] = 0
        self._size[x] = 1
        self._num_components += 1

    def find(self, x: Any) -> Any:
        if x not in self._parent:
            raise KeyError(f"Element {x} not found in DisjointSet")
        # Iterative path compression to avoid recursion limit
        root = x
        while root != self._parent[root]:
            root = self._parent[root]
        curr = x
        while curr != root:
            nxt = self._parent[curr]
            self._parent[curr] = root
            curr = nxt
        return root

    def union(self, x: Any, y: Any) -> bool:
        root_x = self.find(x)
        root_y = self.find(y)

        if root_x == root_y:
            return False

        if self._rank[root_x] < self._rank[root_y]:
            root_x, root_y = root_y, root_x

        self._parent[root_y] = root_x
        self._size[root_x] += self._size[root_y]
        if self._rank[root_x] == self._rank[root_y]:
            self._rank[root_x] += 1

        self._num_components -= 1
        return True

    def connected(self, x: Any, y: Any) -> bool:
        return self.find(x) == self.find(y)

    def get_component_size(self, x: Any) -> int:
        root = self.find(x)
        return self._size[root]

    def count_components(self) -> int:
        return self._num_components
""",
        "visible_tests": """def test_dsu_basic_operations():
    dsu = DisjointSet()
    for item in ["A", "B", "C", "D"]:
        dsu.make_set(item)

    assert dsu.count_components() == 4
    assert dsu.connected("A", "B") is False
    assert dsu.union("A", "B") is True
    assert dsu.connected("A", "B") is True
    assert dsu.count_components() == 3
    assert dsu.get_component_size("A") == 2


def test_dsu_transitive_connectivity():
    dsu = DisjointSet()
    for i in range(5):
        dsu.make_set(i)

    dsu.union(0, 1)
    dsu.union(1, 2)
    assert dsu.connected(0, 2) is True
    assert dsu.get_component_size(0) == 3
    assert dsu.connected(0, 4) is False
""",
        "hidden_tests": """import pytest


def test_dsu_idempotent_union():
    dsu = DisjointSet()
    dsu.make_set(1)
    dsu.make_set(2)
    assert dsu.union(1, 2) is True
    assert dsu.union(1, 2) is False  # already connected
    assert dsu.count_components() == 1


def test_dsu_unknown_element_raises_key_error():
    dsu = DisjointSet()
    dsu.make_set(10)
    with pytest.raises(KeyError):
        dsu.find(99)
    with pytest.raises(KeyError):
        dsu.union(10, 99)
    with pytest.raises(KeyError):
        dsu.connected(10, 99)


def test_dsu_component_sizes_tracking():
    dsu = DisjointSet()
    for i in range(10):
        dsu.make_set(i)

    dsu.union(0, 1)
    dsu.union(2, 3)
    dsu.union(0, 2)
    assert dsu.get_component_size(3) == 4
    assert dsu.get_component_size(5) == 1
    assert dsu.count_components() == 7


def test_dsu_duplicate_make_set_noop():
    dsu = DisjointSet()
    dsu.make_set("x")
    dsu.make_set("x")
    assert dsu.count_components() == 1
    assert dsu.get_component_size("x") == 1


def test_dsu_large_chain_scale():
    dsu = DisjointSet()
    n = 10000
    for i in range(n):
        dsu.make_set(i)

    for i in range(n - 1):
        dsu.union(i, i + 1)

    assert dsu.count_components() == 1
    assert dsu.connected(0, n - 1) is True
    assert dsu.get_component_size(n // 2) == n


def test_dsu_star_topology():
    dsu = DisjointSet()
    center = 0
    dsu.make_set(center)
    for leaf in range(1, 100):
        dsu.make_set(leaf)
        dsu.union(center, leaf)

    assert dsu.count_components() == 1
    assert dsu.get_component_size(center) == 100
""",
    },
    {
        "task_id": "EF-PY-007",
        "title": "Probabilistic SkipList with Ordered Operations",
        "language": "python",
        "difficulty": "hard",
        "category": "data_structures",
        "tags": ["skiplist", "data_structures", "probabilistic", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Probabilistic SkipList with Ordered Operations

Implement a probabilistic Skip List data structure providing $O(\\log N)$ average-case search, insertion, and deletion of key-value pairs sorted in ascending order.

## Requirements

Implement the class `SkipList`:

- `__init__(self, max_level: int = 16, p: float = 0.5)`:
  Initializes skip list with maximum height `max_level >= 1` and coin-flip promotion probability `p` (`0 < p < 1`).
- `insert(self, key: int, val: Any = None) -> None`:
  Inserts `(key, val)`. If `key` already exists in the skip list, updates its value in place without altering the structure or height.
- `search(self, key: int) -> Any | None`:
  Returns the associated value if `key` is present, or `None` if not found.
- `delete(self, key: int) -> bool`:
  Removes `key` from all levels where it appears. Returns `True` if key was found and deleted, `False` otherwise.
- `to_list(self) -> list[tuple[int, Any]]`:
  Returns all elements as a sorted list of `(key, value)` tuples in ascending order.
- `__len__(self) -> int`:
  Returns the current number of unique keys in the skip list.
""",
        "starter_code": """from typing import Any


class SkipList:
    def __init__(self, max_level: int = 16, p: float = 0.5) -> None:
        \"\"\"Initialize SkipList with max levels and promotion probability.\"\"\"
        pass

    def insert(self, key: int, val: Any = None) -> None:
        \"\"\"Insert or update key-value pair.\"\"\"
        pass

    def search(self, key: int) -> Any | None:
        \"\"\"Search for key and return value or None.\"\"\"
        pass

    def delete(self, key: int) -> bool:
        \"\"\"Delete key from skip list. Return True if found, False otherwise.\"\"\"
        pass

    def to_list(self) -> list[tuple[int, Any]]:
        \"\"\"Return sorted list of (key, val) tuples.\"\"\"
        pass

    def __len__(self) -> int:
        \"\"\"Return number of elements.\"\"\"
        pass
""",
        "canonical_solution": """import random
from typing import Any


class _SkipNode:
    def __init__(self, key: int, val: Any, level: int) -> None:
        self.key = key
        self.val = val
        self.forward: list['_SkipNode | None'] = [None] * level


class SkipList:
    def __init__(self, max_level: int = 16, p: float = 0.5) -> None:
        if max_level < 1:
            raise ValueError("max_level must be >= 1")
        if not (0.0 < p < 1.0):
            raise ValueError("p must be between 0 and 1")
        self.max_level = max_level
        self.p = p
        self.header = _SkipNode(-1, None, max_level)
        self.level = 1
        self._size = 0
        self._rng = random.Random(1337)

    def _random_level(self) -> int:
        lvl = 1
        while self._rng.random() < self.p and lvl < self.max_level:
            lvl += 1
        return lvl

    def search(self, key: int) -> Any | None:
        curr = self.header
        for i in reversed(range(self.level)):
            while curr.forward[i] is not None and curr.forward[i].key < key:
                curr = curr.forward[i]
        curr = curr.forward[0]
        if curr is not None and curr.key == key:
            return curr.val
        return None

    def insert(self, key: int, val: Any = None) -> None:
        update: list[_SkipNode] = [self.header] * self.max_level
        curr = self.header

        for i in reversed(range(self.level)):
            while curr.forward[i] is not None and curr.forward[i].key < key:
                curr = curr.forward[i]
            update[i] = curr

        candidate = curr.forward[0]
        if candidate is not None and candidate.key == key:
            candidate.val = val
            return

        new_level = self._random_level()
        if new_level > self.level:
            for i in range(self.level, new_level):
                update[i] = self.header
            self.level = new_level

        new_node = _SkipNode(key, val, new_level)
        for i in range(new_level):
            new_node.forward[i] = update[i].forward[i]
            update[i].forward[i] = new_node

        self._size += 1

    def delete(self, key: int) -> bool:
        update: list[_SkipNode] = [self.header] * self.max_level
        curr = self.header

        for i in reversed(range(self.level)):
            while curr.forward[i] is not None and curr.forward[i].key < key:
                curr = curr.forward[i]
            update[i] = curr

        target = curr.forward[0]
        if target is None or target.key != key:
            return False

        for i in range(self.level):
            if update[i].forward[i] is not target:
                break
            update[i].forward[i] = target.forward[i]

        while self.level > 1 and self.header.forward[self.level - 1] is None:
            self.level -= 1

        self._size -= 1
        return True

    def to_list(self) -> list[tuple[int, Any]]:
        result: list[tuple[int, Any]] = []
        curr = self.header.forward[0]
        while curr is not None:
            result.append((curr.key, curr.val))
            curr = curr.forward[0]
        return result

    def __len__(self) -> int:
        return self._size
""",
        "visible_tests": """def test_skiplist_insert_and_search():
    sl = SkipList()
    sl.insert(10, "ten")
    sl.insert(5, "five")
    sl.insert(20, "twenty")

    assert sl.search(10) == "ten"
    assert sl.search(5) == "five"
    assert sl.search(99) is None
    assert len(sl) == 3
    assert sl.to_list() == [(5, "five"), (10, "ten"), (20, "twenty")]


def test_skiplist_delete():
    sl = SkipList()
    sl.insert(1, "one")
    sl.insert(2, "two")
    assert sl.delete(1) is True
    assert sl.delete(1) is False
    assert sl.search(1) is None
    assert len(sl) == 1
    assert sl.to_list() == [(2, "two")]
""",
        "hidden_tests": """def test_update_existing_key():
    sl = SkipList()
    sl.insert(42, "initial")
    assert sl.search(42) == "initial"
    sl.insert(42, "updated")
    assert sl.search(42) == "updated"
    assert len(sl) == 1
    assert sl.to_list() == [(42, "updated")]


def test_empty_skiplist():
    sl = SkipList()
    assert len(sl) == 0
    assert sl.search(10) is None
    assert sl.delete(10) is False
    assert sl.to_list() == []


def test_delete_head_and_tail():
    sl = SkipList()
    for k in [10, 20, 30, 40]:
        sl.insert(k, k * 2)

    assert sl.delete(10) is True  # delete head
    assert sl.delete(40) is True  # delete tail
    assert sl.to_list() == [(20, 40), (30, 60)]


def test_negative_and_zero_keys():
    sl = SkipList()
    keys = [-10, 0, 10, -5, 5]
    for k in keys:
        sl.insert(k, f"v_{k}")
    assert sl.to_list() == [(-10, "v_-10"), (-5, "v_-5"), (0, "v_0"), (5, "v_5"), (10, "v_10")]


def test_scale_ordered_sequence():
    sl = SkipList(max_level=16)
    n = 1000
    for i in range(n):
        sl.insert(i, i)

    assert len(sl) == n
    assert sl.to_list() == [(i, i) for i in range(n)]

    # Delete odd numbers
    for i in range(1, n, 2):
        assert sl.delete(i) is True

    assert len(sl) == n // 2
    assert sl.to_list() == [(i, i) for i in range(0, n, 2)]


def test_parameter_validation():
    import pytest
    with pytest.raises(ValueError):
        SkipList(max_level=0)
    with pytest.raises(ValueError):
        SkipList(p=1.5)
""",
    },
    {
        "task_id": "EF-PY-008",
        "title": "Streaming JSON Tokenizer State Machine",
        "language": "python",
        "difficulty": "hard",
        "category": "systems",
        "tags": ["lexer", "state-machine", "streaming", "json", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 25,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Streaming JSON Tokenizer State Machine

Implement an incremental streaming JSON lexer / tokenizer state machine that consumes incoming text chunks of arbitrary length and produces complete tokens without buffering the entire payload in memory.

## Requirements

Implement the enum `TokenType`:
- `LEFT_BRACE`: `{`
- `RIGHT_BRACE`: `}`
- `LEFT_BRACKET`: `[`
- `RIGHT_BRACKET`: `]`
- `COLON`: `:`
- `COMMA`: `,`
- `STRING`: String value with escapes unescaped (e.g. `"hello"`)
- `NUMBER`: Integer or floating-point value (e.g. `42`, `-3.14`)
- `BOOLEAN`: Boolean value (`True` or `False`)
- `NULL`: `None`

Implement the dataclass `Token`:
- `type: TokenType`
- `value: Any`

Implement `StreamingJSONTokenizer`:
- `feed(self, chunk: str) -> list[Token]`:
  Feeds an arbitrary string fragment. Returns a list of all tokens completed by this chunk. Tokens split across boundaries must remain buffered until finished.
- `finish(self) -> list[Token]`:
  Signals end-of-input. Flushes any remaining terminal tokens (such as trailing numbers or literals).
  Raises `ValueError` if stream ends inside an unfinished string, escape sequence, or malformed literal.
""",
        "starter_code": """from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COLON = auto()
    COMMA = auto()
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()


@dataclass
class Token:
    type: TokenType
    value: Any


class StreamingJSONTokenizer:
    def __init__(self) -> None:
        \"\"\"Initialize streaming tokenizer state machine.\"\"\"
        pass

    def feed(self, chunk: str) -> list[Token]:
        \"\"\"Feed string chunk and return newly completed tokens.\"\"\"
        pass

    def finish(self) -> list[Token]:
        \"\"\"Flush final tokens or raise ValueError on incomplete input.\"\"\"
        pass
""",
        "canonical_solution": """from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COLON = auto()
    COMMA = auto()
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()


@dataclass
class Token:
    type: TokenType
    value: Any


class StreamingJSONTokenizer:
    def __init__(self) -> None:
        self._buf = ""
        self._in_string = False
        self._escape = False
        self._str_chars: list[str] = []

    def feed(self, chunk: str) -> list[Token]:
        self._buf += chunk
        return self._tokenize(is_eof=False)

    def finish(self) -> list[Token]:
        tokens = self._tokenize(is_eof=True)
        if self._in_string:
            raise ValueError("Unterminated string literal at EOF")
        remaining = self._buf.strip()
        if remaining:
            raise ValueError(f"Unrecognized syntax at EOF: '{remaining}'")
        return tokens

    def _tokenize(self, is_eof: bool) -> list[Token]:
        tokens: list[Token] = []
        i = 0
        n = len(self._buf)

        while i < n:
            c = self._buf[i]

            if self._in_string:
                if self._escape:
                    if c == '"':
                        self._str_chars.append('"')
                    elif c == '\\\\':
                        self._str_chars.append('\\\\')
                    elif c == '/':
                        self._str_chars.append('/')
                    elif c == 'b':
                        self._str_chars.append('\\b')
                    elif c == 'f':
                        self._str_chars.append('\\f')
                    elif c == 'n':
                        self._str_chars.append('\\n')
                    elif c == 'r':
                        self._str_chars.append('\\r')
                    elif c == 't':
                        self._str_chars.append('\\t')
                    else:
                        self._str_chars.append(c)
                    self._escape = False
                elif c == '\\\\':
                    self._escape = True
                elif c == '"':
                    self._in_string = False
                    tokens.append(Token(TokenType.STRING, "".join(self._str_chars)))
                    self._str_chars = []
                else:
                    self._str_chars.append(c)
                i += 1
                continue

            # Outside string
            if c.isspace():
                i += 1
                continue

            if c == '{':
                tokens.append(Token(TokenType.LEFT_BRACE, "{"))
                i += 1
            elif c == '}':
                tokens.append(Token(TokenType.RIGHT_BRACE, "}"))
                i += 1
            elif c == '[':
                tokens.append(Token(TokenType.LEFT_BRACKET, "["))
                i += 1
            elif c == ']':
                tokens.append(Token(TokenType.RIGHT_BRACKET, "]"))
                i += 1
            elif c == ':':
                tokens.append(Token(TokenType.COLON, ":"))
                i += 1
            elif c == ',':
                tokens.append(Token(TokenType.COMMA, ","))
                i += 1
            elif c == '"':
                self._in_string = True
                self._str_chars = []
                self._escape = False
                i += 1
            else:
                # Potential number, boolean (true/false), or null
                start = i
                while i < n and (self._buf[i].isalnum() or self._buf[i] in "-+."):
                    i += 1

                word = self._buf[start:i]

                if not is_eof and i == n:
                    # Token might be incomplete across chunk boundary
                    i = start
                    break

                if word == "true":
                    tokens.append(Token(TokenType.BOOLEAN, True))
                elif word == "false":
                    tokens.append(Token(TokenType.BOOLEAN, False))
                elif word == "null":
                    tokens.append(Token(TokenType.NULL, None))
                else:
                    try:
                        if "." in word or "e" in word.lower():
                            tokens.append(Token(TokenType.NUMBER, float(word)))
                        else:
                            tokens.append(Token(TokenType.NUMBER, int(word)))
                    except ValueError:
                        raise ValueError(f"Malformed token: '{word}'")

        self._buf = self._buf[i:]
        return tokens
""",
        "visible_tests": """def test_json_tokenizer_basic():
    tok = StreamingJSONTokenizer()
    tokens = tok.feed('{"name": "Alice", "age": 30}')
    tokens += tok.finish()

    types = [t.type for t in tokens]
    assert types == [
        TokenType.LEFT_BRACE,
        TokenType.STRING,
        TokenType.COLON,
        TokenType.STRING,
        TokenType.COMMA,
        TokenType.STRING,
        TokenType.COLON,
        TokenType.NUMBER,
        TokenType.RIGHT_BRACE,
    ]
    assert tokens[1].value == "name"
    assert tokens[3].value == "Alice"
    assert tokens[7].value == 30


def test_json_tokenizer_chunk_streaming():
    tok = StreamingJSONTokenizer()
    t1 = tok.feed('{"count": ')
    t2 = tok.feed('12')
    t3 = tok.feed('34, "active": tru')
    t4 = tok.feed('e}')
    t5 = tok.finish()

    all_tokens = t1 + t2 + t3 + t4 + t5
    vals = [(t.type, t.value) for t in all_tokens]
    assert (TokenType.NUMBER, 1234) in vals
    assert (TokenType.BOOLEAN, True) in vals
""",
        "hidden_tests": """import pytest


def test_escaped_string_tokens():
    tok = StreamingJSONTokenizer()
    tokens = tok.feed('"Line 1\\\\nLine 2\\\\tTabbed \\\\\\"Quote\\\\\\""')
    tokens += tok.finish()
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == 'Line 1\\nLine 2\\tTabbed "Quote"'


def test_floats_and_negative_numbers():
    tok = StreamingJSONTokenizer()
    tokens = tok.feed('[-42, 3.1415, -0.5, 1e-3]')
    tokens += tok.finish()
    vals = [t.value for t in tokens if t.type == TokenType.NUMBER]
    assert vals == [-42, 3.1415, -0.5, 0.001]


def test_null_and_boolean_literals():
    tok = StreamingJSONTokenizer()
    tokens = tok.feed('[true, false, null]')
    tokens += tok.finish()
    res = [(t.type, t.value) for t in tokens if t.type in (TokenType.BOOLEAN, TokenType.NULL)]
    assert res == [(TokenType.BOOLEAN, True), (TokenType.BOOLEAN, False), (TokenType.NULL, None)]


def test_character_by_character_feeding():
    tok = StreamingJSONTokenizer()
    raw = '{"arr": [1, 2]}'
    collected = []
    for char in raw:
        collected.extend(tok.feed(char))
    collected.extend(tok.finish())
    types = [t.type for t in collected]
    assert types == [
        TokenType.LEFT_BRACE,
        TokenType.STRING,
        TokenType.COLON,
        TokenType.LEFT_BRACKET,
        TokenType.NUMBER,
        TokenType.COMMA,
        TokenType.NUMBER,
        TokenType.RIGHT_BRACKET,
        TokenType.RIGHT_BRACE,
    ]


def test_unclosed_string_raises():
    tok = StreamingJSONTokenizer()
    tok.feed('{"title": "incomplete')
    with pytest.raises(ValueError):
        tok.finish()


def test_malformed_token_raises():
    tok = StreamingJSONTokenizer()
    with pytest.raises(ValueError):
        tok.feed('{"k": bad_token}')
        tok.finish()
""",
    },
    {
        "task_id": "EF-PY-009",
        "title": "SQL WHERE Clause Boolean AST Evaluator",
        "language": "python",
        "difficulty": "medium",
        "category": "algorithmic",
        "tags": ["ast", "parser", "sql", "interpreter", "algorithmic"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes"],
            "max_cyclomatic_complexity": 25,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# SQL WHERE Clause Boolean AST Evaluator

Implement a parser and evaluator for SQL `WHERE` clause boolean expressions against dictionary rows.

## Supported Operations

1. **Logical operators**: `AND`, `OR`, `NOT` (Precedence: `NOT` > `AND` > `OR`, overridden by parentheses `()`).
2. **Comparison operators**: `=`, `!=`, `>`, `<`, `>=`, `<=` (supporting numbers and strings).
3. **Set inclusion**: `field IN (val1, val2, ...)`
4. **Pattern matching**: `field LIKE 'pattern'` where `'%'` matches zero or more characters.

## Requirements

Implement the class `WhereClauseEvaluator`:

- `parse_and_eval(self, expr_str: str, row: dict[str, Any]) -> bool`:
  Tokenizes, parses, and evaluates the SQL WHERE clause string `expr_str` against `row`.
  Returns `True` if `row` satisfies the predicate, `False` otherwise.
  If a referenced field is missing from `row`, its value is treated as `None`. Comparisons with `None` (other than `=` and `!=`) evaluate to `False`.
- `evaluate_ast(self, ast_node: dict[str, Any], row: dict[str, Any]) -> bool`:
  Evaluates a structured dictionary AST node directly against `row`.
  AST format:
  - `{"op": "AND", "left": <node>, "right": <node>}`
  - `{"op": "OR", "left": <node>, "right": <node>}`
  - `{"op": "NOT", "expr": <node>}`
  - `{"op": "=", "field": "age", "val": 25}` (or `!=`, `>`, `<`, `>=`, `<=`, `IN`, `LIKE`)
""",
        "starter_code": """from typing import Any


class WhereClauseEvaluator:
    def __init__(self) -> None:
        \"\"\"Initialize SQL Where Clause Evaluator.\"\"\"
        pass

    def parse_and_eval(self, expr_str: str, row: dict[str, Any]) -> bool:
        \"\"\"Parse WHERE clause string and evaluate against row dictionary.\"\"\"
        pass

    def evaluate_ast(self, ast_node: dict[str, Any], row: dict[str, Any]) -> bool:
        \"\"\"Evaluate pre-parsed AST node against row dictionary.\"\"\"
        pass
""",
        "canonical_solution": """import re
from typing import Any


class WhereClauseEvaluator:
    def evaluate_ast(self, ast_node: dict[str, Any], row: dict[str, Any]) -> bool:
        op = ast_node.get("op", "").upper()

        if op == "AND":
            return self.evaluate_ast(ast_node["left"], row) and self.evaluate_ast(ast_node["right"], row)
        if op == "OR":
            return self.evaluate_ast(ast_node["left"], row) or self.evaluate_ast(ast_node["right"], row)
        if op == "NOT":
            return not self.evaluate_ast(ast_node["expr"], row)

        field = ast_node["field"]
        val = row.get(field)
        target = ast_node["val"]

        if op == "=":
            return val == target
        if op == "!=":
            return val != target

        if val is None:
            return False

        if op == ">":
            return val > target
        if op == "<":
            return val < target
        if op == ">=":
            return val >= target
        if op == "<=":
            return val <= target
        if op == "IN":
            return val in target
        if op == "LIKE":
            parts = [re.escape(part) for part in str(target).split("%")]
            pattern = "^" + ".*".join(parts) + "$"
            return bool(re.match(pattern, str(val)))

        raise ValueError(f"Unknown operator: {op}")

    def _tokenize(self, expr_str: str) -> list[str]:
        token_spec = [
            ("STRING", r"'[^']*'"),
            ("OP", r"!=|>=|<=|=|>|<"),
            ("LPAREN", r"\\("),
            ("RPAREN", r"\\)"),
            ("COMMA", r","),
            ("WORD", r"[A-Za-z_][A-Za-z0-9_]*"),
            ("NUMBER", r"-?\\d+(\\.\\d+)?"),
            ("WS", r"\\s+"),
        ]
        master_pat = "|".join(f"(?P<{name}>{pat})" for name, pat in token_spec)
        tokens: list[str] = []
        for mo in re.finditer(master_pat, expr_str):
            kind = mo.lastgroup
            val = mo.group()
            if kind != "WS":
                tokens.append(val)
        return tokens

    def parse_and_eval(self, expr_str: str, row: dict[str, Any]) -> bool:
        tokens = self._tokenize(expr_str)
        if not tokens:
            return True

        pos = 0

        def peek() -> str | None:
            nonlocal pos
            return tokens[pos] if pos < len(tokens) else None

        def consume(expected: str | None = None) -> str:
            nonlocal pos
            tok = tokens[pos]
            pos += 1
            return tok

        # Recursive descent parser
        def parse_expr() -> dict[str, Any]:
            return parse_or()

        def parse_or() -> dict[str, Any]:
            node = parse_and()
            while peek() and peek().upper() == "OR":
                consume()
                right = parse_and()
                node = {"op": "AND" if False else "OR", "left": node, "right": right}
            return node

        def parse_and() -> dict[str, Any]:
            node = parse_not()
            while peek() and peek().upper() == "AND":
                consume()
                right = parse_not()
                node = {"op": "AND", "left": node, "right": right}
            return node

        def parse_not() -> dict[str, Any]:
            if peek() and peek().upper() == "NOT":
                consume()
                return {"op": "NOT", "expr": parse_not()}
            return parse_primary()

        def parse_primary() -> dict[str, Any]:
            if peek() == "(":
                consume("(")
                node = parse_expr()
                consume(")")
                return node

            field = consume()
            op = consume().upper()

            if op == "IN":
                consume("(")
                items: list[Any] = []
                while peek() != ")":
                    items.append(_parse_val(consume()))
                    if peek() == ",":
                        consume(",")
                consume(")")
                return {"op": "IN", "field": field, "val": items}

            target = _parse_val(consume())
            return {"op": op, "field": field, "val": target}

        def _parse_val(tok: str) -> Any:
            if tok.startswith("'") and tok.endswith("'"):
                return tok[1:-1]
            try:
                return float(tok) if "." in tok else int(tok)
            except ValueError:
                return tok

        ast_root = parse_expr()
        return self.evaluate_ast(ast_root, row)
""",
        "visible_tests": """def test_simple_equality_and_and():
    evaluator = WhereClauseEvaluator()
    row = {"age": 30, "status": "active", "dept": "eng"}
    assert evaluator.parse_and_eval("age > 21 AND status = 'active'", row) is True
    assert evaluator.parse_and_eval("age < 21 AND status = 'active'", row) is False


def test_or_and_parentheses_precedence():
    evaluator = WhereClauseEvaluator()
    row = {"score": 85, "tier": "gold", "country": "US"}
    # (score > 90 OR tier = 'gold') AND country = 'US' => True
    assert evaluator.parse_and_eval("(score > 90 OR tier = 'gold') AND country = 'US'", row) is True
    # score > 90 OR (tier = 'gold' AND country = 'CA') => False
    assert evaluator.parse_and_eval("score > 90 OR (tier = 'gold' AND country = 'CA')", row) is False
""",
        "hidden_tests": """def test_not_operator():
    evaluator = WhereClauseEvaluator()
    row = {"banned": False, "role": "admin"}
    assert evaluator.parse_and_eval("NOT banned = 'true'", row) is True
    assert evaluator.parse_and_eval("NOT role = 'admin'", row) is False


def test_in_operator():
    evaluator = WhereClauseEvaluator()
    row = {"role": "editor", "level": 3}
    assert evaluator.parse_and_eval("role IN ('admin', 'editor', 'viewer')", row) is True
    assert evaluator.parse_and_eval("level IN (1, 2, 4)", row) is False


def test_like_operator():
    evaluator = WhereClauseEvaluator()
    row = {"email": "john.doe@company.org"}
    assert evaluator.parse_and_eval("email LIKE '%.org'", row) is True
    assert evaluator.parse_and_eval("email LIKE 'john.%'", row) is True
    assert evaluator.parse_and_eval("email LIKE '%.com'", row) is False


def test_missing_column_evaluates_false():
    evaluator = WhereClauseEvaluator()
    row = {"name": "Alice"}
    assert evaluator.parse_and_eval("age > 18", row) is False
    assert evaluator.parse_and_eval("age != 18", row) is True


def test_ast_evaluation_directly():
    evaluator = WhereClauseEvaluator()
    ast = {
        "op": "AND",
        "left": {"op": ">=", "field": "salary", "val": 50000},
        "right": {"op": "=", "field": "department", "val": "Engineering"},
    }
    assert evaluator.evaluate_ast(ast, {"salary": 75000, "department": "Engineering"}) is True
    assert evaluator.evaluate_ast(ast, {"salary": 40000, "department": "Engineering"}) is False


def test_complex_nested_expression():
    evaluator = WhereClauseEvaluator()
    row = {"x": 10, "y": 20, "z": 30}
    expr = "((x = 10 AND y < 25) OR z = 99) AND NOT x > 50"
    assert evaluator.parse_and_eval(expr, row) is True
""",
    },
    {
        "task_id": "EF-PY-010",
        "title": "Regex NFA State Machine Engine",
        "language": "python",
        "difficulty": "hard",
        "category": "algorithmic",
        "tags": ["regex", "automata", "nfa", "compiler", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["subprocess", "socket", "ctypes", "re"],
            "max_cyclomatic_complexity": 25,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Regex NFA State Machine Engine

Implement a linear-time Regular Expression pattern matching engine based on Thompson's Non-deterministic Finite Automaton (NFA) construction.

## Syntax Features Supported

- **Literal characters**: e.g. `a`, `b`, `1`
- **Wildcard character**: `.` matches any single character
- **Concatenation**: e.g. `ab`
- **Alternation**: `|` (e.g. `cat|dog`)
- **Kleene Star**: `*` (zero or more occurrences)
- **Plus Operator**: `+` (one or more occurrences)
- **Optional Operator**: `?` (zero or one occurrence)
- **Grouping**: `( ... )` to override operator precedence

## Requirements

Implement the class `RegexNFA`:

- `compile(pattern: str) -> RegexNFA`:
  Parses infix regex pattern into postfix using Dijkstra's Shunting-Yard algorithm (with explicit concatenation insertion), and compiles it into an NFA.
- `matches(self, text: str) -> bool`:
  Simulates NFA execution over `text` using epsilon-closure transitions. Returns `True` if the full text matches the pattern, `False` otherwise.
- `find_all(self, text: str) -> list[str]`:
  Finds all non-overlapping matching substrings within `text`.
""",
        "starter_code": """class RegexNFA:
    def __init__(self) -> None:
        \"\"\"Initialize Regex NFA.\"\"\"
        pass

    @classmethod
    def compile(cls, pattern: str) -> 'RegexNFA':
        \"\"\"Compile regex pattern into Thompson NFA.\"\"\"
        pass

    def matches(self, text: str) -> bool:
        \"\"\"Check if entire text matches regex pattern.\"\"\"
        pass

    def find_all(self, text: str) -> list[str]:
        \"\"\"Find non-overlapping matching substrings.\"\"\"
        pass
""",
        "canonical_solution": """class _State:
    def __init__(self, c: str | None = None) -> None:
        self.c = c  # None for epsilon transition
        self.out: list['_State'] = []


class RegexNFA:
    def __init__(self, start: _State, accept: _State) -> None:
        self.start = start
        self.accept = accept

    @classmethod
    def compile(cls, pattern: str) -> 'RegexNFA':
        # 1. Insert explicit concatenation operator '.'
        formatted: list[str] = []
        for i in range(len(pattern)):
            c1 = pattern[i]
            formatted.append(c1)
            if i + 1 < len(pattern):
                c2 = pattern[i + 1]
                if (c1.isalnum() or c1 in ".*+?)" ) and (c2.isalnum() or c2 in ".( "):
                    formatted.append("\\0")  # explicit concat token

        # 2. Infix to Postfix (Shunting Yard)
        precedence = {"|": 1, "\\0": 2, "*": 3, "+": 3, "?": 3}
        postfix: list[str] = []
        ops: list[str] = []

        for token in formatted:
            if token == "(":
                ops.append(token)
            elif token == ")":
                while ops and ops[-1] != "(":
                    postfix.append(ops.pop())
                if ops:
                    ops.pop()  # remove '('
            elif token in precedence:
                while ops and ops[-1] != "(" and precedence.get(ops[-1], 0) >= precedence[token]:
                    postfix.append(ops.pop())
                ops.append(token)
            else:
                postfix.append(token)

        while ops:
            postfix.append(ops.pop())

        # 3. Thompson NFA Construction from postfix
        stack: list[tuple[_State, _State]] = []

        for token in postfix:
            if token == "\\0":
                s2_start, s2_accept = stack.pop()
                s1_start, s1_accept = stack.pop()
                s1_accept.out.append(s2_start)
                stack.append((s1_start, s2_accept))
            elif token == "|":
                s2_start, s2_accept = stack.pop()
                s1_start, s1_accept = stack.pop()
                start = _State(None)
                accept = _State(None)
                start.out = [s1_start, s2_start]
                s1_accept.out.append(accept)
                s2_accept.out.append(accept)
                stack.append((start, accept))
            elif token == "*":
                s_start, s_accept = stack.pop()
                start = _State(None)
                accept = _State(None)
                start.out = [s_start, accept]
                s_accept.out = [s_start, accept]
                stack.append((start, accept))
            elif token == "+":
                s_start, s_accept = stack.pop()
                start = _State(None)
                accept = _State(None)
                start.out.append(s_start)
                s_accept.out = [s_start, accept]
                stack.append((start, accept))
            elif token == "?":
                s_start, s_accept = stack.pop()
                start = _State(None)
                accept = _State(None)
                start.out = [s_start, accept]
                s_accept.out.append(accept)
                stack.append((start, accept))
            else:
                # literal or wildcard '.'
                start = _State(token)
                accept = _State(None)
                start.out.append(accept)
                stack.append((start, accept))

        if not stack:
            # Empty pattern matches empty text
            s = _State(None)
            return cls(s, s)

        start, accept = stack.pop()
        return cls(start, accept)

    def _epsilon_closure(self, states: set[_State]) -> set[_State]:
        closure = set(states)
        queue = list(states)
        while queue:
            curr = queue.pop()
            if curr.c is None:
                for nxt in curr.out:
                    if nxt not in closure:
                        closure.add(nxt)
                        queue.append(nxt)
        return closure

    def matches(self, text: str) -> bool:
        curr_states = self._epsilon_closure({self.start})
        for char in text:
            next_states: set[_State] = set()
            for st in curr_states:
                if st.c == "." or st.c == char:
                    for nxt in st.out:
                        next_states.add(nxt)
            curr_states = self._epsilon_closure(next_states)
            if not curr_states:
                return False

        return self.accept in curr_states

    def find_all(self, text: str) -> list[str]:
        results: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            matched_len = 0
            for j in range(i + 1, n + 1):
                sub = text[i:j]
                if self.matches(sub):
                    matched_len = j - i
            if matched_len > 0:
                results.append(text[i: i + matched_len])
                i += matched_len
            else:
                i += 1
        return results
""",
        "visible_tests": """def test_regex_literals_and_alternation():
    nfa = RegexNFA.compile("cat|dog")
    assert nfa.matches("cat") is True
    assert nfa.matches("dog") is True
    assert nfa.matches("bat") is False


def test_regex_kleene_star_and_wildcard():
    nfa = RegexNFA.compile("a.*b")
    assert nfa.matches("ab") is True
    assert nfa.matches("axxxb") is True
    assert nfa.matches("a123b") is True
    assert nfa.matches("axxx") is False
""",
        "hidden_tests": """def test_regex_plus_and_optional():
    nfa = RegexNFA.compile("a+b?")
    assert nfa.matches("a") is True
    assert nfa.matches("ab") is True
    assert nfa.matches("aaaab") is True
    assert nfa.matches("b") is False
    assert nfa.matches("") is False


def test_regex_grouping_precedence():
    nfa = RegexNFA.compile("(ab|cd)+e")
    assert nfa.matches("abe") is True
    assert nfa.matches("cde") is True
    assert nfa.matches("abcdabe") is True
    assert nfa.matches("e") is False


def test_regex_find_all():
    nfa = RegexNFA.compile("ab*")
    matches = nfa.find_all("abb c abb d a")
    assert matches == ["abb", "abb", "a"]


def test_empty_string_matching():
    nfa = RegexNFA.compile("a*")
    assert nfa.matches("") is True
    assert nfa.matches("aaa") is True


def test_no_catastrophic_backtracking():
    # Famous regex trap that causes exponential time in backtracking engines
    nfa = RegexNFA.compile("(a|aa)*b")
    assert nfa.matches("a" * 30 + "c") is False
    assert nfa.matches("a" * 30 + "b") is True


def test_wildcard_dot_only():
    nfa = RegexNFA.compile("...")
    assert nfa.matches("xyz") is True
    assert nfa.matches("123") is True
    assert nfa.matches("ab") is False
    assert nfa.matches("abcd") is False
""",
    },
]
