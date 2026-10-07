#pragma once
#include "array.hpp"
#include "proof_contract.hpp"
#include <bit>
#include "../tensor.hpp"
#include <optional>

namespace sage_cpp::api {
// Public API bridge to the proved Tensor methods, restricted to the proof domain.
inline bool proof_dyad(double x) {
  return contract::dyad_bits(std::bit_cast<std::uint64_t>(x));
}
inline contract::Metadata proof_metadata(const Array &a) {
  return {a.dtype == DType::Float64, a.shape.size(),
          a.shape.empty() ? 0 : a.shape[0], a.shape.size() < 2 ? 0 : a.shape[1],
          a.values.size(), std::all_of(a.values.begin(), a.values.end(), [](Complex z) {
            return z.imag() == 0. && proof_dyad(z.real());
          })};
}
inline std::optional<Array> bounded_tensor(unsigned op, const Array &a,
                                         const Array *b, double scalar) {
  const bool binary = op == 1 || op == 2 || op == 4;
  if (!contract::route(op, b ? 2u : 1u, proof_metadata(a),
      proof_metadata(b ? *b : a), proof_dyad(scalar))) return std::nullopt;
  double av[16]{}, bv[16]{};
  for (std::size_t i = 0; i < a.values.size(); ++i) av[i] = a.values[i].real();
  if (binary)
    for (std::size_t i = 0; i < b->values.size(); ++i) bv[i] = b->values[i].real();
  auto ta = sage_cpp::Tensor::from_values(
      a.shape[0], a.shape[1], std::span<const double>(av, a.values.size()));
  auto out = ta.copy();
  if (binary) {
    auto tb = sage_cpp::Tensor::from_values(
        b->shape[0], b->shape[1], std::span<const double>(bv, b->values.size()));
    if (op == 1) out = ta.added(tb);
    if (op == 2) out = ta.multiplied(tb);
    if (op == 4) out = ta.matmul(tb);
  } else if (op == 3) out = ta.transposed();
  else if (op == 5) out = ta.scaled(scalar);
  std::vector<Complex> values;
  for (double x : out.values()) values.emplace_back(x, 0.);
  return Array(DType::Float64, {out.rows(), out.cols()}, std::move(values));
}
} // namespace sage_cpp::api
