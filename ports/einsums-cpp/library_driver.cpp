#include "api/api.hpp"
#include "api/bounded_tensor.hpp"
#include <array>
#include <fstream>
#include <iostream>
using namespace sage_cpp::api;
static Array run(const std::array<unsigned char, 36> &bytes) {
  auto op = bytes[0];
  std::size_t m = bytes[1], k = bytes[2], n = bytes[3];
  require(op < 23 && m >= 1 && m <= 4 && k >= 1 && k <= 4 && n >= 1 && n <= 4,
          "invalid profile input");
  std::vector<Complex> v;
  for (std::size_t i = 4; i < bytes.size(); ++i)
    v.push_back((bytes[i] < 128 ? static_cast<int>(bytes[i])
                                : static_cast<int>(bytes[i]) - 256) /
                8.);
  auto make = [&](Shape s, std::size_t offset) {
    auto count = size(s);
    return Array(DType::Float64, s,
                 {v.begin() + offset, v.begin() + offset + count});
  };
  auto a = make({m, k}, 0), b = make(op == 4 ? Shape{k, n} : Shape{m, k}, 16);
  if (op <= 5) {
    auto proved = bounded_tensor(op, a, &b, v[16].real());
    if (proved) return std::move(*proved);
  }
  auto scalar = [](double x) {
    return Array(DType::Float64, {1, 1}, {Complex(x)});
  };
  switch (op) {
  case 0:
    return a;
  case 1:
    return a.zip(b, [](auto x, auto y) { return x + y; });
  case 2:
    return a.zip(b, [](auto x, auto y) { return x * y; });
  case 3:
    return a.transpose();
  case 4:
    return a.matmul(b);
  case 5:
    return a.map([&](auto x) { return x * v[16]; });
  case 6:
    return a.zip(b, [](auto x, auto y) { return x - y; });
  case 7:
    return a.zip(b, [](auto x, auto y) { return x / (std::abs(y) + 1.); });
  case 8:
    return a.map([](auto x) { return -x; });
  case 9: {
    auto out = Array::zeros(a.dtype, {m, 1});
    for (std::size_t i = 0; i < m; ++i)
      out.values[i] = a.values[i * k];
    return out;
  }
  case 10: {
    Complex sum = 0.;
    for (std::size_t i = 0; i < a.values.size(); ++i)
      sum += a.values[i] * b.values[i];
    return scalar(sum.real());
  }
  case 11:
    return a.zip(b, [](auto x, auto y) { return 2. * x + y; });
  case 12:
    return a.zip(b, [](auto x, auto y) { return 2. * x - .5 * y; });
  case 13:
    return a.matmul(make({k, 1}, 16));
  case 14: {
    auto out = a;
    for (std::size_t i = 0; i < m * k; ++i)
      out.values[i] += 2. * v[i / k] * v[16 + i % k];
    return out;
  }
  case 15:
    return scalar(a.norm());
  case 16:
    return scalar(a.zip(b, [](auto x, auto y) { return x - y; }).norm() /
                  std::sqrt(m * k));
  case 17:
  case 18:
  case 19: {
    auto gram = a.matmul(a.transpose());
    for (std::size_t i = 0; i < m; ++i)
      gram.values[i * m + i] += 1.;
    if (op == 17)
      return inverse(gram);
    if (op == 18)
      return eigh(gram)[0].reshape({1, m});
    auto packed = qr(gram);
    auto f = unpack_qr(packed[0], packed[1]);
    return f[0].matmul(f[1]);
  }
  case 20:
  case 21: {
    auto input = Array::zeros(DType::Complex128, {k});
    for (std::size_t i = 0; i < k; ++i)
      input.values[i] = {v[i].real(), v[16 + i].real()};
    auto transformed = transform(input, op == 20 ? "fft" : "ifft", k);
    auto out = Array::zeros(DType::Float64, {k, 2});
    for (std::size_t i = 0; i < k; ++i) {
      out.values[i * 2] = transformed.values[i].real();
      out.values[i * 2 + 1] = transformed.values[i].imag();
    }
    return out;
  }
  case 22:
    return frequencies(k, 1.).reshape({1, k});
  default:
    throw Error("ValueError", "unsupported profile operation");
  }
}
int main(int argc, char **argv) {
  if (argc != 2)
    return 64;
  try {
    std::ifstream stream(argv[1], std::ios::binary);
    std::array<unsigned char, 36> input{};
    stream.read(reinterpret_cast<char *>(input.data()), input.size());
    require(stream.gcount() == 36 &&
                stream.peek() == std::char_traits<char>::eof(),
            "profile expects 36 bytes");
    auto out = run(input);
    Json values = Json::array();
    for (std::size_t i = 0; i < out.shape[0]; ++i) {
      Json row = Json::array();
      for (std::size_t j = 0; j < out.shape[1]; ++j)
        row.push_back(out.values[i * out.shape[1] + j].real());
      values.push_back(row);
    }
    std::cout << Json({{"shape", Json::array({out.shape})},
                       {"strides", Json::array({strides(out.shape)})},
                       {"values", values}})
                     .dump()
              << '\n';
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 65;
  }
}
