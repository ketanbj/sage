//! Public API bridge to the formally checked six-operation Tensor implementation.
//! Only the proof domain uses this path; other inputs retain the general Array API.
use super::{
    array::{Array, DType},
    arrays, Request, Response, Result,
};
use crate::Tensor;
use num_complex::Complex64 as C;

fn dyad(x: f64) -> bool {
    x.is_finite()
        && (-16.0..=15.875).contains(&x)
        && (x * 8.0).fract() == 0.0
        && (x != 0.0 || x.to_bits() == 0)
}
fn eligible(a: &Array) -> bool {
    a.dtype == DType::Float64
        && a.shape.len() == 2
        && a.shape.iter().all(|&d| (1..=4).contains(&d))
        && a.values.len() == a.shape[0] * a.shape[1]
        && a.values.iter().all(|z| z.im == 0.0 && dyad(z.re))
}
pub(super) fn execute(req: &Request, alpha: C) -> Option<Result<Response>> {
    let op = match req.op.as_str() {
        "copy" => 0,
        "add" => 1,
        "multiply" => 2,
        "permute" if req.ints("axes").ok().as_deref() == Some(&[1, 0]) => 3,
        "matmul" if req.text("trans_a", "N") == "N" && req.text("trans_b", "N") == "N" => 4,
        "scale" if alpha.im == 0.0 && dyad(alpha.re) => 5,
        _ => return None,
    };
    let binary = matches!(op, 1 | 2 | 4);
    if req.arrays.len() != if binary { 2 } else { 1 } {
        return None;
    }
    let a = &req.arrays[0];
    if !eligible(a) {
        return None;
    }
    let ta = Tensor::from_vec(a.shape.clone(), a.values.iter().map(|z| z.re).collect()).ok()?;
    let tb = if binary {
        let b = &req.arrays[1];
        if !eligible(b)
            || if op == 4 {
                a.shape[1] != b.shape[0]
            } else {
                a.shape != b.shape
            }
        {
            return None;
        }
        Some(Tensor::from_vec(b.shape.clone(), b.values.iter().map(|z| z.re).collect()).ok()?)
    } else {
        None
    };
    let out = match op {
        0 => ta.clone(),
        1 => ta.zip(tb.as_ref()?, |x, y| x + y).ok()?,
        2 => ta.zip(tb.as_ref()?, |x, y| x * y).ok()?,
        3 => ta.permute(&[1, 0]).ok()?,
        4 => ta.matmul(tb.as_ref()?).ok()?,
        5 => ta.map(|x| alpha.re * x),
        _ => return None,
    };
    Some(
        Array::new(
            DType::Float64,
            out.shape().to_vec(),
            out.as_slice().iter().map(|&x| C::new(x, 0.0)).collect(),
        )
        .map(|a| arrays(vec![a])),
    )
}
