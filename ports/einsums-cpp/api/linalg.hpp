#pragma once
#include "array.hpp"
namespace sage_cpp::api {
std::pair<Array, Shape> lu(const Array &);
std::vector<Array> extract_plu(const Array &, const Shape &);
Array solve(const Array &, const Array &);
Array inverse(const Array &);
Array lu_inverse(const Array &, const Shape &);
Complex determinant(const Array &);
std::vector<Array> qr(const Array &);
std::vector<Array> unpack_qr(const Array &, const Array &);
std::vector<Array> eigh(const Array &);
std::vector<Array> geev(const Array &);
std::vector<Array> svd(const Array &, bool full = true);
Array pseudoinverse(const Array &, double);
Array nullspace(const Array &, double);
Array lyapunov(const Array &, const Array &);
Array cholesky(const Array &);
Array matrix_power(const Array &, Complex,
                   double cutoff = std::numeric_limits<double>::epsilon());
} // namespace sage_cpp::api
