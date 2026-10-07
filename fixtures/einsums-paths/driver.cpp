// Production library decisions are instrumented directly; no floating arithmetic is symbolically modeled.
#include "proof_contract.hpp"
#include <stdio.h>
#include <string.h>
extern "C" __attribute__((noinline)) long long library_decision(const unsigned char *raw) {
  uint64_t a, b;
  memcpy(&a, raw + 4, 8); memcpy(&b, raw + 12, 8);
  if (raw[0] == 0)
    return sage_cpp::contract::frequency_bin(raw[1], raw[2], raw[3] != 0);
  if (raw[0] == 1) {
    if (!sage_cpp::contract::finite_bits(a) || !sage_cpp::contract::finite_bits(b)) return -999;
    return sage_cpp::contract::greater_magnitude(a, b);
  }
  return sage_cpp::contract::dyad_bits(a);
}
int main(int argc, char **argv) {
  if (argc != 2) return 64;
  FILE *fp = fopen(argv[1], "rb"); if (!fp) return 65;
  unsigned char raw[21] = {0}; size_t n = fread(raw, 1, sizeof(raw), fp); fclose(fp);
  if (n != 20 || raw[0] > 2) return 65;
  if (raw[0] == 0 && (raw[1] == 0 || raw[1] > 64 || raw[2] >= raw[1])) return 65;
  long long result = library_decision(raw);
  if (result == -999) return 65;
  printf("%lld\n", result); return 0;
}
