#include "tensor.hpp"
#include <cassert>
#include <utility>

template<class Error, class Function> void expect_error(Function&& call) {
    bool caught = false;
    try { std::forward<Function>(call)(); }
    catch (const Error&) { caught = true; }
    assert(caught);
}

int main() {
    using sage_cpp::Tensor;
    for (unsigned rows = 1; rows <= 4; ++rows) {
        for (unsigned cols = 1; cols <= 4; ++cols) {
            std::array<double, 16> values{};
            for (unsigned i = 0; i < 16; ++i) values[i] = (int(i) - 8) / 8.;
            auto original = Tensor::from_values(rows, cols, std::span(values).first(rows*cols));
            values[0] = 500; // from_values owns its data.
            auto copy = original.copy();
            auto automatic_copy = original; // Standard C++ value semantics also owns its data.
            auto transpose = original.transposed();
            assert(transpose.rows() == cols && transpose.cols() == rows);
            auto roundtrip = transpose.transposed();
            for (unsigned r = 0; r < rows; ++r) {
                for (unsigned c = 0; c < cols; ++c) {
                    assert(copy.at(r,c) == original.at(r,c));
                    assert(roundtrip.at(r,c) == original.at(r,c));
                    assert(transpose.at(c,r) == original.at(r,c));
                }
            }
            const double saved = original.at(0,0);
            copy.at(0,0) = 77;
            automatic_copy.at(0,0) = 88;
            transpose.at(0,0) = 99;
            assert(original.at(0,0) == saved);
            assert(original.values().size() == rows*cols);
            expect_error<std::out_of_range>([&] { original.at(rows,0); });
            expect_error<std::out_of_range>([&] { std::as_const(original).at(0,cols); });
            expect_error<std::invalid_argument>([&] {
                Tensor::from_values(rows, cols, std::span(values).first(rows*cols-1));
            });
        }
    }
    expect_error<std::invalid_argument>([] { Tensor(0,1); });
    expect_error<std::invalid_argument>([] { Tensor(1,5); });
    expect_error<std::invalid_argument>([] { Tensor(1,1).added(Tensor(1,2)); });
    expect_error<std::invalid_argument>([] { Tensor(1,1).multiplied(Tensor(2,1)); });
    expect_error<std::invalid_argument>([] { Tensor(1,2).matmul(Tensor(1,1)); });
}
