FROM gcc:13-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/sandbox_user/.local/bin:$PATH"

# Install CMake, Google Test source, and minimal Python 3.11 runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cmake \
        make \
        libgtest-dev \
        python3 \
        python3-minimal && \
    cmake -B /tmp/gtest-build -S /usr/src/googletest -DCMAKE_INSTALL_PREFIX=/usr/local && \
    cmake --build /tmp/gtest-build && \
    cmake --install /tmp/gtest-build && \
    cp -a /usr/local/lib/libgtest*.a /usr/lib/ 2>/dev/null || true && \
    cp -a /usr/local/lib/*/libgtest*.a /usr/lib/ 2>/dev/null || true && \
    ldconfig && \
    rm -rf /tmp/gtest-build /var/lib/apt/lists/*

# Create unprivileged user and group (UID 10001, GID 10001) with home directory
RUN groupadd -g 10001 sandbox_user && \
    useradd -u 10001 -g 10001 -m -s /bin/bash sandbox_user && \
    mkdir -p /workspace/run && \
    chown -R sandbox_user:sandbox_user /workspace/run && \
    chmod 0755 /workspace/run

USER 10001:10001
WORKDIR /workspace/run

CMD ["tail", "-f", "/dev/null"]
