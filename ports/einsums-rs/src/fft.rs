use crate::complex::Complex;
/// Independent complex DFT. Einsums' inverse is unnormalized, matching FFTW.
pub fn transform(input: &[Complex], inverse: bool) -> Vec<Complex> {
    let n = input.len();
    let sign = if inverse { 1. } else { -1. };
    (0..n)
        .map(|k| {
            input
                .iter()
                .enumerate()
                .fold(Complex::default(), |acc, (j, &x)| {
                    let phase = sign * std::f64::consts::TAU * (j as f64) * (k as f64) / (n as f64);
                    let (s, c) = phase.sin_cos();
                    acc + x * Complex::new(c, s)
                })
        })
        .collect()
}
pub fn frequencies(n: usize, d: f64) -> Vec<f64> {
    (0..n)
        .map(|i| crate::proof_contract::frequency_bin(n, i, false) as f64 / (n as f64 * d))
        .collect()
}
