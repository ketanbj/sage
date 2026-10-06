#pragma once
#include "kernels.hpp"
#include <algorithm>
#include <array>
#include <cstddef>
#include <span>
#include <stdexcept>

namespace sage_cpp {
// Deliberately bounded rank-two, contiguous binary64 tensor. Owns its storage;
// spans are borrowed views and must not outlive the tensor.
template<class Scalar> struct NativeArithmetic {
    static Scalar add(Scalar a, Scalar b) { return a+b; }
    static Scalar multiply(Scalar a, Scalar b) { return a*b; }
};
// Arithmetic is a policy so the same public-method control flow can be proved
// with injective expression trees. Tensor selects ordinary binary64 arithmetic.
template<class Scalar, class Arithmetic = NativeArithmetic<Scalar>> class BasicTensor {
    unsigned rows_, cols_;
    std::array<Scalar, 16> data_;

    void require_same_shape(const BasicTensor& other) const {
        if (rows_ != other.rows_ || cols_ != other.cols_)
            throw std::invalid_argument("tensor shape mismatch");
    }
public:
    BasicTensor(unsigned rows, unsigned cols) : rows_(rows), cols_(cols) {
        for (unsigned i = 0; i < 16; ++i) data_[i] = Scalar();
        if (rows < 1 || rows > 4 || cols < 1 || cols > 4)
            throw std::invalid_argument("dimensions must be 1..4");
    }
    static BasicTensor from_values(unsigned rows, unsigned cols, std::span<const Scalar> values) {
        BasicTensor out(rows, cols);
        if (values.size() != out.size())
            throw std::invalid_argument("wrong number of tensor values");
        std::copy(values.begin(), values.end(), out.data_.begin());
        return out;
    }
    unsigned rows() const noexcept { return rows_; }
    unsigned cols() const noexcept { return cols_; }
    unsigned size() const noexcept { return rows_ * cols_; }
    std::span<const Scalar> values() const noexcept { return {data_.data(), size()}; }
    Scalar& at(unsigned r, unsigned c) {
        if (r >= rows_ || c >= cols_) throw std::out_of_range("tensor index");
        return data_[r * cols_ + c];
    }
    Scalar at(unsigned r, unsigned c) const {
        if (r >= rows_ || c >= cols_) throw std::out_of_range("tensor index");
        return data_[r * cols_ + c];
    }
    BasicTensor copy() const {
        BasicTensor out(rows_, cols_);
        copy_kernel(data_.data(), out.data_.data(), rows_, cols_);
        return out;
    }
    BasicTensor transposed() const {
        BasicTensor out(cols_, rows_);
        transpose_kernel(data_.data(), out.data_.data(), rows_, cols_);
        return out;
    }
    BasicTensor added(const BasicTensor& other) const {
        require_same_shape(other);
        BasicTensor out(rows_, cols_);
        for (unsigned i = 0; i < size(); ++i) out.data_[i] = Arithmetic::add(data_[i], other.data_[i]);
        return out;
    }
    BasicTensor multiplied(const BasicTensor& other) const {
        require_same_shape(other);
        BasicTensor out(rows_, cols_);
        for (unsigned i = 0; i < size(); ++i) out.data_[i] = Arithmetic::multiply(data_[i], other.data_[i]);
        return out;
    }
    BasicTensor scaled(Scalar scalar) const {
        BasicTensor out(rows_, cols_);
        for (unsigned i = 0; i < size(); ++i) out.data_[i] = Arithmetic::multiply(scalar, data_[i]);
        return out;
    }
    BasicTensor matmul(const BasicTensor& other) const {
        if (cols_ != other.rows_) throw std::invalid_argument("matmul shape mismatch");
        BasicTensor out(rows_, other.cols_);
        for (unsigned r = 0; r < rows_; ++r)
            for (unsigned c = 0; c < other.cols_; ++c)
                for (unsigned k = 0; k < cols_; ++k)
                    out.at(r, c) = Arithmetic::add(out.at(r, c),
                        Arithmetic::multiply(at(r, k), other.at(k, c)));
        return out;
    }
};
using Tensor = BasicTensor<double>;
} // namespace sage_cpp
