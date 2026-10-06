use std::{error, fmt, ops::Range};
#[derive(Debug, Clone, PartialEq)]
pub enum Error {
    Shape,
    Index,
    Overflow,
    Singular,
    NonFinite,
    Unsupported,
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}
impl error::Error for Error {}
#[derive(Debug, Clone, PartialEq)]
pub struct Tensor<T = f64> {
    pub(crate) shape: Vec<usize>,
    pub(crate) strides: Vec<usize>,
    pub(crate) data: Vec<T>,
}
fn layout(shape: &[usize]) -> Result<(Vec<usize>, usize), Error> {
    let mut strides = vec![1; shape.len()];
    let mut size = 1usize;
    for i in (0..shape.len()).rev() {
        strides[i] = size;
        size = size.checked_mul(shape[i]).ok_or(Error::Overflow)?;
    }
    Ok((strides, size))
}
impl<T> Tensor<T> {
    pub fn shape(&self) -> &[usize] {
        &self.shape
    }
    pub fn strides(&self) -> &[usize] {
        &self.strides
    }
    pub fn as_slice(&self) -> &[T] {
        &self.data
    }
    pub fn as_mut_slice(&mut self) -> &mut [T] {
        &mut self.data
    }
    pub fn from_vec(shape: Vec<usize>, data: Vec<T>) -> Result<Self, Error> {
        let (strides, size) = layout(&shape)?;
        if size != data.len() {
            return Err(Error::Shape);
        }
        Ok(Self {
            shape,
            strides,
            data,
        })
    }
    fn offset(&self, indices: &[usize]) -> Result<usize, Error> {
        if indices.len() != self.shape.len() {
            return Err(Error::Index);
        }
        let mut offset = 0;
        for (i, &x) in indices.iter().enumerate() {
            if x >= self.shape[i] {
                return Err(Error::Index);
            }
            offset += x * self.strides[i];
        }
        Ok(offset)
    }
    pub fn get(&self, indices: &[usize]) -> Result<&T, Error> {
        Ok(&self.data[self.offset(indices)?])
    }
    pub fn get_mut(&mut self, indices: &[usize]) -> Result<&mut T, Error> {
        let index = self.offset(indices)?;
        Ok(&mut self.data[index])
    }
    pub fn reshape(mut self, shape: Vec<usize>) -> Result<Self, Error> {
        let (strides, size) = layout(&shape)?;
        if size != self.data.len() {
            return Err(Error::Shape);
        }
        self.shape = shape;
        self.strides = strides;
        Ok(self)
    }
    pub fn view(&self) -> View<'_, T> {
        View {
            data: &self.data,
            shape: self.shape.clone(),
            strides: self.strides.clone(),
            offset: 0,
        }
    }
}
impl<T: Clone + Default> Tensor<T> {
    pub fn zeros(shape: Vec<usize>) -> Result<Self, Error> {
        let (_, size) = layout(&shape)?;
        let mut data = Vec::new();
        data.try_reserve_exact(size).map_err(|_| Error::Overflow)?;
        data.resize(size, T::default());
        Self::from_vec(shape, data)
    }
}
impl<T: Clone> Tensor<T> {
    pub fn permute(&self, axes: &[usize]) -> Result<Self, Error> {
        self.view().permute(axes)?.to_owned()
    }
}
#[derive(Debug, Clone)]
pub struct View<'a, T = f64> {
    data: &'a [T],
    pub(crate) shape: Vec<usize>,
    pub(crate) strides: Vec<usize>,
    offset: usize,
}
impl<'a, T> View<'a, T> {
    pub fn shape(&self) -> &[usize] {
        &self.shape
    }
    pub fn strides(&self) -> &[usize] {
        &self.strides
    }
    pub fn get(&self, indices: &[usize]) -> Result<&'a T, Error> {
        if indices.len() != self.shape.len() {
            return Err(Error::Index);
        }
        let mut offset = self.offset;
        for (i, &x) in indices.iter().enumerate() {
            if x >= self.shape[i] {
                return Err(Error::Index);
            }
            offset += x * self.strides[i];
        }
        self.data.get(offset).ok_or(Error::Index)
    }
    pub fn slice(mut self, ranges: &[Range<usize>]) -> Result<Self, Error> {
        if ranges.len() != self.shape.len() {
            return Err(Error::Shape);
        }
        for (i, r) in ranges.iter().enumerate() {
            if r.start > r.end || r.end > self.shape[i] {
                return Err(Error::Index);
            }
            self.offset += r.start * self.strides[i];
            self.shape[i] = r.end - r.start;
        }
        Ok(self)
    }
    pub fn permute(mut self, axes: &[usize]) -> Result<Self, Error> {
        let mut sorted = axes.to_vec();
        sorted.sort_unstable();
        if sorted != (0..self.shape.len()).collect::<Vec<_>>() {
            return Err(Error::Shape);
        }
        self.shape = axes.iter().map(|&i| self.shape[i]).collect();
        self.strides = axes.iter().map(|&i| self.strides[i]).collect();
        Ok(self)
    }
}
impl<T: Clone> View<'_, T> {
    pub fn to_owned(&self) -> Result<Tensor<T>, Error> {
        let (strides, size) = layout(&self.shape)?;
        let mut data = Vec::with_capacity(size);
        for flat in 0..size {
            let indices: Vec<_> = self
                .shape
                .iter()
                .enumerate()
                .map(|(i, d)| flat / strides[i] % d)
                .collect();
            data.push(self.get(&indices)?.clone());
        }
        Tensor::from_vec(self.shape.clone(), data)
    }
}
impl<T: Copy> Tensor<T> {
    pub fn map(&self, f: impl Fn(T) -> T) -> Self {
        Self {
            shape: self.shape.clone(),
            strides: self.strides.clone(),
            data: self.data.iter().map(|&x| f(x)).collect(),
        }
    }
    pub fn zip(&self, b: &Self, f: impl Fn(T, T) -> T) -> Result<Self, Error> {
        if self.shape != b.shape {
            return Err(Error::Shape);
        }
        Self::from_vec(
            self.shape.clone(),
            self.data
                .iter()
                .zip(&b.data)
                .map(|(&x, &y)| f(x, y))
                .collect(),
        )
    }
}
impl<T: Copy + Default + std::ops::AddAssign + std::ops::Mul<Output = T>> Tensor<T> {
    pub fn matmul(&self, b: &Self) -> Result<Self, Error> {
        if self.shape.len() != 2 || b.shape.len() != 2 || self.shape[1] != b.shape[0] {
            return Err(Error::Shape);
        }
        let (m, k, n) = (self.shape[0], self.shape[1], b.shape[1]);
        let mut c = Self::zeros(vec![m, n])?;
        for i in 0..m {
            for j in 0..n {
                for p in 0..k {
                    c.data[i * n + j] += self.data[i * k + p] * b.data[p * n + j];
                }
            }
        }
        Ok(c)
    }
}
impl Tensor<f64> {
    pub fn sum(&self) -> f64 {
        self.data.iter().sum()
    }
    pub fn dot(&self, b: &Self) -> Result<f64, Error> {
        Ok(self.zip(b, |x, y| x * y)?.sum())
    }
    pub fn norm(&self) -> f64 {
        self.data.iter().fold(0., |a, &b| a.hypot(b))
    }
    /// Two-operand Einstein contraction with explicit, unique output labels.
    /// Repeated input labels select diagonals; labels omitted from output are reduced.
    pub fn einsum(
        &self,
        a_labels: &str,
        b: &Self,
        b_labels: &str,
        out_labels: &str,
    ) -> Result<Self, Error> {
        let (al, bl, ol) = (
            a_labels.as_bytes(),
            b_labels.as_bytes(),
            out_labels.as_bytes(),
        );
        if al.len() != self.shape.len() || bl.len() != b.shape.len() {
            return Err(Error::Shape);
        }
        let mut labels = Vec::new();
        let mut dims = Vec::new();
        for (&label, &dim) in al.iter().zip(&self.shape).chain(bl.iter().zip(&b.shape)) {
            if !label.is_ascii_alphabetic() {
                return Err(Error::Unsupported);
            }
            if let Some(i) = labels.iter().position(|&x| x == label) {
                if dims[i] != dim {
                    return Err(Error::Shape);
                }
            } else {
                labels.push(label);
                dims.push(dim);
            }
        }
        let mut output_axes = Vec::new();
        for label in ol {
            let axis = labels.iter().position(|x| x == label).ok_or(Error::Shape)?;
            if output_axes.contains(&axis) {
                return Err(Error::Shape);
            }
            output_axes.push(axis);
        }
        let mut out = Self::zeros(output_axes.iter().map(|&i| dims[i]).collect())?;
        let (strides, size) = layout(&dims)?;
        for flat in 0..size {
            let idx: Vec<_> = dims
                .iter()
                .enumerate()
                .map(|(i, d)| flat / strides[i] % d)
                .collect();
            let ai: Vec<_> = al
                .iter()
                .map(|l| idx[labels.iter().position(|x| x == l).unwrap()])
                .collect();
            let bi: Vec<_> = bl
                .iter()
                .map(|l| idx[labels.iter().position(|x| x == l).unwrap()])
                .collect();
            let oi: Vec<_> = output_axes.iter().map(|&i| idx[i]).collect();
            *out.get_mut(&oi)? += self.get(&ai)? * b.get(&bi)?;
        }
        Ok(out)
    }
}
