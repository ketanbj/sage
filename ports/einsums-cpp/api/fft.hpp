#pragma once
#include "array.hpp"
#include <numbers>
namespace sage_cpp::api {
inline Array transform(const Array &a, const std::string &op, std::size_t n) {
  require(a.shape.size() == 1, "FFT requires a vector", "rank_error");
  require(n > 0, "FFT length must be positive", "ValueError");
  require(op == "fft" || op == "ifft" || op == "rfft" || op == "irfft",
          "unknown FFT operation", "ValueError");
  bool inverse = op == "ifft" || op == "irfft";
  if (op == "rfft")
    require(!is_complex(a.dtype), "rfft requires real input", "TypeError");
  std::vector<Complex> input(n);
  for (std::size_t i = 0; i < std::min(n, a.values.size()); ++i)
    input[i] = a.values[i];
  if (op == "irfft")
    for (std::size_t i = n / 2 + 1; i < n; ++i)
      input[i] = std::conj(input[n - i]);
  auto count = op == "rfft" ? n / 2 + 1 : n;
  auto out = Array::zeros(
      op == "irfft" ? real_dtype(a.dtype) : complex_dtype(a.dtype), {count});
  for (std::size_t k = 0; k < count; ++k) {
    Complex sum = 0.;
    for (std::size_t j = 0; j < n; ++j) {
      double angle = (inverse ? 1. : -1.) * 2. * std::numbers::pi *
                     static_cast<double>(k) * static_cast<double>(j) /
                     static_cast<double>(n);
      sum += input[j] * std::polar(1., angle);
    }
    out.values[k] = cast(out.dtype, sum);
  }
  return out; // Einsums inverse transforms deliberately remain unnormalized.
}
inline Array frequencies(std::size_t n, double d, bool real = false) {
  require(n > 0 && d != 0. && std::isfinite(d),
          "frequency coordinates require positive n and finite nonzero spacing",
          "ValueError");
  auto out = Array::zeros(DType::Float64, {real ? n / 2 + 1 : n});
  for (std::size_t i = 0; i < out.values.size(); ++i)
    out.values[i] = (real || i < (n + 1) / 2
                         ? static_cast<double>(i)
                         : static_cast<double>(i) - static_cast<double>(n)) /
                    (static_cast<double>(n) * d);
  return out;
}
} // namespace sage_cpp::api
