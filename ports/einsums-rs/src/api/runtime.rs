//! Process-wide CPU configuration and profiling with typed, synchronized state.
use super::{ApiError, Result};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    sync::{Mutex, OnceLock},
    time::Instant,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ConfigValue {
    Bool(bool),
    Integer(i64),
    Float(f64),
    Text(String),
}
#[derive(Default)]
pub struct Runtime {
    pub initialized: bool,
    pub arguments: Vec<String>,
    config: BTreeMap<(String, String), ConfigValue>,
    sections: BTreeMap<String, (f64, u64)>,
}
static RUNTIME: OnceLock<Mutex<Runtime>> = OnceLock::new();
fn state() -> std::sync::MutexGuard<'static, Runtime> {
    RUNTIME
        .get_or_init(|| Mutex::new(Runtime::default()))
        .lock()
        .unwrap_or_else(|e| e.into_inner())
}
pub fn initialize(arguments: Vec<String>) {
    let mut s = state();
    s.initialized = true;
    s.arguments = arguments;
}
pub fn finalize() {
    state().initialized = false;
}
pub fn initialized() -> bool {
    state().initialized
}
pub fn set(kind: &str, key: &str, value: ConfigValue) -> Result<()> {
    if !matches!(
        (kind, &value),
        ("bool", ConfigValue::Bool(_))
            | ("int", ConfigValue::Integer(_))
            | ("float", ConfigValue::Float(_))
            | ("str", ConfigValue::Text(_))
    ) {
        return Err(ApiError::dtype("configuration type differs from its map"));
    }
    state().config.insert((kind.into(), key.into()), value);
    Ok(())
}
pub fn get(kind: &str, key: &str) -> Result<ConfigValue> {
    state()
        .config
        .get(&(kind.into(), key.into()))
        .cloned()
        .ok_or_else(|| ApiError {
            kind: "KeyError",
            message: key.into(),
        })
}
pub fn size() -> usize {
    state().config.len()
}
pub fn profiles() -> BTreeMap<String, (f64, u64)> {
    state().sections.clone()
}
pub struct Section {
    label: String,
    start: Option<Instant>,
}
impl Section {
    pub fn new(label: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            start: Some(Instant::now()),
        }
    }
    pub fn end(&mut self) {
        if let Some(start) = self.start.take() {
            let mut s = state();
            let entry = s.sections.entry(self.label.clone()).or_default();
            entry.0 += start.elapsed().as_secs_f64();
            entry.1 += 1;
        }
    }
}
impl Drop for Section {
    fn drop(&mut self) {
        self.end();
    }
}
