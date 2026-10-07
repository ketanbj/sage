//! CPU API shared by Rust and the Python compatibility package. Numerical work
//! stays in Rust; HDF5 uses the independently linked HDF5 C library, never Einsums.
pub mod array;
mod bounded_tensor;
mod complex_values;
pub mod decomposition;
pub mod linalg;
pub mod runtime;
pub mod storage;
use array::{Array, DType};
use num_complex::Complex64 as C;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{ffi::CString, os::raw::c_char, path::Path, ptr};

#[derive(Debug, Serialize)]
pub struct ApiError {
    pub kind: &'static str,
    pub message: String,
}
impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.kind, self.message)
    }
}
impl std::error::Error for ApiError {}
pub type Result<T> = std::result::Result<T, ApiError>;
macro_rules! errors {($($name:ident=>$kind:literal),*)=>{impl ApiError{$(pub fn $name(message:impl Into<String>)->Self{Self{kind:$kind,message:message.into()}})*}}}
errors!(shape=>"dimension_error",rank=>"rank_error",dtype=>"TypeError",value=>"ValueError",singular=>"SingularError",convergence=>"ConvergenceError",io=>"OSError");
#[derive(Debug, Deserialize)]
pub struct Request {
    pub op: String,
    #[serde(default)]
    pub arrays: Vec<Array>,
    #[serde(default)]
    pub params: Value,
}
#[derive(Debug, Default, Serialize)]
pub struct Response {
    pub arrays: Vec<Array>,
    #[serde(with = "complex_values")]
    pub scalars: Vec<C>,
    pub indices: Vec<usize>,
}
fn arrays(values: Vec<Array>) -> Response {
    Response {
        arrays: values,
        ..Default::default()
    }
}
fn scalar(value: C) -> Response {
    Response {
        scalars: vec![value],
        ..Default::default()
    }
}
impl Request {
    fn a(&self, i: usize) -> Result<&Array> {
        self.arrays
            .get(i)
            .ok_or_else(|| ApiError::value("missing array argument"))
    }
    fn text(&self, key: &str, default: &str) -> String {
        self.params
            .get(key)
            .and_then(Value::as_str)
            .unwrap_or(default)
            .into()
    }
    fn float(&self, key: &str, default: f64) -> Result<f64> {
        match self.params.get(key) {
            None => Ok(default),
            Some(v) => complex_values::number(v).map_err(ApiError::value),
        }
    }
    fn int(&self, key: &str, default: usize) -> Result<usize> {
        match self.params.get(key) {
            None => Ok(default),
            Some(v) => v
                .as_u64()
                .and_then(|x| usize::try_from(x).ok())
                .ok_or_else(|| ApiError::value(format!("{key} must be nonnegative integer"))),
        }
    }
    fn ints(&self, key: &str) -> Result<Vec<usize>> {
        serde_json::from_value(self.params.get(key).cloned().unwrap_or(json!([])))
            .map_err(|e| ApiError::value(e.to_string()))
    }
    fn labels(&self, key: &str) -> Result<Vec<String>> {
        let v = self.params.get(key).cloned().unwrap_or(json!([]));
        if let Some(s) = v.as_str() {
            Ok(s.chars().map(|c| c.to_string()).collect())
        } else {
            serde_json::from_value(v).map_err(|e| ApiError::value(e.to_string()))
        }
    }
    fn z(&self, key: &str, default: C) -> Result<C> {
        match self.params.get(key) {
            None => Ok(default),
            Some(v) => {
                if !v.is_array() {
                    Ok(C::new(
                        complex_values::number(v).map_err(ApiError::value)?,
                        0.,
                    ))
                } else {
                    complex_values::pair(v).map_err(ApiError::value)
                }
            }
        }
    }
    fn dtype(&self) -> Result<DType> {
        serde_json::from_value(
            self.params
                .get("dtype")
                .cloned()
                .unwrap_or(json!("float64")),
        )
        .map_err(|e| ApiError::dtype(e.to_string()))
    }
}
fn blend(product: Array, original: &Array, alpha: C, beta: C) -> Result<Array> {
    if product.shape != original.shape || product.dtype != original.dtype {
        return Err(ApiError::shape("output has incorrect shape or dtype"));
    }
    if beta == C::new(0., 0.) {
        Ok(product.map(|z| alpha * z))
    } else {
        product.zip(original, |x, y| alpha * x + beta * y)
    }
}
fn truncate_columns(a: &Array, k: usize) -> Result<Array> {
    let (m, n) = a.matrix_shape()?;
    if k > n {
        return Err(ApiError::shape("truncation rank exceeds dimension"));
    }
    Array::new(
        a.dtype,
        vec![m, k],
        (0..m)
            .flat_map(|i| (0..k).map(move |j| a.values[i * n + j]))
            .collect(),
    )
}
pub fn execute(req: &Request) -> Result<Response> {
    let arity = match req.op.as_str() {
        "copy" | "permute" | "scale" | "negate" => Some(1),
        "add" | "subtract" | "multiply" | "divide" | "matmul" => Some(2),
        _ => None,
    };
    if arity.is_some_and(|n| req.arrays.len() != n) {
        return Err(ApiError::value("wrong number of array arguments"));
    }
    for a in &req.arrays {
        a.validate()?;
    }
    let one = C::new(1., 0.);
    let zero = C::new(0., 0.);
    let alpha = req.z("alpha", one)?;
    let beta = req.z("beta", zero)?;
    if let Some(result) = bounded_tensor::execute(req, alpha) {
        return result;
    }
    match req.op.as_str() {
        "copy" => Ok(arrays(vec![req.a(0)?.clone()])),
        "add" | "subtract" | "multiply" | "divide" => {
            let a = req.a(0)?;
            let b = req.a(1)?;
            let c = a.zip(b, |x, y| {
                if !a.dtype.is_complex() {
                    C::new(
                        match req.op.as_str() {
                            "add" => x.re + y.re,
                            "subtract" => x.re - y.re,
                            "multiply" => x.re * y.re,
                            _ => x.re / y.re,
                        },
                        0.,
                    )
                } else {
                    match req.op.as_str() {
                        "add" => x + y,
                        "subtract" => x - y,
                        "multiply" => x * y,
                        _ => x / y,
                    }
                }
            })?;
            Ok(arrays(vec![c]))
        }
        "scale" | "negate" | "conjugate" | "pow" | "exp" | "log" | "sqrt" | "abs" => {
            let a = req.a(0)?;
            let mut c = a.map(|x| match req.op.as_str() {
                "scale" => alpha * x,
                "negate" => -x,
                "conjugate" => x.conj(),
                "pow" => {
                    if a.dtype.is_complex() {
                        x.powc(alpha)
                    } else {
                        C::new(x.re.powf(alpha.re), 0.)
                    }
                }
                "exp" => x.exp(),
                "log" => {
                    if a.dtype.is_complex() {
                        x.ln()
                    } else {
                        C::new(x.re.ln(), 0.)
                    }
                }
                "sqrt" => {
                    if a.dtype.is_complex() {
                        x.sqrt()
                    } else {
                        C::new(x.re.sqrt(), 0.)
                    }
                }
                _ => C::new(x.norm(), 0.),
            });
            if req.op == "abs" {
                c.dtype = a.dtype.real();
            }
            Ok(arrays(vec![c]))
        }
        "reshape" => Ok(arrays(vec![req.a(0)?.reshape(req.ints("shape")?)?])),
        "permute" => Ok(arrays(vec![req.a(0)?.permute(&req.ints("axes")?)?])),
        "einsum" => {
            let product = req.a(0)?.einsum(
                &req.labels("a_labels")?,
                req.a(1)?,
                &req.labels("b_labels")?,
                &req.labels("out_labels")?,
            )?;
            Ok(arrays(vec![if req.arrays.len() > 2 {
                blend(product, req.a(2)?, alpha, beta)?
            } else {
                product.map(|z| alpha * z)
            }]))
        }
        "gemm" | "matmul" => {
            let a = req.a(0)?.transpose(&req.text("trans_a", "N"))?;
            let b = req.a(1)?.transpose(&req.text("trans_b", "N"))?;
            let product = a.matmul(&b)?;
            Ok(arrays(vec![if req.arrays.len() > 2 {
                blend(product, req.a(2)?, alpha, beta)?
            } else {
                product
            }]))
        }
        "gemv" => {
            let a = req.a(0)?.transpose(&req.text("trans_a", "N"))?;
            let b = req.a(1)?;
            if b.shape.len() != 1 {
                return Err(ApiError::rank("gemv requires a vector"));
            }
            let x = b.reshape(vec![b.shape[0], 1])?;
            let product = a.matmul(&x)?.reshape(vec![a.shape[0]])?;
            Ok(arrays(vec![blend(product, req.a(2)?, alpha, beta)?]))
        }
        "axpy" | "axpby" => Ok(arrays(vec![blend(
            req.a(0)?.clone(),
            req.a(1)?,
            alpha,
            if req.op == "axpy" { one } else { beta },
        )?])),
        "direct_product" => Ok(arrays(vec![blend(
            req.a(0)?.zip(req.a(1)?, |x, y| x * y)?,
            req.a(2)?,
            alpha,
            beta,
        )?])),
        "ger" => {
            let x = req.a(0)?;
            let y = req.a(1)?;
            if x.shape.len() != 1 || y.shape.len() != 1 {
                return Err(ApiError::rank("ger requires vectors"));
            }
            let p = x.einsum(&["i".into()], y, &["j".into()], &["i".into(), "j".into()])?;
            Ok(arrays(vec![blend(p, req.a(2)?, alpha, one)?]))
        }
        "scale_row" | "scale_column" => {
            let a = req.a(0)?;
            let (m, n) = a.matrix_shape()?;
            let i = req.int("index", 0)?;
            let row = req.op == "scale_row";
            if i >= if row { m } else { n } {
                return Err(ApiError::shape("row/column index out of bounds"));
            }
            let mut out = a.clone();
            for j in 0..if row { n } else { m } {
                out.values[if row { i * n + j } else { j * n + i }] *= alpha;
            }
            Ok(arrays(vec![out]))
        }
        "sum" => Ok(scalar(req.a(0)?.values.iter().copied().sum())),
        "dot" | "true_dot" => {
            let p = req.a(0)?.zip(req.a(1)?, |x, y| {
                if req.op == "dot" {
                    x * y
                } else {
                    x.conj() * y
                }
            })?;
            Ok(scalar(p.values.iter().copied().sum()))
        }
        "vec_norm" => Ok(scalar(C::new(req.a(0)?.norm(), 0.))),
        "rmsd" => {
            let a = req.a(0)?;
            if a.values.is_empty() {
                return Err(ApiError::value("RMSD of empty arrays is undefined"));
            }
            Ok(scalar(C::new(
                a.zip(req.a(1)?, |x, y| x - y)?.norm() / (a.values.len() as f64).sqrt(),
                0.,
            )))
        }
        "sum_square" => {
            let a = req.a(0)?;
            if a.shape.len() != 1 {
                return Err(ApiError::rank("sum_square requires a vector"));
            }
            let scale = a
                .values
                .iter()
                .fold(0f64, |s, z| s.max(z.re.abs()).max(z.im.abs()));
            let sum = if scale == 0. {
                0.
            } else {
                a.values
                    .iter()
                    .map(|z| (z.re / scale).powi(2) + (z.im / scale).powi(2))
                    .sum()
            };
            Ok(Response {
                scalars: vec![C::new(sum, 0.), C::new(scale, 0.)],
                ..Default::default()
            })
        }
        "norm" => {
            let a = req.a(0)?;
            let (m, n) = a.matrix_shape()?;
            let x = match req.text("kind", "FROBENIUS").as_str() {
                "MAXABS" => a.values.iter().fold(0f64, |s, z| s.max(z.norm())),
                "ONE" => (0..n)
                    .map(|j| (0..m).map(|i| a.values[i * n + j].norm()).sum::<f64>())
                    .fold(0f64, f64::max),
                "INFINITY" => (0..m)
                    .map(|i| (0..n).map(|j| a.values[i * n + j].norm()).sum::<f64>())
                    .fold(0f64, f64::max),
                "FROBENIUS" => a.norm(),
                _ => return Err(ApiError::value("unknown norm")),
            };
            Ok(scalar(C::new(x, 0.)))
        }
        "getrf" => {
            let (a, piv) = linalg::lu(req.a(0)?)?;
            Ok(Response {
                arrays: vec![a],
                indices: piv,
                ..Default::default()
            })
        }
        "extract_plu" => Ok(arrays(linalg::extract_plu(
            req.a(0)?,
            &req.ints("pivots")?,
        )?)),
        "getri" => Ok(arrays(vec![linalg::lu_inverse(
            req.a(0)?,
            &req.ints("pivots")?,
        )?])),
        "invert" => Ok(arrays(vec![linalg::inverse(req.a(0)?)?])),
        "gesv" | "solve" => {
            let x = linalg::solve(req.a(0)?, req.a(1)?)?;
            if req.op == "gesv" {
                let (a, piv) = linalg::lu(req.a(0)?)?;
                Ok(Response {
                    arrays: vec![a, x],
                    indices: piv,
                    ..Default::default()
                })
            } else {
                Ok(arrays(vec![x]))
            }
        }
        "det" => Ok(scalar(linalg::determinant(req.a(0)?)?)),
        "qr" => Ok(arrays(linalg::qr(req.a(0)?)?)),
        "q" | "r" => {
            let mut factors = linalg::unpack_qr(req.a(0)?, req.a(1)?)?;
            Ok(arrays(vec![factors.remove(if req.op == "q" {
                0
            } else {
                1
            })]))
        }
        "syev" | "heev" => Ok(arrays(linalg::eigh(req.a(0)?)?)),
        "geev" => Ok(arrays(linalg::geev(req.a(0)?)?)),
        "svd" | "svd_dd" => Ok(arrays(linalg::svd(
            req.a(0)?,
            req.text("job", "ALL") == "ALL",
        )?)),
        "truncated_svd" => {
            let f = linalg::svd(req.a(0)?, false)?;
            let k = req.int("k", 0)?;
            if k > f[1].values.len() {
                return Err(ApiError::shape("truncation rank exceeds dimension"));
            }
            let n = f[2].shape[1];
            Ok(arrays(vec![
                truncate_columns(&f[0], k)?,
                Array::new(f[1].dtype, vec![k], f[1].values[..k].to_vec())?,
                Array::new(f[2].dtype, vec![k, n], f[2].values[..k * n].to_vec())?,
            ]))
        }
        "truncated_syev" => {
            let f = linalg::eigh(req.a(0)?)?;
            let k = req.int("k", 0)?;
            let n = f[0].values.len();
            if k > n {
                return Err(ApiError::shape("truncation rank exceeds dimension"));
            }
            let mut order: Vec<_> = (0..n).collect();
            order.sort_by(|&i, &j| f[0].values[j].norm().total_cmp(&f[0].values[i].norm()));
            let w = Array::new(
                f[0].dtype,
                vec![k],
                order[..k].iter().map(|&i| f[0].values[i]).collect(),
            )?;
            let v = Array::new(
                f[1].dtype,
                vec![n, k],
                (0..n)
                    .flat_map(|i| {
                        let f = &f;
                        order[..k].iter().map(move |&j| f[1].values[i * n + j])
                    })
                    .collect(),
            )?;
            Ok(arrays(vec![v, w]))
        }
        "pseudoinverse" => Ok(arrays(vec![linalg::pseudoinverse(
            req.a(0)?,
            req.float("tol", 1e-12)?,
        )?])),
        "svd_nullspace" => {
            let a = req.a(0)?;
            Ok(arrays(vec![linalg::nullspace(
                a,
                req.float(
                    "tol",
                    a.dtype.epsilon()
                        * a.norm()
                        * a.shape.iter().copied().max().unwrap_or(1) as f64,
                )?,
            )?]))
        }
        "solve_continuous_lyapunov" => Ok(arrays(vec![linalg::lyapunov(req.a(0)?, req.a(1)?)?])),
        "cholesky" => {
            let a = req.a(0)?;
            let l = a
                .matrix()?
                .cholesky()
                .ok_or_else(|| ApiError::value("matrix is not positive definite"))?
                .l();
            Ok(arrays(vec![Array::from_matrix(a.dtype, &l)?]))
        }
        "matrix_power" => {
            let f = linalg::eigh(req.a(0)?)?;
            let n = f[0].values.len();
            let mut diagonal = Array::zeros(f[1].dtype, vec![n, n])?;
            for i in 0..n {
                diagonal.values[i * n + i] = f[0].values[i].powc(alpha);
            }
            Ok(arrays(vec![f[1]
                .matmul(&diagonal)?
                .matmul(&f[1].transpose("C")?)?]))
        }
        "unfold" => Ok(arrays(vec![req.a(0)?.unfold(req.int("mode", 0)?)?])),
        "khatri_rao" => Ok(arrays(vec![decomposition::khatri_rao(
            req.a(0)?,
            req.a(1)?,
        )?])),
        "mode_product" => Ok(arrays(vec![req
            .a(0)?
            .mode_product(req.a(1)?, req.int("mode", 0)?)?])),
        "tucker" | "hooi" => Ok(arrays(decomposition::tucker(
            req.a(0)?,
            &req.ints("ranks")?,
            if req.op == "tucker" {
                0
            } else {
                req.int("iterations", 100)?
            },
            req.float("tol", 1e-8)?,
        )?)),
        "weight_tensor" => Ok(arrays(vec![decomposition::weight_tensor(
            req.a(0)?,
            req.a(1)?,
        )?])),
        "weighted_parafac" => Ok(arrays(decomposition::weighted_parafac(
            req.a(0)?,
            req.a(1)?,
            req.int("rank", 1)?,
            req.int("iterations", 100)?,
            req.float("tol", 1e-8)?,
        )?)),
        "cp" => Ok(arrays(decomposition::cp(
            req.a(0)?,
            req.int("rank", 1)?,
            req.int("iterations", 100)?,
            req.float("tol", 1e-8)?,
        )?)),
        "reconstruct_tucker" => Ok(arrays(vec![decomposition::reconstruct_tucker(
            req.a(0)?,
            &req.arrays[1..],
        )?])),
        "reconstruct_cp" => Ok(arrays(vec![decomposition::reconstruct_cp(&req.arrays)?])),
        "write_hdf5" => {
            storage::write_hdf5(
                Path::new(&req.text("path", "")),
                &req.text("name", "tensor"),
                req.a(0)?,
                req.params
                    .get("overwrite")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
            )?;
            Ok(Response::default())
        }
        "read_hdf5" => Ok(arrays(vec![storage::read_hdf5(
            Path::new(&req.text("path", "")),
            &req.text("name", "tensor"),
        )?])),
        "tile_dense" => {
            let partitions: Vec<Vec<usize>> =
                serde_json::from_value(req.params["partitions"].clone())
                    .map_err(|e| ApiError::value(e.to_string()))?;
            let indices: Vec<Vec<usize>> = serde_json::from_value(req.params["indices"].clone())
                .map_err(|e| ApiError::value(e.to_string()))?;
            if indices.len() != req.arrays.len() {
                return Err(ApiError::shape("tile indices/data length differ"));
            }
            let mut out = storage::TiledTensor::new(req.dtype()?, partitions)?;
            for (index, a) in indices.into_iter().zip(&req.arrays) {
                out.insert(index, a.clone())?;
            }
            Ok(arrays(vec![out.to_dense()?]))
        }
        "block_dense" => {
            let blocks = req.ints("blocks")?;
            if blocks.len() != req.arrays.len() {
                return Err(ApiError::shape("block sizes/data length differ"));
            }
            let mut out = storage::BlockTensor::new(req.dtype()?, req.int("rank", 2)?, blocks)?;
            for (i, a) in req.arrays.iter().enumerate() {
                out.insert(i, a.clone())?;
            }
            Ok(arrays(vec![out.to_dense()?]))
        }
        "zeros" => Ok(arrays(vec![Array::zeros(
            req.dtype()?,
            req.ints("shape")?,
        )?])),
        "identity" => Ok(arrays(vec![Array::identity(
            req.dtype()?,
            req.int("n", 0)?,
        )?])),
        "diagonal" => {
            let a = req.a(0)?;
            if a.shape.len() == 1 {
                let n = a.shape[0];
                let mut out = Array::zeros(a.dtype, vec![n, n])?;
                for i in 0..n {
                    out.values[i * n + i] = a.values[i];
                }
                Ok(arrays(vec![out]))
            } else {
                let (m, n) = a.matrix_shape()?;
                Ok(arrays(vec![Array::new(
                    a.dtype,
                    vec![m.min(n)],
                    (0..m.min(n)).map(|i| a.values[i * n + i]).collect(),
                )?]))
            }
        }
        "arange" => {
            let (start, stop, step) = (
                req.float("start", 0.)?,
                req.float("stop", 0.)?,
                req.float("step", 1.)?,
            );
            if !start.is_finite() || !stop.is_finite() || !step.is_finite() || step == 0. {
                return Err(ApiError::value(
                    "arange requires finite bounds and nonzero step",
                ));
            }
            let length = ((stop - start) / step).ceil().max(0.);
            if length > isize::MAX as f64 {
                return Err(ApiError::shape("arange too large"));
            }
            let mut out = Array::zeros(req.dtype()?, vec![length as usize])?;
            for (i, z) in out.values.iter_mut().enumerate() {
                *z = out.dtype.cast(C::new(start + i as f64 * step, 0.));
            }
            Ok(arrays(vec![out]))
        }
        "fft" | "ifft" | "rfft" | "irfft" => {
            let a = req.a(0)?;
            if a.shape.len() != 1 {
                return Err(ApiError::rank("FFT requires a vector"));
            }
            let inverse = req.op == "ifft" || req.op == "irfft";
            let n = req.int(
                "n",
                if req.op == "irfft" {
                    a.values.len().saturating_sub(1) * 2
                } else {
                    a.values.len()
                },
            )?;
            if n == 0 {
                return Err(ApiError::value("FFT length must be positive"));
            }
            let mut data = vec![crate::complex::Complex::default(); n];
            for (i, z) in a.values.iter().take(n).enumerate() {
                data[i] = crate::complex::Complex::new(z.re, z.im);
            }
            if req.op == "irfft" {
                if a.values.len() != n / 2 + 1 {
                    return Err(ApiError::shape("half-spectrum length disagrees with n"));
                }
                for i in 1..(n + 1) / 2 {
                    data[n - i] = data[i].conj();
                }
            }
            let output = crate::fft::transform(&data, inverse);
            let length = if req.op == "rfft" { n / 2 + 1 } else { n };
            let dtype = if req.op == "irfft" {
                a.dtype.real()
            } else {
                a.dtype.complex()
            };
            Ok(arrays(vec![Array::new(
                dtype,
                vec![length],
                output[..length]
                    .iter()
                    .map(|z| C::new(z.re, z.im))
                    .collect(),
            )?]))
        }
        "fftfreq" | "rfftfreq" => {
            let n = req.int("n", 0)?;
            let d = req.float("d", 1.)?;
            if n == 0 || d == 0. || !d.is_finite() {
                return Err(ApiError::value(
                    "frequency coordinates require positive n and finite nonzero spacing",
                ));
            }
            let values = if req.op == "rfftfreq" {
                (0..n / 2 + 1).map(|i| i as f64 / (n as f64 * d)).collect()
            } else {
                crate::fft::frequencies(n, d)
            };
            Ok(arrays(vec![Array::new(
                DType::Float64,
                vec![values.len()],
                values.into_iter().map(|x| C::new(x, 0.)).collect(),
            )?]))
        }
        "random" | "random_definite" | "random_semidefinite" => {
            let mut seed = req.int("seed", 1)? as u64;
            if seed == 0 {
                seed = 1;
            }
            let mut next = || {
                seed ^= seed << 13;
                seed ^= seed >> 7;
                seed ^= seed << 17;
                (seed >> 11) as f64 / (1u64 << 53) as f64
            };
            let dtype = req.dtype()?;
            let shape = if req.op == "random" {
                req.ints("shape")?
            } else {
                let n = req.int("n", 1)?;
                let zero = if req.op == "random_semidefinite" {
                    req.int("force_zeros", 1)?
                } else {
                    0
                };
                if zero > n {
                    return Err(ApiError::shape("force_zeros exceeds dimension"));
                }
                vec![n, n]
            };
            let mut a = Array::zeros(dtype, shape)?;
            for z in &mut a.values {
                let magnitude = (-2. * next().max(f64::MIN_POSITIVE).ln()).sqrt();
                let phase = std::f64::consts::TAU * next();
                *z = dtype.cast(C::new(
                    magnitude * phase.cos(),
                    if dtype.is_complex() {
                        magnitude * phase.sin()
                    } else {
                        0.
                    },
                ));
            }
            if req.op != "random" {
                let mean = req.float("mean", 1.)?;
                if !mean.is_finite() || (mean == 0. && req.op == "random_definite") {
                    return Err(ApiError::value("definite mean must be finite and nonzero"));
                }
                let packed = linalg::qr(&a)?;
                let q = linalg::unpack_qr(&packed[0], &packed[1])?.remove(0);
                let n = a.shape[0];
                let zeros = if req.op == "random_semidefinite" {
                    req.int("force_zeros", 1)?
                } else {
                    0
                };
                let sigma = mean.abs() * (std::f64::consts::PI / 8.).sqrt();
                let mut diagonal = Array::zeros(dtype, vec![n, n])?;
                for i in zeros..n {
                    let mut magnitude = 0f64;
                    for _ in 0..3 {
                        let normal = (-2. * next().max(f64::MIN_POSITIVE).ln()).sqrt()
                            * (std::f64::consts::TAU * next()).cos();
                        magnitude = magnitude.hypot(normal);
                    }
                    diagonal.values[i * n + i] = C::new((sigma * magnitude).copysign(mean), 0.);
                }
                a = q.matmul(&diagonal)?.matmul(&q.transpose("C")?)?;
            }
            Ok(arrays(vec![a]))
        }
        _ => Err(ApiError::value(format!("unknown API operation {}", req.op))),
    }
}
/// # Safety
/// Input points to `length` readable bytes. Returned string must be released once
/// with sage_api_free. Errors and Rust panics are represented as JSON, never unwound.
#[no_mangle]
pub unsafe extern "C" fn sage_api_request(input: *const u8, length: usize) -> *mut c_char {
    if input.is_null() || length > isize::MAX as usize {
        return ptr::null_mut();
    }
    let out = std::panic::catch_unwind(|| {
        let bytes = unsafe { std::slice::from_raw_parts(input, length) };
        let req: Request =
            serde_json::from_slice(bytes).map_err(|e| ApiError::value(e.to_string()))?;
        execute(&req)
    });
    let value = match out {
        Ok(Ok(response)) => json!({"ok":response}),
        Ok(Err(e)) => json!({"error":e}),
        Err(_) => json!({"error":{"kind":"RuntimeError","message":"Rust API panicked"}}),
    };
    CString::new(value.to_string()).unwrap().into_raw()
}
/// # Safety
/// `value` is null or the live pointer returned by sage_api_request, freed exactly once.
#[no_mangle]
pub unsafe extern "C" fn sage_api_free(value: *mut c_char) {
    if !value.is_null() {
        drop(unsafe { CString::from_raw(value) });
    }
}
