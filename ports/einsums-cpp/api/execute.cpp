#include "execute.hpp"
#include "bounded_tensor.hpp"
#include "decomposition.hpp"
#include "fft.hpp"
#include "storage.hpp"
#include <cstdlib>
#include <cstring>
#include <random>
namespace sage_cpp::api {
static double number(const Json &j) {
  if (j.is_number())
    return j.get<double>();
  if (j == "NaN")
    return std::numeric_limits<double>::quiet_NaN();
  if (j == "Infinity")
    return std::numeric_limits<double>::infinity();
  if (j == "-Infinity")
    return -std::numeric_limits<double>::infinity();
  throw Error("ValueError", "invalid floating value");
}
static Json number(double x) {
  if (std::isfinite(x))
    return x;
  if (std::isnan(x))
    return "NaN";
  return x > 0 ? "Infinity" : "-Infinity";
}
static Complex pair(const Json &j) {
  require(j.is_array() && j.size() == 2, "complex value must be a pair",
          "ValueError");
  return {number(j[0]), number(j[1])};
}
static Json pair(Complex z) {
  return Json::array({number(z.real()), number(z.imag())});
}
Array decode_array(const Json &j) {
  auto d = dtype_from_name(j.at("dtype").get<std::string>());
  Shape s;
  for (const auto &n : j.at("shape")) {
    require(n.is_number_unsigned() ||
                (n.is_number_integer() && n.get<long long>() >= 0),
            "shape must contain nonnegative integers", "ValueError");
    s.push_back(n.get<std::size_t>());
  }
  size(s);
  std::vector<Complex> v;
  for (const auto &p : j.at("values")) {
    auto z = pair(p);
    require(is_complex(d) || z.imag() == 0.,
            "real array contains imaginary values", "TypeError");
    v.push_back(z);
  }
  return {d, s, v};
}
Json encode_array(const Array &a) {
  Json v = Json::array();
  for (auto z : a.values)
    v.push_back(pair(z));
  return {{"dtype", dtype_name(a.dtype)}, {"shape", a.shape}, {"values", v}};
}
struct Request {
  std::string op;
  std::vector<Array> arrays;
  Json params;
  explicit Request(const Json &j)
      : op(j.at("op").get<std::string>()),
        params(j.value("params", Json::object())) {
    require(params.is_object(), "params must be an object", "ValueError");
    for (const auto &a : j.value("arrays", Json::array()))
      arrays.push_back(decode_array(a));
  }
  const Array &a(std::size_t i) const {
    require(i < arrays.size(), "missing array argument", "ValueError");
    return arrays[i];
  }
  std::string text(const std::string &key,
                   const std::string &fallback = "") const {
    return params.value(key, fallback);
  }
  double floating(const std::string &key, double fallback) const {
    return params.contains(key) ? number(params[key]) : fallback;
  }
  std::size_t integer(const std::string &key, std::size_t fallback = 0) const {
    if (!params.contains(key))
      return fallback;
    const auto &x = params[key];
    require(x.is_number_unsigned() ||
                (x.is_number_integer() && x.get<long long>() >= 0),
            key + " must be nonnegative integer", "ValueError");
    return x.get<std::size_t>();
  }
  Shape ints(const std::string &key) const {
    Shape out;
    if (params.contains(key))
      for (const auto &x : params[key]) {
        require(x.is_number_unsigned() ||
                    (x.is_number_integer() && x.get<long long>() >= 0),
                key + " must contain nonnegative integers", "ValueError");
        out.push_back(x.get<std::size_t>());
      }
    return out;
  }
  std::vector<std::string> labels(const std::string &key) const {
    if (!params.contains(key))
      return {};
    if (params[key].is_string()) {
      std::vector<std::string> out;
      for (char c : params[key].get<std::string>())
        out.push_back(std::string(1, c));
      return out;
    }
    return params[key].get<std::vector<std::string>>();
  }
  Complex z(const std::string &key, Complex fallback) const {
    if (!params.contains(key))
      return fallback;
    return params[key].is_array() ? pair(params[key])
                                  : Complex(number(params[key]));
  }
  DType dtype() const { return dtype_from_name(text("dtype", "float64")); }
};
struct Response {
  std::vector<Array> arrays;
  std::vector<Complex> scalars;
  Shape indices;
  Json json() const {
    Json a = Json::array(), s = Json::array();
    for (const auto &v : arrays)
      a.push_back(encode_array(v));
    for (auto z : scalars)
      s.push_back(pair(z));
    return {{"arrays", a}, {"scalars", s}, {"indices", indices}};
  }
};
Json execute(const Json &request) {
  Request r(request);
  const auto &op = r.op;
  const bool unary = op == "copy" || op == "permute" || op == "scale" || op == "negate";
  const bool binary = op == "add" || op == "subtract" || op == "multiply" || op == "divide" || op == "matmul";
  require((!unary || r.arrays.size() == 1) && (!binary || r.arrays.size() == 2),
          "wrong number of array arguments", "ValueError");
  auto alpha = r.z("alpha", 1.), beta = r.z("beta", 0.);
  Response out;
  auto result = [&](Array a) { out.arrays.push_back(std::move(a)); };
  auto scalar = [&](Complex z) { out.scalars.push_back(z); };
  unsigned proved_op = 6;
  if (op == "copy") proved_op = 0;
  if (op == "add") proved_op = 1;
  if (op == "multiply") proved_op = 2;
  if (op == "permute" && r.params.value("axes", Json()) == Json::array({1, 0}))
    proved_op = 3;
  if (op == "matmul" && r.text("trans_a", "N") == "N" &&
      r.text("trans_b", "N") == "N") proved_op = 4;
  if (op == "scale" && alpha.imag() == 0.) proved_op = 5;
  bool proved_binary = proved_op == 1 || proved_op == 2 || proved_op == 4;
  if (proved_op < 6 && r.arrays.size() == (proved_binary ? 2u : 1u)) {
    auto proved = bounded_tensor(proved_op, r.arrays[0],
                                 proved_binary ? &r.arrays[1] : nullptr, alpha.real());
    if (proved) {
      result(std::move(*proved));
      return out.json();
    }
  }
  if (op == "copy")
    result(r.a(0));
  else if (op == "add" || op == "subtract" || op == "multiply" ||
           op == "divide")
    result(r.a(0).zip(r.a(1), [&](Complex x, Complex y) {
      if (!is_complex(r.a(0).dtype)) {
        double a = x.real(), b = y.real();
        return Complex(op == "add"        ? a + b
                       : op == "subtract" ? a - b
                       : op == "multiply" ? a * b
                                          : a / b);
      }
      return op == "add"        ? x + y
             : op == "subtract" ? x - y
             : op == "multiply" ? x * y
                                : x / y;
    }));
  else if (op == "scale" || op == "negate" || op == "conjugate" ||
           op == "pow" || op == "exp" || op == "log" || op == "sqrt" ||
           op == "abs") {
    auto a = r.a(0);
    result(a.map([&](Complex x) {
      if (op == "scale")
        return alpha * x;
      if (op == "negate")
        return -x;
      if (op == "conjugate")
        return std::conj(x);
      if (op == "abs")
        return Complex(std::abs(x));
      if (op == "exp")
        return std::exp(x);
      if (op == "pow")
        return is_complex(a.dtype) ? std::pow(x, alpha)
                                   : Complex(std::pow(x.real(), alpha.real()));
      if (op == "log")
        return is_complex(a.dtype) ? std::log(x) : Complex(std::log(x.real()));
      return is_complex(a.dtype) ? std::sqrt(x) : Complex(std::sqrt(x.real()));
    }));
    if (op == "abs")
      out.arrays[0].dtype = real_dtype(a.dtype);
  } else if (op == "reshape")
    result(r.a(0).reshape(r.ints("shape")));
  else if (op == "permute")
    result(r.a(0).permute(r.ints("axes")));
  else if (op == "einsum") {
    auto p = r.a(0).einsum(r.labels("a_labels"), r.a(1), r.labels("b_labels"),
                           r.labels("out_labels"));
    result(r.arrays.size() > 2 ? blend(p, r.a(2), alpha, beta)
                               : p.map([&](Complex z) { return alpha * z; }));
  } else if (op == "gemm" || op == "matmul") {
    auto p = r.a(0)
                 .transpose(r.text("trans_a", "N"))
                 .matmul(r.a(1).transpose(r.text("trans_b", "N")));
    result(r.arrays.size() > 2 ? blend(p, r.a(2), alpha, beta) : p);
  } else if (op == "gemv") {
    auto a = r.a(0).transpose(r.text("trans_a", "N"));
    auto b = r.a(1);
    require(b.shape.size() == 1, "gemv requires a vector", "rank_error");
    result(blend(a.matmul(b.reshape({b.shape[0], 1})).reshape({a.shape[0]}),
                 r.a(2), alpha, beta));
  } else if (op == "axpy" || op == "axpby")
    result(blend(r.a(0), r.a(1), alpha, op == "axpy" ? Complex(1.) : beta));
  else if (op == "direct_product")
    result(blend(r.a(0).zip(r.a(1), [](Complex x, Complex y) { return x * y; }),
                 r.a(2), alpha, beta));
  else if (op == "ger") {
    require(r.a(0).shape.size() == 1 && r.a(1).shape.size() == 1,
            "ger requires vectors", "rank_error");
    result(blend(r.a(0).einsum({"i"}, r.a(1), {"j"}, {"i", "j"}), r.a(2), alpha,
                 1.));
  } else if (op == "scale_row" || op == "scale_column") {
    auto a = r.a(0);
    auto [m, n] = a.matrix_shape();
    auto i = r.integer("index");
    bool row = op == "scale_row";
    require(i < (row ? m : n), "row/column index out of bounds");
    for (std::size_t j = 0; j < (row ? n : m); ++j) {
      auto idx = row ? i * n + j : j * n + i;
      a.values[idx] = cast(a.dtype, alpha * a.values[idx]);
    }
    result(a);
  } else if (op == "sum" || op == "dot" || op == "true_dot") {
    auto a =
        op == "sum" ? r.a(0) : r.a(0).zip(r.a(1), [&](Complex x, Complex y) {
          return (op == "true_dot" ? std::conj(x) : x) * y;
        });
    Complex sum = 0.;
    for (auto z : a.values)
      sum += z;
    scalar(sum);
  } else if (op == "vec_norm")
    scalar(r.a(0).norm());
  else if (op == "rmsd") {
    require(!r.a(0).values.empty(), "RMSD of empty arrays is undefined",
            "ValueError");
    scalar(
        r.a(0).zip(r.a(1), [](Complex x, Complex y) { return x - y; }).norm() /
        std::sqrt(r.a(0).values.size()));
  } else if (op == "sum_square") {
    const auto &a = r.a(0);
    require(a.shape.size() == 1, "sum_square requires a vector", "rank_error");
    double s = 0., sum = 0.;
    for (auto z : a.values)
      s = std::max({s, std::abs(z.real()), std::abs(z.imag())});
    if (s != 0.)
      for (auto z : a.values)
        sum += std::norm(z / s);
    scalar(sum);
    scalar(s);
  } else if (op == "norm") {
    const auto &a = r.a(0);
    auto [m, n] = a.matrix_shape();
    auto kind = r.text("kind", "FROBENIUS");
    double value = 0.;
    if (kind == "FROBENIUS")
      value = a.norm();
    else if (kind == "MAXABS")
      for (auto z : a.values)
        value = std::max(value, std::abs(z));
    else if (kind == "ONE")
      for (std::size_t j = 0; j < n; ++j) {
        double sum = 0.;
        for (std::size_t i = 0; i < m; ++i)
          sum += std::abs(a.values[i * n + j]);
        value = std::max(value, sum);
      }
    else if (kind == "INFINITY")
      for (std::size_t i = 0; i < m; ++i) {
        double sum = 0.;
        for (std::size_t j = 0; j < n; ++j)
          sum += std::abs(a.values[i * n + j]);
        value = std::max(value, sum);
      }
    else
      throw Error("ValueError", "unknown norm");
    scalar(value);
  } else if (op == "getrf") {
    auto [a, p] = lu(r.a(0));
    result(a);
    out.indices = p;
  } else if (op == "extract_plu")
    out.arrays = extract_plu(r.a(0), r.ints("pivots"));
  else if (op == "getri")
    result(lu_inverse(r.a(0), r.ints("pivots")));
  else if (op == "invert")
    result(inverse(r.a(0)));
  else if (op == "solve" || op == "gesv") {
    auto x = solve(r.a(0), r.a(1));
    if (op == "gesv") {
      auto [a, p] = lu(r.a(0));
      result(a);
      out.indices = p;
    }
    result(x);
  } else if (op == "det")
    scalar(determinant(r.a(0)));
  else if (op == "qr")
    out.arrays = qr(r.a(0));
  else if (op == "q" || op == "r") {
    auto f = unpack_qr(r.a(0), r.a(1));
    result(f[op == "q" ? 0 : 1]);
  } else if (op == "syev" || op == "heev")
    out.arrays = eigh(r.a(0));
  else if (op == "geev")
    out.arrays = geev(r.a(0));
  else if (op == "svd" || op == "svd_dd")
    out.arrays = svd(r.a(0), r.text("job", "ALL") == "ALL");
  else if (op == "truncated_svd") {
    auto f = svd(r.a(0), false);
    auto k = r.integer("k");
    require(k <= f[1].values.size(), "truncation rank exceeds dimension");
    auto n = f[2].shape[1];
    result(first_columns(f[0], k));
    result(
        Array(f[1].dtype, {k}, {f[1].values.begin(), f[1].values.begin() + k}));
    result(Array(f[2].dtype, {k, n},
                 {f[2].values.begin(), f[2].values.begin() + k * n}));
  } else if (op == "truncated_syev") {
    auto f = eigh(r.a(0));
    auto n = f[0].values.size(), k = r.integer("k");
    require(k <= n, "truncation rank exceeds dimension");
    Shape order(n);
    std::iota(order.begin(), order.end(), 0);
    std::stable_sort(order.begin(), order.end(), [&](auto i, auto j) {
      return std::abs(f[0].values[i]) > std::abs(f[0].values[j]);
    });
    auto w = Array::zeros(f[0].dtype, {k}),
         v = Array::zeros(f[1].dtype, {n, k});
    for (std::size_t j = 0; j < k; ++j) {
      w.values[j] = f[0].values[order[j]];
      for (std::size_t i = 0; i < n; ++i)
        v.values[i * k + j] = f[1].values[i * n + order[j]];
    }
    result(v);
    result(w);
  } else if (op == "pseudoinverse")
    result(pseudoinverse(r.a(0), r.floating("tol", 1e-12)));
  else if (op == "svd_nullspace")
    result(nullspace(r.a(0),
                     r.floating("tol", (is_low(r.a(0).dtype) ? 1e-6 : 1e-12) *
                                           std::max(r.a(0).norm(), 1.))));
  else if (op == "solve_continuous_lyapunov")
    result(lyapunov(r.a(0), r.a(1)));
  else if (op == "cholesky")
    result(cholesky(r.a(0)));
  else if (op == "matrix_power")
    result(matrix_power(
        r.a(0), alpha,
        r.floating("cutoff", is_low(r.a(0).dtype)
                                 ? std::numeric_limits<float>::epsilon()
                                 : std::numeric_limits<double>::epsilon())));
  else if (op == "unfold")
    result(r.a(0).unfold(r.integer("mode")));
  else if (op == "mode_product")
    result(r.a(0).mode_product(r.a(1), r.integer("mode")));
  else if (op == "khatri_rao")
    result(khatri_rao(r.a(0), r.a(1)));
  else if (op == "tucker" || op == "hooi")
    out.arrays = tucker(r.a(0), r.ints("ranks"),
                        op == "tucker" ? 0 : r.integer("iterations", 100),
                        r.floating("tol", 1e-8));
  else if (op == "cp")
    out.arrays = cp(r.a(0), r.integer("rank", 1), r.integer("iterations", 100),
                    r.floating("tol", 1e-8));
  else if (op == "weight_tensor")
    result(weight_tensor(r.a(0), r.a(1)));
  else if (op == "weighted_parafac")
    out.arrays =
        weighted_parafac(r.a(0), r.a(1), r.integer("rank", 1),
                         r.integer("iterations", 100), r.floating("tol", 1e-8));
  else if (op == "reconstruct_tucker") {
    require(!r.arrays.empty(), "missing core", "ValueError");
    result(reconstruct_tucker(r.a(0), {r.arrays.begin() + 1, r.arrays.end()}));
  } else if (op == "reconstruct_cp")
    result(reconstruct_cp(r.arrays));
  else if (op == "write_hdf5")
    write_hdf5(r.text("path"), r.text("name", "tensor"), r.a(0),
               r.params.value("overwrite", false));
  else if (op == "read_hdf5")
    result(read_hdf5(r.text("path"), r.text("name", "tensor")));
  else if (op == "tile_dense") {
    auto partitions = r.params.at("partitions").get<std::vector<Shape>>(),
         indices = r.params.at("indices").get<std::vector<Shape>>();
    require(indices.size() == r.arrays.size(),
            "tile indices/data length differ");
    TiledTensor t(r.dtype(), partitions);
    for (std::size_t i = 0; i < indices.size(); ++i)
      t.insert(indices[i], r.a(i));
    result(t.to_dense());
  } else if (op == "block_dense") {
    auto blocks = r.ints("blocks");
    require(blocks.size() == r.arrays.size(), "block sizes/data length differ");
    BlockTensor t(r.dtype(), r.integer("rank", 2), blocks);
    for (std::size_t i = 0; i < blocks.size(); ++i)
      t.insert(i, r.a(i));
    result(t.to_dense());
  } else if (op == "zeros")
    result(Array::zeros(r.dtype(), r.ints("shape")));
  else if (op == "identity")
    result(Array::identity(r.dtype(), r.integer("n")));
  else if (op == "diagonal") {
    const auto &a = r.a(0);
    if (a.shape.size() == 1) {
      auto n = a.shape[0];
      auto d = Array::zeros(a.dtype, {n, n});
      for (std::size_t i = 0; i < n; ++i)
        d.values[i * n + i] = a.values[i];
      result(d);
    } else {
      auto [m, n] = a.matrix_shape();
      auto d = Array::zeros(a.dtype, {std::min(m, n)});
      for (std::size_t i = 0; i < d.values.size(); ++i)
        d.values[i] = a.values[i * n + i];
      result(d);
    }
  } else if (op == "arange") {
    double start = r.floating("start", 0.), stop = r.floating("stop", 0.),
           step = r.floating("step", 1.);
    require(std::isfinite(start) && std::isfinite(stop) &&
                std::isfinite(step) && step != 0.,
            "arange requires finite bounds and nonzero step", "ValueError");
    double n = std::max(std::ceil((stop - start) / step), 0.);
    require(n < static_cast<double>(std::numeric_limits<std::ptrdiff_t>::max()),
            "arange too large");
    auto a = Array::zeros(r.dtype(), {static_cast<std::size_t>(n)});
    for (std::size_t i = 0; i < a.values.size(); ++i)
      a.values[i] = cast(a.dtype, start + i * step);
    result(a);
  } else if (op == "fft" || op == "ifft" || op == "rfft" || op == "irfft") {
    auto length = r.a(0).values.size();
    require(op != "irfft" || length >= 2 || r.params.contains("n"),
            "irfft requires explicit positive length for short input",
            "ValueError");
    result(
        transform(r.a(0), op,
                  r.integer("n", op == "irfft" ? 2 * (length ? length - 1 : 0)
                                               : length)));
  } else if (op == "fftfreq" || op == "rfftfreq")
    result(frequencies(r.integer("n"), r.floating("d", 1.), op == "rfftfreq"));
  else if (op == "random" || op == "random_definite" ||
           op == "random_semidefinite") {
    std::uint64_t seed = r.integer("seed", 1);
    if (seed == 0)
      seed = 1;
    auto next = [&]() {
      seed ^= seed << 13;
      seed ^= seed >> 7;
      seed ^= seed << 17;
      return static_cast<double>(seed >> 11) /
             static_cast<double>(std::uint64_t(1) << 53);
    };
    auto normal = [&]() {
      double magnitude = std::sqrt(
                 -2. * std::log(std::max(next(),
                                         std::numeric_limits<double>::min()))),
             phase = 2. * std::numbers::pi * next();
      return Complex(magnitude * std::cos(phase),
                     is_complex(r.dtype()) ? magnitude * std::sin(phase) : 0.);
    };
    auto n = r.integer("n", 1),
         zeros = op == "random_semidefinite" ? r.integer("force_zeros", 1) : 0;
    require(zeros <= n, "force_zeros exceeds dimension");
    auto a =
        Array::zeros(r.dtype(), op == "random" ? r.ints("shape") : Shape{n, n});
    for (auto &z : a.values)
      z = cast(a.dtype, normal());
    if (op != "random") {
      double mean = r.floating("mean", 1.);
      require(std::isfinite(mean) &&
                  (mean != 0. || op == "random_semidefinite"),
              "definite mean must be finite and nonzero", "ValueError");
      auto packed = qr(a);
      auto q = unpack_qr(packed[0], packed[1])[0];
      auto diagonal = Array::zeros(a.dtype, {n, n});
      double sigma = std::abs(mean) * std::sqrt(std::numbers::pi / 8.);
      for (std::size_t i = zeros; i < n; ++i) {
        double magnitude = 0.;
        for (int j = 0; j < 3; ++j) {
          double z = std::sqrt(-2. * std::log(std::max(
                                         next(),
                                         std::numeric_limits<double>::min()))) *
                     std::cos(2. * std::numbers::pi * next());
          magnitude = std::hypot(magnitude, z);
        }
        diagonal.values[i * n + i] =
            cast(a.dtype, std::copysign(sigma * magnitude, mean));
      }
      a = q.matmul(diagonal).matmul(q.transpose("C"));
    }
    result(a);
  } else
    throw Error("ValueError", "unknown API operation " + op);
  return out.json();
}
} // namespace sage_cpp::api
extern "C" char *sage_api_request(const void *input,
                                  std::size_t length) noexcept {
  if (!input || length > static_cast<std::size_t>(
                             std::numeric_limits<std::ptrdiff_t>::max()))
    return nullptr;
  try {
    using namespace sage_cpp::api;
    Json response;
    try {
      const auto *begin = static_cast<const char *>(input);
      response = {{"ok", execute(Json::parse(begin, begin + length))}};
    } catch (const Error &e) {
      response = {{"error", {{"kind", e.kind}, {"message", e.what()}}}};
    } catch (const Json::exception &e) {
      response = {{"error", {{"kind", "ValueError"}, {"message", e.what()}}}};
    } catch (const std::exception &e) {
      response = {{"error", {{"kind", "RuntimeError"}, {"message", e.what()}}}};
    }
    // Parser diagnostics can include invalid UTF-8 from the rejected input.
    // Keep the error envelope readable instead of turning it into a null result.
    auto text = response.dump(-1, ' ', false, Json::error_handler_t::replace);
    auto *out = static_cast<char *>(std::malloc(text.size() + 1));
    if (!out)
      return nullptr;
    std::memcpy(out, text.c_str(), text.size() + 1);
    return out;
  } catch (...) {
    return nullptr;
  }
}
extern "C" void sage_api_free(char *value) noexcept { std::free(value); }
