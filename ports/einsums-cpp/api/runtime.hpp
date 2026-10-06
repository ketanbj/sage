#pragma once
#include "array.hpp"
#include <chrono>
#include <iostream>
#include <map>
#include <mutex>
#include <variant>
namespace sage_cpp::api::runtime {
using ConfigValue = std::variant<bool, std::int64_t, double, std::string>;
struct State {
  std::mutex mutex;
  bool initialized = false;
  std::vector<std::string> arguments;
  std::map<std::pair<std::string, std::string>, ConfigValue> config;
  std::map<std::string, std::pair<double, std::uint64_t>> sections;
};
inline State &state() {
  static State instance;
  return instance;
}
inline void initialize(std::vector<std::string> args = {}) {
  auto &s = state();
  std::lock_guard lock(s.mutex);
  s.initialized = true;
  s.arguments = std::move(args);
}
inline void finalize() {
  auto &s = state();
  std::lock_guard lock(s.mutex);
  s.initialized = false;
}
inline bool initialized() {
  auto &s = state();
  std::lock_guard lock(s.mutex);
  return s.initialized;
}
inline bool gpu_enabled() { return false; }
inline void set(const std::string &kind, const std::string &key,
                ConfigValue value) {
  bool valid = (kind == "bool" && std::holds_alternative<bool>(value)) ||
               (kind == "int" && std::holds_alternative<std::int64_t>(value)) ||
               (kind == "float" && std::holds_alternative<double>(value)) ||
               (kind == "str" && std::holds_alternative<std::string>(value));
  require(valid, "configuration type differs from its map", "TypeError");
  auto &s = state();
  std::lock_guard lock(s.mutex);
  s.config.insert_or_assign({kind, key}, std::move(value));
}
inline ConfigValue get(const std::string &kind, const std::string &key) {
  auto &s = state();
  std::lock_guard lock(s.mutex);
  auto it = s.config.find({kind, key});
  require(it != s.config.end(), key, "KeyError");
  return it->second;
}
inline std::size_t size() {
  auto &s = state();
  std::lock_guard lock(s.mutex);
  return s.config.size();
}
inline auto profiles() {
  auto &s = state();
  std::lock_guard lock(s.mutex);
  return s.sections;
}
inline void log(unsigned level, const std::string &message) {
  require(level < 6, "log level must be in 0..5", "ValueError");
  auto &s = state();
  std::lock_guard lock(s.mutex);
  std::clog << "einsums[" << level << "] " << message << '\n';
}
class Section {
  std::string label_;
  std::chrono::steady_clock::time_point start_;
  bool ended_ = false;

public:
  explicit Section(std::string label)
      : label_(std::move(label)), start_(std::chrono::steady_clock::now()) {}
  Section(const Section &) = delete;
  Section &operator=(const Section &) = delete;
  void end() {
    if (ended_)
      return;
    double elapsed =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start_)
            .count();
    auto &s = state();
    std::lock_guard lock(s.mutex);
    auto &entry = s.sections[label_];
    entry.first += elapsed;
    ++entry.second;
    ended_ = true;
  }
  ~Section() { end(); }
};
} // namespace sage_cpp::api::runtime
