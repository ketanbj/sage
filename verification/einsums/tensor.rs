#![allow(dead_code)]
#[path = "../../ports/einsums-rs/src/tensor.rs"]
mod tensor;

fn check<const M: usize, const K: usize>(transpose: bool) {
    let bytes: [i8; 16] = kani::any();
    let data: Vec<f64> = bytes[..M * K].iter().map(|&x| x as f64 / 8.0).collect();
    let source = tensor::Tensor::from_vec(vec![M, K], data).unwrap();
    let result = if transpose {
        source.permute(&[1, 0]).unwrap()
    } else {
        source.clone()
    };
    let (rows, cols) = if transpose { (K, M) } else { (M, K) };
    assert_eq!(result.shape(), &[rows, cols]);
    assert_eq!(result.strides(), &[cols, 1]);
    for row in 0..rows {
        for col in 0..cols {
            let index = if transpose {
                col * K + row
            } else {
                row * K + col
            };
            assert_eq!(
                result.get(&[row, col]).unwrap().to_bits(),
                (bytes[index] as f64 / 8.0).to_bits()
            );
        }
    }
    for i in 0..M * K {
        assert_eq!(
            source.as_slice()[i].to_bits(),
            (bytes[i] as f64 / 8.0).to_bits()
        );
    }
}

macro_rules! proofs {
    ($copy:ident, $transpose:ident, $m:expr, $k:expr) => {
        #[kani::proof]
        #[kani::unwind(18)]
        fn $copy() {
            check::<$m, $k>(false);
        }
        #[kani::proof]
        #[kani::unwind(18)]
        fn $transpose() {
            check::<$m, $k>(true);
        }
    };
}
proofs!(copy_1x1, transpose_1x1, 1, 1);
proofs!(copy_1x2, transpose_1x2, 1, 2);
proofs!(copy_1x3, transpose_1x3, 1, 3);
proofs!(copy_1x4, transpose_1x4, 1, 4);
proofs!(copy_2x1, transpose_2x1, 2, 1);
proofs!(copy_2x2, transpose_2x2, 2, 2);
proofs!(copy_2x3, transpose_2x3, 2, 3);
proofs!(copy_2x4, transpose_2x4, 2, 4);
proofs!(copy_3x1, transpose_3x1, 3, 1);
proofs!(copy_3x2, transpose_3x2, 3, 2);
proofs!(copy_3x3, transpose_3x3, 3, 3);
proofs!(copy_3x4, transpose_3x4, 3, 4);
proofs!(copy_4x1, transpose_4x1, 4, 1);
proofs!(copy_4x2, transpose_4x2, 4, 2);
proofs!(copy_4x3, transpose_4x3, 4, 3);
proofs!(copy_4x4, transpose_4x4, 4, 4);
