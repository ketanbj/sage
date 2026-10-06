FROM ubuntu:24.04 AS symsan-build
ARG SYMSAN_COMMIT=ecbe8a7d6a5ceb687df16660d6f3f60f844b5bd4
ARG Z3_VERSION=4.13.3
ARG Z3_SHA256=32c7377026733c9d7b33c21cd77a68f50ba682367207b031a6bfd80140a8722f
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates cmake git make ninja-build python3 python3-dev python-is-python3 \
    clang-18 llvm-18-dev llvm-18-tools libc++-18-dev libc++abi-18-dev \
    libboost-container-dev libgoogle-perftools-dev libz3-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && \
    curl -fsSL --retry 3 \
      "https://github.com/Z3Prover/z3/releases/download/z3-${Z3_VERSION}/z3-${Z3_VERSION}-x64-glibc-2.35.zip" \
      -o /tmp/z3.zip && \
    echo "${Z3_SHA256}  /tmp/z3.zip" | sha256sum -c - && \
    unzip -q /tmp/z3.zip -d /tmp && \
    cp -a "/tmp/z3-${Z3_VERSION}-x64-glibc-2.35/include/." /usr/local/include/ && \
    cp -a "/tmp/z3-${Z3_VERSION}-x64-glibc-2.35/bin/libz3.so" /usr/local/lib/ && \
    rm -rf /tmp/z3.zip "/tmp/z3-${Z3_VERSION}-x64-glibc-2.35" /var/lib/apt/lists/*
RUN git clone https://github.com/R-Fuzz/symsan.git /src/symsan && \
    git -C /src/symsan checkout --detach "$SYMSAN_COMMIT"
RUN cmake -S /src/symsan -B /build -G Ninja \
    -DCMAKE_C_COMPILER=clang-18 -DCMAKE_CXX_COMPILER=clang++-18 \
    -DLLVM_DIR="$(llvm-config-18 --cmakedir)" -DCMAKE_INSTALL_PREFIX=/opt/symsan \
    -DCMAKE_BUILD_TYPE=Release && cmake --build /build && cmake --install /build

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang-18 libc++-18-dev libc++abi-18-dev libboost-container-dev \
    libgoogle-perftools-dev libz3-4 zlib1g-dev python3-dev && \
    ln -s /usr/bin/clang-18 /usr/local/bin/clang && \
    ln -s /usr/bin/clang++-18 /usr/local/bin/clang++ && \
    rm -rf /var/lib/apt/lists/*
COPY --from=symsan-build /opt/symsan /opt/symsan
COPY --from=symsan-build /usr/local/lib/libz3.so* /usr/local/lib/
COPY driver.py /opt/symsan/bin/sage-symsan-driver
ENV PATH=/opt/symsan/bin:$PATH \
    LD_LIBRARY_PATH=/opt/symsan/lib/symsan:/usr/local/lib \
    PYTHONPATH=/opt/symsan/lib/symsan
ENTRYPOINT ["/opt/symsan/bin/ko-clang"]
