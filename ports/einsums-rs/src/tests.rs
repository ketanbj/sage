use crate::{complex::Complex, fft, linalg, Error, Tensor};
fn close(a: &[f64], b: &[f64]) {
    assert_eq!(a.len(), b.len());
    for (a, b) in a.iter().zip(b) {
        assert!((a - b).abs() < 1e-9, "{a} != {b}");
    }
}
#[test]
fn arbitrary_rank_permutation_and_views() {
    let a = Tensor::from_vec(vec![2, 3, 4], (0..24).map(|x| x as f64).collect()).unwrap();
    let b = a.permute(&[2, 0, 1]).unwrap();
    assert_eq!(b.shape, vec![4, 2, 3]);
    assert_eq!(b.get(&[3, 1, 2]), a.get(&[1, 2, 3]));
    let view = a.view().slice(&[1..2, 1..3, 0..2]).unwrap();
    assert_eq!(view.to_owned().unwrap().data, vec![16., 17., 20., 21.]);
    assert_eq!(a.get(&[2, 0, 0]), Err(Error::Index));
    assert!(a.permute(&[0, 0, 1]).is_err());
    assert!(Tensor::<f64>::zeros(vec![usize::MAX, 2]).is_err());
}
#[test]
fn einsum_diagonal_trace_and_outer_product() {
    let a = Tensor::from_vec(vec![2, 2], vec![1., 2., 3., 4.]).unwrap();
    let one = Tensor::from_vec(vec![], vec![1.]).unwrap();
    close(&a.einsum("ii", &one, "", "").unwrap().data, &[5.]);
    let v = Tensor::from_vec(vec![2], vec![2., 3.]).unwrap();
    close(
        &v.einsum("i", &v, "j", "ij").unwrap().data,
        &[4., 6., 6., 9.],
    );
}
#[test]
fn solve_with_pivoting_and_singular_failure() {
    let a = Tensor::from_vec(vec![2, 2], vec![0., 2., 1., 3.]).unwrap();
    let b = Tensor::from_vec(vec![2, 1], vec![4., 7.]).unwrap();
    close(&linalg::solve(&a, &b).unwrap().data, &[1., 2.]);
    assert_eq!(
        linalg::inverse(&Tensor::zeros(vec![2, 2]).unwrap()),
        Err(Error::Singular)
    );
}
#[test]
fn qr_and_eigensystem_residuals() {
    for shape in [vec![3, 2], vec![2, 3]] {
        let a = Tensor::from_vec(shape, vec![2., 1., 0., 3., 4., 1.]).unwrap();
        let (q, r) = linalg::qr(&a).unwrap();
        close(&q.matmul(&r).unwrap().data, &a.data);
        close(
            &q.permute(&[1, 0]).unwrap().matmul(&q).unwrap().data,
            &[1., 0., 0., 1.],
        );
    }
    let a = Tensor::from_vec(vec![3, 3], vec![2., 1., 0., 1., 2., 0., 0., 0., 3.]).unwrap();
    let (w, v) = linalg::eigh(&a).unwrap();
    close(&w.data, &[1., 3., 3.]);
    let mut vd = v.clone();
    for i in 0..3 {
        for j in 0..3 {
            vd.data[i * 3 + j] *= w.data[j];
        }
    }
    close(&a.matmul(&v).unwrap().data, &vd.data);
}
#[test]
fn inverse_transform_is_unnormalized() {
    let a = vec![
        Complex::new(1., 2.),
        Complex::new(-3., 1.),
        Complex::new(2., -1.),
    ];
    let b = fft::transform(&fft::transform(&a, false), true);
    for (a, b) in a.iter().zip(b) {
        close(&[b.re, b.im], &[3. * a.re, 3. * a.im]);
    }
    close(&fft::frequencies(4, 1.), &[0., 0.25, -0.5, -0.25]);
}
#[test]
fn bounded_api_rejects_inconsistent_shape_data_metadata() {
    use crate::api::{
        array::{Array, DType},
        Request,
    };
    let mut a = Array::new(
        DType::Float64,
        vec![1, 1],
        vec![num_complex::Complex64::new(1., 0.)],
    )
    .unwrap();
    a.values.resize(17, num_complex::Complex64::new(1., 0.));
    let request = Request {
        op: "copy".into(),
        arrays: vec![a],
        params: serde_json::json!({}),
    };
    assert!(crate::api::execute(&request).is_err());
}

#[test]
fn concurrent_runtime_configuration_and_profile_lifetimes() {
    use crate::api::runtime::{self, ConfigValue, Section};
    let workers: Vec<_> = (0..8)
        .map(|i| {
            std::thread::spawn(move || {
                let key = format!("pending-proofs-worker-{i}");
                for value in 0..64 {
                    runtime::set("int", &key, ConfigValue::Integer(value)).unwrap();
                    assert!(matches!(runtime::get("int", &key).unwrap(), ConfigValue::Integer(x) if x == value));
                    assert!(runtime::set("int", &key, ConfigValue::Text("invalid".into())).is_err());
                    assert!(matches!(runtime::get("int", &key).unwrap(), ConfigValue::Integer(x) if x == value));
                    let mut section = Section::new(&key);
                    section.end();
                    section.end(); // Explicit end plus drop must record only once.
                }
                assert_eq!(runtime::profiles()[&key].1, 64);
            })
        })
        .collect();
    for worker in workers {
        worker.join().unwrap();
    }
}
