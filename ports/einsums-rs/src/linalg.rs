use crate::{Error, Tensor};
pub fn identity(n: usize) -> Result<Tensor, Error> {
    let mut t = Tensor::zeros(vec![n, n])?;
    for i in 0..n {
        t.data[i * n + i] = 1.;
    }
    Ok(t)
}
/// Partial-pivot Gaussian elimination; RHS contains one or more column vectors.
pub fn solve(a: &Tensor, b: &Tensor) -> Result<Tensor, Error> {
    if a.shape.len() != 2
        || a.shape[0] != a.shape[1]
        || b.shape.len() != 2
        || b.shape[0] != a.shape[0]
    {
        return Err(Error::Shape);
    }
    if !a.data.iter().chain(&b.data).all(|x| x.is_finite()) {
        return Err(Error::NonFinite);
    }
    let (n, r) = (a.shape[0], b.shape[1]);
    let mut a = a.clone();
    let mut x = b.clone();
    for k in 0..n {
        let p = (k..n)
            .max_by(|&i, &j| a.data[i * n + k].abs().total_cmp(&a.data[j * n + k].abs()))
            .unwrap();
        if a.data[p * n + k] == 0. {
            return Err(Error::Singular);
        }
        for j in 0..n {
            a.data.swap(k * n + j, p * n + j);
        }
        for j in 0..r {
            x.data.swap(k * r + j, p * r + j);
        }
        for i in k + 1..n {
            let f = a.data[i * n + k] / a.data[k * n + k];
            a.data[i * n + k] = 0.;
            for j in k + 1..n {
                a.data[i * n + j] -= f * a.data[k * n + j];
            }
            for j in 0..r {
                x.data[i * r + j] -= f * x.data[k * r + j];
            }
        }
    }
    for i in (0..n).rev() {
        for j in 0..r {
            for k in i + 1..n {
                x.data[i * r + j] -= a.data[i * n + k] * x.data[k * r + j];
            }
            x.data[i * r + j] /= a.data[i * n + i];
        }
    }
    Ok(x)
}
pub fn inverse(a: &Tensor) -> Result<Tensor, Error> {
    solve(a, &identity(*a.shape.first().ok_or(Error::Shape)?)?)
}
/// Householder QR. Returns thin Q and R, preserving Q*R=A.
pub fn qr(a: &Tensor) -> Result<(Tensor, Tensor), Error> {
    if a.shape.len() != 2 {
        return Err(Error::Shape);
    }
    if !a.data.iter().all(|x| x.is_finite()) {
        return Err(Error::NonFinite);
    }
    let (m, n) = (a.shape[0], a.shape[1]);
    let k = m.min(n);
    let mut r = a.clone();
    let mut q = identity(m)?;
    for j in 0..k {
        let mut v: Vec<_> = (j..m).map(|i| r.data[i * n + j]).collect();
        let norm = v.iter().fold(0.0_f64, |acc, &x| acc.hypot(x));
        if norm == 0. {
            continue;
        }
        v[0] += if v[0] >= 0. { norm } else { -norm };
        let vv: f64 = v.iter().map(|x| x * x).sum();
        if vv == 0. {
            continue;
        }
        for col in j..n {
            let scale = 2. * (j..m).map(|i| v[i - j] * r.data[i * n + col]).sum::<f64>() / vv;
            for i in j..m {
                r.data[i * n + col] -= scale * v[i - j];
            }
        }
        for row in 0..m {
            let scale = 2. * (j..m).map(|i| q.data[row * m + i] * v[i - j]).sum::<f64>() / vv;
            for i in j..m {
                q.data[row * m + i] -= scale * v[i - j];
            }
        }
    }
    let mut thin = Tensor::zeros(vec![m, k])?;
    let mut upper = Tensor::zeros(vec![k, n])?;
    for i in 0..m {
        for j in 0..k {
            thin.data[i * k + j] = q.data[i * m + j];
        }
    }
    for i in 0..k {
        for j in 0..n {
            upper.data[i * n + j] = r.data[i * n + j];
        }
    }
    Ok((thin, upper))
}
/// Symmetric real Jacobi eigensolver. Returns sorted values and eigenvector columns.
pub fn eigh(a: &Tensor) -> Result<(Tensor, Tensor), Error> {
    if a.shape.len() != 2 || a.shape[0] != a.shape[1] {
        return Err(Error::Shape);
    }
    if !a.data.iter().all(|x| x.is_finite()) {
        return Err(Error::NonFinite);
    }
    let n = a.shape[0];
    let mut a = a.clone();
    let mut v = identity(n)?;
    for i in 0..n {
        for j in 0..n {
            if (a.data[i * n + j] - a.data[j * n + i]).abs() > 1e-12 {
                return Err(Error::Shape);
            }
        }
    }
    let mut converged = n < 2;
    for _ in 0..(100 * n * n) {
        let mut p = 0;
        let mut q = 0;
        let mut max = 0.;
        for i in 0..n {
            for j in i + 1..n {
                if a.data[i * n + j].abs() > max {
                    max = a.data[i * n + j].abs();
                    p = i;
                    q = j;
                }
            }
        }
        if max <= 1e-14 * a.norm().max(1.) {
            converged = true;
            break;
        }
        let angle = 0.5 * (2. * a.data[p * n + q]).atan2(a.data[q * n + q] - a.data[p * n + p]);
        let (s, c) = angle.sin_cos();
        let (app, aqq, apq) = (a.data[p * n + p], a.data[q * n + q], a.data[p * n + q]);
        for i in 0..n {
            if i != p && i != q {
                let (x, y) = (a.data[i * n + p], a.data[i * n + q]);
                a.data[i * n + p] = c * x - s * y;
                a.data[p * n + i] = a.data[i * n + p];
                a.data[i * n + q] = s * x + c * y;
                a.data[q * n + i] = a.data[i * n + q];
            }
        }
        a.data[p * n + p] = c * c * app - 2. * s * c * apq + s * s * aqq;
        a.data[q * n + q] = s * s * app + 2. * s * c * apq + c * c * aqq;
        a.data[p * n + q] = 0.;
        a.data[q * n + p] = 0.;
        for i in 0..n {
            let (x, y) = (v.data[i * n + p], v.data[i * n + q]);
            v.data[i * n + p] = c * x - s * y;
            v.data[i * n + q] = s * x + c * y;
        }
    }
    if !converged {
        return Err(Error::Unsupported);
    }
    let mut order: Vec<_> = (0..n).collect();
    order.sort_by(|&i, &j| a.data[i * n + i].total_cmp(&a.data[j * n + j]));
    let values = Tensor::from_vec(vec![n], order.iter().map(|&i| a.data[i * n + i]).collect())?;
    let mut vectors = Tensor::zeros(vec![n, n])?;
    for i in 0..n {
        for j in 0..n {
            vectors.data[i * n + j] = v.data[i * n + order[j]];
        }
    }
    Ok((values, vectors))
}
