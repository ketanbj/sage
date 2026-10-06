//! JSON represents nonfinite IEEE values as strings, never null or invalid JSON.
use num_complex::Complex64;
use serde::{de::Error, Deserialize, Deserializer, Serialize, Serializer};
use serde_json::Value;
pub fn number(value: &Value) -> std::result::Result<f64, String> {
    if let Some(n) = value.as_f64() {
        return Ok(n);
    }
    match value.as_str() {
        Some("NaN") => Ok(f64::NAN),
        Some("Infinity") => Ok(f64::INFINITY),
        Some("-Infinity") => Ok(f64::NEG_INFINITY),
        _ => Err("expected a number or IEEE special value".into()),
    }
}
pub fn pair(value: &Value) -> std::result::Result<Complex64, String> {
    let pair = value
        .as_array()
        .filter(|a| a.len() == 2)
        .ok_or("expected [real, imaginary]")?;
    Ok(Complex64::new(number(&pair[0])?, number(&pair[1])?))
}
fn encode(x: f64) -> Value {
    if x.is_finite() {
        serde_json::json!(x)
    } else if x.is_nan() {
        serde_json::json!("NaN")
    } else if x.is_sign_positive() {
        serde_json::json!("Infinity")
    } else {
        serde_json::json!("-Infinity")
    }
}
pub fn serialize<S: Serializer>(
    values: &[Complex64],
    s: S,
) -> std::result::Result<S::Ok, S::Error> {
    values
        .iter()
        .map(|z| [encode(z.re), encode(z.im)])
        .collect::<Vec<_>>()
        .serialize(s)
}
pub fn deserialize<'de, D: Deserializer<'de>>(
    d: D,
) -> std::result::Result<Vec<Complex64>, D::Error> {
    Vec::<Value>::deserialize(d)?
        .iter()
        .map(|v| pair(v).map_err(D::Error::custom))
        .collect()
}
