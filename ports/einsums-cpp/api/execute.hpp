#pragma once
#include "array.hpp"
#include <nlohmann/json.hpp>
namespace sage_cpp::api {
using Json = nlohmann::json;
Json execute(const Json &request);
Array decode_array(const Json &);
Json encode_array(const Array &);
} // namespace sage_cpp::api
#include "../sage_api.h"
