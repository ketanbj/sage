//! Public API bridge to the formally checked six-operation Tensor implementation.
//! Only the proof domain uses this path; other inputs retain the general Array API.
use super::{
    array::{Array, DType},
    arrays, Request, Response, Result,
};
use crate::Tensor;
use num_complex::Complex64 as C;

fn dyad(x: f64) -> bool {
    crate::proof_contract::dyad_bits(x.to_bits())
}
fn metadata(a: &Array) -> crate::proof_contract::Metadata {
    crate::proof_contract::Metadata {
        f64: a.dtype == DType::Float64,
        rank: a.shape.len(),
        rows: a.shape.first().copied().unwrap_or(0),
        cols: a.shape.get(1).copied().unwrap_or(0),
        values: a.values.len(),
        dyadic: a.values.iter().all(|z| z.im == 0.0 && dyad(z.re)),
    }
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
    let a = req.arrays.first()?;
    let b = req.arrays.get(1).unwrap_or(a);
    if !crate::proof_contract::route(
        op,
        req.arrays.len(),
        metadata(a),
        metadata(b),
        alpha.im == 0.0 && dyad(alpha.re),
    ) {
        return None;
    }
    let ta = Tensor::from_vec(a.shape.clone(), a.values.iter().map(|z| z.re).collect()).ok()?;
    let tb = if binary {
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
