#pragma once
#include "array.hpp"
#include <nlohmann/json.hpp>
namespace sage_cpp::api {
using Json = nlohmann::json;
Json execute(const Json &request);
Array decode_array(const Json &);
Json encode_array(const Array &);
} // namespace sage_cpp::api
// Input is length readable bytes; the returned NUL-terminated string is owned
// by the caller and must be released exactly once with sage_api_free.
extern "C" char *sage_api_request(const void *input,
                                  std::size_t length) noexcept;
extern "C" void sage_api_free(char *value) noexcept;
