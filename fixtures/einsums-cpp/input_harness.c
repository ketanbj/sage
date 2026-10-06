/* SymSan input-contract harness. Einsums itself executes as native C++.
 * Decoding active tensor regions supplies symbolic loop bounds. Padding has no
 * semantics; never count bootstrap inputs as generated validation evidence. */
#include <stdio.h>
#include <stddef.h>
extern int einsums_kernel(const unsigned char *bytes);

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    FILE *fp = fopen(argv[1], "rb");
    if (!fp) return 65;
    unsigned char raw[37] = {0}, decoded[36] = {0};
    size_t size = fread(raw, 1, sizeof(raw), fp);
    fclose(fp);
    if (size != 36) return 65;
    unsigned op = raw[0], m = raw[1], k = raw[2], n = raw[3];
    if (op > 5 || m < 1 || m > 4 || k < 1 || k > 4 || n < 1 || n > 4) return 65;
    for (size_t i = 0; i < 4; ++i) decoded[i] = raw[i];
    for (size_t i = 0; i < m*k; ++i) decoded[4+i] = raw[4+i];
    unsigned b_size = op == 4 ? k*n : m*k;
    for (size_t i = 0; i < b_size; ++i) decoded[20+i] = raw[20+i];
    return einsums_kernel(decoded);
}
