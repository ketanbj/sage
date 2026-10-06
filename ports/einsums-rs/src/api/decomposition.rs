use super::{
    array::{coords, size, Array},
    linalg, ApiError, Result,
};
use num_complex::Complex64 as C;

pub fn khatri_rao(a: &Array, b: &Array) -> Result<Array> {
    let (m, k) = a.matrix_shape()?;
    let (n, l) = b.matrix_shape()?;
    if k != l || a.dtype != b.dtype {
        return Err(ApiError::shape("Khatri-Rao columns/dtype must match"));
    }
    let mut out = Array::zeros(
        a.dtype,
        vec![
            m.checked_mul(n)
                .ok_or_else(|| ApiError::shape("Khatri-Rao size overflow"))?,
            k,
        ],
    )?;
    for i in 0..m {
        for j in 0..n {
            for c in 0..k {
                out.values[(i * n + j) * k + c] = a.values[i * k + c] * b.values[j * k + c];
            }
        }
    }
    Ok(out)
}
fn first_columns(a: &Array, k: usize) -> Result<Array> {
    let (m, n) = a.matrix_shape()?;
    if k > n {
        return Err(ApiError::shape("requested rank exceeds factor columns"));
    }
    Array::new(
        a.dtype,
        vec![m, k],
        (0..m)
            .flat_map(|i| (0..k).map(move |j| a.values[i * n + j]))
            .collect(),
    )
}
pub fn tucker(a: &Array, ranks: &[usize], iterations: usize, tol: f64) -> Result<Vec<Array>> {
    if !tol.is_finite() || tol < 0. {
        return Err(ApiError::value("tolerance must be finite and nonnegative"));
    }
    if ranks.len() != a.shape.len() || ranks.iter().zip(&a.shape).any(|(&r, &n)| r == 0 || r > n) {
        return Err(ApiError::shape(
            "Tucker ranks must be positive and bounded by each dimension",
        ));
    }
    let mut factors = Vec::new();
    for (mode, &r) in ranks.iter().enumerate() {
        factors.push(first_columns(&linalg::svd(&a.unfold(mode)?, true)?[0], r)?);
    }
    let mut previous = f64::NEG_INFINITY;
    for _ in 0..iterations {
        for (mode, &r) in ranks.iter().enumerate() {
            let mut projected = a.clone();
            for (other, f) in factors.iter().enumerate() {
                if other != mode {
                    projected = projected.mode_product(&f.transpose("C")?, other)?;
                }
            }
            factors[mode] = first_columns(&linalg::svd(&projected.unfold(mode)?, true)?[0], r)?;
        }
        let mut core = a.clone();
        for (mode, f) in factors.iter().enumerate() {
            core = core.mode_product(&f.transpose("C")?, mode)?;
        }
        let score = core.norm();
        if (score - previous).abs() <= tol * score.max(1.) {
            break;
        }
        previous = score;
    }
    let mut core = a.clone();
    for (mode, f) in factors.iter().enumerate() {
        core = core.mode_product(&f.transpose("C")?, mode)?;
    }
    let mut result = vec![core];
    result.extend(factors);
    Ok(result)
}
pub fn reconstruct_tucker(core: &Array, factors: &[Array]) -> Result<Array> {
    if factors.len() != core.shape.len() {
        return Err(ApiError::rank("one factor per tensor mode required"));
    }
    let mut out = core.clone();
    for (mode, f) in factors.iter().enumerate() {
        out = out.mode_product(f, mode)?;
    }
    Ok(out)
}
pub fn reconstruct_cp(factors: &[Array]) -> Result<Array> {
    let first = factors
        .first()
        .ok_or_else(|| ApiError::rank("at least one CP factor required"))?;
    let (_, r) = first.matrix_shape()?;
    let mut shape = Vec::new();
    for f in factors {
        let (n, k) = f.matrix_shape()?;
        if k != r || f.dtype != first.dtype {
            return Err(ApiError::shape(
                "CP factors must share dtype and column count",
            ));
        }
        shape.push(n);
    }
    let mut out = Array::zeros(first.dtype, shape.clone())?;
    for flat in 0..size(&shape)? {
        let c = coords(flat, &shape);
        for col in 0..r {
            let mut z = C::new(1., 0.);
            for (f, &i) in factors.iter().zip(&c) {
                z *= f.values[i * r + col];
            }
            out.values[flat] += z;
        }
    }
    Ok(out)
}
pub fn cp(a: &Array, rank: usize, iterations: usize, tol: f64) -> Result<Vec<Array>> {
    if !tol.is_finite() || tol < 0. {
        return Err(ApiError::value("tolerance must be finite and nonnegative"));
    }
    if rank == 0 || a.shape.is_empty() || a.shape.contains(&0) {
        return Err(ApiError::shape(
            "CP requires positive rank and nonempty modes",
        ));
    }
    let mut factors = Vec::new();
    for (mode, &n) in a.shape.iter().enumerate() {
        factors.push(Array::new(
            a.dtype,
            vec![n, rank],
            (0..n * rank)
                .map(|i| C::new(((i + 1 + mode * 17) as f64 * 1.618033988749895).sin(), 0.))
                .collect(),
        )?);
    }
    let mut previous = f64::INFINITY;
    for _ in 0..iterations {
        for mode in 0..a.shape.len() {
            let mut product = Array::new(a.dtype, vec![1, rank], vec![C::new(1., 0.); rank])?;
            for (other, f) in factors.iter().enumerate() {
                if other != mode {
                    product = khatri_rao(&product, f)?;
                }
            }
            let gram = product.transpose("T")?.matmul(&product.map(|x| x.conj()))?;
            let rhs = a.unfold(mode)?.matmul(&product.map(|x| x.conj()))?;
            factors[mode] =
                rhs.matmul(&linalg::pseudoinverse(&gram, 1e-12 * gram.norm().max(1.))?)?;
        }
        let residual = a.zip(&reconstruct_cp(&factors)?, |x, y| x - y)?.norm();
        if (previous - residual).abs() <= tol * a.norm().max(1.) {
            break;
        }
        previous = residual;
    }
    Ok(factors)
}

