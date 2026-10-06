#include "linalg.hpp"
#include <Eigen/Dense>
#include <Eigen/Eigenvalues>
#include <Eigen/SVD>
namespace sage_cpp::api {
using Matrix = Eigen::MatrixXcd;
static Matrix matrix(const Array &a) {
  auto [m, n] = a.matrix_shape();
  Matrix out(m, n);
  for (std::size_t i = 0; i < m; ++i)
    for (std::size_t j = 0; j < n; ++j) {
      auto z = a.values[i * n + j];
      require(std::isfinite(z.real()) && std::isfinite(z.imag()),
              "factorizations require finite inputs", "ValueError");
      out(i, j) = z;
    }
  return out;
}
static Array from_matrix(DType d, const Matrix &a) {
  auto out = Array::zeros(d, {static_cast<std::size_t>(a.rows()),
                              static_cast<std::size_t>(a.cols())});
  for (Eigen::Index i = 0; i < a.rows(); ++i)
    for (Eigen::Index j = 0; j < a.cols(); ++j)
      out.values[i * a.cols() + j] = cast(d, a(i, j));
  return out;
}
std::pair<Array, Shape> lu(const Array &input) {
  auto [m, n] = input.matrix_shape();
  matrix(input);
  Array a = input;
  Shape piv;
  for (std::size_t k = 0; k < std::min(m, n); ++k) {
    std::size_t p = k;
    for (std::size_t i = k + 1; i < m; ++i)
      if (std::abs(a.values[i * n + k]) > std::abs(a.values[p * n + k]))
        p = i;
    piv.push_back(p + 1);
    for (std::size_t j = 0; j < n; ++j)
      std::swap(a.values[k * n + j], a.values[p * n + j]);
    if (a.values[k * n + k] == Complex(0.))
      continue;
    for (std::size_t i = k + 1; i < m; ++i) {
      auto f = a.values[i * n + k] / a.values[k * n + k];
      a.values[i * n + k] = f;
      for (std::size_t j = k + 1; j < n; ++j)
        a.values[i * n + j] -= f * a.values[k * n + j];
    }
  }
  return {Array(a.dtype, a.shape, a.values), piv};
}
std::vector<Array> extract_plu(const Array &a, const Shape &piv) {
  auto [m, n] = a.matrix_shape();
  auto k = std::min(m, n);
  require(piv.size() == k, "invalid LU pivot list", "ValueError");
  auto p = Array::identity(a.dtype, m), l = Array::zeros(a.dtype, {m, k}),
       u = Array::zeros(a.dtype, {k, n});
  for (std::size_t i = 0; i < k; ++i) {
    require(piv[i] > 0 && piv[i] <= m, "invalid LU pivot list", "ValueError");
    for (std::size_t j = 0; j < m; ++j)
      std::swap(p.values[i * m + j], p.values[(piv[i] - 1) * m + j]);
  }
  for (std::size_t i = 0; i < m; ++i)
    for (std::size_t j = 0; j < k; ++j)
      l.values[i * k + j] = i == j  ? Complex(1.)
                            : i > j ? a.values[i * n + j]
                                    : Complex(0.);
  for (std::size_t i = 0; i < k; ++i)
    for (std::size_t j = i; j < n; ++j)
      u.values[i * n + j] = a.values[i * n + j];
  return {p, l, u};
}
Array solve(const Array &a, const Array &b) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "coefficient matrix must be square");
  auto bb = b.shape.size() == 1 ? b.reshape({b.shape[0], 1}) : b;
  auto [rows, cols] = bb.matrix_shape();
  (void)cols;
  require(rows == m && a.dtype == b.dtype,
          "right-hand side dimensions/dtype differ");
  if (m == 0)
    return b;
  Matrix mat = matrix(a);
  Eigen::FullPivLU<Matrix> dec(mat);
  dec.setThreshold(0.);
  require(dec.isInvertible(), "coefficient matrix is singular",
          "SingularError");
  Matrix x = dec.solve(matrix(bb));
  auto out = from_matrix(a.dtype, x);
  return b.shape.size() == 1 ? out.reshape({m}) : out;
}
Array inverse(const Array &a) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "inverse requires square matrix");
  return solve(a, Array::identity(a.dtype, n));
}
Array lu_inverse(const Array &a, const Shape &piv) {
  auto f = extract_plu(a, piv);
  return inverse(f[0].transpose().matmul(f[1]).matmul(f[2]));
}
Complex determinant(const Array &a) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "determinant requires square matrix");
  auto [packed, piv] = lu(a);
  Complex z = 1.;
  for (std::size_t i = 0; i < n; ++i)
    z *= packed.values[i * n + i] * (piv[i] == i + 1 ? 1. : -1.);
  return z;
}
std::vector<Array> qr(const Array &a) {
  auto [m, n] = a.matrix_shape();
  matrix(a);
  auto p = a, tau = Array::zeros(a.dtype, {std::min(m, n)});
  for (std::size_t j = 0; j < std::min(m, n); ++j) {
    auto alpha = p.values[j * n + j];
    double tail = 0.;
    for (std::size_t i = j + 1; i < m; ++i)
      tail = std::hypot(tail, std::abs(p.values[i * n + j]));
    if (tail == 0. && alpha.imag() == 0.)
      continue;
    double beta =
        -std::copysign(std::hypot(std::abs(alpha), tail), alpha.real());
    Complex t = (beta - alpha) / beta, divisor = alpha - beta;
    tau.values[j] = t;
    p.values[j * n + j] = beta;
    for (std::size_t i = j + 1; i < m; ++i)
      p.values[i * n + j] /= divisor;
    for (std::size_t c = j + 1; c < n; ++c) {
      Complex dot = p.values[j * n + c];
      for (std::size_t i = j + 1; i < m; ++i)
        dot += std::conj(p.values[i * n + j]) * p.values[i * n + c];
      dot *= std::conj(t);
      p.values[j * n + c] -= dot;
      for (std::size_t i = j + 1; i < m; ++i)
        p.values[i * n + c] -= p.values[i * n + j] * dot;
    }
  }
  return {Array(p.dtype, p.shape, p.values),
          Array(tau.dtype, tau.shape, tau.values)};
}
std::vector<Array> unpack_qr(const Array &a, const Array &tau) {
  auto [m, n] = a.matrix_shape();
  auto k = std::min(m, n);
  require(tau.shape == Shape{k} && tau.dtype == a.dtype,
          "QR tau has incorrect size/dtype");
  auto full = Array::identity(a.dtype, m);
  for (std::size_t j = 0; j < k; ++j)
    for (std::size_t row = 0; row < m; ++row) {
      Complex dot = full.values[row * m + j];
      for (std::size_t i = j + 1; i < m; ++i)
        dot += full.values[row * m + i] * a.values[i * n + j];
      dot *= tau.values[j];
      full.values[row * m + j] -= dot;
      for (std::size_t i = j + 1; i < m; ++i)
        full.values[row * m + i] -= dot * std::conj(a.values[i * n + j]);
    }
  auto q = Array::zeros(a.dtype, {m, k}), r = Array::zeros(a.dtype, {k, n});
  for (std::size_t i = 0; i < m; ++i)
    for (std::size_t j = 0; j < k; ++j)
      q.values[i * k + j] = cast(a.dtype, full.values[i * m + j]);
  for (std::size_t i = 0; i < k; ++i)
    for (std::size_t j = i; j < n; ++j)
      r.values[i * n + j] = a.values[i * n + j];
  return {q, r};
}
std::vector<Array> eigh(const Array &a) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "eigensystem requires square matrix");
  Matrix mat = matrix(a);
  if (n == 0)
    return {Array::zeros(real_dtype(a.dtype), {0}), a};
  for (std::size_t i = 0; i < n; ++i) {
    mat(i, i) = mat(i, i).real();
    for (std::size_t j = 0; j < i; ++j)
      mat(i, j) = std::conj(mat(j, i));
  }
  Eigen::SelfAdjointEigenSolver<Matrix> dec(mat);
  require(dec.info() == Eigen::Success,
          "Hermitian eigensystem did not converge", "ConvergenceError");
  auto w = Array::zeros(real_dtype(a.dtype), {n});
  for (std::size_t i = 0; i < n; ++i)
    w.values[i] = cast(w.dtype, dec.eigenvalues()[i]);
  return {w, from_matrix(a.dtype, dec.eigenvectors())};
}
std::vector<Array> svd(const Array &a, bool full) {
  auto [m, n] = a.matrix_shape();
  auto k = std::min(m, n);
  if (k == 0)
    return {full ? Array::identity(a.dtype, m) : Array::zeros(a.dtype, {m, 0}),
            Array::zeros(real_dtype(a.dtype), {0}),
            full ? Array::identity(a.dtype, n) : Array::zeros(a.dtype, {0, n})};
  Eigen::JacobiSVD<Matrix> dec(
      matrix(a), full ? Eigen::ComputeFullU | Eigen::ComputeFullV
                      : Eigen::ComputeThinU | Eigen::ComputeThinV);
  require(dec.info() == Eigen::Success, "SVD did not converge",
          "ConvergenceError");
  auto s = Array::zeros(real_dtype(a.dtype), {k});
  for (std::size_t i = 0; i < k; ++i)
    s.values[i] = cast(s.dtype, dec.singularValues()[i]);
  return {from_matrix(a.dtype, dec.matrixU()), s,
          from_matrix(a.dtype, dec.matrixV().adjoint())};
}
Array pseudoinverse(const Array &a, double tol) {
  require(std::isfinite(tol) && tol >= 0.,
          "tolerance must be finite and nonnegative", "ValueError");
  auto f = svd(a, false);
  auto [m, n] = a.matrix_shape();
  auto k = std::min(m, n);
  auto out = Array::zeros(a.dtype, {n, m});
  for (std::size_t t = 0; t < k; ++t)
    if (f[1].values[t].real() > tol)
      for (std::size_t i = 0; i < n; ++i)
        for (std::size_t j = 0; j < m; ++j)
          out.values[i * m + j] += std::conj(f[2].values[t * n + i]) *
                                   std::conj(f[0].values[j * k + t]) /
                                   f[1].values[t].real();
  return Array(out.dtype, out.shape, out.values);
}
Array nullspace(const Array &a, double tol) {
  require(std::isfinite(tol) && tol >= 0.,
          "tolerance must be finite and nonnegative", "ValueError");
  auto f = svd(a, true);
  auto n = a.shape[1];
  std::size_t rank = 0;
  for (auto z : f[1].values)
    if (z.real() > tol)
      ++rank;
  auto out = Array::zeros(a.dtype, {n, n - rank});
  for (std::size_t i = 0; i < n; ++i)
    for (std::size_t j = rank; j < n; ++j)
      out.values[i * (n - rank) + j - rank] = std::conj(f[2].values[j * n + i]);
  return out;
}
std::vector<Array> geev(const Array &a) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "general eigensystem requires square matrix");
  auto d = complex_dtype(a.dtype);
  if (n == 0)
    return {Array::zeros(d, {0}), Array::zeros(d, {0, 0}),
            Array::zeros(d, {0, 0})};
  Matrix mat = matrix(a);
  Eigen::ComplexEigenSolver<Matrix> dec(mat, true);
  require(dec.info() == Eigen::Success, "general eigensystem did not converge",
          "ConvergenceError");
  Shape order(n);
  std::iota(order.begin(), order.end(), 0);
  std::sort(order.begin(), order.end(), [&](auto i, auto j) {
    auto x = dec.eigenvalues()[i], y = dec.eigenvalues()[j];
    return x.real() == y.real() ? x.imag() < y.imag() : x.real() < y.real();
  });
  auto w = Array::zeros(d, {n}), left = Array::zeros(d, {n, n}),
       right = Array::zeros(d, {n, n});
  // Rank-revealing nullspaces handle repeated roots without assuming a unique
  // basis.
  for (std::size_t j = 0; j < n; ++j) {
    Complex lambda = dec.eigenvalues()[order[j]];
    w.values[j] = cast(d, lambda);
    std::size_t repeated = 0;
    for (std::size_t i = 0; i < j; ++i)
      if (std::abs(w.values[i] - lambda) < 1e-10 * (1. + std::abs(lambda)))
        ++repeated;
    for (bool is_left : {false, true}) {
      Matrix b = is_left ? Matrix(mat.adjoint()) : mat;
      b.diagonal().array() -= is_left ? std::conj(lambda) : lambda;
      Eigen::JacobiSVD<Matrix> s(b, Eigen::ComputeFullV);
      require(s.info() == Eigen::Success, "eigenvector solve failed",
              "ConvergenceError");
      std::size_t nullity = 0;
      for (Eigen::Index i = 0; i < s.singularValues().size(); ++i)
        if (s.singularValues()[i] < 1e-10 * (1. + mat.norm()))
          ++nullity;
      auto column =
          n - 1 - std::min(repeated, std::max(std::size_t(1), nullity) - 1);
      auto &out = is_left ? left : right;
      for (std::size_t i = 0; i < n; ++i)
        out.values[i * n + j] = cast(d, s.matrixV()(i, column));
    }
  }
  return {w, left, right};
}
Array lyapunov(const Array &a, const Array &q) {
  auto [m, n] = a.matrix_shape();
  require(m == n && q.shape == a.shape && q.dtype == a.dtype,
          "Lyapunov requires matching square matrices");
  if (n == 0)
    return q;
  Eigen::ComplexSchur<Matrix> dec(matrix(a));
  require(dec.info() == Eigen::Success,
          "Lyapunov Schur iteration did not converge", "ConvergenceError");
  Matrix u = dec.matrixU(), t = dec.matrixT(), f = u.adjoint() * matrix(q) * u,
         y = Matrix::Zero(n, n);
  for (std::size_t i = n; i-- > 0;)
    for (std::size_t j = n; j-- > 0;) {
      Complex rhs = f(i, j);
      for (std::size_t k = i + 1; k < n; ++k)
        rhs -= t(i, k) * y(k, j);
      for (std::size_t k = j + 1; k < n; ++k)
        rhs -= y(i, k) * std::conj(t(j, k));
      Complex den = t(i, i) + std::conj(t(j, j));
      require(std::abs(den) > 0., "Lyapunov equation has no unique solution",
              "SingularError");
      y(i, j) = rhs / den;
    }
  return from_matrix(a.dtype, u * y * u.adjoint());
}
Array cholesky(const Array &a) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "Cholesky requires square matrix");
  if (n == 0)
    return a;
  Eigen::LLT<Matrix> dec(matrix(a));
  require(dec.info() == Eigen::Success, "matrix is not positive definite",
          "SingularError");
  return from_matrix(a.dtype, Matrix(dec.matrixL()));
}
Array matrix_power(const Array &a, Complex exponent, double cutoff) {
  auto [m, n] = a.matrix_shape();
  require(m == n, "matrix power requires square matrix");
  require(exponent.imag() == 0. && std::isfinite(exponent.real()) &&
              std::isfinite(cutoff) && cutoff >= 0.,
          "Hermitian matrix power requires a finite real exponent and "
          "nonnegative cutoff",
          "ValueError");
  auto f = eigh(a);
  auto v = matrix(f[1]);
  Matrix diagonal = Matrix::Zero(n, n);
  double largest = 0.;
  for (auto z : f[0].values)
    largest = std::max(largest, std::abs(z.real()));
  for (std::size_t i = 0; i < n; ++i) {
    double eigenvalue = f[0].values[i].real();
    double value =
        exponent.real() < 0. && std::abs(eigenvalue) < cutoff * largest
            ? 0.
            : std::pow(eigenvalue, exponent.real());
    // Match the pinned Hermitian power's cutoff/nonfinite-to-zero policy.
    diagonal(i, i) = std::isfinite(value) ? value : 0.;
  }
  return from_matrix(a.dtype, v * diagonal * v.adjoint());
}
} // namespace sage_cpp::api
