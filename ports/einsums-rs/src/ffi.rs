//! Owned f64 tensors across the C/Python boundary.
//!
//! # Safety
//! All handles must come from this library and remain live for a call. Callers
//! must serialize writes and never free an in-use handle. Pointer/length pairs
//! must describe valid aligned memory; output buffers must not alias inputs.
use crate::{linalg, Error, Tensor};
use std::{cell::RefCell, ffi::CString, os::raw::c_char, ptr};

thread_local! { static LAST_ERROR: RefCell<CString> = RefCell::new(CString::new("").unwrap()); }
fn failure(message: String) {
    LAST_ERROR.with(|s| *s.borrow_mut() = CString::new(message.replace('\0', " ")).unwrap());
}
fn result(f: impl FnOnce() -> Result<Tensor, Error>) -> *mut Tensor {
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(f)) {
        Ok(Ok(t)) => Box::into_raw(Box::new(t)),
        Ok(Err(e)) => {
            failure(e.to_string());
            ptr::null_mut()
        }
        Err(_) => {
            failure("Rust operation panicked".into());
            ptr::null_mut()
        }
    }
}
unsafe fn array<'a, T>(p: *const T, n: usize) -> Result<&'a [T], Error> {
    if n == 0 {
        return Ok(&[]);
    }
    if p.is_null() || n > isize::MAX as usize / std::mem::size_of::<T>() {
        return Err(Error::Index);
    }
    Ok(unsafe { std::slice::from_raw_parts(p, n) })
}
#[no_mangle]
pub extern "C" fn sage_tensor_last_error() -> *const c_char {
    LAST_ERROR.with(|s| s.borrow().as_ptr())
}
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_new(
    shape: *const usize,
    rank: usize,
    data: *const f64,
    len: usize,
) -> *mut Tensor {
    result(|| {
        Tensor::from_vec(
            unsafe { array(shape, rank)? }.to_vec(),
            unsafe { array(data, len)? }.to_vec(),
        )
    })
}
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_free(handle: *mut Tensor) {
    if !handle.is_null() {
        drop(unsafe { Box::from_raw(handle) });
    }
}
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_shape(
    handle: *const Tensor,
    out: *mut usize,
    capacity: usize,
) -> isize {
    let Some(t) = (unsafe { handle.as_ref() }) else {
        return -1;
    };
    if capacity < t.shape.len() {
        return t.shape.len() as isize;
    }
    if !t.shape.is_empty() {
        if out.is_null() {
            return -1;
        }
        unsafe {
            ptr::copy_nonoverlapping(t.shape.as_ptr(), out, t.shape.len());
        }
    }
    t.shape.len() as isize
}
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_values(
    handle: *const Tensor,
    out: *mut f64,
    capacity: usize,
) -> isize {
    let Some(t) = (unsafe { handle.as_ref() }) else {
        return -1;
    };
    if capacity < t.data.len() {
        return t.data.len() as isize;
    }
    if !t.data.is_empty() {
        if out.is_null() {
            return -1;
        }
        unsafe {
            ptr::copy_nonoverlapping(t.data.as_ptr(), out, t.data.len());
        }
    }
    t.data.len() as isize
}
/// Operations: copy, negate, scale, inverse, transpose/permute, reshape,
/// add, subtract, multiply, divide, matmul, solve, sum, norm, dot, power,
/// exponential, logarithm. Returned handles have independent ownership.
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_apply(
    op: u32,
    a: *const Tensor,
    b: *const Tensor,
    scalar: f64,
    params: *const usize,
    count: usize,
) -> *mut Tensor {
    result(|| {
        let a = unsafe { a.as_ref() }.ok_or(Error::Index)?;
        let p = unsafe { array(params, count)? };
        let other = || unsafe { b.as_ref() }.ok_or(Error::Index);
        match op {
            0 => Ok(a.clone()),
            1 => Ok(a.map(|x| -x)),
            2 => Ok(a.map(|x| scalar * x)),
            3 => linalg::inverse(a),
            4 => a.permute(p),
            5 => a.clone().reshape(p.to_vec()),
            6 => a.zip(other()?, |x, y| x + y),
            7 => a.zip(other()?, |x, y| x - y),
            8 => a.zip(other()?, |x, y| x * y),
            9 => a.zip(other()?, |x, y| x / y),
            10 => a.matmul(other()?),
            11 => linalg::solve(a, other()?),
            12 => Tensor::from_vec(vec![], vec![a.sum()]),
            13 => Tensor::from_vec(vec![], vec![a.norm()]),
            14 => Tensor::from_vec(vec![], vec![a.dot(other()?)?]),
            15 => Ok(a.map(|x| x.powf(scalar))),
            16 => Ok(a.map(f64::exp)),
            17 => Ok(a.map(f64::ln)),
            18 => Ok(a.map(f64::abs)),
            19 => Ok(a.map(|x| x + scalar)),
            20 => {
                if p.len() != 2 * a.shape.len() {
                    return Err(Error::Shape);
                }
                let ranges: Vec<_> = (0..a.shape.len())
                    .map(|i| p[i]..p[i + a.shape.len()])
                    .collect();
                a.view().slice(&ranges)?.to_owned()
            }
            _ => Err(Error::Unsupported),
        }
    })
}
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_einsum(
    a: *const Tensor,
    b: *const Tensor,
    al: *const u8,
    an: usize,
    bl: *const u8,
    bn: usize,
    ol: *const u8,
    on: usize,
) -> *mut Tensor {
    result(|| {
        let a = unsafe { a.as_ref() }.ok_or(Error::Index)?;
        let b = unsafe { b.as_ref() }.ok_or(Error::Index)?;
        let al = std::str::from_utf8(unsafe { array(al, an)? }).map_err(|_| Error::Unsupported)?;
        let bl = std::str::from_utf8(unsafe { array(bl, bn)? }).map_err(|_| Error::Unsupported)?;
        let ol = std::str::from_utf8(unsafe { array(ol, on)? }).map_err(|_| Error::Unsupported)?;
        a.einsum(al, b, bl, ol)
    })
}
#[no_mangle]
pub unsafe extern "C" fn sage_tensor_set(
    a: *mut Tensor,
    indices: *const usize,
    rank: usize,
    value: f64,
) -> i32 {
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let a = unsafe { a.as_mut() }.ok_or(Error::Index)?;
        *a.get_mut(unsafe { array(indices, rank)? })? = value;
        Ok::<_, Error>(())
    })) {
        Ok(Ok(())) => 0,
        Ok(Err(e)) => {
            failure(e.to_string());
            -1
        }
        Err(_) => {
            failure("Rust indexing panicked".into());
            -1
        }
    }
}
