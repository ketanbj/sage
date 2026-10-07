#pragma once
#include <stddef.h>
#include <stdint.h>
namespace sage_cpp { namespace contract {
inline bool finite_bits(uint64_t bits) {
  return (bits & 0x7ff0000000000000ULL) != 0x7ff0000000000000ULL;
}
inline bool dyad_bits(uint64_t bits) {
  if (bits == 0) return true;
  uint64_t exponent = (bits >> 52) & 2047;
  if (exponent < 1020 || exponent > 1027) return false;
  uint64_t mantissa = (bits & 0x000fffffffffffffULL) | (1ULL << 52);
  uint64_t shift = 1072 - exponent;
  if ((mantissa & ((1ULL << shift) - 1)) != 0) return false;
  uint64_t units = mantissa >> shift;
  return units <= ((bits >> 63) == 0 ? 127u : 128u);
}
inline bool greater_magnitude(uint64_t a, uint64_t b) {
  if ((a & 0x7fffffffffffffffULL) > (b & 0x7fffffffffffffffULL)) return true;
  return false;
}
struct Metadata {
  bool f64; size_t rank, rows, cols, values; bool dyadic;
};
inline bool eligible(Metadata a) {
  return a.f64 && a.rank == 2 && a.rows >= 1 && a.rows <= 4 && a.cols >= 1 &&
         a.cols <= 4 && a.values == a.rows * a.cols && a.dyadic;
}
inline bool route(unsigned op, size_t arity, Metadata a, Metadata b, bool scalar) {
  bool binary = op == 1 || op == 2 || op == 4;
  return op < 6 && arity == (binary ? 2u : 1u) && eligible(a) &&
    (!binary || (eligible(b) && (op == 4 ? a.cols == b.rows :
      a.rows == b.rows && a.cols == b.cols))) && (op != 5 || scalar);
}
// Precondition: 0 < n <= INT64_MAX, i < n. Also used by rfftfreq.
inline int64_t frequency_bin(size_t n, size_t i, bool real) {
  return real || i < n / 2 + n % 2 ? static_cast<int64_t>(i) :
    -static_cast<int64_t>(n - i);
}
} }
