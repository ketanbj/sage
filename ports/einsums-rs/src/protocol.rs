use crate::{complex::Complex, fft, linalg, Error, Tensor};
pub const OPERATIONS: &[&str] = &[
    "copy",
    "add",
    "multiply",
    "transpose",
    "matmul",
    "scale",
    "subtract",
    "divide",
    "negate",
    "slice",
    "dot",
    "axpy",
    "axpby",
    "gemv",
    "ger",
    "norm",
    "rmsd",
    "inverse",
    "syev_values",
    "qr_reconstruct",
    "fft",
    "ifft",
    "fftfreq",
];
pub fn execute(bytes: &[u8]) -> Result<Tensor, Error> {
    if bytes.len() != 36 {
        return Err(Error::Shape);
    }
    let (op, m, k, n) = (
        bytes[0] as usize,
        bytes[1] as usize,
        bytes[2] as usize,
        bytes[3] as usize,
    );
    if op >= OPERATIONS.len() || [m, k, n].iter().any(|d| !(1..=4).contains(d)) {
        return Err(Error::Shape);
    }
    let values: Vec<_> = bytes[4..].iter().map(|&x| x as i8 as f64 / 8.).collect();
    let a = Tensor::from_vec(vec![m, k], values[..m * k].to_vec())?;
    let b = Tensor::from_vec(
        if op == 4 { vec![k, n] } else { vec![m, k] },
        values[16..16 + if op == 4 { k * n } else { m * k }].to_vec(),
    )?;
    let scalar = |x| Tensor::from_vec(vec![1, 1], vec![x]);
    match op {
        0 => Ok(a),
        1 => a.zip(&b, |x, y| x + y),
        2 => a.zip(&b, |x, y| x * y),
        3 => a.permute(&[1, 0]),
        4 => a.matmul(&b),
        5 => Ok(a.map(|x| values[16] * x)),
        6 => a.zip(&b, |x, y| x - y),
        // Construct strictly nonzero denominators in every language.
        7 => a.zip(&b, |x, y| x / (y.abs() + 1.)),
        8 => Ok(a.map(|x| -x)),
        9 => a.view().slice(&[0..m, 0..1])?.to_owned(),
        10 => scalar(a.dot(&b)?),
        11 => a.zip(&b, |x, y| 2. * x + y),
        12 => a.zip(&b, |x, y| 2. * x - 0.5 * y),
        13 => a.matmul(&Tensor::from_vec(vec![k, 1], values[16..16 + k].to_vec())?),
        14 => Tensor::from_vec(
            vec![m, k],
            (0..m * k)
                .map(|i| 2. * values[i / k] * values[16 + i % k] + a.data[i])
                .collect(),
        ),
        15 => scalar(a.norm()),
        16 => scalar((a.zip(&b, |x, y| (x - y) * (x - y))?.sum() / (m * k) as f64).sqrt()),
        17 | 18 => {
            let mut gram = a.matmul(&a.permute(&[1, 0])?)?;
            for i in 0..m {
                gram.data[i * m + i] += 1.;
            }
            if op == 17 {
                linalg::inverse(&gram)
            } else {
                linalg::eigh(&gram)?.0.reshape(vec![1, m])
            }
        }
        19 => {
            let mut square = a.matmul(&a.permute(&[1, 0])?)?;
            for i in 0..m {
                square.data[i * m + i] += 1.;
            }
            let (q, r) = linalg::qr(&square)?;
            q.matmul(&r)
        }
        20 | 21 => {
            let input: Vec<_> = (0..k)
                .map(|i| Complex::new(values[i], values[16 + i]))
                .collect();
            let out = fft::transform(&input, op == 21);
            Tensor::from_vec(vec![k, 2], out.iter().flat_map(|x| [x.re, x.im]).collect())
        }
        22 => Tensor::from_vec(vec![1, k], fft::frequencies(k, 1.)),
        _ => Err(Error::Unsupported),
    }
}
pub fn json(t: &Tensor) -> String {
    let (rows, cols) = (t.shape[0], t.shape[1]);
    let mut s = format!("{{\"shape\":[[{rows},{cols}]],\"strides\":[[{cols},1]],\"values\":[");
    for i in 0..rows {
        if i > 0 {
            s.push(',');
        }
        s.push('[');
        for j in 0..cols {
            if j > 0 {
                s.push(',');
            }
            s.push_str(&format!("{:.17}", t.data[i * cols + j]));
        }
        s.push(']');
    }
    s.push_str("]}");
    s
}
