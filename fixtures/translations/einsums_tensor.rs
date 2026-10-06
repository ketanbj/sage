// SAGE Rust translation of the bounded Einsums tensor contract.
// CPU f64, rank two, row-major dimensions 1..=4; no external crates.
use std::{env, fs, process};

struct Tensor {
    rows: usize,
    cols: usize,
    data: Vec<f64>,
}
impl Tensor {
    fn new(rows: usize, cols: usize) -> Self {
        Self { rows, cols, data: vec![0.0; rows * cols] }
    }
    fn at(&self, row: usize, col: usize) -> f64 {
        self.data[row * self.cols + col]
    }
    fn set(&mut self, row: usize, col: usize, value: f64) {
        self.data[row * self.cols + col] = value;
    }
}
fn run(bytes: &[u8]) -> Result<Tensor, ()> {
    if bytes.len() != 36 { return Err(()); }
    let (op, m, k, n) = (bytes[0], bytes[1] as usize, bytes[2] as usize, bytes[3] as usize);
    if op > 5 || [m, k, n].iter().any(|d| !(1..=4).contains(d)) { return Err(()); }
    let mut a = Tensor::new(m, k);
    let mut b = Tensor::new(if op == 4 { k } else { m }, if op == 4 { n } else { k });
    for (i, x) in a.data.iter_mut().enumerate() { *x = bytes[4 + i] as i8 as f64 / 8.0; }
    for (i, x) in b.data.iter_mut().enumerate() { *x = bytes[20 + i] as i8 as f64 / 8.0; }
    let mut c = Tensor::new(if op == 3 { k } else { m }, if op == 3 { m } else if op == 4 { n } else { k });
    for row in 0..c.rows {
        for col in 0..c.cols {
            let value = match op {
                0 => a.at(row, col),
                1 => a.at(row, col) + b.at(row, col),
                2 => a.at(row, col) * b.at(row, col),
                3 => a.at(col, row),
                4 => (0..k).map(|i| a.at(row, i) * b.at(i, col)).sum(),
                5 => a.at(row, col) * (bytes[20] as i8 as f64 / 8.0),
                _ => return Err(()),
            };
            c.set(row, col, value);
        }
    }
    Ok(c)
}
fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 { process::exit(64); }
    let bytes = fs::read(&args[1]).unwrap_or_else(|_| process::exit(65));
    let c = run(&bytes).unwrap_or_else(|_| process::exit(65));
    print!("{{\"shape\":[[{},{}]],\"strides\":[[{},1]],\"values\":[", c.rows, c.cols, c.cols);
    for r in 0..c.rows {
        if r != 0 { print!(","); }
        print!("[");
        for col in 0..c.cols {
            if col != 0 { print!(","); }
            print!("{:.17}", c.at(r, col));
        }
        print!("]");
    }
    println!("]}}");
}
