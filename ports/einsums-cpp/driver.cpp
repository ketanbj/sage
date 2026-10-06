#include "tensor.hpp"
#include <array>
#include <fstream>
#include <iomanip>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) return 64;
    std::ifstream input(argv[1], std::ios::binary);
    std::array<unsigned char, 37> bytes{};
    input.read(reinterpret_cast<char*>(bytes.data()), bytes.size());
    if (input.gcount() != 36) return 65;
    const unsigned op = bytes[0], m = bytes[1], k = bytes[2], n = bytes[3];
    if (op > 5 || m < 1 || m > 4 || k < 1 || k > 4 || n < 1 || n > 4) return 65;
    std::array<double, 16> a{}, b{};
    for (unsigned i = 0; i < 16; ++i) {
        // Explicit conversion avoids implementation-defined signed-char conversion.
        const int av = bytes[4+i], bv = bytes[20+i];
        a[i] = (av < 128 ? av : av - 256) / 8.;
        b[i] = (bv < 128 ? bv : bv - 256) / 8.;
    }
    try {
        using sage_cpp::Tensor;
        const Tensor A = Tensor::from_values(m, k, std::span(a).first(m*k));
        const unsigned br = op == 4 ? k : m, bc = op == 4 ? n : k;
        const Tensor B = Tensor::from_values(br, bc, std::span(b).first(br*bc));
        const Tensor C = [&]() {
            switch (op) {
                case 0: return A.copy();
                case 1: return A.added(B);
                case 2: return A.multiplied(B);
                case 3: return A.transposed();
                case 4: return A.matmul(B);
                case 5: return A.scaled(b[0]);
                default: throw std::invalid_argument("operation");
            }
        }();
        std::cout << std::setprecision(17) << "{\"shape\":[[" << C.rows() << ',' << C.cols()
                  << "]],\"strides\":[[" << C.cols() << ",1]],\"values\":[";
        for (unsigned r = 0; r < C.rows(); ++r) {
            if (r) std::cout << ',';
            std::cout << '[';
            for (unsigned c = 0; c < C.cols(); ++c) {
                if (c) std::cout << ',';
                std::cout << C.at(r, c);
            }
            std::cout << ']';
        }
        std::cout << "]}\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 70;
    }
}
