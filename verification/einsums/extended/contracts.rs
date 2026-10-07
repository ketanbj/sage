#![allow(dead_code)]
#[path = "../../../ports/einsums-rs/src/proof_contract.rs"] mod contract;
#[path = "../../../ports/einsums-rs/src/tensor.rs"] mod tensor;
use contract::Metadata;
fn metadata() -> Metadata {
 Metadata { f64:kani::any(), rank:kani::any(), rows:kani::any(), cols:kani::any(), values:kani::any(), dyadic:kani::any() }
}
fn valid(a: Metadata) -> bool {
 if !a.f64 || !a.dyadic || a.rank != 2 || a.rows == 0 || a.cols == 0 || a.rows > 4 || a.cols > 4 {false}
 else {a.values == a.rows * a.cols}
}
#[kani::proof] fn adapter_guard() {
 let (op,arity,a,b,scalar) = (kani::any::<u32>(),kani::any::<usize>(),metadata(),metadata(),kani::any::<bool>());
 let expected = match op {
  0|3 => arity==1 && valid(a),
  5 => arity==1 && valid(a) && scalar,
  1|2 => arity==2 && valid(a) && valid(b) && a.rows==b.rows && a.cols==b.cols,
  4 => arity==2 && valid(a) && valid(b) && a.cols==b.rows,
  _ => false,
 };
 assert_eq!(contract::route(op,arity,a,b,scalar),expected,"adapter contract matches specification");
}
#[kani::proof] fn dyad_sound() {
 let bits:u64=kani::any();
 if contract::dyad_bits(bits) {
   let x=f64::from_bits(bits);
   assert!(x.is_finite() && x>=-16.0 && x<=15.875 && (x*8.0).fract()==0.0 && (bits==0 || x!=0.0),"dyadic eligibility matches specification");
 }
}
#[kani::proof] fn dyad_complete() {
 let x=kani::any::<i8>() as f64/8.0;
 assert!(contract::dyad_bits(x.to_bits()),"all signed byte dyadics accepted");
}
#[kani::proof] fn real_pivot() {
 let (a,b):(u64,u64)=(kani::any(),kani::any());
 kani::assume(contract::finite_bits(a) && contract::finite_bits(b));
 assert_eq!(contract::greater_magnitude(a,b),f64::from_bits(a).abs()>f64::from_bits(b).abs(),"pivot order matches finite absolute values");
}
#[kani::proof] fn frequency() {
 let (n,i,real):(usize,usize,bool)=(kani::any(),kani::any(),kani::any());
 kani::assume(n>0 && n<=i64::MAX as usize && i<n);
 let expected = if real || i <= (n-1)/2 {i as i64} else {i as i64-n as i64};
 assert_eq!(contract::frequency_bin(n,i,real),expected,"frequency bin matches specification");
}
fn layout<const M:usize,const K:usize>() {
 let data:Vec<u64>=(0..M*K).map(|_|kani::any()).collect();
 let a=tensor::Tensor::from_vec(vec![M,K],data.clone()).unwrap();
 let copy=a.clone(); let t=a.permute(&[1,0]).unwrap();
 for i in 0..M*K {
  assert_eq!(copy.as_slice()[i],data[i],"copy preserves all 64 bits");
  assert_eq!(a.as_slice()[i],data[i],"input unchanged");
 }
 assert_eq!(t.shape(),&[K,M]); assert_eq!(t.strides(),&[M,1]);
 for r in 0..M {for c in 0..K {
  assert_eq!(*t.get(&[c,r]).unwrap(),data[r*K+c],"transpose preserves all 64 bits");
 }}
}
macro_rules! layout_proof {($name:ident,$m:expr,$k:expr)=>{
 #[kani::proof] #[kani::unwind(66)] fn $name(){layout::<$m,$k>();}
};}
layout_proof!(layout_1x1,1,1);
layout_proof!(layout_1x2,1,2);
layout_proof!(layout_1x3,1,3);
layout_proof!(layout_1x4,1,4);
layout_proof!(layout_1x5,1,5);
layout_proof!(layout_1x6,1,6);
layout_proof!(layout_1x7,1,7);
layout_proof!(layout_1x8,1,8);
layout_proof!(layout_2x1,2,1);
layout_proof!(layout_2x2,2,2);
layout_proof!(layout_2x3,2,3);
layout_proof!(layout_2x4,2,4);
layout_proof!(layout_2x5,2,5);
layout_proof!(layout_2x6,2,6);
layout_proof!(layout_2x7,2,7);
layout_proof!(layout_2x8,2,8);
layout_proof!(layout_3x1,3,1);
layout_proof!(layout_3x2,3,2);
layout_proof!(layout_3x3,3,3);
layout_proof!(layout_3x4,3,4);
layout_proof!(layout_3x5,3,5);
layout_proof!(layout_3x6,3,6);
layout_proof!(layout_3x7,3,7);
layout_proof!(layout_3x8,3,8);
layout_proof!(layout_4x1,4,1);
layout_proof!(layout_4x2,4,2);
layout_proof!(layout_4x3,4,3);
layout_proof!(layout_4x4,4,4);
layout_proof!(layout_4x5,4,5);
layout_proof!(layout_4x6,4,6);
layout_proof!(layout_4x7,4,7);
layout_proof!(layout_4x8,4,8);
layout_proof!(layout_5x1,5,1);
layout_proof!(layout_5x2,5,2);
layout_proof!(layout_5x3,5,3);
layout_proof!(layout_5x4,5,4);
layout_proof!(layout_5x5,5,5);
layout_proof!(layout_5x6,5,6);
layout_proof!(layout_5x7,5,7);
layout_proof!(layout_5x8,5,8);
layout_proof!(layout_6x1,6,1);
layout_proof!(layout_6x2,6,2);
layout_proof!(layout_6x3,6,3);
layout_proof!(layout_6x4,6,4);
layout_proof!(layout_6x5,6,5);
layout_proof!(layout_6x6,6,6);
layout_proof!(layout_6x7,6,7);
layout_proof!(layout_6x8,6,8);
layout_proof!(layout_7x1,7,1);
layout_proof!(layout_7x2,7,2);
layout_proof!(layout_7x3,7,3);
layout_proof!(layout_7x4,7,4);
layout_proof!(layout_7x5,7,5);
layout_proof!(layout_7x6,7,6);
layout_proof!(layout_7x7,7,7);
layout_proof!(layout_7x8,7,8);
layout_proof!(layout_8x1,8,1);
layout_proof!(layout_8x2,8,2);
layout_proof!(layout_8x3,8,3);
layout_proof!(layout_8x4,8,4);
layout_proof!(layout_8x5,8,5);
layout_proof!(layout_8x6,8,6);
layout_proof!(layout_8x7,8,7);
layout_proof!(layout_8x8,8,8);
