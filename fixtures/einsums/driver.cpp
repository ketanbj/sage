// SAGE bounded Einsums v1.1.5 tensor harness. Einsums is MIT licensed;
// the unmodified upstream implementation and license are captured per run.
#include <Einsums/Tensor.hpp>
#include <Einsums/TensorAlgebra.hpp>
#include <Einsums/Profile/Timer.hpp>
#include <cstdio>
#include <cstdint>

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    FILE *fp = std::fopen(argv[1], "rb");
    if (!fp) return 65;
    unsigned char bytes[37]{};
    size_t size = std::fread(bytes, 1, sizeof(bytes), fp);
    std::fclose(fp);
    if (size != 36) return 65;
    unsigned op = bytes[0], m = bytes[1], k = bytes[2], n = bytes[3];
    if (op > 5 || m < 1 || m > 4 || k < 1 || k > 4 || n < 1 || n > 4) return 65;
    einsums::profile::initialize();
    using einsums::Tensor;
    using einsums::Indices;
    using namespace einsums::tensor_algebra;
    using namespace einsums::index;
    Tensor<double, 2> A{"A", m, k};
    Tensor<double, 2> B{"B", op == 4 ? k : m, op == 4 ? n : k};
    for (size_t r = 0; r < A.dim(0); ++r)
        for (size_t c = 0; c < A.dim(1); ++c)
            A(r, c) = static_cast<int8_t>(bytes[4 + r * k + c]) / 8.0;
    for (size_t r = 0; r < B.dim(0); ++r)
        for (size_t c = 0; c < B.dim(1); ++c)
            B(r, c) = static_cast<int8_t>(bytes[20 + r * B.dim(1) + c]) / 8.0;
    Tensor<double, 2> C{"C", op == 3 ? k : m, op == 3 ? m : (op == 4 ? n : k)};
    C.zero();
    switch (op) {
    case 0: C = A; break;
    case 1: C = A + B; break;
    case 2: C = A * B; break;
    case 3: permute(Indices{i, j}, &C, Indices{j, i}, A); break;
    case 4: einsum(Indices{i, j}, &C, Indices{i, l}, A, Indices{l, j}, B); break;
    case 5: C = (static_cast<int8_t>(bytes[20]) / 8.0) * A; break;
    }
    // Shape, strides and indexed values are all observable; data are row-major.
    std::printf("{\"shape\":[[%zu,%zu]],\"strides\":[[%zu,%zu]],\"values\":[",
                C.dim(0), C.dim(1), C.stride(0), C.stride(1));
    for (size_t r = 0; r < C.dim(0); ++r) {
        std::printf("%s[", r ? "," : "");
        for (size_t c = 0; c < C.dim(1); ++c)
            std::printf("%s%.17g", c ? "," : "", C(r, c));
        std::printf("]");
    }
    std::printf("]}\n");
    return 0;
}
