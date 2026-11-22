"""Tasks EF-CPP-006 through EF-CPP-010."""

TASKS = [
    {
        "task_id": "EF-CPP-006",
        "title": "C++20 Coroutine Range Generator",
        "language": "cpp",
        "difficulty": "hard",
        "category": "systems",
        "tags": ["coroutines", "generator", "cpp20", "lazy-evaluation", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# C++20 Coroutine Range Generator

Implement a generic C++20 coroutine-based `Generator<T>` type supporting `co_yield` for lazy sequence evaluation, standard range/iterator protocol, and clean RAII lifecycle cleanup.

## Requirements

Implement the template class:
```cpp
template <typename T>
class Generator;
```

### Components:
- `struct promise_type`:
  - `Generator get_return_object() noexcept`
  - `std::suspend_always initial_suspend() noexcept`
  - `std::suspend_always final_suspend() noexcept`
  - `std::suspend_always yield_value(T value) noexcept`
  - `void return_void() noexcept`
  - `void unhandled_exception()`
- `struct iterator`:
  - Input iterator supporting `operator*()`, `operator++()`, and `operator!=(const iterator&)`.
- Methods:
  - `iterator begin()`: Resumes coroutine to produce first item.
  - `iterator end() noexcept`: Sentinel.
  - Move-constructible and move-assignable; non-copyable.
  - Destructor destroys underlying `std::coroutine_handle` safely.

### Helper Functions:
- `inline Generator<int> range(int start, int end, int step = 1)`
- `inline Generator<uint64_t> fibonacci(size_t count)`
""",
        "starter_code": """#pragma once
#include <coroutine>
#include <cstddef>
#include <cstdint>

template <typename T>
class Generator {
public:
    struct promise_type;
    // Define iterator and generator interface
};

inline Generator<int> range(int start, int end, int step = 1);
inline Generator<uint64_t> fibonacci(size_t count);
""",
        "canonical_solution": """#pragma once
#include <coroutine>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <utility>

template <typename T>
class Generator {
public:
    struct promise_type {
        T current_value{};
        std::exception_ptr exception{nullptr};

        Generator get_return_object() noexcept {
            return Generator{std::coroutine_handle<promise_type>::from_promise(*this)};
        }

        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }

        std::suspend_always yield_value(T value) noexcept {
            current_value = std::move(value);
            return {};
        }

        void return_void() noexcept {}

        void unhandled_exception() {
            exception = std::current_exception();
        }
    };

    using handle_type = std::coroutine_handle<promise_type>;

    explicit Generator(handle_type h) noexcept : coro_(h) {}

    ~Generator() {
        if (coro_) {
            coro_.destroy();
        }
    }

    Generator(const Generator&) = delete;
    Generator& operator=(const Generator&) = delete;

    Generator(Generator&& other) noexcept : coro_(other.coro_) {
        other.coro_ = nullptr;
    }

    Generator& operator=(Generator&& other) noexcept {
        if (this != &other) {
            if (coro_) {
                coro_.destroy();
            }
            coro_ = other.coro_;
            other.coro_ = nullptr;
        }
        return *this;
    }

    struct iterator {
        handle_type coro{nullptr};

        iterator& operator++() {
            if (coro && !coro.done()) {
                coro.resume();
                if (coro.promise().exception) {
                    std::rethrow_exception(coro.promise().exception);
                }
            }
            return *this;
        }

        const T& operator*() const noexcept {
            return coro.promise().current_value;
        }

        bool operator==(const iterator& other) const noexcept {
            bool done1 = !coro || coro.done();
            bool done2 = !other.coro || other.coro.done();
            return done1 == done2;
        }

        bool operator!=(const iterator& other) const noexcept {
            return !(*this == other);
        }
    };

    iterator begin() {
        if (coro_) {
            coro_.resume();
            if (coro_.promise().exception) {
                std::rethrow_exception(coro_.promise().exception);
            }
        }
        return iterator{coro_};
    }

    iterator end() noexcept {
        return iterator{nullptr};
    }

private:
    handle_type coro_{nullptr};
};

inline Generator<int> range(int start, int end, int step = 1) {
    if (step > 0) {
        for (int i = start; i < end; i += step) {
            co_yield i;
        }
    } else if (step < 0) {
        for (int i = start; i > end; i += step) {
            co_yield i;
        }
    }
}

inline Generator<uint64_t> fibonacci(size_t count) {
    uint64_t a = 0;
    uint64_t b = 1;
    for (size_t i = 0; i < count; ++i) {
        co_yield a;
        uint64_t next = a + b;
        a = b;
        b = next;
    }
}
""",
        "visible_tests": """#include <gtest/gtest.h>
#include <vector>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(GeneratorTest, RangeBasic) {
    std::vector<int> vals;
    for (int x : range(0, 5)) {
        vals.push_back(x);
    }
    EXPECT_EQ(vals, (std::vector<int>{0, 1, 2, 3, 4}));
}

TEST(GeneratorTest, FibonacciSequence) {
    std::vector<uint64_t> fibs;
    for (uint64_t n : fibonacci(6)) {
        fibs.push_back(n);
    }
    EXPECT_EQ(fibs, (std::vector<uint64_t>{0, 1, 1, 2, 3, 5}));
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <vector>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(GeneratorTest, EmptyRange) {
    std::vector<int> vals;
    for (int x : range(5, 5)) {
        vals.push_back(x);
    }
    EXPECT_TRUE(vals.empty());
}

TEST(GeneratorTest, NegativeStepRange) {
    std::vector<int> vals;
    for (int x : range(5, 0, -1)) {
        vals.push_back(x);
    }
    EXPECT_EQ(vals, (std::vector<int>{5, 4, 3, 2, 1}));
}

TEST(GeneratorTest, EarlyBreakLifecycle) {
    int count = 0;
    for (int x : range(0, 1000)) {
        if (++count == 3) {
            break;
        }
    }
    EXPECT_EQ(count, 3);
}

TEST(GeneratorTest, MoveConstructor) {
    auto gen1 = range(1, 4);
    auto gen2 = std::move(gen1);

    std::vector<int> res;
    for (int v : gen2) {
        res.push_back(v);
    }
    EXPECT_EQ(res, (std::vector<int>{1, 2, 3}));
}

TEST(GeneratorTest, LargeSequenceIteration) {
    size_t count = 0;
    for (int x : range(0, 10000)) {
        (void)x;
        count++;
    }
    EXPECT_EQ(count, 10000);
}

TEST(GeneratorTest, ZeroFibonacciCount) {
    std::vector<uint64_t> fibs;
    for (uint64_t n : fibonacci(0)) {
        fibs.push_back(n);
    }
    EXPECT_TRUE(fibs.empty());
}
""",
    },
    {
        "task_id": "EF-CPP-007",
        "title": "Concurrent Read-Write Spinlock Using Atomic Bit Flags",
        "language": "cpp",
        "difficulty": "hard",
        "category": "concurrency",
        "tags": ["spinlock", "rwlock", "concurrency", "atomics", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Concurrent Read-Write Spinlock Using Atomic Bit Flags

Implement a high-performance, low-latency concurrent Read-Write Spinlock in C++20 compacted into a single `std::atomic<uint32_t>`.

## State Representation

- Bit 31 (MSB, `0x80000000`): Exclusive write lock flag (`1` = write locked, `0` = write unlocked).
- Bits 0..30 (`0x7FFFFFFF`): Shared reader reference counter.

## Requirements

Implement the class `RWSpinLock`:

- `void lock_shared() noexcept`:
  Spins until no writer holds the lock (bit 31 is 0), then atomically increments reader count.
- `bool try_lock_shared() noexcept`:
  Non-blocking attempt. Returns `true` if read lock acquired, `false` if writer is active.
- `void unlock_shared() noexcept`:
  Decrements reader count.
- `void lock() noexcept`:
  Spins until no writer and no readers are present (`state == 0`), then atomically sets bit 31.
- `bool try_lock() noexcept`:
  Non-blocking attempt. Returns `true` if acquired exclusively, `false` otherwise.
- `void unlock() noexcept`:
  Clears the write lock bit.

Implement RAII wrappers:
- `class ReadGuard`
- `class WriteGuard`
""",
        "starter_code": """#pragma once
#include <atomic>
#include <cstdint>

class RWSpinLock {
public:
    void lock_shared() noexcept;
    bool try_lock_shared() noexcept;
    void unlock_shared() noexcept;

    void lock() noexcept;
    bool try_lock() noexcept;
    void unlock() noexcept;
};

class ReadGuard {
public:
    explicit ReadGuard(RWSpinLock& lock);
    ~ReadGuard();
};

class WriteGuard {
public:
    explicit WriteGuard(RWSpinLock& lock);
    ~WriteGuard();
};
""",
        "canonical_solution": """#pragma once
#include <atomic>
#include <cstdint>
#include <thread>

class RWSpinLock {
public:
    RWSpinLock() : state_(0) {}

    void lock_shared() noexcept {
        while (true) {
            uint32_t expected = state_.load(std::memory_order_relaxed);
            if ((expected & WRITE_FLAG) == 0) {
                if (state_.compare_exchange_weak(expected, expected + 1,
                                                std::memory_order_acquire,
                                                std::memory_order_relaxed)) {
                    return;
                }
            } else {
                std::this_thread::yield();
            }
        }
    }

    bool try_lock_shared() noexcept {
        uint32_t expected = state_.load(std::memory_order_relaxed);
        if ((expected & WRITE_FLAG) != 0) {
            return false;
        }
        return state_.compare_exchange_strong(expected, expected + 1,
                                              std::memory_order_acquire,
                                              std::memory_order_relaxed);
    }

    void unlock_shared() noexcept {
        state_.fetch_sub(1, std::memory_order_release);
    }

    void lock() noexcept {
        while (true) {
            uint32_t expected = 0;
            if (state_.compare_exchange_weak(expected, WRITE_FLAG,
                                            std::memory_order_acquire,
                                            std::memory_order_relaxed)) {
                return;
            }
            std::this_thread::yield();
        }
    }

    bool try_lock() noexcept {
        uint32_t expected = 0;
        return state_.compare_exchange_strong(expected, WRITE_FLAG,
                                              std::memory_order_acquire,
                                              std::memory_order_relaxed);
    }

    void unlock() noexcept {
        state_.fetch_and(~WRITE_FLAG, std::memory_order_release);
    }

private:
    static constexpr uint32_t WRITE_FLAG = 0x80000000U;
    alignas(64) std::atomic<uint32_t> state_{0};
};

class ReadGuard {
public:
    explicit ReadGuard(RWSpinLock& lock) : lock_(lock) {
        lock_.lock_shared();
    }
    ~ReadGuard() {
        lock_.unlock_shared();
    }
    ReadGuard(const ReadGuard&) = delete;
    ReadGuard& operator=(const ReadGuard&) = delete;

private:
    RWSpinLock& lock_;
};

class WriteGuard {
public:
    explicit WriteGuard(RWSpinLock& lock) : lock_(lock) {
        lock_.lock();
    }
    ~WriteGuard() {
        lock_.unlock();
    }
    WriteGuard(const WriteGuard&) = delete;
    WriteGuard& operator=(const WriteGuard&) = delete;

private:
    RWSpinLock& lock_;
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(RWSpinLockTest, MultipleReadersShared) {
    RWSpinLock lock;
    EXPECT_TRUE(lock.try_lock_shared());
    EXPECT_TRUE(lock.try_lock_shared()); // Multiple readers allowed

    EXPECT_FALSE(lock.try_lock()); // Writer rejected when readers present

    lock.unlock_shared();
    lock.unlock_shared();
    EXPECT_TRUE(lock.try_lock()); // Writer succeeds once readers release
    lock.unlock();
}

TEST(RWSpinLockTest, ExclusiveWriter) {
    RWSpinLock lock;
    lock.lock();
    EXPECT_FALSE(lock.try_lock_shared()); // Readers rejected
    EXPECT_FALSE(lock.try_lock());        // Second writer rejected
    lock.unlock();
    EXPECT_TRUE(lock.try_lock_shared());
    lock.unlock_shared();
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

TEST(RWSpinLockTest, RAIIReadGuard) {
    RWSpinLock lock;
    {
        ReadGuard guard(lock);
        EXPECT_FALSE(lock.try_lock());
    }
    EXPECT_TRUE(lock.try_lock());
    lock.unlock();
}

TEST(RWSpinLockTest, RAIIWriteGuard) {
    RWSpinLock lock;
    {
        WriteGuard guard(lock);
        EXPECT_FALSE(lock.try_lock_shared());
    }
    EXPECT_TRUE(lock.try_lock_shared());
    lock.unlock_shared();
}

TEST(RWSpinLockTest, ConcurrentReadersAndWriters) {
    RWSpinLock lock;
    int shared_val = 0;
    std::vector<std::thread> threads;

    // 4 writers
    for (int i = 0; i < 4; ++i) {
        threads.emplace_back([&lock, &shared_val]() {
            for (int j = 0; j < 50; ++j) {
                WriteGuard g(lock);
                shared_val++;
            }
        });
    }

    // 4 readers
    for (int i = 0; i < 4; ++i) {
        threads.emplace_back([&lock, &shared_val]() {
            for (int j = 0; j < 50; ++j) {
                ReadGuard g(lock);
                int val = shared_val;
                (void)val;
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    EXPECT_EQ(shared_val, 200);
}

TEST(RWSpinLockTest, TryLockFailureUnderWriteLock) {
    RWSpinLock lock;
    lock.lock();
    EXPECT_FALSE(lock.try_lock());
    EXPECT_FALSE(lock.try_lock_shared());
    lock.unlock();
}

TEST(RWSpinLockTest, SuccessiveAcquireRelease) {
    RWSpinLock lock;
    for (int i = 0; i < 100; ++i) {
        lock.lock();
        lock.unlock();
        lock.lock_shared();
        lock.unlock_shared();
    }
}

TEST(RWSpinLockTest, MultipleReadGuards) {
    RWSpinLock lock;
    {
        ReadGuard r1(lock);
        ReadGuard r2(lock);
        EXPECT_FALSE(lock.try_lock());
    }
    EXPECT_TRUE(lock.try_lock());
    lock.unlock();
}
""",
    },
    {
        "task_id": "EF-CPP-008",
        "title": "Custom Polymorphic Memory Resource (std::pmr) Monotonic Allocator",
        "language": "cpp",
        "difficulty": "medium",
        "category": "systems",
        "tags": ["pmr", "memory_resource", "allocator", "cpp20", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Custom Polymorphic Memory Resource (std::pmr) Monotonic Allocator

Implement a custom `std::pmr::memory_resource` in C++20 that allocates memory from a fixed preallocated contiguous buffer, delegates to an upstream resource on exhaustion, and performs fast $O(1)$ release.

## Requirements

Implement the class `MonotonicBufferResource` inheriting from `std::pmr::memory_resource`:

- `MonotonicBufferResource(void* buffer, size_t size, std::pmr::memory_resource* upstream = std::pmr::get_default_resource())`:
  Uses caller-provided contiguous buffer.
- `void* do_allocate(size_t bytes, size_t alignment) override`:
  Allocates aligned memory from initial buffer. If insufficient space, delegates allocation to `upstream`.
- `void do_deallocate(void* p, size_t bytes, size_t alignment) override`:
  No-op for buffer allocations (monotonic). If `p` was allocated by `upstream`, deallocates via upstream.
- `bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override`:
  Returns `this == &other`.
- `[[nodiscard]] size_t bytes_allocated() const noexcept`:
  Returns total bytes allocated out of the initial buffer.
- `void release() noexcept`:
  Resets buffer allocation offset back to 0.
""",
        "starter_code": """#pragma once
#include <cstddef>
#include <memory_resource>

class MonotonicBufferResource : public std::pmr::memory_resource {
public:
    MonotonicBufferResource(void* buffer, size_t size,
                            std::pmr::memory_resource* upstream = std::pmr::get_default_resource());

    size_t bytes_allocated() const noexcept;
    void release() noexcept;

protected:
    void* do_allocate(size_t bytes, size_t alignment) override;
    void do_deallocate(void* p, size_t bytes, size_t alignment) override;
    bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override;
};
""",
        "canonical_solution": """#pragma once
#include <cstddef>
#include <cstdint>
#include <memory_resource>
#include <vector>

class MonotonicBufferResource : public std::pmr::memory_resource {
public:
    MonotonicBufferResource(void* buffer, size_t size,
                            std::pmr::memory_resource* upstream = std::pmr::get_default_resource())
        : buffer_(static_cast<std::byte*>(buffer)),
          capacity_(size),
          offset_(0),
          upstream_(upstream ? upstream : std::pmr::get_default_resource()) {}

    ~MonotonicBufferResource() override {
        // Free any active upstream allocations
        for (const auto& alloc : upstream_allocs_) {
            upstream_->deallocate(alloc.ptr, alloc.bytes, alloc.alignment);
        }
    }

    [[nodiscard]] size_t bytes_allocated() const noexcept {
        return offset_;
    }

    void release() noexcept {
        offset_ = 0;
        for (const auto& alloc : upstream_allocs_) {
            upstream_->deallocate(alloc.ptr, alloc.bytes, alloc.alignment);
        }
        upstream_allocs_.clear();
    }

protected:
    void* do_allocate(size_t bytes, size_t alignment) override {
        if (bytes == 0) return nullptr;

        uintptr_t curr = reinterpret_cast<uintptr_t>(buffer_ + offset_);
        uintptr_t aligned = (curr + (alignment - 1)) & ~(alignment - 1);
        size_t padding = aligned - curr;

        if (offset_ + padding + bytes <= capacity_) {
            offset_ += padding + bytes;
            return reinterpret_cast<void*>(aligned);
        }

        // Delegate overflow to upstream resource
        void* p = upstream_->allocate(bytes, alignment);
        upstream_allocs_.push_back({p, bytes, alignment});
        return p;
    }

    void do_deallocate(void* p, size_t bytes, size_t alignment) override {
        if (p == nullptr) return;
        uintptr_t addr = reinterpret_cast<uintptr_t>(p);
        uintptr_t buf_start = reinterpret_cast<uintptr_t>(buffer_);
        uintptr_t buf_end = buf_start + capacity_;

        if (addr >= buf_start && addr < buf_end) {
            // Monotonic: deallocation from initial buffer is a no-op
            return;
        }

        // Deallocate upstream
        for (auto it = upstream_allocs_.begin(); it != upstream_allocs_.end(); ++it) {
            if (it->ptr == p) {
                upstream_->deallocate(p, bytes, alignment);
                upstream_allocs_.erase(it);
                return;
            }
        }
    }

    bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override {
        return this == &other;
    }

private:
    struct UpstreamAlloc {
        void* ptr;
        size_t bytes;
        size_t alignment;
    };

    std::byte* buffer_;
    size_t capacity_;
    size_t offset_;
    std::pmr::memory_resource* upstream_;
    std::vector<UpstreamAlloc> upstream_allocs_;
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#include <vector>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(PmrMonotonicResourceTest, VectorAllocation) {
    alignas(64) std::byte raw_buffer[1024];
    MonotonicBufferResource mr(raw_buffer, sizeof(raw_buffer));

    std::pmr::vector<int> vec(&mr);
    for (int i = 0; i < 50; ++i) {
        vec.push_back(i);
    }
    EXPECT_GT(mr.bytes_allocated(), 0);
    EXPECT_EQ(vec.size(), 50);
}

TEST(PmrMonotonicResourceTest, AlignmentRespects64) {
    alignas(64) std::byte raw_buffer[512];
    MonotonicBufferResource mr(raw_buffer, sizeof(raw_buffer));

    void* p = mr.allocate(32, 64);
    EXPECT_NE(p, nullptr);
    EXPECT_EQ(reinterpret_cast<uintptr_t>(p) % 64, 0);
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <string>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(PmrMonotonicResourceTest, UpstreamFallbackOnOverflow) {
    alignas(16) std::byte small_buf[32];
    MonotonicBufferResource mr(small_buf, sizeof(small_buf));

    void* p1 = mr.allocate(24, 8);
    EXPECT_NE(p1, nullptr);

    // This request exceeds remaining 8 bytes, must fallback to upstream
    void* p2 = mr.allocate(64, 8);
    EXPECT_NE(p2, nullptr);
    mr.deallocate(p2, 64, 8);
}

TEST(PmrMonotonicResourceTest, ReleaseRecyclesBuffer) {
    alignas(16) std::byte raw_buf[256];
    MonotonicBufferResource mr(raw_buf, sizeof(raw_buf));

    void* p1 = mr.allocate(128);
    EXPECT_NE(p1, nullptr);
    EXPECT_GT(mr.bytes_allocated(), 0);

    mr.release();
    EXPECT_EQ(mr.bytes_allocated(), 0);

    void* p2 = mr.allocate(128);
    EXPECT_NE(p2, nullptr);
}

TEST(PmrMonotonicResourceTest, EqualityComparison) {
    alignas(16) std::byte b1[64], b2[64];
    MonotonicBufferResource mr1(b1, sizeof(b1));
    MonotonicBufferResource mr2(b2, sizeof(b2));

    EXPECT_TRUE(mr1.is_equal(mr1));
    EXPECT_FALSE(mr1.is_equal(mr2));
}

TEST(PmrMonotonicResourceTest, PmrStringVectorIntegration) {
    alignas(64) std::byte buf[2048];
    MonotonicBufferResource mr(buf, sizeof(buf));

    std::pmr::vector<std::pmr::string> words(&mr);
    words.emplace_back("Alpha", &mr);
    words.emplace_back("Beta", &mr);
    words.emplace_back("Gamma", &mr);

    EXPECT_EQ(words.size(), 3);
    EXPECT_EQ(words[0], "Alpha");
}

TEST(PmrMonotonicResourceTest, ZeroBytesAllocation) {
    alignas(16) std::byte buf[64];
    MonotonicBufferResource mr(buf, sizeof(buf));
    EXPECT_EQ(mr.allocate(0), nullptr);
}

TEST(PmrMonotonicResourceTest, MultipleSequentialAllocations) {
    alignas(16) std::byte buf[1024];
    MonotonicBufferResource mr(buf, sizeof(buf));
    for (int i = 0; i < 20; ++i) {
        void* p = mr.allocate(16, 8);
        EXPECT_NE(p, nullptr);
    }
    EXPECT_LE(mr.bytes_allocated(), 1024);
}
""",
    },
    {
        "task_id": "EF-CPP-009",
        "title": "Radix Tree (Patricia Trie) with Edge Compression in C++20",
        "language": "cpp",
        "difficulty": "hard",
        "category": "data_structures",
        "tags": ["radix-tree", "patricia-trie", "trie", "data_structures", "cpp20"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 22,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Radix Tree (Patricia Trie) with Edge Compression in C++20

Implement a Radix Tree (compacted prefix tree) in C++20 where edges represent variable-length common prefixes, supporting insertion, edge splitting, deletion, and prefix queries.

## Requirements

Implement the class `RadixTree`:

- `void insert(std::string_view key, int value)`:
  Inserts `(key, value)`. If `key` already exists, updates value. Splits edges when keys diverge mid-edge.
- `[[nodiscard]] std::optional<int> find(std::string_view key) const`:
  Returns value if exact `key` is stored in the tree, or `std::nullopt` otherwise.
- `bool remove(std::string_view key)`:
  Deletes `key`. Merges redundant single-child parent edges if applicable. Returns `true` if found and deleted, `false` otherwise.
- `[[nodiscard]] std::vector<std::string> keys_with_prefix(std::string_view prefix) const`:
  Returns all keys in the tree starting with `prefix` in lexicographical order.
- `[[nodiscard]] size_t size() const noexcept`:
  Returns number of unique keys stored.
""",
        "starter_code": """#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

class RadixTree {
public:
    RadixTree() = default;

    void insert(std::string_view key, int value);
    [[nodiscard]] std::optional<int> find(std::string_view key) const;
    bool remove(std::string_view key);
    [[nodiscard]] std::vector<std::string> keys_with_prefix(std::string_view prefix) const;
    [[nodiscard]] size_t size() const noexcept;
};
""",
        "canonical_solution": """#pragma once
#include <algorithm>
#include <cstddef>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

class RadixTree {
    struct Node {
        std::string edge_label;
        std::optional<int> value;
        std::map<char, std::unique_ptr<Node>> children;

        bool is_leaf() const {
            return children.empty();
        }
    };

public:
    RadixTree() : root_(std::make_unique<Node>()), size_(0) {}

    void insert(std::string_view key, int value) {
        Node* curr = root_.get();
        std::string_view rem = key;

        while (true) {
            if (rem.empty()) {
                if (!curr->value.has_value()) {
                    size_++;
                }
                curr->value = value;
                return;
            }

            char first = rem[0];
            auto it = curr->children.find(first);
            if (it == curr->children.end()) {
                // No matching child, create new edge
                auto child = std::make_unique<Node>();
                child->edge_label = std::string(rem);
                child->value = value;
                curr->children[first] = std::move(child);
                size_++;
                return;
            }

            Node* child = it->second.get();
            std::string_view edge = child->edge_label;

            // Find common prefix length
            size_t common = 0;
            size_t min_len = std::min(rem.size(), edge.size());
            while (common < min_len && rem[common] == edge[common]) {
                common++;
            }

            if (common < edge.size()) {
                // Split edge
                auto split_node = std::make_unique<Node>();
                split_node->edge_label = edge.substr(0, common);

                child->edge_label = edge.substr(common);
                split_node->children[child->edge_label[0]] = std::move(it->second);

                if (common == rem.size()) {
                    split_node->value = value;
                    size_++;
                } else {
                    auto new_child = std::make_unique<Node>();
                    new_child->edge_label = std::string(rem.substr(common));
                    new_child->value = value;
                    split_node->children[new_child->edge_label[0]] = std::move(new_child);
                    size_++;
                }

                curr->children[first] = std::move(split_node);
                return;
            }

            // Exactly matches or extends edge
            rem = rem.substr(common);
            curr = child;
        }
    }

    [[nodiscard]] std::optional<int> find(std::string_view key) const {
        const Node* curr = root_.get();
        std::string_view rem = key;

        while (curr) {
            if (rem.empty()) {
                return curr->value;
            }

            char first = rem[0];
            auto it = curr->children.find(first);
            if (it == curr->children.end()) {
                return std::nullopt;
            }

            const Node* child = it->second.get();
            std::string_view edge = child->edge_label;

            if (!rem.starts_with(edge)) {
                return std::nullopt;
            }

            rem = rem.substr(edge.size());
            curr = child;
        }

        return std::nullopt;
    }

    bool remove(std::string_view key) {
        bool deleted = false;
        root_ = remove_helper(std::move(root_), key, deleted);
        if (deleted) {
            size_--;
        }
        return deleted;
    }

    [[nodiscard]] std::vector<std::string> keys_with_prefix(std::string_view prefix) const {
        std::vector<std::string> results;
        const Node* curr = root_.get();
        std::string_view rem = prefix;
        std::string built_prefix;

        while (!rem.empty() && curr) {
            char first = rem[0];
            auto it = curr->children.find(first);
            if (it == curr->children.end()) {
                return {};
            }

            const Node* child = it->second.get();
            std::string_view edge = child->edge_label;

            if (rem.size() < edge.size()) {
                if (edge.starts_with(rem)) {
                    built_prefix += edge;
                    collect_all(child, built_prefix, results);
                    std::sort(results.begin(), results.end());
                    return results;
                }
                return {};
            }

            if (!rem.starts_with(edge)) {
                return {};
            }

            built_prefix += edge;
            rem = rem.substr(edge.size());
            curr = child;
        }

        if (curr) {
            collect_all(curr, built_prefix, results);
        }

        std::sort(results.begin(), results.end());
        return results;
    }

    [[nodiscard]] size_t size() const noexcept {
        return size_;
    }

private:
    std::unique_ptr<Node> remove_helper(std::unique_ptr<Node> node, std::string_view rem, bool& deleted) {
        if (!node) return nullptr;

        if (rem.empty()) {
            if (node->value.has_value()) {
                node->value.reset();
                deleted = true;
            }
        } else {
            char first = rem[0];
            auto it = node->children.find(first);
            if (it != node->children.end()) {
                std::string_view edge = it->second->edge_label;
                if (rem.starts_with(edge)) {
                    it->second = remove_helper(std::move(it->second), rem.substr(edge.size()), deleted);
                    if (!it->second) {
                        node->children.erase(it);
                    }
                }
            }
        }

        // If not root, check if edge can be merged with child
        if (node.get() != root_.get() && !node->value.has_value() && node->children.size() == 1) {
            auto only_child = std::move(node->children.begin()->second);
            node->edge_label += only_child->edge_label;
            node->value = only_child->value;
            node->children = std::move(only_child->children);
        }

        return node;
    }

    void collect_all(const Node* node, const std::string& prefix, std::vector<std::string>& out) const {
        if (node->value.has_value()) {
            out.push_back(prefix);
        }
        for (const auto& [c, child] : node->children) {
            collect_all(child.get(), prefix + child->edge_label, out);
        }
    }

    std::unique_ptr<Node> root_;
    size_t size_;
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(RadixTreeTest, BasicInsertAndFind) {
    RadixTree tree;
    tree.insert("apple", 1);
    tree.insert("app", 2);
    tree.insert("application", 3);

    EXPECT_EQ(tree.find("apple"), 1);
    EXPECT_EQ(tree.find("app"), 2);
    EXPECT_EQ(tree.find("application"), 3);
    EXPECT_EQ(tree.find("appl"), std::nullopt);
    EXPECT_EQ(tree.size(), 3);
}

TEST(RadixTreeTest, PrefixSearch) {
    RadixTree tree;
    tree.insert("romane", 1);
    tree.insert("romanus", 2);
    tree.insert("romulus", 3);
    tree.insert("rubens", 4);

    auto matches = tree.keys_with_prefix("rom");
    EXPECT_EQ(matches, (std::vector<std::string>{"romane", "romanus", "romulus"}));
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(RadixTreeTest, DeleteAndMergeEdge) {
    RadixTree tree;
    tree.insert("slow", 1);
    tree.insert("slower", 2);
    EXPECT_TRUE(tree.remove("slower"));
    EXPECT_EQ(tree.find("slower"), std::nullopt);
    EXPECT_EQ(tree.find("slow"), 1);
    EXPECT_FALSE(tree.remove("slower")); // Already deleted
}

TEST(RadixTreeTest, UpdateExistingKey) {
    RadixTree tree;
    tree.insert("item", 10);
    EXPECT_EQ(tree.find("item"), 10);
    tree.insert("item", 20);
    EXPECT_EQ(tree.find("item"), 20);
    EXPECT_EQ(tree.size(), 1);
}

TEST(RadixTreeTest, EmptyPrefixReturnsAll) {
    RadixTree tree;
    tree.insert("b", 2);
    tree.insert("a", 1);
    tree.insert("c", 3);
    auto all = tree.keys_with_prefix("");
    EXPECT_EQ(all, (std::vector<std::string>{"a", "b", "c"}));
}

TEST(RadixTreeTest, NonExistentPrefix) {
    RadixTree tree;
    tree.insert("dog", 1);
    EXPECT_TRUE(tree.keys_with_prefix("cat").empty());
}

TEST(RadixTreeTest, EmptyStringKey) {
    RadixTree tree;
    tree.insert("", 42);
    EXPECT_EQ(tree.find(""), 42);
    EXPECT_EQ(tree.size(), 1);
}

TEST(RadixTreeTest, ScaleDictionary) {
    RadixTree tree;
    for (int i = 0; i < 500; ++i) {
        tree.insert("test_key_" + std::to_string(i), i);
    }
    EXPECT_EQ(tree.size(), 500);
    EXPECT_EQ(tree.find("test_key_250"), 250);
}
""",
    },
    {
        "task_id": "EF-CPP-010",
        "title": "Zero-Copy Circular Byte Buffer with std::span",
        "language": "cpp",
        "difficulty": "medium",
        "category": "systems",
        "tags": ["zero-copy", "span", "ring-buffer", "streaming", "systems"],
        "time_limit_sec": 2.0,
        "memory_limit_mb": 256,
        "rubric_rules": {
            "banned_imports": ["system", "fork"],
            "max_cyclomatic_complexity": 20,
            "max_lines": 200,
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
        },
        "prompt": """# Zero-Copy Circular Byte Buffer with std::span

Implement a zero-copy circular ring buffer in C++20 for raw byte streaming that returns memory slices as `std::span` views to facilitate zero-copy socket or I/O writes.

## Requirements

Implement the class `CircularByteBuffer`:

- `explicit CircularByteBuffer(size_t capacity)`:
  Initializes contiguous byte buffer of `capacity` bytes.
- `std::pair<std::span<uint8_t>, std::span<uint8_t>> prepare_write()`:
  Returns up to two contiguous mutable byte spans available for writing.
  If available write space does not wrap around, the second span is empty.
- `void commit_write(size_t bytes)`:
  Advances write offset by `bytes` (where `bytes <= available_write()`).
- `std::pair<std::span<const uint8_t>, std::span<const uint8_t>> prepare_read() const`:
  Returns up to two contiguous const byte spans containing buffered unread data.
- `void commit_read(size_t bytes)`:
  Advances read offset by `bytes` (where `bytes <= available_read()`).
- `[[nodiscard]] size_t available_read() const noexcept`:
  Returns number of unread bytes.
- `[[nodiscard]] size_t available_write() const noexcept`:
  Returns remaining write capacity.
- `[[nodiscard]] size_t capacity() const noexcept`:
  Returns total capacity.
""",
        "starter_code": """#pragma once
#include <cstddef>
#include <cstdint>
#include <span>
#include <utility>

class CircularByteBuffer {
public:
    explicit CircularByteBuffer(size_t capacity);
    ~CircularByteBuffer();

    std::pair<std::span<uint8_t>, std::span<uint8_t>> prepare_write();
    void commit_write(size_t bytes);

    std::pair<std::span<const uint8_t>, std::span<const uint8_t>> prepare_read() const;
    void commit_read(size_t bytes);

    [[nodiscard]] size_t available_read() const noexcept;
    [[nodiscard]] size_t available_write() const noexcept;
    [[nodiscard]] size_t capacity() const noexcept;
};
""",
        "canonical_solution": """#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <utility>

class CircularByteBuffer {
public:
    explicit CircularByteBuffer(size_t capacity)
        : capacity_(capacity), read_idx_(0), write_idx_(0), size_(0) {
        if (capacity == 0) {
            throw std::invalid_argument("Capacity must be at least 1");
        }
        buffer_ = new uint8_t[capacity];
    }

    ~CircularByteBuffer() {
        delete[] buffer_;
    }

    CircularByteBuffer(const CircularByteBuffer&) = delete;
    CircularByteBuffer& operator=(const CircularByteBuffer&) = delete;

    CircularByteBuffer(CircularByteBuffer&& other) noexcept
        : buffer_(other.buffer_),
          capacity_(other.capacity_),
          read_idx_(other.read_idx_),
          write_idx_(other.write_idx_),
          size_(other.size_) {
        other.buffer_ = nullptr;
        other.capacity_ = 0;
        other.size_ = 0;
    }

    CircularByteBuffer& operator=(CircularByteBuffer&& other) noexcept {
        if (this != &other) {
            delete[] buffer_;
            buffer_ = other.buffer_;
            capacity_ = other.capacity_;
            read_idx_ = other.read_idx_;
            write_idx_ = other.write_idx_;
            size_ = other.size_;
            other.buffer_ = nullptr;
            other.capacity_ = 0;
            other.size_ = 0;
        }
        return *this;
    }

    std::pair<std::span<uint8_t>, std::span<uint8_t>> prepare_write() {
        size_t free_space = capacity_ - size_;
        if (free_space == 0) {
            return {{}, {}};
        }

        if (write_idx_ >= read_idx_ && size_ < capacity_) {
            size_t tail_space = capacity_ - write_idx_;
            if (read_idx_ > 0) {
                return {std::span<uint8_t>(buffer_ + write_idx_, tail_space),
                        std::span<uint8_t>(buffer_, read_idx_)};
            }
            return {std::span<uint8_t>(buffer_ + write_idx_, tail_space), {}};
        }

        return {std::span<uint8_t>(buffer_ + write_idx_, read_idx_ - write_idx_), {}};
    }

    void commit_write(size_t bytes) {
        if (bytes > (capacity_ - size_)) {
            throw std::overflow_error("Cannot commit more than available write capacity");
        }
        write_idx_ = (write_idx_ + bytes) % capacity_;
        size_ += bytes;
    }

    std::pair<std::span<const uint8_t>, std::span<const uint8_t>> prepare_read() const {
        if (size_ == 0) {
            return {{}, {}};
        }

        if (write_idx_ <= read_idx_) {
            size_t tail_data = capacity_ - read_idx_;
            if (write_idx_ > 0) {
                return {std::span<const uint8_t>(buffer_ + read_idx_, tail_data),
                        std::span<const uint8_t>(buffer_, write_idx_)};
            }
            return {std::span<const uint8_t>(buffer_ + read_idx_, tail_data), {}};
        }

        return {std::span<const uint8_t>(buffer_ + read_idx_, size_), {}};
    }

    void commit_read(size_t bytes) {
        if (bytes > size_) {
            throw std::underflow_error("Cannot commit more than available unread bytes");
        }
        read_idx_ = (read_idx_ + bytes) % capacity_;
        size_ -= bytes;
    }

    [[nodiscard]] size_t available_read() const noexcept {
        return size_;
    }

    [[nodiscard]] size_t available_write() const noexcept {
        return capacity_ - size_;
    }

    [[nodiscard]] size_t capacity() const noexcept {
        return capacity_;
    }

private:
    uint8_t* buffer_{nullptr};
    size_t capacity_{0};
    size_t read_idx_{0};
    size_t write_idx_{0};
    size_t size_{0};
};
""",
        "visible_tests": """#include <gtest/gtest.h>
#include <cstring>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(CircularByteBufferTest, BasicWriteAndRead) {
    CircularByteBuffer buf(16);
    EXPECT_EQ(buf.available_read(), 0);
    EXPECT_EQ(buf.available_write(), 16);

    auto [w1, w2] = buf.prepare_write();
    ASSERT_GE(w1.size(), 5);
    std::memcpy(w1.data(), "Hello", 5);
    buf.commit_write(5);

    EXPECT_EQ(buf.available_read(), 5);

    auto [r1, r2] = buf.prepare_read();
    EXPECT_EQ(r1.size(), 5);
    EXPECT_TRUE(r2.empty());
    EXPECT_EQ(std::memcmp(r1.data(), "Hello", 5), 0);

    buf.commit_read(5);
    EXPECT_EQ(buf.available_read(), 0);
}

TEST(CircularByteBufferTest, CapacityLimits) {
    CircularByteBuffer buf(8);
    auto [w1, w2] = buf.prepare_write();
    buf.commit_write(8);
    EXPECT_EQ(buf.available_write(), 0);
    EXPECT_THROW(buf.commit_write(1), std::overflow_error);
}
""",
        "hidden_tests": """#include <gtest/gtest.h>
#include <cstring>
#if __has_include("solution.hpp")
#include "solution.hpp"
#elif __has_include("solution.cpp")
#include "solution.cpp"
#endif

TEST(CircularByteBufferTest, WrapAroundTwoSpanWrite) {
    CircularByteBuffer buf(10);
    // Write 7 bytes, read 5 bytes -> write_idx is 7, read_idx is 5
    auto [w1, _] = buf.prepare_write();
    buf.commit_write(7);
    buf.commit_read(5);

    // Available write = 10 - 2 = 8 bytes: 3 bytes at end [7..10), 5 bytes at start [0..5)
    auto [sw1, sw2] = buf.prepare_write();
    EXPECT_EQ(sw1.size(), 3);
    EXPECT_EQ(sw2.size(), 5);
}

TEST(CircularByteBufferTest, WrapAroundTwoSpanRead) {
    CircularByteBuffer buf(10);
    buf.commit_write(7);
    buf.commit_read(5);
    // Now write 6 bytes, wrapping around
    buf.commit_write(6);
    // Unread data = 2 + 6 = 8 bytes: 3 bytes at end [7..10), 5 bytes at start [0..5)
    auto [r1, r2] = buf.prepare_read();
    EXPECT_EQ(r1.size(), 3);
    EXPECT_EQ(r2.size(), 5);
    buf.commit_read(8);
    EXPECT_EQ(buf.available_read(), 0);
}

TEST(CircularByteBufferTest, EmptyReadCommitThrows) {
    CircularByteBuffer buf(10);
    EXPECT_THROW(buf.commit_read(1), std::underflow_error);
}

TEST(CircularByteBufferTest, ZeroCapacityThrows) {
    EXPECT_THROW(CircularByteBuffer(0), std::invalid_argument);
}

TEST(CircularByteBufferTest, FullBufferPrepareWriteEmpty) {
    CircularByteBuffer buf(4);
    buf.commit_write(4);
    auto [w1, w2] = buf.prepare_write();
    EXPECT_TRUE(w1.empty());
    EXPECT_TRUE(w2.empty());
}

TEST(CircularByteBufferTest, StreamThroughputSimulation) {
    CircularByteBuffer buf(32);
    for (int i = 0; i < 500; ++i) {
        auto [w1, w2] = buf.prepare_write();
        ASSERT_GE(w1.size(), 4);
        uint32_t val = static_cast<uint32_t>(i);
        std::memcpy(w1.data(), &val, sizeof(val));
        buf.commit_write(4);

        auto [r1, r2] = buf.prepare_read();
        ASSERT_GE(r1.size(), 4);
        uint32_t read_val = 0;
        std::memcpy(&read_val, r1.data(), sizeof(read_val));
        EXPECT_EQ(read_val, val);
        buf.commit_read(4);
    }
}
""",
    },
]
