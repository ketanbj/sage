FROM sage-symsan:ecbe8a7
ARG EINSUMS_COMMIT=22a115978041e905461b24d9ca2a17bfcce01f32
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git cmake ninja-build libopenblas-dev libhdf5-dev libomp-18-dev \
    libfftw3-dev libspdlog-dev && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/Einsums/Einsums.git /opt/einsums-src && \
    git -C /opt/einsums-src checkout --detach "$EINSUMS_COMMIT"
RUN git clone --branch v1.14.1 --depth 1 https://github.com/gabime/spdlog.git /opt/spdlog-src
RUN cmake -S /opt/einsums-src -B /opt/einsums-build -G Ninja \
    -DCMAKE_C_COMPILER=clang-18 -DCMAKE_CXX_COMPILER=clang++-18 \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/einsums \
    -DCMAKE_DISABLE_FIND_PACKAGE_spdlog=TRUE -DFETCHCONTENT_SOURCE_DIR_SPDLOG=/opt/spdlog-src \
    -DEINSUMS_WITH_TESTS=OFF -DEINSUMS_WITH_EXAMPLES=OFF \
    -DEINSUMS_WITH_BACKTRACES=OFF -DEINSUMS_BUILD_PYTHON=OFF \
    -DEINSUMS_WITH_HIP=OFF -DEINSUMS_WITH_CUDA=OFF \
    -DEINSUMS_WITH_MALLOC=system && \
    cmake --build /opt/einsums-build --parallel 2 && \
    cmake --install /opt/einsums-build
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
ENTRYPOINT []
