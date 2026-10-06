#pragma once
#include "linalg.hpp"
namespace sage_cpp::api {
inline Array first_columns(const Array &a, std::size_t k) {
  auto [m, n] = a.matrix_shape();
  require(k <= n, "requested rank exceeds factor columns");
  auto out = Array::zeros(a.dtype, {m, k});
  for (std::size_t i = 0; i < m; ++i)
    for (std::size_t j = 0; j < k; ++j)
      out.values[i * k + j] = a.values[i * n + j];
  return out;
}
inline Array khatri_rao(const Array &a, const Array &b) {
  auto [m, k] = a.matrix_shape();
  auto [n, l] = b.matrix_shape();
  require(k == l && a.dtype == b.dtype, "Khatri-Rao columns/dtype must match");
  auto out = Array::zeros(a.dtype, {size({m, n}), k});
  for (std::size_t i = 0; i < m; ++i)
    for (std::size_t j = 0; j < n; ++j)
      for (std::size_t c = 0; c < k; ++c)
        out.values[(i * n + j) * k + c] =
            cast(a.dtype, a.values[i * k + c] * b.values[j * k + c]);
  return out;
}
inline Array reconstruct_tucker(const Array &core,
                                const std::vector<Array> &factors) {
  require(factors.size() == core.shape.size(),
          "one factor per tensor mode required", "rank_error");
  auto out = core;
  for (std::size_t i = 0; i < factors.size(); ++i)
    out = out.mode_product(factors[i], i);
  return out;
}
inline std::vector<Array> tucker(const Array &a, const Shape &ranks,
                                 std::size_t iterations, double tol) {
  require(std::isfinite(tol) && tol >= 0.,
          "tolerance must be finite and nonnegative", "ValueError");
  require(ranks.size() == a.shape.size(), "one rank per tensor mode required");
  std::vector<Array> factors;
  for (std::size_t i = 0; i < ranks.size(); ++i) {
    require(ranks[i] > 0 && ranks[i] <= a.shape[i],
            "Tucker ranks must be positive and bounded by each dimension");
    factors.push_back(first_columns(svd(a.unfold(i), true)[0], ranks[i]));
  }
  double previous = -std::numeric_limits<double>::infinity();
  for (std::size_t iter = 0; iter < iterations; ++iter) {
    for (std::size_t mode = 0; mode < ranks.size(); ++mode) {
      auto projected = a;
      for (std::size_t other = 0; other < factors.size(); ++other)
        if (other != mode)
          projected =
              projected.mode_product(factors[other].transpose("C"), other);
      factors[mode] =
          first_columns(svd(projected.unfold(mode), true)[0], ranks[mode]);
    }
    auto core = a;
    for (std::size_t i = 0; i < factors.size(); ++i)
      core = core.mode_product(factors[i].transpose("C"), i);
    double score = core.norm();
    if (std::abs(score - previous) <= tol * std::max(score, 1.))
      break;
    previous = score;
  }
  auto core = a;
  for (std::size_t i = 0; i < factors.size(); ++i)
    core = core.mode_product(factors[i].transpose("C"), i);
  factors.insert(factors.begin(), core);
  return factors;
}
inline Array reconstruct_cp(const std::vector<Array> &factors) {
  require(!factors.empty(), "at least one CP factor required", "rank_error");
  auto [first_n, rank] = factors[0].matrix_shape();
  (void)first_n;
  Shape s;
  for (const auto &f : factors) {
    auto [n, r] = f.matrix_shape();
    require(r == rank && f.dtype == factors[0].dtype,
            "CP factors must share dtype and column count");
    s.push_back(n);
  }
  auto out = Array::zeros(factors[0].dtype, s);
  for (std::size_t i = 0; i < out.values.size(); ++i) {
    auto c = coords(i, s);
    Complex sum = 0.;
    for (std::size_t r = 0; r < rank; ++r) {
      Complex z = 1.;
      for (std::size_t mode = 0; mode < s.size(); ++mode)
        z *= factors[mode].values[c[mode] * rank + r];
      sum += z;
    }
    out.values[i] = cast(out.dtype, sum);
  }
  return out;
}
inline std::vector<Array> cp(const Array &a, std::size_t rank,
                             std::size_t iterations, double tol) {
  require(std::isfinite(tol) && tol >= 0.,
          "tolerance must be finite and nonnegative", "ValueError");
  require(rank > 0 && !a.shape.empty() &&
              std::find(a.shape.begin(), a.shape.end(), 0) == a.shape.end(),
          "CP requires positive rank and nonempty modes");
  std::vector<Array> factors;
  for (std::size_t mode = 0; mode < a.shape.size(); ++mode) {
    auto f = Array::zeros(a.dtype, {a.shape[mode], rank});
    for (std::size_t i = 0; i < f.values.size(); ++i)
      f.values[i] =
          cast(a.dtype, std::sin((i + 1 + mode * 17) * 1.618033988749895));
    factors.push_back(f);
  }
  double previous = std::numeric_limits<double>::infinity();
  for (std::size_t iter = 0; iter < iterations; ++iter) {
    for (std::size_t mode = 0; mode < a.shape.size(); ++mode) {
      auto product = Array::zeros(a.dtype, {1, rank});
      std::fill(product.values.begin(), product.values.end(), Complex(1.));
      for (std::size_t other = 0; other < factors.size(); ++other)
        if (other != mode)
          product = khatri_rao(product, factors[other]);
      auto conjugate = product.map([](Complex z) { return std::conj(z); });
      auto gram = product.transpose().matmul(conjugate),
           rhs = a.unfold(mode).matmul(conjugate);
      factors[mode] =
          rhs.matmul(pseudoinverse(gram, 1e-12 * std::max(gram.norm(), 1.)));
    }
    double residual = a.zip(reconstruct_cp(factors), [](Complex x, Complex y) {
                         return x - y;
                       }).norm();
    if (std::abs(previous - residual) <= tol * std::max(a.norm(), 1.))
      break;
    previous = residual;
  }
  return factors;
}
inline Array weight_tensor(const Array &a, const Array &weights) {
  require(!a.shape.empty() && weights.shape == Shape{a.shape[0]} &&
              a.dtype == weights.dtype,
          "weights must match the first mode and dtype");
  auto out = a;
  Shape rest(a.shape.begin() + 1, a.shape.end());
  auto stride = size(rest);
  for (std::size_t i = 0; i < a.values.size(); ++i)
    out.values[i] = cast(a.dtype, a.values[i] * weights.values[i / stride]);
  return out;
}
inline std::vector<Array> weighted_parafac(const Array &a, const Array &weights,
                                           std::size_t rank,
                                           std::size_t iterations, double tol) {
  auto factors = cp(weight_tensor(a, weights), rank, iterations, tol);
  for (std::size_t i = 0; i < a.shape[0]; ++i)
    for (std::size_t j = 0; j < rank; ++j)
      factors[0].values[i * rank + j] = cast(
          a.dtype, weights.values[i] == Complex(0.)
                       ? Complex(0.)
                       : factors[0].values[i * rank + j] / weights.values[i]);
  return factors;
}
} // namespace sage_cpp::api
