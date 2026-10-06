//! Independent Rust implementation. Module coverage is recorded by SAGE, not inferred
//! from this crate's existence. No call delegates calculations to upstream Einsums.
pub mod api;
pub mod complex;
pub mod ffi;
pub mod fft;
pub mod linalg;
pub mod protocol;
pub mod tensor;
pub use tensor::{Error, Tensor, View};

/// Execute the bounded campaign protocol through a stable C ABI.
/// Python uses this exact implementation, not a second NumPy implementation.
///
/// # Safety
/// `input` must point to `length` readable bytes and `output` to `capacity` writable
/// bytes. Buffers must not overlap. Returns bytes written or a negative error code.
#[no_mangle]
pub unsafe extern "C" fn sage_einsums_execute(
    input: *const u8,
    length: usize,
    output: *mut u8,
    capacity: usize,
) -> isize {
    if input.is_null() || output.is_null() || length != 36 {
        return -1;
    }
    let result = std::panic::catch_unwind(|| {
        let bytes = unsafe { std::slice::from_raw_parts(input, length) };
        protocol::execute(bytes).map(|t| protocol::json(&t))
    });
    match result {
        Ok(Ok(text)) if text.len() <= capacity => {
            unsafe {
                std::ptr::copy_nonoverlapping(text.as_ptr(), output, text.len());
            }
            text.len() as isize
        }
        Ok(Ok(_)) => -2,
        Ok(Err(_)) => -1,
        Err(_) => -3,
    }
}

#[cfg(test)]
mod tests;
