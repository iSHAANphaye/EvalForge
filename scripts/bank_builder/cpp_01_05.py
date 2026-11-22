"""Tasks EF-CPP-001 through EF-CPP-005."""

TASKS = [
    {
        "task_id": "EF-CPP-001",
        "title": "Lock-Free SPSC Ring Buffer in C++20",
        "language": "cpp",
        "difficulty": "hard",
        "category": "concurrency",
        "tags": ["lock-free", "spsc", "concurrency", "atomics", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Lock-Free SPSC Ring Buffer in C++20

Implement a high-throughput, cache-conscious, lock-free Single-Producer Single-Consumer (SPSC) bounded circular ring buffer in C++20 using `std::atomic` with explicit memory order semantics (`std::memory_order_acquire` and `std::memory_order_release`).

## Requirements

Implement the template class:
```cpp
template <typename T, size_t Capacity>
class SpscRingBuffer;
```

### Methods:
- `bool push(const T& item)`:
  Inserts an element into the buffer. Returns `true` on success, or `false` if the buffer is full.
- `bool push(T&& item)`:
  Move-inserts an element. Returns `true` on success, or `false` if full.
- `bool pop(T& item)`:
  Extracts the oldest element into `item`. Returns `true` on success, or `false` if empty.
- `[[nodiscard]] bool empty() const noexcept`:
  Returns `true` if no elements are currently available to consume.
- `[[nodiscard]] bool full() const noexcept`:
  Returns `true` if the buffer has reached maximum capacity.
- `[[nodiscard]] size_t size() const noexcept`:
  Returns current number of elements in the buffer.
- `[[nodiscard]] constexpr size_t capacity() const noexcept`:
  Returns compile-time `Capacity`.

### Constraints:
- Must not use mutexes, spinlocks, or conditional variables.
- Must ensure lock-free progress for single producer and single consumer.
""",
        "starter_code": """#pragma once
#include <atomic>
#include <cstddef>
#include <utility>

template <typename T, size_t Capacity>
class SpscRingBuffer {
public:
    SpscRingBuffer() = default;

    bool push(const T& item);
    bool push(T&& item);
    bool pop(T& item);

    [[nodiscard]] bool empty() const noexcept;
    [[nodiscard]] bool full() const noexcept;
    [[nodiscard]] size_t size() const noexcept;
    [[nodiscard]] constexpr size_t capacity() const noexcept { return Capacity; }
};
""",
        "canonical_solution": """#pragma once
#include <atomic>
#include <cstddef>
#include <new>
#include <type_traits>
#include <utility>

template <typename T, size_t Capacity>
class SpscRingBuffer {
    static_assert(Capacity >= 1, "Capacity must be at least 1");

public:
    SpscRingBuffer() : head_(0), tail_(0) {}

    ~SpscRingBuffer() {
        T discard;
        while (pop(discard)) {}
    }

    bool push(const T& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t current_head = head_.load(std::memory_order_acquire);

        if ((current_tail - current_head) >= Capacity) {
            return false; // Full
        }

        new (&storage_[current_tail % BufferSize]) T(item);
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool push(T&& item) {
        const size_t current_tail = tail_.load(std::memory_order_relaxed);
        const size_t current_head = head_.load(std::memory_order_acquire);

        if ((current_tail - current_head) >= Capacity) {
            return false; // Full
        }

        new (&storage_[current_tail % BufferSize]) T(std::move(item));
        tail_.store(current_tail + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& item) {
        const size_t current_head = head_.load(std::memory_order_relaxed);
        const size_t current_tail = tail_.load(std::memory_order_acquire);

        if (current_head == current_tail) {
            return false; // Empty
        }

        auto* ptr = reinterpret_cast<T*>(&storage_[current_head % BufferSize]);
        item = std::move(*ptr);
        ptr->~T();

        head_.store(current_head + 1, std::memory_order_release);
        return true;
    }

    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_acquire) == tail_.load(std::memory_order_acquire);
    }

    [[nodiscard]] bool full() const noexcept {
        return size() >= Capacity;
    }

    [[nodiscard]] size_t size() const noexcept {
        const size_t h = head_.load(std::memory_order_acquire);
        const size_t t = tail_.load(std::memory_order_acquire);
        return (t >= h) ? (t - h) : 0;
    }

    [[nodiscard]] constexpr size_t capacity() const noexcept {
        return Capacity;
    }

private:
    static constexpr size_t BufferSize = Capacity + 1;
    alignas(alignof(T)) std::byte storage_[BufferSize][sizeof(T)];

    alignas(64) std::atomic<size_t> tail_{0};
    alignas(64) std::atomic<size_t> head_{0};
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(SpscRingBufferTest, BasicPushPop) {
    SpscRingBuffer<int, 4> buffer;
    EXPECT_TRUE(buffer.empty());
    EXPECT_EQ(buffer.size(), 0);

    EXPECT_TRUE(buffer.push(10));
    EXPECT_TRUE(buffer.push(20));
    EXPECT_FALSE(buffer.empty());
    EXPECT_EQ(buffer.size(), 2);

    int val = 0;
    EXPECT_TRUE(buffer.pop(val));
    EXPECT_EQ(val, 10);
    EXPECT_TRUE(buffer.pop(val));
    EXPECT_EQ(val, 20);
    EXPECT_TRUE(buffer.empty());
}

TEST(SpscRingBufferTest, CapacityBoundary) {
    SpscRingBuffer<int, 2> buffer;
    EXPECT_TRUE(buffer.push(1));
    EXPECT_TRUE(buffer.push(2));
    EXPECT_TRUE(buffer.full());
    EXPECT_FALSE(buffer.push(3)); // Buffer full
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <thread>
#include <vector>
#include <string>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(SpscRingBufferTest, MoveSemantics) {
    SpscRingBuffer<std::string, 3> buffer;
    std::string s = "move_me_please";
    EXPECT_TRUE(buffer.push(std::move(s)));
    std::string out;
    EXPECT_TRUE(buffer.pop(out));
    EXPECT_EQ(out, "move_me_please");
}

TEST(SpscRingBufferTest, EmptyPopFailure) {
    SpscRingBuffer<int, 5> buffer;
    int x = -1;
    EXPECT_FALSE(buffer.pop(x));
    EXPECT_EQ(x, -1);
}

TEST(SpscRingBufferTest, WrapAroundStress) {
    SpscRingBuffer<int, 3> buffer;
    for (int i = 0; i < 500; ++i) {
        EXPECT_TRUE(buffer.push(i));
        int val = -1;
        EXPECT_TRUE(buffer.pop(val));
        EXPECT_EQ(val, i);
    }
    EXPECT_TRUE(buffer.empty());
}

TEST(SpscRingBufferTest, SingleItemBuffer) {
    SpscRingBuffer<int, 1> buffer;
    EXPECT_TRUE(buffer.push(42));
    EXPECT_TRUE(buffer.full());
    EXPECT_FALSE(buffer.push(99));
    int out = 0;
    EXPECT_TRUE(buffer.pop(out));
    EXPECT_EQ(out, 42);
    EXPECT_TRUE(buffer.empty());
}

TEST(SpscRingBufferTest, MultiThreadedSpsc) {
    constexpr int TotalItems = 20000;
    SpscRingBuffer<int, 128> buffer;

    std::thread producer([&]() {
        for (int i = 0; i < TotalItems; ++i) {
            while (!buffer.push(i)) {
                std::this_thread::yield();
            }
        }
    });

    std::vector<int> consumed;
    consumed.reserve(TotalItems);

    std::thread consumer([&]() {
        for (int i = 0; i < TotalItems; ++i) {
            int val = 0;
            while (!buffer.pop(val)) {
                std::this_thread::yield();
            }
            consumed.push_back(val);
        }
    });

    producer.join();
    consumer.join();

    EXPECT_EQ(consumed.size(), TotalItems);
    for (int i = 0; i < TotalItems; ++i) {
        EXPECT_EQ(consumed[i], i);
    }
}

TEST(SpscRingBufferTest, AccurateCapacityReport) {
    SpscRingBuffer<double, 64> buffer;
    EXPECT_EQ(buffer.capacity(), 64);
}
""",
    },
    {
        "task_id": "EF-CPP-002",
        "title": "Fixed-Size Arena Bump Memory Allocator with 64-Bit Alignment",
        "language": "cpp",
        "difficulty": "medium",
        "category": "systems",
        "tags": ["memory-allocator", "arena", "systems", "performance", "cpp20"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Fixed-Size Arena Bump Memory Allocator with 64-Bit Alignment

Implement a fast linear/arena (bump) memory allocator in C++20 with custom alignment support (default 8-byte / 64-bit alignment) and RAII object construction.

## Requirements

Implement the class `ArenaAllocator`:

- `explicit ArenaAllocator(size_t total_bytes)`:
  Allocates a contiguous heap buffer of `total_bytes`.
- `void* allocate(size_t bytes, size_t alignment = alignof(std::max_align_t))`:
  Bumps internal allocation pointer forward, respecting `alignment` padding (where `alignment` is a power of two).
  Returns a properly aligned pointer to allocated space, or `nullptr` if insufficient contiguous memory remains.
- `template <typename T, typename... Args> T* create(Args&&... args)`:
  Allocates aligned memory for `sizeof(T)` with `alignof(T)` and constructs object using in-place placement-new. Returns `T*` or `nullptr`.
- `void reset() noexcept`:
  Resets the allocation offset to 0, recycling all previously allocated memory in $O(1)$ time without calling individual object destructors.
- `[[nodiscard]] size_t used_bytes() const noexcept`:
  Returns total bytes used (including alignment padding).
- `[[nodiscard]] size_t total_capacity() const noexcept`:
  Returns total size of the arena.
""",
        "starter_code": """#pragma once
#include <cstddef>
#include <new>
#include <utility>

class ArenaAllocator {
public:
    explicit ArenaAllocator(size_t total_bytes);
    ~ArenaAllocator();

    void* allocate(size_t bytes, size_t alignment = alignof(std::max_align_t));

    template <typename T, typename... Args>
    T* create(Args&&... args);

    void reset() noexcept;

    [[nodiscard]] size_t used_bytes() const noexcept;
    [[nodiscard]] size_t total_capacity() const noexcept;
};
""",
        "canonical_solution": """#pragma once
#include <cstddef>
#include <cstdint>
#include <new>
#include <utility>

class ArenaAllocator {
public:
    explicit ArenaAllocator(size_t total_bytes)
        : capacity_(total_bytes), offset_(0) {
        buffer_ = new std::byte[total_bytes];
    }

    ~ArenaAllocator() {
        delete[] buffer_;
    }

    ArenaAllocator(const ArenaAllocator&) = delete;
    ArenaAllocator& operator=(const ArenaAllocator&) = delete;

    ArenaAllocator(ArenaAllocator&& other) noexcept
        : buffer_(other.buffer_), capacity_(other.capacity_), offset_(other.offset_) {
        other.buffer_ = nullptr;
        other.capacity_ = 0;
        other.offset_ = 0;
    }

    ArenaAllocator& operator=(ArenaAllocator&& other) noexcept {
        if (this != &other) {
            delete[] buffer_;
            buffer_ = other.buffer_;
            capacity_ = other.capacity_;
            offset_ = other.offset_;
            other.buffer_ = nullptr;
            other.capacity_ = 0;
            other.offset_ = 0;
        }
        return *this;
    }

    void* allocate(size_t bytes, size_t alignment = alignof(std::max_align_t)) {
        if (bytes == 0 || buffer_ == nullptr) {
            return nullptr;
        }

        uintptr_t current_addr = reinterpret_cast<uintptr_t>(buffer_ + offset_);
        uintptr_t aligned_addr = (current_addr + (alignment - 1)) & ~(alignment - 1);
        size_t padding = aligned_addr - current_addr;

        if (offset_ + padding + bytes > capacity_) {
            return nullptr; // Out of memory
        }

        offset_ += padding + bytes;
        return reinterpret_cast<void*>(aligned_addr);
    }

    template <typename T, typename... Args>
    T* create(Args&&... args) {
        void* mem = allocate(sizeof(T), alignof(T));
        if (!mem) {
            return nullptr;
        }
        return ::new (mem) T(std::forward<Args>(args)...);
    }

    void reset() noexcept {
        offset_ = 0;
    }

    [[nodiscard]] size_t used_bytes() const noexcept {
        return offset_;
    }

    [[nodiscard]] size_t total_capacity() const noexcept {
        return capacity_;
    }

private:
    std::byte* buffer_{nullptr};
    size_t capacity_{0};
    size_t offset_{0};
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(ArenaAllocatorTest, BasicAllocation) {
    ArenaAllocator arena(1024);
    EXPECT_EQ(arena.total_capacity(), 1024);
    EXPECT_EQ(arena.used_bytes(), 0);

    void* p1 = arena.allocate(64, 8);
    EXPECT_NE(p1, nullptr);
    EXPECT_EQ(reinterpret_cast<uintptr_t>(p1) % 8, 0);

    void* p2 = arena.allocate(128, 16);
    EXPECT_NE(p2, nullptr);
    EXPECT_EQ(reinterpret_cast<uintptr_t>(p2) % 16, 0);
}

TEST(ArenaAllocatorTest, ObjectCreation) {
    struct Point {
        int x;
        int y;
        Point(int x_, int y_) : x(x_), y(y_) {}
    };

    ArenaAllocator arena(256);
    Point* pt = arena.create<Point>(10, 20);
    ASSERT_NE(pt, nullptr);
    EXPECT_EQ(pt->x, 10);
    EXPECT_EQ(pt->y, 20);
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(ArenaAllocatorTest, OutOfMemoryReturnsNull) {
    ArenaAllocator arena(100);
    void* p1 = arena.allocate(80);
    EXPECT_NE(p1, nullptr);
    void* p2 = arena.allocate(40);
    EXPECT_EQ(p2, nullptr); // Over capacity
}

TEST(ArenaAllocatorTest, ResetRecyclesMemory) {
    ArenaAllocator arena(200);
    void* p1 = arena.allocate(150);
    EXPECT_NE(p1, nullptr);
    EXPECT_GT(arena.used_bytes(), 0);

    arena.reset();
    EXPECT_EQ(arena.used_bytes(), 0);

    void* p2 = arena.allocate(150);
    EXPECT_NE(p2, nullptr);
}

TEST(ArenaAllocatorTest, CustomHighAlignment64) {
    ArenaAllocator arena(4096);
    void* p = arena.allocate(128, 64);
    ASSERT_NE(p, nullptr);
    EXPECT_EQ(reinterpret_cast<uintptr_t>(p) % 64, 0);
}

TEST(ArenaAllocatorTest, ZeroBytesAllocation) {
    ArenaAllocator arena(128);
    EXPECT_EQ(arena.allocate(0), nullptr);
}

TEST(ArenaAllocatorTest, ManySmallAllocationsPacking) {
    ArenaAllocator arena(10000);
    for (int i = 0; i < 500; ++i) {
        void* ptr = arena.allocate(8, 8);
        ASSERT_NE(ptr, nullptr);
    }
    EXPECT_LE(arena.used_bytes(), 10000);
}

TEST(ArenaAllocatorTest, MoveConstructor) {
    ArenaAllocator a1(512);
    void* p1 = a1.allocate(64);
    EXPECT_NE(p1, nullptr);

    ArenaAllocator a2(std::move(a1));
    EXPECT_EQ(a2.total_capacity(), 512);
    EXPECT_GT(a2.used_bytes(), 0);
}
""",
    },
    {
        "task_id": "EF-CPP-003",
        "title": "Vectorized Float Dot Product with Manual Unrolling",
        "language": "cpp",
        "difficulty": "medium",
        "category": "algorithmic",
        "tags": ["simd", "vectorization", "unrolling", "hpc", "algorithms"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Vectorized Float Dot Product with Manual Unrolling

Implement an optimized vector dot product computation in C++20 for single-precision floats and double-precision floats using 4-way loop unrolling to maximize instruction-level parallelism.

## Requirements

Implement the functions:
```cpp
inline float dot_product(std::span<const float> a, std::span<const float> b);
inline double dot_product_double(std::span<const double> a, std::span<const double> b);
```

### Constraints:
- If vectors differ in length, throws `std::invalid_argument("Vector length mismatch")`.
- If vectors are empty, returns `0.0`.
- Must compute $\\sum_{i=0}^{N-1} a[i] \\times b[i]$.
- Uses multiple independent accumulator variables (`sum0`, `sum1`, `sum2`, `sum3`) to break loop-carried dependency chains and facilitate SIMD vectorization.
""",
        "starter_code": """#pragma once
#include <span>
#include <stdexcept>

inline float dot_product(std::span<const float> a, std::span<const float> b);
inline double dot_product_double(std::span<const double> a, std::span<const double> b);
""",
        "canonical_solution": """#pragma once
#include <span>
#include <stdexcept>

inline float dot_product(std::span<const float> a, std::span<const float> b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Vector length mismatch");
    }

    const size_t n = a.size();
    float s0 = 0.0f;
    float s1 = 0.0f;
    float s2 = 0.0f;
    float s3 = 0.0f;

    size_t i = 0;
    for (; i + 4 <= n; i += 4) {
        s0 += a[i + 0] * b[i + 0];
        s1 += a[i + 1] * b[i + 1];
        s2 += a[i + 2] * b[i + 2];
        s3 += a[i + 3] * b[i + 3];
    }

    float total = (s0 + s1) + (s2 + s3);

    for (; i < n; ++i) {
        total += a[i] * b[i];
    }

    return total;
}

inline double dot_product_double(std::span<const double> a, std::span<const double> b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Vector length mismatch");
    }

    const size_t n = a.size();
    double s0 = 0.0;
    double s1 = 0.0;
    double s2 = 0.0;
    double s3 = 0.0;

    size_t i = 0;
    for (; i + 4 <= n; i += 4) {
        s0 += a[i + 0] * b[i + 0];
        s1 += a[i + 1] * b[i + 1];
        s2 += a[i + 2] * b[i + 2];
        s3 += a[i + 3] * b[i + 3];
    }

    double total = (s0 + s1) + (s2 + s3);

    for (; i < n; ++i) {
        total += a[i] * b[i];
    }

    return total;
}
""",
        "visible_tests": """#include <gtest/gtest.h>
#include <vector>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(DotProductTest, SimpleVectors) {
    std::vector<float> a = {1.0f, 2.0f, 3.0f};
    std::vector<float> b = {4.0f, 5.0f, 6.0f};
    // 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32
    EXPECT_FLOAT_EQ(dot_product(a, b), 32.0f);
}

TEST(DotProductTest, OrthogonalVectors) {
    std::vector<float> a = {1.0f, 0.0f, 0.0f};
    std::vector<float> b = {0.0f, 1.0f, 0.0f};
    EXPECT_FLOAT_EQ(dot_product(a, b), 0.0f);
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <vector>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(DotProductTest, EmptyVectorsReturnZero) {
    std::vector<float> empty_a;
    std::vector<float> empty_b;
    EXPECT_FLOAT_EQ(dot_product(empty_a, empty_b), 0.0f);
}

TEST(DotProductTest, MismatchedLengthThrows) {
    std::vector<float> a = {1.0f, 2.0f};
    std::vector<float> b = {1.0f, 2.0f, 3.0f};
    EXPECT_THROW(dot_product(a, b), std::invalid_argument);
}

TEST(DotProductTest, NegativeNumbers) {
    std::vector<float> a = {-2.0f, 3.0f, -4.0f};
    std::vector<float> b = {3.0f, -2.0f, -1.0f};
    // (-2*3) + (3*-2) + (-4*-1) = -6 - 6 + 4 = -8
    EXPECT_FLOAT_EQ(dot_product(a, b), -8.0f);
}

TEST(DotProductTest, UnalignedRemainderTail) {
    // Size 7: 4 unrolled items + 3 remainder items
    std::vector<float> a = {1.0f, 1.0f, 1.0f, 1.0f, 2.0f, 2.0f, 2.0f};
    std::vector<float> b = {2.0f, 2.0f, 2.0f, 2.0f, 3.0f, 3.0f, 3.0f};
    // 4*(1*2) + 3*(2*3) = 8 + 18 = 26
    EXPECT_FLOAT_EQ(dot_product(a, b), 26.0f);
}

TEST(DotProductTest, DoublePrecisionLargeScale) {
    constexpr size_t N = 10000;
    std::vector<double> a(N, 1.5);
    std::vector<double> b(N, 2.0);
    // Each product is 3.0, total = 30000.0
    EXPECT_DOUBLE_EQ(dot_product_double(a, b), 30000.0);
}

TEST(DotProductTest, SingleElement) {
    std::vector<float> a = {5.5f};
    std::vector<float> b = {2.0f};
    EXPECT_FLOAT_EQ(dot_product(a, b), 11.0f);
}
""",
    },
    {
        "task_id": "EF-CPP-004",
        "title": "Thread-Safe Connection Pool with RAII Leased Guard",
        "language": "cpp",
        "difficulty": "hard",
        "category": "concurrency",
        "tags": ["raii", "connection-pool", "concurrency", "thread-safety", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Thread-Safe Connection Pool with RAII Leased Guard

Implement a thread-safe connection pool in C++20 with an RAII `Lease` guard that automatically returns borrowed connections to the pool upon destruction or scope exit.

## Requirements

### `MockConnection`
- `explicit MockConnection(int id)`
- `[[nodiscard]] int id() const noexcept`
- `[[nodiscard]] bool is_valid() const noexcept`

### `ConnectionPool`
- `ConnectionPool(size_t pool_size, std::chrono::milliseconds timeout)`:
  Preallocates `pool_size` connections with IDs `0` through `pool_size - 1`.
- `Lease acquire()`:
  Blocks waiting for an available connection up to `timeout`.
  Throws `std::runtime_error("Pool acquisition timeout")` if timeout expires before a connection is leased.
- `[[nodiscard]] size_t available_count() const noexcept`:
  Returns number of idle connections currently in the pool.
- `[[nodiscard]] size_t capacity() const noexcept`:
  Returns total connection pool size.

### `ConnectionPool::Lease` (RAII Guard)
- Move-only RAII guard wrapping borrowed `MockConnection*`.
- When destructed, automatically releases connection back to the parent pool.
- `MockConnection* operator->()`
- `MockConnection& operator*()`
""",
        "starter_code": """#pragma once
#include <chrono>
#include <memory>
#include <stdexcept>

class MockConnection {
public:
    explicit MockConnection(int id) : id_(id) {}
    int id() const noexcept { return id_; }
    bool is_valid() const noexcept { return true; }
private:
    int id_;
};

class ConnectionPool {
public:
    class Lease;

    ConnectionPool(size_t pool_size, std::chrono::milliseconds timeout);
    ~ConnectionPool();

    Lease acquire();
    size_t available_count() const noexcept;
    size_t capacity() const noexcept;
};
""",
        "canonical_solution": """#pragma once
#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <vector>

class MockConnection {
public:
    explicit MockConnection(int id) : id_(id) {}
    [[nodiscard]] int id() const noexcept { return id_; }
    [[nodiscard]] bool is_valid() const noexcept { return true; }
private:
    int id_;
};

class ConnectionPool {
public:
    class Lease {
    public:
        Lease() : pool_(nullptr), conn_(nullptr) {}

        Lease(ConnectionPool* pool, MockConnection* conn)
            : pool_(pool), conn_(conn) {}

        ~Lease() {
            release();
        }

        Lease(const Lease&) = delete;
        Lease& operator=(const Lease&) = delete;

        Lease(Lease&& other) noexcept
            : pool_(other.pool_), conn_(other.conn_) {
            other.pool_ = nullptr;
            other.conn_ = nullptr;
        }

        Lease& operator=(Lease&& other) noexcept {
            if (this != &other) {
                release();
                pool_ = other.pool_;
                conn_ = other.conn_;
                other.pool_ = nullptr;
                other.conn_ = nullptr;
            }
            return *this;
        }

        MockConnection* operator->() const noexcept { return conn_; }
        MockConnection& operator*() const noexcept { return *conn_; }
        MockConnection* get() const noexcept { return conn_; }
        explicit operator bool() const noexcept { return conn_ != nullptr; }

    private:
        void release() {
            if (pool_ && conn_) {
                pool_->return_connection(conn_);
                pool_ = nullptr;
                conn_ = nullptr;
            }
        }

        ConnectionPool* pool_{nullptr};
        MockConnection* conn_{nullptr};
    };

    ConnectionPool(size_t pool_size, std::chrono::milliseconds timeout)
        : capacity_(pool_size), timeout_(timeout) {
        if (pool_size == 0) {
            throw std::invalid_argument("pool_size must be >= 1");
        }
        for (size_t i = 0; i < pool_size; ++i) {
            connections_.push_back(std::make_unique<MockConnection>(static_cast<int>(i)));
            available_.push_back(connections_.back().get());
        }
    }

    ~ConnectionPool() = default;

    Lease acquire() {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!cv_.wait_for(lock, timeout_, [this]() { return !available_.empty(); })) {
            throw std::runtime_error("Pool acquisition timeout");
        }
        MockConnection* conn = available_.back();
        available_.pop_back();
        return Lease(this, conn);
    }

    [[nodiscard]] size_t available_count() const noexcept {
        std::lock_guard<std::mutex> lock(mutex_);
        return available_.size();
    }

    [[nodiscard]] size_t capacity() const noexcept {
        return capacity_;
    }

private:
    void return_connection(MockConnection* conn) {
        std::lock_guard<std::mutex> lock(mutex_);
        available_.push_back(conn);
        cv_.notify_one();
    }

    size_t capacity_;
    std::chrono::milliseconds timeout_;
    mutable std::mutex mutex_;
    std::condition_variable cv_;
    std::vector<std::unique_ptr<MockConnection>> connections_;
    std::vector<MockConnection*> available_;
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(ConnectionPoolTest, BasicAcquireAndRelease) {
    ConnectionPool pool(2, std::chrono::milliseconds(500));
    EXPECT_EQ(pool.available_count(), 2);

    {
        auto lease = pool.acquire();
        EXPECT_EQ(pool.available_count(), 1);
        EXPECT_TRUE(lease->is_valid());
    } // Lease goes out of scope, returning connection

    EXPECT_EQ(pool.available_count(), 2);
}

TEST(ConnectionPoolTest, ExhaustionAndTimeout) {
    ConnectionPool pool(1, std::chrono::milliseconds(50));
    auto lease1 = pool.acquire();
    EXPECT_EQ(pool.available_count(), 0);

    // Second acquire should timeout and throw
    EXPECT_THROW(pool.acquire(), std::runtime_error);
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <thread>
#include <vector>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(ConnectionPoolTest, MoveSemanticsOfLease) {
    ConnectionPool pool(2, std::chrono::milliseconds(200));
    auto lease1 = pool.acquire();
    EXPECT_EQ(pool.available_count(), 1);

    auto lease2 = std::move(lease1);
    EXPECT_EQ(pool.available_count(), 1);
    EXPECT_TRUE(lease2->is_valid());
}

TEST(ConnectionPoolTest, MultiThreadedContention) {
    constexpr size_t PoolSize = 4;
    ConnectionPool pool(PoolSize, std::chrono::milliseconds(1000));
    std::vector<std::thread> workers;

    for (int i = 0; i < 16; ++i) {
        workers.emplace_back([&pool]() {
            for (int j = 0; j < 20; ++j) {
                auto lease = pool.acquire();
                EXPECT_TRUE(lease->is_valid());
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
        });
    }

    for (auto& w : workers) {
        w.join();
    }

    EXPECT_EQ(pool.available_count(), PoolSize);
}

TEST(ConnectionPoolTest, ZeroPoolSizeThrows) {
    EXPECT_THROW(ConnectionPool(0, std::chrono::milliseconds(100)), std::invalid_argument);
}

TEST(ConnectionPoolTest, PointerAndDereferenceOperators) {
    ConnectionPool pool(1, std::chrono::milliseconds(100));
    auto lease = pool.acquire();
    EXPECT_EQ((*lease).id(), 0);
    EXPECT_EQ(lease->id(), 0);
}

TEST(ConnectionPoolTest, FullCapacityDrainAndRefill) {
    ConnectionPool pool(5, std::chrono::milliseconds(100));
    std::vector<ConnectionPool::Lease> leases;
    for (int i = 0; i < 5; ++i) {
        leases.push_back(pool.acquire());
    }
    EXPECT_EQ(pool.available_count(), 0);
    leases.clear(); // Return all
    EXPECT_EQ(pool.available_count(), 5);
}

TEST(ConnectionPoolTest, CapacityCheck) {
    ConnectionPool pool(10, std::chrono::milliseconds(100));
    EXPECT_EQ(pool.capacity(), 10);
}
""",
    },
    {
        "task_id": "EF-CPP-005",
        "title": "Counting Bloom Filter with Multiple Hashes and Deletion",
        "language": "cpp",
        "difficulty": "medium",
        "category": "data_structures",
        "tags": ["bloom-filter", "counting-bloom-filter", "data_structures", "hashing"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Counting Bloom Filter with Multiple Hashes and Deletion

Implement an 8-bit Counting Bloom Filter in C++20 supporting element insertion, membership testing, and element deletion using Kirsch-Mitzenmacher double hashing.

## Requirements

Implement the class `CountingBloomFilter`:

- `CountingBloomFilter(size_t num_buckets, size_t num_hashes)`:
  Initializes filter with `num_buckets` 8-bit saturating counter buckets and `num_hashes` independent hash projections.
- `void insert(std::string_view key)`:
  Hashes `key` across all $k$ hash locations and increments their 8-bit counters (saturating at 255 without overflowing).
- `bool remove(std::string_view key)`:
  If `contains(key)` is `true`, decrements all $k$ counters (without underflowing below 0) and returns `true`.
  If `contains(key)` is `false`, leaves counters unchanged and returns `false`.
- `[[nodiscard]] bool contains(std::string_view key) const noexcept`:
  Returns `true` if all $k$ counter buckets for `key` are strictly greater than 0.
- `void clear() noexcept`:
  Resets all bucket counters to 0.
- Double Hashing:
  Use Kirsch-Mitzenmacher technique: $h_i(x) = (h_1(x) + i \\times h_2(x)) \\pmod{\\text{num\\_buckets}}$ where $h_1$ is FNV-1a and $h_2$ is Murmur-style / std::hash.
""",
        "starter_code": """#pragma once
#include <cstddef>
#include <string_view>

class CountingBloomFilter {
public:
    CountingBloomFilter(size_t num_buckets, size_t num_hashes);

    void insert(std::string_view key);
    bool remove(std::string_view key);
    [[nodiscard]] bool contains(std::string_view key) const noexcept;
    void clear() noexcept;
};
""",
        "canonical_solution": """#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>
#include <string_view>
#include <vector>

class CountingBloomFilter {
public:
    CountingBloomFilter(size_t num_buckets, size_t num_hashes)
        : num_buckets_(num_buckets), num_hashes_(num_hashes), buckets_(num_buckets, 0) {
        if (num_buckets == 0 || num_hashes == 0) {
            num_buckets_ = 1;
            num_hashes_ = 1;
            buckets_.assign(1, 0);
        }
    }

    void insert(std::string_view key) {
        auto [h1, h2] = compute_hashes(key);
        for (size_t i = 0; i < num_hashes_; ++i) {
            size_t idx = (h1 + i * h2) % num_buckets_;
            if (buckets_[idx] < 255) {
                buckets_[idx]++;
            }
        }
    }

    bool remove(std::string_view key) {
        if (!contains(key)) {
            return false;
        }
        auto [h1, h2] = compute_hashes(key);
        for (size_t i = 0; i < num_hashes_; ++i) {
            size_t idx = (h1 + i * h2) % num_buckets_;
            if (buckets_[idx] > 0 && buckets_[idx] < 255) {
                buckets_[idx]--;
            }
        }
        return true;
    }

    [[nodiscard]] bool contains(std::string_view key) const noexcept {
        auto [h1, h2] = compute_hashes(key);
        for (size_t i = 0; i < num_hashes_; ++i) {
            size_t idx = (h1 + i * h2) % num_buckets_;
            if (buckets_[idx] == 0) {
                return false;
            }
        }
        return true;
    }

    void clear() noexcept {
        std::fill(buckets_.begin(), buckets_.end(), 0);
    }

private:
    std::pair<size_t, size_t> compute_hashes(std::string_view key) const noexcept {
        // FNV-1a 64-bit hash
        uint64_t fnv = 14695981039346656037ULL;
        for (char c : key) {
            fnv ^= static_cast<uint8_t>(c);
            fnv *= 1099511628211ULL;
        }

        // Secondary hash via std::hash
        size_t h2 = std::hash<std::string_view>{}(key);
        if (h2 == 0) h2 = 1; // ensure non-zero step

        return {static_cast<size_t>(fnv), h2};
    }

    size_t num_buckets_;
    size_t num_hashes_;
    std::vector<uint8_t> buckets_;
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(CountingBloomFilterTest, BasicInsertAndContains) {
    CountingBloomFilter cbf(1000, 4);
    EXPECT_FALSE(cbf.contains("apple"));

    cbf.insert("apple");
    EXPECT_TRUE(cbf.contains("apple"));
    EXPECT_FALSE(cbf.contains("banana"));
}

TEST(CountingBloomFilterTest, DeletionSupport) {
    CountingBloomFilter cbf(1000, 4);
    cbf.insert("cherry");
    EXPECT_TRUE(cbf.contains("cherry"));

    EXPECT_TRUE(cbf.remove("cherry"));
    EXPECT_FALSE(cbf.contains("cherry"));
    EXPECT_FALSE(cbf.remove("cherry")); // Already deleted
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <string>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(CountingBloomFilterTest, MultipleInsertionsAndDeletions) {
    CountingBloomFilter cbf(500, 3);
    cbf.insert("key");
    cbf.insert("key");
    EXPECT_TRUE(cbf.contains("key"));

    EXPECT_TRUE(cbf.remove("key"));
    // Still present because inserted twice
    EXPECT_TRUE(cbf.contains("key"));

    EXPECT_TRUE(cbf.remove("key"));
    EXPECT_FALSE(cbf.contains("key"));
}

TEST(CountingBloomFilterTest, ClearResetsAll) {
    CountingBloomFilter cbf(500, 4);
    cbf.insert("alpha");
    cbf.insert("beta");
    cbf.clear();
    EXPECT_FALSE(cbf.contains("alpha"));
    EXPECT_FALSE(cbf.contains("beta"));
}

TEST(CountingBloomFilterTest, NonExistentDeleteReturnsFalse) {
    CountingBloomFilter cbf(500, 3);
    EXPECT_FALSE(cbf.remove("ghost_key"));
}

TEST(CountingBloomFilterTest, ScaleDatasetInsertion) {
    CountingBloomFilter cbf(20000, 5);
    for (int i = 0; i < 1000; ++i) {
        cbf.insert("item_" + std::to_string(i));
    }
    for (int i = 0; i < 1000; ++i) {
        EXPECT_TRUE(cbf.contains("item_" + std::to_string(i)));
    }
}

TEST(CountingBloomFilterTest, EmptyStringKey) {
    CountingBloomFilter cbf(100, 3);
    cbf.insert("");
    EXPECT_TRUE(cbf.contains(""));
    EXPECT_TRUE(cbf.remove(""));
    EXPECT_FALSE(cbf.contains(""));
}

TEST(CountingBloomFilterTest, ZeroBucketsFallback) {
    CountingBloomFilter cbf(0, 0);
    cbf.insert("test");
    EXPECT_TRUE(cbf.contains("test"));
}
""",
    },
]
