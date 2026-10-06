use super::{ApiError, Result};
use nalgebra::DMatrix;
use num_complex::Complex64 as C;
use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DType {
    Float32,
    Float64,
    Complex64,
    Complex128,
}
impl DType {
    pub fn real(self) -> Self {
        match self {
            Self::Float32 | Self::Complex64 => Self::Float32,
            _ => Self::Float64,
        }
    }
    pub fn complex(self) -> Self {
        match self {
            Self::Float32 | Self::Complex64 => Self::Complex64,
            _ => Self::Complex128,
        }
    }
    pub fn is_complex(self) -> bool {
        matches!(self, Self::Complex64 | Self::Complex128)
    }
    pub fn epsilon(self) -> f64 {
        if self.real() == Self::Float32 {
            f32::EPSILON as f64
        } else {
            f64::EPSILON
        }
    }
    pub fn cast(self, z: C) -> C {
        match self {
            Self::Float32 => C::new(z.re as f32 as f64, 0.),
            Self::Float64 => C::new(z.re, 0.),
            Self::Complex64 => C::new(z.re as f32 as f64, z.im as f32 as f64),
            Self::Complex128 => z,
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Array {
    pub dtype: DType,
    pub shape: Vec<usize>,
    #[serde(with = "super::complex_values")]
    pub values: Vec<C>,
}
pub fn size(shape: &[usize]) -> Result<usize> {
    shape.iter().try_fold(1usize, |n, d| {
        n.checked_mul(*d)
            .ok_or_else(|| ApiError::shape("shape overflows address space"))
    })
}
pub fn strides(shape: &[usize]) -> Result<Vec<usize>> {
    let mut out = vec![1; shape.len()];
    let mut n = 1usize;
    for i in (0..shape.len()).rev() {
        out[i] = n;
        n = n
            .checked_mul(shape[i])
            .ok_or_else(|| ApiError::shape("stride overflow"))?;
    }
    Ok(out)
}
pub fn coords(mut flat: usize, shape: &[usize]) -> Vec<usize> {
    let mut out = vec![0; shape.len()];
    for i in (0..shape.len()).rev() {
        out[i] = flat % shape[i];
        flat /= shape[i];
    }
    out
}
impl Array {
    pub fn new(dtype: DType, shape: Vec<usize>, values: Vec<C>) -> Result<Self> {
        if size(&shape)? != values.len() {
            return Err(ApiError::shape("shape and data length differ"));
        }
        Ok(Self {
            dtype,
            shape,
            values: values.into_iter().map(|z| dtype.cast(z)).collect(),
        })
    }
    pub fn validate(&self) -> Result<()> {
        if size(&self.shape)? != self.values.len() {
            return Err(ApiError::shape("shape and data length differ"));
        }
        if !self.dtype.is_complex() && self.values.iter().any(|x| x.im != 0.) {
            return Err(ApiError::dtype("real array contains imaginary values"));
        }
        Ok(())
    }
    pub fn zeros(dtype: DType, shape: Vec<usize>) -> Result<Self> {
        let n = size(&shape)?;
        let mut values = Vec::new();
        values
            .try_reserve_exact(n)
            .map_err(|_| ApiError::shape("allocation too large"))?;
        values.resize(n, C::new(0., 0.));
        Ok(Self {
            dtype,
            shape,
            values,
        })
    }
    pub fn scalar(dtype: DType, value: C) -> Self {
        Self {
            dtype,
            shape: vec![],
            values: vec![dtype.cast(value)],
        }
    }
    pub fn identity(dtype: DType, n: usize) -> Result<Self> {
        let mut a = Self::zeros(dtype, vec![n, n])?;
        for i in 0..n {
            a.values[i * n + i] = C::new(1., 0.);
        }
        Ok(a)
    }
    pub fn map(&self, f: impl Fn(C) -> C) -> Self {
        Self {
            dtype: self.dtype,
            shape: self.shape.clone(),
            values: self.values.iter().map(|&x| self.dtype.cast(f(x))).collect(),
        }
    }
    pub fn zip(&self, b: &Self, f: impl Fn(C, C) -> C) -> Result<Self> {
        if self.dtype != b.dtype {
            return Err(ApiError::dtype("operand dtypes must match"));
        }
        if self.shape != b.shape && !self.shape.is_empty() && !b.shape.is_empty() {
            return Err(ApiError::shape("operand shapes must match"));
        }
        let shape = if self.shape.is_empty() {
            b.shape.clone()
        } else {
            self.shape.clone()
        };
        let n = size(&shape)?;
        Self::new(
            self.dtype,
            shape,
            (0..n)
                .map(|i| {
                    f(
                        self.values[if self.shape.is_empty() { 0 } else { i }],
                        b.values[if b.shape.is_empty() { 0 } else { i }],
                    )
                })
                .collect(),
        )
    }
    pub fn reshape(&self, shape: Vec<usize>) -> Result<Self> {
        Self::new(self.dtype, shape, self.values.clone())
    }
    pub fn permute(&self, axes: &[usize]) -> Result<Self> {
        let mut sorted = axes.to_vec();
        sorted.sort_unstable();
        if sorted != (0..self.shape.len()).collect::<Vec<_>>() {
            return Err(ApiError::shape("axes must be a permutation"));
        }
        let shape: Vec<_> = axes.iter().map(|&i| self.shape[i]).collect();
        let old = strides(&self.shape)?;
        Self::new(
            self.dtype,
            shape.clone(),
            (0..self.values.len())
                .map(|i| {
                    let c = coords(i, &shape);
                    self.values[c
                        .iter()
                        .enumerate()
                        .map(|(j, x)| x * old[axes[j]])
                        .sum::<usize>()]
                })
                .collect(),
        )
    }
    pub fn transpose(&self, mode: &str) -> Result<Self> {
        match mode.to_uppercase().as_str() {
            "N" => Ok(self.clone()),
            "T" | "C" => {
                self.matrix_shape()?;
                let out = self.permute(&[1, 0])?;
                Ok(if mode.eq_ignore_ascii_case("C") {
                    out.map(|x| x.conj())
                } else {
                    out
                })
            }
            _ => Err(ApiError::value("transpose must be N, T, or C")),
        }
    }
    pub fn matrix_shape(&self) -> Result<(usize, usize)> {
        if self.shape.len() != 2 {
            Err(ApiError::rank("matrix required"))
        } else {
            Ok((self.shape[0], self.shape[1]))
        }
    }
    pub fn matrix(&self) -> Result<DMatrix<C>> {
        let (m, n) = self.matrix_shape()?;
        if self
            .values
            .iter()
            .any(|z| !z.re.is_finite() || !z.im.is_finite())
        {
            return Err(ApiError::value("factorizations require finite inputs"));
        }
        Ok(DMatrix::from_row_slice(m, n, &self.values))
    }
    pub fn from_matrix(dtype: DType, a: &DMatrix<C>) -> Result<Self> {
        Self::new(
            dtype,
            vec![a.nrows(), a.ncols()],
            (0..a.nrows())
                .flat_map(|i| (0..a.ncols()).map(move |j| a[(i, j)]))
                .collect(),
        )
    }
    pub fn matmul(&self, b: &Self) -> Result<Self> {
        if self.dtype != b.dtype {
            return Err(ApiError::dtype("operand dtypes must match"));
        }
        let (m, k) = self.matrix_shape()?;
        let (l, n) = b.matrix_shape()?;
        if k != l {
            return Err(ApiError::shape("matrix contraction dimensions differ"));
        }
        let mut c = Self::zeros(self.dtype, vec![m, n])?;
        for i in 0..m {
            for j in 0..n {
                let mut s = C::new(0., 0.);
                for t in 0..k {
                    s += self.values[i * k + t] * b.values[t * n + j];
                }
                c.values[i * n + j] = self.dtype.cast(s);
            }
        }
        Ok(c)
    }
    pub fn einsum(&self, al: &[String], b: &Self, bl: &[String], ol: &[String]) -> Result<Self> {
        if al.len() != self.shape.len() || bl.len() != b.shape.len() {
            return Err(ApiError::rank("labels must match operand ranks"));
        }
        if self.dtype != b.dtype {
            return Err(ApiError::dtype("operand dtypes must match"));
        }
        let (mut labels, mut dims) = (Vec::<String>::new(), Vec::new());
        for (label, &dim) in al.iter().zip(&self.shape).chain(bl.iter().zip(&b.shape)) {
            if let Some(i) = labels.iter().position(|x| x == label) {
                if dims[i] != dim {
                    return Err(ApiError::shape("label dimensions differ"));
                }
            } else {
                labels.push(label.clone());
                dims.push(dim);
            }
        }
        let mut out_axes = Vec::new();
        for label in ol {
            let axis = labels
                .iter()
                .position(|x| x == label)
                .ok_or_else(|| ApiError::shape("unknown output label"))?;
            if out_axes.contains(&axis) {
                return Err(ApiError::shape("repeated output label"));
            }
            out_axes.push(axis);
        }
        let mut c = Self::zeros(self.dtype, out_axes.iter().map(|&i| dims[i]).collect())?;
        let aa: Vec<_> = al
            .iter()
            .map(|x| labels.iter().position(|l| l == x).unwrap())
            .collect();
        let ba: Vec<_> = bl
            .iter()
            .map(|x| labels.iter().position(|l| l == x).unwrap())
            .collect();
        let (sa, sb, sc) = (
            strides(&self.shape)?,
            strides(&b.shape)?,
            strides(&c.shape)?,
        );
        for flat in 0..size(&dims)? {
            let idx = coords(flat, &dims);
            let ai = aa.iter().zip(&sa).map(|(a, s)| idx[*a] * s).sum::<usize>();
            let bi = ba.iter().zip(&sb).map(|(a, s)| idx[*a] * s).sum::<usize>();
            let ci = out_axes
                .iter()
                .zip(&sc)
                .map(|(a, s)| idx[*a] * s)
                .sum::<usize>();
            c.values[ci] += self.values[ai] * b.values[bi];
        }
        for z in &mut c.values {
            *z = c.dtype.cast(*z);
        }
        Ok(c)
    }
    pub fn norm(&self) -> f64 {
        self.values.iter().fold(0f64, |n, z| n.hypot(z.norm()))
    }
    pub fn unfold(&self, mode: usize) -> Result<Self> {
        if mode >= self.shape.len() {
            return Err(ApiError::rank("mode outside tensor rank"));
        }
        let axes: Vec<_> = std::iter::once(mode)
            .chain((0..self.shape.len()).filter(|&i| i != mode))
            .collect();
        let columns = size(
            &self
                .shape
                .iter()
                .enumerate()
                .filter(|(i, _)| *i != mode)
                .map(|(_, &d)| d)
                .collect::<Vec<_>>(),
        )?;
        self.permute(&axes)?
            .reshape(vec![self.shape[mode], columns])
    }
    pub fn mode_product(&self, b: &Self, mode: usize) -> Result<Self> {
        let (r, n) = b.matrix_shape()?;
        if mode >= self.shape.len() || self.shape[mode] != n {
            return Err(ApiError::shape("mode product dimensions differ"));
        }
        let product = b.matmul(&self.unfold(mode)?)?;
        let axes: Vec<_> = std::iter::once(mode)
            .chain((0..self.shape.len()).filter(|&i| i != mode))
            .collect();
        let mut shape = self.shape.clone();
        shape[mode] = r;
        let temp = product.reshape(axes.iter().map(|&i| shape[i]).collect())?;
        let mut inverse = vec![0; axes.len()];
        for (i, &a) in axes.iter().enumerate() {
            inverse[a] = i;
        }
        temp.permute(&inverse)
    }
}
