use std::ops::{Add, Div, Mul, Neg, Sub};
#[derive(Clone, Copy, Debug, Default, PartialEq)]
#[repr(C)]
pub struct Complex {
    pub re: f64,
    pub im: f64,
}
impl Complex {
    pub fn new(re: f64, im: f64) -> Self {
        Self { re, im }
    }
    pub fn conj(self) -> Self {
        Self::new(self.re, -self.im)
    }
    pub fn norm(self) -> f64 {
        self.re.hypot(self.im)
    }
}
impl Add for Complex {
    type Output = Self;
    fn add(self, b: Self) -> Self {
        Self::new(self.re + b.re, self.im + b.im)
    }
}
impl Sub for Complex {
    type Output = Self;
    fn sub(self, b: Self) -> Self {
        Self::new(self.re - b.re, self.im - b.im)
    }
}
impl Mul for Complex {
    type Output = Self;
    fn mul(self, b: Self) -> Self {
        Self::new(
            self.re * b.re - self.im * b.im,
            self.re * b.im + self.im * b.re,
        )
    }
}
impl Div for Complex {
    type Output = Self;
    fn div(self, b: Self) -> Self {
        if b.re.abs() >= b.im.abs() {
            let ratio = b.im / b.re;
            let d = b.re + b.im * ratio;
            Self::new(
                (self.re + self.im * ratio) / d,
                (self.im - self.re * ratio) / d,
            )
        } else {
            let ratio = b.re / b.im;
            let d = b.im + b.re * ratio;
            Self::new(
                (self.re * ratio + self.im) / d,
                (self.im * ratio - self.re) / d,
            )
        }
    }
}
impl Neg for Complex {
    type Output = Self;
    fn neg(self) -> Self {
        Self::new(-self.re, -self.im)
    }
}
