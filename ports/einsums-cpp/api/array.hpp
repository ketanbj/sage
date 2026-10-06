#pragma once
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace sage_cpp::api {
using Complex = std::complex<double>;
using Shape = std::vector<std::size_t>;
struct Error : std::runtime_error {
  std::string kind;
  Error(std::string type, std::string message)
      : std::runtime_error(message), kind(std::move(type)) {}
};
inline void require(bool condition, const std::string &message,
                    const std::string &kind = "dimension_error") {
  if (!condition)
    throw Error(kind, message);
}
enum class DType { Float32, Float64, Complex64, Complex128 };
inline bool is_complex(DType d) {
  return d == DType::Complex64 || d == DType::Complex128;
}
inline bool is_low(DType d) {
  return d == DType::Float32 || d == DType::Complex64;
}
inline DType real_dtype(DType d) {
  return is_low(d) ? DType::Float32 : DType::Float64;
}
inline DType complex_dtype(DType d) {
  return is_low(d) ? DType::Complex64 : DType::Complex128;
}
inline std::string dtype_name(DType d) {
  switch (d) {
  case DType::Float32:
    return "float32";
  case DType::Float64:
    return "float64";
  case DType::Complex64:
    return "complex64";
  case DType::Complex128:
    return "complex128";
  }
  throw Error("TypeError", "unknown dtype");
}
inline DType dtype_from_name(const std::string &s) {
  for (auto d :
       {DType::Float32, DType::Float64, DType::Complex64, DType::Complex128})
    if (s == dtype_name(d))
      return d;
  throw Error("TypeError", "expected float32/64 or complex64/128");
}
inline Complex cast(DType d, Complex z) {
  double r = z.real(), i = is_complex(d) ? z.imag() : 0.;
  if (is_low(d)) {
    r = static_cast<float>(r);
    i = static_cast<float>(i);
  }
  return {r, i};
}
inline std::size_t checked_add(std::size_t a, std::size_t b) {
  require(b <= std::numeric_limits<std::size_t>::max() - a,
          "shape sum overflow");
  return a + b;
}
inline std::size_t size(const Shape &shape) {
  std::size_t n = 1;
  for (auto d : shape) {
    require(d == 0 || n <= static_cast<std::size_t>(
                               std::numeric_limits<std::ptrdiff_t>::max()) /
                               d,
            "shape product overflow");
    n *= d;
  }
  return n;
}
inline Shape strides(const Shape &shape) {
  Shape out(shape.size());
  std::size_t s = 1;
  for (std::size_t i = shape.size(); i-- > 0;) {
    out[i] = s;
    s = size({s, shape[i]});
  }
  return out;
}
inline Shape coords(std::size_t flat, const Shape &shape) {
  Shape out(shape.size());
  for (std::size_t i = shape.size(); i-- > 0;) {
    require(shape[i] != 0, "empty axis has no coordinates");
    out[i] = flat % shape[i];
    flat /= shape[i];
  }
  return out;
}
// Value-owned, arbitrary-rank array. Double working precision with an explicit
// cast at operation boundaries, matching the declared four-dtype API contract.
struct Array {
  DType dtype;
  Shape shape;
  std::vector<Complex> values;
  Array(DType d, Shape s, std::vector<Complex> v)
      : dtype(d), shape(std::move(s)), values(std::move(v)) {
    require(size(shape) == values.size(), "shape and data length differ");
    for (auto &z : values)
      z = cast(dtype, z);
  }
  static Array zeros(DType d, Shape s) {
    auto n = size(s);
    return {d, std::move(s), std::vector<Complex>(n)};
  }
  static Array identity(DType d, std::size_t n) {
    auto out = zeros(d, {n, n});
    for (std::size_t i = 0; i < n; ++i)
      out.values[i * n + i] = 1.;
    return out;
  }
  void validate() const {
    require(size(shape) == values.size(), "shape and data length differ");
  }
  std::pair<std::size_t, std::size_t> matrix_shape() const {
    require(shape.size() == 2, "matrix required", "rank_error");
    return {shape[0], shape[1]};
  }
  template <class F> Array map(F f) const {
    Array out = *this;
    for (auto &z : out.values)
      z = cast(dtype, f(z));
    return out;
  }
  template <class F> Array zip(const Array &b, F f) const {
    require(dtype == b.dtype, "operand dtypes must match", "TypeError");
    require(shape == b.shape || shape.empty() || b.shape.empty(),
            "operand shapes must match");
    auto out = zeros(dtype, shape.empty() ? b.shape : shape);
    for (std::size_t i = 0; i < out.values.size(); ++i)
      out.values[i] = cast(dtype, f(values[shape.empty() ? 0 : i],
                                    b.values[b.shape.empty() ? 0 : i]));
    return out;
  }
  Array reshape(Shape s) const { return {dtype, std::move(s), values}; }
  Array permute(const Shape &axes) const {
    auto sorted = axes;
    std::sort(sorted.begin(), sorted.end());
    Shape expected(shape.size());
    std::iota(expected.begin(), expected.end(), 0);
    require(sorted == expected, "axes must be a permutation");
    Shape s;
    for (auto a : axes)
      s.push_back(shape[a]);
    auto out = zeros(dtype, s);
    auto old = strides(shape);
    for (std::size_t i = 0; i < values.size(); ++i) {
      auto c = coords(i, s);
      std::size_t src = 0;
      for (std::size_t j = 0; j < c.size(); ++j)
        src += c[j] * old[axes[j]];
      out.values[i] = values[src];
    }
    return out;
  }
  Array transpose(std::string mode = "T") const {
    std::transform(mode.begin(), mode.end(), mode.begin(),
                   [](unsigned char c) { return std::toupper(c); });
    if (mode == "N")
      return *this;
    require(mode == "T" || mode == "C", "transpose must be N, T, or C",
            "ValueError");
    matrix_shape();
    auto out = permute({1, 0});
    return mode == "C" ? out.map([](Complex z) { return std::conj(z); }) : out;
  }
  Array matmul(const Array &b) const {
    require(dtype == b.dtype, "operand dtypes must match", "TypeError");
    auto [m, k] = matrix_shape();
    auto [l, n] = b.matrix_shape();
    require(k == l, "matrix contraction dimensions differ");
    auto out = zeros(dtype, {m, n});
    for (std::size_t i = 0; i < m; ++i)
      for (std::size_t j = 0; j < n; ++j) {
        Complex z = 0.;
        for (std::size_t t = 0; t < k; ++t)
          z += values[i * k + t] * b.values[t * n + j];
        out.values[i * n + j] = cast(dtype, z);
      }
    return out;
  }
  Array einsum(const std::vector<std::string> &al, const Array &b,
               const std::vector<std::string> &bl,
               const std::vector<std::string> &ol) const {
    require(al.size() == shape.size() && bl.size() == b.shape.size(),
            "labels must match operand ranks", "rank_error");
    require(dtype == b.dtype, "operand dtypes must match", "TypeError");
    std::vector<std::string> labels;
    Shape dims;
    auto add = [&](const auto &names, const Shape &s) {
      for (std::size_t j = 0; j < s.size(); ++j) {
        auto it = std::find(labels.begin(), labels.end(), names[j]);
        if (it == labels.end()) {
          labels.push_back(names[j]);
          dims.push_back(s[j]);
        } else
          require(dims[it - labels.begin()] == s[j], "label dimensions differ");
      }
    };
    add(al, shape);
    add(bl, b.shape);
    auto axes = [&](const auto &names) {
      Shape out;
      for (const auto &name : names) {
        auto it = std::find(labels.begin(), labels.end(), name);
        require(it != labels.end(), "unknown output label");
        out.push_back(it - labels.begin());
      }
      return out;
    };
    auto aa = axes(al), ba = axes(bl), oa = axes(ol), sorted = oa;
    std::sort(sorted.begin(), sorted.end());
    require(std::adjacent_find(sorted.begin(), sorted.end()) == sorted.end(),
            "repeated output label");
    Shape s;
    for (auto i : oa)
      s.push_back(dims[i]);
    auto out = zeros(dtype, s);
    auto sa = strides(shape), sb = strides(b.shape), sc = strides(s);
    for (std::size_t f = 0; f < size(dims); ++f) {
      auto c = coords(f, dims);
      auto flat = [&](const auto &ax, const auto &st) {
        std::size_t n = 0;
        for (std::size_t j = 0; j < ax.size(); ++j)
          n += c[ax[j]] * st[j];
        return n;
      };
      out.values[flat(oa, sc)] += values[flat(aa, sa)] * b.values[flat(ba, sb)];
    }
    for (auto &z : out.values)
      z = cast(dtype, z);
    return out;
  }
  double norm() const {
    double n = 0.;
    for (auto z : values)
      n = std::hypot(n, std::abs(z));
    return n;
  }
  Array unfold(std::size_t mode) const {
    require(mode < shape.size(), "mode outside tensor rank", "rank_error");
    Shape axes{mode}, other;
    for (std::size_t i = 0; i < shape.size(); ++i)
      if (i != mode) {
        axes.push_back(i);
        other.push_back(shape[i]);
      }
    return permute(axes).reshape({shape[mode], size(other)});
  }
  Array mode_product(const Array &b, std::size_t mode) const {
    auto [r, n] = b.matrix_shape();
    require(mode < shape.size() && shape[mode] == n,
            "mode product dimensions differ");
    auto product = b.matmul(unfold(mode));
    Shape axes{mode};
    for (std::size_t i = 0; i < shape.size(); ++i)
      if (i != mode)
        axes.push_back(i);
    auto s = shape;
    s[mode] = r;
    Shape ordered, inverse(axes.size());
    for (std::size_t i = 0; i < axes.size(); ++i) {
      ordered.push_back(s[axes[i]]);
      inverse[axes[i]] = i;
    }
    return product.reshape(ordered).permute(inverse);
  }
};
inline Array blend(const Array &product, const Array &original, Complex alpha,
                   Complex beta) {
  require(product.shape == original.shape && product.dtype == original.dtype,
          "output has incorrect shape or dtype");
  if (beta == Complex(0.))
    return product.map([&](Complex z) { return alpha * z; });
  return product.zip(
      original, [&](Complex x, Complex y) { return alpha * x + beta * y; });
}
} // namespace sage_cpp::api
