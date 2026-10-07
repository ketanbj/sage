#ifndef SAGE_CPU_API_H
#define SAGE_CPU_API_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#define SAGE_API_NOEXCEPT noexcept
#else
#define SAGE_API_NOEXCEPT
#endif
/* Both independent backends export this ABI. Link/load exactly one backend.
 * input must identify length readable bytes. Null input or length>PTRDIFF_MAX
 * returns null. Malformed requests produce an owned UTF-8 JSON error envelope.
 * Success returns an owned NUL-terminated UTF-8 JSON envelope. Input storage is
 * borrowed only for the call. Release each result once in its originating library.
 * Null result denotes inability to produce a response. Null free is allowed.
 * Independent calls may overlap. Caller-owned mutation/free must be serialized. */
char *sage_api_request(const void *input, size_t length) SAGE_API_NOEXCEPT;
void sage_api_free(char *value) SAGE_API_NOEXCEPT;
#undef SAGE_API_NOEXCEPT
#ifdef __cplusplus
}
#endif
#endif
