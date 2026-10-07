//! Pure production decisions shared by the API and bounded proof harnesses.
pub const MAGNITUDE: u64 = 0x7fff_ffff_ffff_ffff;

pub fn finite_bits(bits: u64) -> bool {
    bits & 0x7ff0_0000_0000_0000 != 0x7ff0_0000_0000_0000
}

/// Exactly the 256 signed-byte/8 values, using positive zero only.
pub fn dyad_bits(bits: u64) -> bool {
    if bits == 0 {
        return true;
    }
    let exponent = (bits >> 52) & 2047;
    if !(1020..=1027).contains(&exponent) {
        return false;
    }
    let mantissa = (bits & 0x000f_ffff_ffff_ffff) | (1 << 52);
    let shift = 1072 - exponent;
    if mantissa & ((1 << shift) - 1) != 0 {
        return false;
    }
    let units = mantissa >> shift;
    units <= if bits >> 63 == 0 { 127 } else { 128 }
}

/// For finite binary64 operands, unsigned magnitudes have the same ordering as abs.
/// Strict comparison preserves the first row on a pivot tie, including signed zero.
pub fn greater_magnitude(a: u64, b: u64) -> bool {
    a & MAGNITUDE > b & MAGNITUDE
}

#[derive(Clone, Copy)]
pub struct Metadata {
    pub f64: bool,
    pub rank: usize,
    pub rows: usize,
    pub cols: usize,
    pub values: usize,
    pub dyadic: bool,
}
pub fn eligible(a: Metadata) -> bool {
    a.f64
        && a.rank == 2
        && (1..=4).contains(&a.rows)
        && (1..=4).contains(&a.cols)
        && a.values == a.rows * a.cols
        && a.dyadic
}
pub fn route(op: u32, arity: usize, a: Metadata, b: Metadata, scalar: bool) -> bool {
    let binary = matches!(op, 1 | 2 | 4);
    op < 6
        && arity == if binary { 2 } else { 1 }
        && eligible(a)
        && (!binary
            || (eligible(b)
                && if op == 4 {
                    a.cols == b.rows
                } else {
                    a.rows == b.rows && a.cols == b.cols
                }))
        && (op != 5 || scalar)
}

/// Precondition: 0 < n <= i64::MAX, i < n. Avoids overflowing n+1.
pub fn frequency_bin(n: usize, i: usize, real: bool) -> i64 {
    if real || i < n / 2 + n % 2 {
        i as i64
    } else {
        -((n - i) as i64)
    }
}
