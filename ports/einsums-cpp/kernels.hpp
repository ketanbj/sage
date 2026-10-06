#ifndef SAGE_EINSUMS_CPP_KERNELS_HPP
#define SAGE_EINSUMS_CPP_KERNELS_HPP

// Production kernels shared by the C++20 Tensor and the CBMC harness.
// The C++11-compatible syntax lets CBMC inspect this exact source without
// replacing std::span or the standard-library implementation with a model.
namespace sage_cpp {
template<class Scalar>
inline void copy_kernel(const Scalar* input, Scalar* output, unsigned rows, unsigned cols) {
    for (unsigned i = 0; i < rows * cols; ++i)
        output[i] = input[i];
}

template<class Scalar>
inline void transpose_kernel(const Scalar* input, Scalar* output, unsigned rows, unsigned cols) {
    for (unsigned r = 0; r < rows; ++r)
        for (unsigned c = 0; c < cols; ++c)
            output[c * rows + r] = input[r * cols + c];
}
} // namespace sage_cpp
#endif