/// Apply first-mode weights, matching the CPU weight_tensor contract.
pub fn weight_tensor(a: &Array, weights: &Array) -> Result<Array> {
    if a.shape.is_empty() || weights.shape != [a.shape[0]] || a.dtype != weights.dtype {
        return Err(ApiError::shape(
            "weights must match the first mode and dtype",
        ));
    }
    let stride = size(&a.shape[1..])?;
    Array::new(
        a.dtype,
        a.shape.clone(),
        a.values
            .iter()
            .enumerate()
            .map(|(i, &z)| z * weights.values[i / stride])
            .collect(),
    )
}
/// Weighted least squares CP. Zero-weight rows use the minimum-norm zero factor.
pub fn weighted_parafac(
    a: &Array,
    weights: &Array,
    rank: usize,
    iterations: usize,
    tol: f64,
) -> Result<Vec<Array>> {
    let weighted = weight_tensor(a, weights)?;
    let mut factors = cp(&weighted, rank, iterations, tol)?;
    for i in 0..a.shape[0] {
        for j in 0..rank {
            factors[0].values[i * rank + j] = if weights.values[i].norm() == 0. {
                C::new(0., 0.)
            } else {
                factors[0].values[i * rank + j] / weights.values[i]
            };
        }
    }
    Ok(factors)
}
pub use cp as parafac;
pub use reconstruct_cp as parafac_reconstruct;
pub use reconstruct_tucker as tucker_reconstruct;
pub fn tucker_ho_svd(a: &Array, ranks: &[usize]) -> Result<Vec<Array>> {
    tucker(a, ranks, 0, 1e-8)
}
pub fn tucker_ho_oi(
    a: &Array,
    ranks: &[usize],
    iterations: usize,
    tolerance: f64,
) -> Result<Vec<Array>> {
    tucker(a, ranks, iterations, tolerance)
}
