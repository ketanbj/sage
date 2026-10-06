FROM sage-einsums:22a1159
RUN apt-get update && apt-get install -y --no-install-recommends python3-dev python3-numpy \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --branch v2.13.6 --depth 1 https://github.com/pybind/pybind11.git /opt/pybind11-src \
    && cmake -S /opt/pybind11-src -B /opt/pybind11-build -G Ninja -DCMAKE_CXX_COMPILER=clang++-18 -DPYBIND11_TEST=OFF -DCMAKE_INSTALL_PREFIX=/opt/pybind11 \
    && cmake --install /opt/pybind11-build
RUN cmake -S /opt/einsums-src -B /opt/einsums-build \
    -DEINSUMS_BUILD_PYTHON=ON -Dpybind11_DIR=/opt/pybind11/share/cmake/pybind11 \
    -DPython_EXECUTABLE=/usr/bin/python3 \
    && cmake --build /opt/einsums-build --parallel 2 \
    && cmake --install /opt/einsums-build
ENV PYTHONPATH=/opt/einsums/lib LD_LIBRARY_PATH=/opt/einsums/lib
RUN python3 -c 'import einsums; assert not einsums.core.gpu_enabled()'
