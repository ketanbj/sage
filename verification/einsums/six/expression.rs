// Injective prefix encoding of ordered expression trees, not a numeric approximation.
// Tokens: +0=0, inputs=2..33, add=60, multiply=61. Six bits per token;
// the longest expression has 17 tokens (four-term left-associated dot product).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Expr { pub code: u128, pub len: u32 }
impl Default for Expr {
    fn default() -> Self { Self { code: 0, len: 1 } }
}
impl Expr {
    pub fn leaf(index: usize) -> Self {
        assert!(index < 32);
        Self { code: (index + 2) as u128, len: 1 }
    }
    fn join(self, other: Self, op: u128) -> Self {
        let len = self.len + other.len + 1;
        assert!(len <= 21);
        Self { code: (op << ((len - 1) * 6)) | (self.code << (other.len * 6)) | other.code, len }
    }
}
impl std::ops::Add for Expr {
    type Output = Self;
    fn add(self, other: Self) -> Self { self.join(other, 60) }
}
impl std::ops::Mul for Expr {
    type Output = Self;
    fn mul(self, other: Self) -> Self { self.join(other, 61) }
}
impl std::ops::AddAssign for Expr {
    fn add_assign(&mut self, other: Self) { *self = *self + other; }
}

// Independent specification emits the prefix token stream directly.
pub fn expected(op: usize, _m: usize, k: usize, n: usize, r: usize, c: usize) -> Expr {
    let mut code=0u128; let mut len=0u32;
    let mut emit=|token:u128| {code=(code<<6)|token; len+=1;};
    let a=(r*k+c+2) as u128; let b=(r*k+c+18) as u128;
    match op {
     0=>emit(a), 1=>{emit(60);emit(a);emit(b);},2=>{emit(61);emit(a);emit(b);},
     3=>emit((c*k+r+2) as u128),
     4=>{for _ in 0..k {emit(60);} emit(0);for p in 0..k {emit(61);emit((r*k+p+2) as u128);emit((p*n+c+18) as u128);}},
     5=>{emit(61);emit(18);emit(a);}, _=>unreachable!(),
    }
    assert!(len<=21); Expr{code,len}
}
