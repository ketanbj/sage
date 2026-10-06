#include "api/api.hpp"
#include "api/bounded_tensor.hpp"
#include <cassert>
#include <thread>
using namespace sage_cpp::api;
int main() {
  Array invalid(DType::Float64, {1, 1}, {1.});
  invalid.values.resize(17, 1.);
  assert(!bounded_tensor(0, invalid, nullptr, 1.));
  auto survivor = []() {
    RuntimeTensorD a({2, 3}, {1, 2, 3, 4, 5, 6});
    auto snapshot = a;
    auto view = a.view().slice(1, 2, 3, -1);
    view.at({0, 0}) = 30.;
    assert(snapshot.at({0, 2}) == 3.);
    return view;
  }();
  assert(survivor.at({0, 0}) == 30.);
  assert(survivor.copy().at({1, 2}) == 4.);
  bool caught = false;
  try {
    survivor.readonly().at({0, 0}) = 7.;
  } catch (const Error &) {
    caught = true;
  }
  assert(caught);
  caught = false;
  try {
    survivor.slice(0, 0, 99);
  } catch (const Error &) {
    caught = true;
  }
  assert(caught);
  runtime::initialize({"native-test"});
  assert(runtime::initialized());
  runtime::set("int", "threads", std::int64_t(2));
  assert(std::get<std::int64_t>(runtime::get("int", "threads")) == 2);
  {
    runtime::Section section("native-test");
    section.end();
  }
  assert(runtime::profiles().at("native-test").second == 1);
  std::thread other(
      []() { runtime::set("str", "worker", std::string("ready")); });
  other.join();
  assert(runtime::size() == 2);
  runtime::finalize();
  assert(!runtime::initialized());
  for (auto dtype :
       {DType::Float32, DType::Float64, DType::Complex64, DType::Complex128}) {
    Array a(dtype, {2, 2}, {4., 1., 1., 3.});
    auto chol = cholesky(a);
    assert(a.zip(chol.matmul(chol.transpose("C")), [](auto x, auto y) {
              return x - y;
            }).norm() < 1e-5);
    auto square = matrix_power(a, 2.);
    assert(
        square.zip(a.matmul(a), [](auto x, auto y) { return x - y; }).norm() <
        1e-4);
    Array diagonal(dtype, {2, 2}, {0., 0., 0., 4.});
    auto inv_power = matrix_power(diagonal, -1.);
    assert(inv_power.values[0] == Complex(0.) &&
           std::abs(inv_power.values[3] - Complex(.25)) < 1e-6);
    auto tiles = TiledTensor::from_dense(a, {{1, 1}, {1, 1}});
    assert(tiles.to_dense().values == a.values);
    auto encoded = encode_array(a);
    assert(decode_array(encoded).values == a.values);
  }
  for (const std::string text :
       {"{}", "not JSON", "{\"op\":\"invert\"}",
        "{\"op\":\"zeros\",\"params\":{\"shape\":[-1]}}"}) {
    char *response = sage_api_request(text.data(), text.size());
    assert(response);
    assert(Json::parse(response).contains("error"));
    sage_api_free(response);
  }
  assert(sage_api_request(nullptr, 1) == nullptr);
  sage_api_free(nullptr);
}
