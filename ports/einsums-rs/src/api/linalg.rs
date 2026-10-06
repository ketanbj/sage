use super::{array::Array, ApiError, Result};
use nalgebra::{
    linalg::{Schur, SymmetricEigen, SVD},
    DMatrix,
};
use num_complex::Complex64 as C;

pub fn lu(a: &Array) -> Result<(Array, Vec<usize>)> {
    let (m, n) = a.matrix_shape()?;
    a.matrix()?;
    let mut a = a.clone();
    let mut piv = Vec::new();
    for k in 0..m.min(n) {
        let p = (k..m)
            .max_by(|&i, &j| {
                a.values[i * n + k]
                    .norm()
                    .total_cmp(&a.values[j * n + k].norm())
            })
            .unwrap();
        piv.push(p + 1);
        for j in 0..n {
            a.values.swap(k * n + j, p * n + j);
        }
        if a.values[k * n + k].norm() == 0. {
            continue;
        }
        for i in k + 1..m {
            let f = a.values[i * n + k] / a.values[k * n + k];
            a.values[i * n + k] = f;
            for j in k + 1..n {
                let x = a.values[k * n + j];
                a.values[i * n + j] -= f * x;
            }
        }
    }
    Ok((a, piv))
}
pub fn extract_plu(a: &Array, piv: &[usize]) -> Result<Vec<Array>> {
    let (m, n) = a.matrix_shape()?;
    let k = m.min(n);
    if piv.len() != k || piv.iter().any(|&p| p == 0 || p > m) {
        return Err(ApiError::value("invalid LU pivot list"));
    }
    let (mut p, mut l, mut u) = (
        Array::identity(a.dtype, m)?,
        Array::zeros(a.dtype, vec![m, k])?,
        Array::zeros(a.dtype, vec![k, n])?,
    );
    for (i, &r) in piv.iter().enumerate() {
        for j in 0..m {
            p.values.swap(i * m + j, (r - 1) * m + j);
        }
    }
    for i in 0..m {
        for j in 0..k {
            l.values[i * k + j] = if i == j {
                C::new(1., 0.)
            } else if i > j {
                a.values[i * n + j]
            } else {
                C::new(0., 0.)
            };
        }
    }
    for i in 0..k {
        for j in i..n {
            u.values[i * n + j] = a.values[i * n + j];
        }
    }
    Ok(vec![p, l, u])
}
pub fn solve(a: &Array, b: &Array) -> Result<Array> {
    let (m, n) = a.matrix_shape()?;
    if m != n {
        return Err(ApiError::shape("coefficient matrix must be square"));
    }
    let vector = b.shape.len() == 1;
    let bb = if vector {
        b.reshape(vec![b.shape[0], 1])?
    } else {
        b.clone()
    };
    if bb.shape.first() != Some(&m) || a.dtype != b.dtype {
        return Err(ApiError::shape("right-hand side dimensions/dtype differ"));
    }
    let rhs = bb.matrix()?;
    let x = a
        .matrix()?
        .lu()
        .solve(&rhs)
        .ok_or_else(|| ApiError::singular("coefficient matrix is singular"))?;
    let out = Array::from_matrix(a.dtype, &x)?;
    if vector {
        out.reshape(vec![m])
    } else {
        Ok(out)
    }
}
pub fn inverse(a: &Array) -> Result<Array> {
    let (m, n) = a.matrix_shape()?;
    if m != n {
        return Err(ApiError::shape("inverse requires square matrix"));
    }
    solve(a, &Array::identity(a.dtype, n)?)
}
pub fn lu_inverse(a: &Array, piv: &[usize]) -> Result<Array> {
    let factors = extract_plu(a, piv)?;
    let original = factors[0]
        .transpose("T")?
        .matmul(&factors[1])?
        .matmul(&factors[2])?;
    inverse(&original)
}
pub fn determinant(a: &Array) -> Result<C> {
    let (m, n) = a.matrix_shape()?;
    if m != n {
        return Err(ApiError::shape("determinant requires square matrix"));
    }
    let (p, piv) = lu(a)?;
    Ok((0..n).fold(C::new(1., 0.), |x, i| {
        x * p.values[i * n + i] * if piv[i] == i + 1 { 1. } else { -1. }
    }))
}
/// LAPACK-style packed reflectors, with H = I - tau v v*. Supports complex data.
pub fn qr(a: &Array) -> Result<Vec<Array>> {
    let (m, n) = a.matrix_shape()?;
    a.matrix()?;
    let mut packed = a.clone();
    let mut tau = Array::zeros(a.dtype, vec![m.min(n)])?;
    for j in 0..m.min(n) {
        let alpha = packed.values[j * n + j];
        let tail = (j + 1..m).fold(0f64, |norm, i| norm.hypot(packed.values[i * n + j].norm()));
        if tail == 0. && alpha.im == 0. {
            continue;
        }
        let beta = -alpha.norm().hypot(tail).copysign(alpha.re);
        let t = (C::new(beta, 0.) - alpha) / beta;
        let divisor = alpha - C::new(beta, 0.);
        tau.values[j] = t;
        packed.values[j * n + j] = C::new(beta, 0.);
        for i in j + 1..m {
            packed.values[i * n + j] /= divisor;
        }
        for col in j + 1..n {
            let mut dot = packed.values[j * n + col];
            for i in j + 1..m {
                dot += packed.values[i * n + j].conj() * packed.values[i * n + col];
            }
            dot *= t.conj();
            packed.values[j * n + col] -= dot;
            for i in j + 1..m {
                let v = packed.values[i * n + j];
                packed.values[i * n + col] -= v * dot;
            }
        }
    }
    Ok(vec![packed, tau])
}
pub fn unpack_qr(a: &Array, tau: &Array) -> Result<Vec<Array>> {
    let (m, n) = a.matrix_shape()?;
    let k = m.min(n);
    if tau.shape != [k] || a.dtype != tau.dtype {
        return Err(ApiError::shape("QR tau has incorrect size/dtype"));
    }
    let mut q = Array::identity(a.dtype, m)?;
    for j in 0..k {
        for row in 0..m {
            let mut dot = q.values[row * m + j];
            for i in j + 1..m {
                dot += q.values[row * m + i] * a.values[i * n + j];
            }
            dot *= tau.values[j];
            q.values[row * m + j] -= dot;
            for i in j + 1..m {
                q.values[row * m + i] -= dot * a.values[i * n + j].conj();
            }
        }
    }
    let q = Array::new(
        a.dtype,
        vec![m, k],
        (0..m)
            .flat_map(|i| {
                let q = &q;
                (0..k).map(move |j| q.values[i * m + j])
            })
            .collect(),
    )?;
    let r = Array::new(
        a.dtype,
        vec![k, n],
        (0..k)
            .flat_map(|i| {
                (0..n).map(move |j| {
                    if i <= j {
                        a.values[i * n + j]
                    } else {
                        C::new(0., 0.)
                    }
                })
            })
            .collect(),
    )?;
    Ok(vec![q, r])
}
pub fn eigh(a: &Array) -> Result<Vec<Array>> {
    let (m, n) = a.matrix_shape()?;
    if m != n {
        return Err(ApiError::shape("eigensystem requires square matrix"));
    }
    let mut mat = a.matrix()?;
    // The upstream API selects the upper triangle, as do its LAPACK wrappers.
    for i in 0..n {
        mat[(i, i)].im = 0.;
        for j in 0..i {
            mat[(i, j)] = mat[(j, i)].conj();
        }
    }
    if n == 0 {
        return Ok(vec![Array::zeros(a.dtype.real(), vec![0])?, a.clone()]);
    }
    let eig = SymmetricEigen::try_new(mat, 1e-14, 100000)
        .ok_or_else(|| ApiError::convergence("Hermitian eigensystem did not converge"))?;
    let mut order: Vec<_> = (0..n).collect();
    order.sort_by(|&i, &j| eig.eigenvalues[i].total_cmp(&eig.eigenvalues[j]));
    let w = Array::new(
        a.dtype.real(),
        vec![n],
        order
            .iter()
            .map(|&i| C::new(eig.eigenvalues[i], 0.))
            .collect(),
    )?;
    let v = Array::new(
        a.dtype,
        vec![n, n],
        (0..n)
            .flat_map(|i| {
                let order = &order;
                let eig = &eig;
                (0..n).map(move |j| eig.eigenvectors[(i, order[j])])
            })
            .collect(),
    )?;
    Ok(vec![w, v])
}
fn complete_columns(thin: &DMatrix<C>) -> Result<DMatrix<C>> {
    let m = thin.nrows();
    let mut out = DMatrix::<C>::zeros(m, m);
    let k = thin.ncols();
    out.columns_mut(0, k).copy_from(thin);
    let mut col = k;
    for axis in 0..m {
        if col == m {
            break;
        }
        let mut v = nalgebra::DVector::<C>::zeros(m);
        v[axis] = C::new(1., 0.);
        for _ in 0..2 {
            for j in 0..col {
                let d = out.column(j).dotc(&v);
                for i in 0..m {
                    v[i] -= out[(i, j)] * d;
                }
            }
        }
        let norm = v.norm();
        if norm > 1e-12 {
            for i in 0..m {
                out[(i, col)] = v[i] / norm;
            }
            col += 1;
        }
    }
    if col != m {
        return Err(ApiError::convergence(
            "could not complete orthonormal basis",
        ));
    }
    Ok(out)
}
pub fn svd(a: &Array, full: bool) -> Result<Vec<Array>> {
    let (m, n) = a.matrix_shape()?;
    let k = m.min(n);
    if k == 0 {
        return Ok(vec![
            if full {
                Array::identity(a.dtype, m)?
            } else {
                Array::zeros(a.dtype, vec![m, 0])?
            },
            Array::zeros(a.dtype.real(), vec![0])?,
            if full {
                Array::identity(a.dtype, n)?
            } else {
                Array::zeros(a.dtype, vec![0, n])?
            },
        ]);
    }
    let dec = SVD::try_new(a.matrix()?, true, true, 1e-14, 100000)
        .ok_or_else(|| ApiError::convergence("SVD did not converge"))?;
    let mut u = dec.u.unwrap();
    let mut vh = dec.v_t.unwrap();
    if full {
        u = complete_columns(&u)?;
        vh = complete_columns(&vh.adjoint())?.adjoint();
    }
    Ok(vec![
        Array::from_matrix(a.dtype, &u)?,
        Array::new(
            a.dtype.real(),
            vec![k],
            dec.singular_values.iter().map(|&x| C::new(x, 0.)).collect(),
        )?,
        Array::from_matrix(a.dtype, &vh)?,
    ])
}
pub fn pseudoinverse(a: &Array, tol: f64) -> Result<Array> {
    if !tol.is_finite() || tol < 0. {
        return Err(ApiError::value("tolerance must be finite and nonnegative"));
    }
    let factors = svd(a, false)?;
    let u = factors[0].matrix()?;
    let vh = factors[2].matrix()?;
    let mut inv = DMatrix::<C>::zeros(a.shape[1], a.shape[0]);
    for k in 0..factors[1].values.len() {
        let s = factors[1].values[k].re;
        if s > tol {
            for i in 0..inv.nrows() {
                for j in 0..inv.ncols() {
                    inv[(i, j)] += vh[(k, i)].conj() * u[(j, k)].conj() / s;
                }
            }
        }
    }
    Array::from_matrix(a.dtype, &inv)
}
pub fn nullspace(a: &Array, tol: f64) -> Result<Array> {
    if !tol.is_finite() || tol < 0. {
        return Err(ApiError::value("tolerance must be finite and nonnegative"));
    }
    let factors = svd(a, true)?;
    let n = a.shape[1];
    let rank = factors[1].values.iter().filter(|z| z.re > tol).count();
    let vh = &factors[2];
    Array::new(
        a.dtype,
        vec![n, n - rank],
        (0..n)
            .flat_map(|i| (rank..n).map(move |j| vh.values[j * n + i].conj()))
            .collect(),
    )
}
pub fn geev(a: &Array) -> Result<Vec<Array>> {
    let (m, n) = a.matrix_shape()?;
    if m != n {
        return Err(ApiError::shape(
            "general eigensystem requires square matrix",
        ));
    }
    if n == 0 {
        return Ok(vec![
            Array::zeros(a.dtype.complex(), vec![0])?,
            a.clone(),
            a.clone(),
        ]);
    }
    let mat = a.matrix()?;
    let (schur_vectors, t) = Schur::try_new(mat.clone(), 1e-14, 100000)
        .ok_or_else(|| ApiError::convergence("Schur iteration did not converge"))?
        .unpack();
    let mut order: Vec<_> = (0..n).collect();
    order.sort_by(|&i, &j| {
        t[(i, i)]
            .re
            .total_cmp(&t[(j, j)].re)
            .then(t[(i, i)].im.total_cmp(&t[(j, j)].im))
    });
    let w: Vec<_> = order.iter().map(|&i| t[(i, i)]).collect();
    let mut vectors = Vec::new();
    for left in [true, false] {
        let mut v = DMatrix::<C>::zeros(n, n);
        for (j, &lambda) in w.iter().enumerate() {
            let index = order[j];
            let mut y = nalgebra::DVector::<C>::zeros(n);
            y[index] = C::new(1., 0.);
            let rows: Vec<usize> = if left {
                (index + 1..n).collect()
            } else {
                (0..index).rev().collect()
            };
            let mut fallback = w.iter().enumerate().any(|(other, &z)| {
                other != j && (z - lambda).norm() < 1e-10 * (1. + lambda.norm())
            });
            for row in rows {
                let denominator = if left {
                    (t[(row, row)] - lambda).conj()
                } else {
                    t[(row, row)] - lambda
                };
                if denominator.norm() < 1e-12 * (1. + mat.norm()) {
                    fallback = true;
                    break;
                }
                let rhs: C = if left {
                    (index..row).map(|k| t[(k, row)].conj() * y[k]).sum()
                } else {
                    (row + 1..=index).map(|k| t[(row, k)] * y[k]).sum()
                };
                y[row] = -rhs / denominator;
                let norm = y.norm();
                if norm > 1e100 {
                    y /= C::new(norm, 0.);
                }
            }
            if !fallback {
                let mut column = &schur_vectors * y;
                let norm = column.norm();
                if norm.is_finite() && norm > 0. {
                    column /= C::new(norm, 0.);
                    v.set_column(j, &column);
                    continue;
                }
            }
            // Repeated/defective roots need a rank-revealing nullspace solve.
            let mut b = if left { mat.adjoint() } else { mat.clone() };
            for i in 0..n {
                b[(i, i)] -= if left { lambda.conj() } else { lambda };
            }
            let d = SVD::try_new(b, false, true, 1e-14, 100000)
                .ok_or_else(|| ApiError::convergence("eigenvector solve failed"))?;
            let repeated = w[..j]
                .iter()
                .filter(|&&x| (x - lambda).norm() < 1e-10 * (1. + lambda.norm()))
                .count();
            let nullity = d
                .singular_values
                .iter()
                .filter(|&&x| x < 1e-10 * (1. + mat.norm()))
                .count()
                .max(1);
            let row = n - 1 - repeated.min(nullity - 1);
            let vh = d.v_t.unwrap();
            for i in 0..n {
                v[(i, j)] = vh[(row, i)].conj();
            }
        }
        vectors.push(Array::from_matrix(a.dtype.complex(), &v)?);
    }
    Ok(vec![
        Array::new(a.dtype.complex(), vec![n], w)?,
        vectors.remove(0),
        vectors.remove(0),
    ])
}
pub fn lyapunov(a: &Array, q: &Array) -> Result<Array> {
    let (m, n) = a.matrix_shape()?;
    if m != n || q.shape != a.shape || q.dtype != a.dtype {
        return Err(ApiError::shape(
            "Lyapunov requires matching square matrices",
        ));
    }
    if n == 0 {
        return Ok(q.clone());
    }
    let (u, t) = Schur::try_new(a.matrix()?, 1e-14, 100000)
        .ok_or_else(|| ApiError::convergence("Lyapunov Schur iteration did not converge"))?
        .unpack();
    let f = u.adjoint() * q.matrix()? * &u;
    let mut y = DMatrix::<C>::zeros(n, n);
    // Bartels-Stewart triangular solve, O(n^3) work and O(n^2) storage.
    for i in (0..n).rev() {
        for j in (0..n).rev() {
            let mut rhs = f[(i, j)];
            for k in i + 1..n {
                rhs -= t[(i, k)] * y[(k, j)];
            }
            for k in j + 1..n {
                rhs -= y[(i, k)] * t[(j, k)].conj();
            }
            let denominator = t[(i, i)] + t[(j, j)].conj();
            if denominator.norm() == 0. {
                return Err(ApiError::singular(
                    "Lyapunov equation has no unique solution",
                ));
            }
            y[(i, j)] = rhs / denominator;
        }
    }
    Array::from_matrix(a.dtype, &(&u * y * u.adjoint()))
}
