#pragma once
#include "array.hpp"
#include <memory>
#include <span>
namespace sage_cpp::api {
inline std::ptrdiff_t signed_add(std::ptrdiff_t a, std::ptrdiff_t b) {
  constexpr auto max = std::numeric_limits<std::ptrdiff_t>::max();
  constexpr auto min = std::numeric_limits<std::ptrdiff_t>::min();
  require(b >= 0 ? a <= max - b : a >= min - b, "view offset overflow");
  return a + b;
}
inline std::ptrdiff_t signed_multiply(std::ptrdiff_t a, std::ptrdiff_t b) {
  constexpr auto max = std::numeric_limits<std::ptrdiff_t>::max();
  constexpr auto min = std::numeric_limits<std::ptrdiff_t>::min();
  if (a == 0 || b == 0)
    return 0;
  bool valid = a > 0 ? (b > 0 ? a <= max / b : b >= min / a)
                     : (b > 0 ? a >= min / b : a >= max / b);
  require(valid, "view stride overflow");
  return a * b;
}
template <class T> class DenseTensor;
// Views retain their storage owner, including after an originating tensor dies.
// Owning copies are deep. View copies remain aliases. Metadata is checked
// before indexing so invalid strides never construct an out-of-buffer pointer.
template <class T> class TensorView {
  std::shared_ptr<std::vector<T>> owner_;
  Shape shape_;
  std::vector<std::ptrdiff_t> strides_;
  std::ptrdiff_t offset_;
  bool writable_;
  friend class DenseTensor<T>;

public:
  TensorView(std::shared_ptr<std::vector<T>> owner, Shape shape,
             std::vector<std::ptrdiff_t> st, std::ptrdiff_t offset = 0,
             bool writable = true)
      : owner_(std::move(owner)), shape_(std::move(shape)),
        strides_(std::move(st)), offset_(offset), writable_(writable) {
    require(owner_ && shape_.size() == strides_.size(),
            "invalid view metadata");
    size(shape_);
    require(offset_ >= 0 && static_cast<std::size_t>(offset_) <= owner_->size(),
            "view offset outside buffer");
    if (size(shape_) == 0)
      return;
    std::ptrdiff_t lo = offset_, hi = offset_;
    for (std::size_t i = 0; i < shape_.size(); ++i) {
      require(shape_[i] <= static_cast<std::size_t>(
                               std::numeric_limits<std::ptrdiff_t>::max()),
              "view dimension overflow");
      auto delta = signed_multiply(static_cast<std::ptrdiff_t>(shape_[i] - 1),
                                   strides_[i]);
      if (delta < 0)
        lo = signed_add(lo, delta);
      else
        hi = signed_add(hi, delta);
    }
    require(lo >= 0 && static_cast<std::size_t>(hi) < owner_->size(),
            "view strides outside buffer");
  }
  const Shape &shape() const { return shape_; }
  const auto &strides() const { return strides_; }
  std::size_t flat_index(const Shape &idx) const {
    require(idx.size() == shape_.size(), "view index rank mismatch",
            "rank_error");
    std::ptrdiff_t n = offset_;
    for (std::size_t i = 0; i < idx.size(); ++i) {
      require(idx[i] < shape_[i], "view index out of bounds", "IndexError");
      n = signed_add(
          n, signed_multiply(static_cast<std::ptrdiff_t>(idx[i]), strides_[i]));
    }
    return static_cast<std::size_t>(n);
  }
  const T &at(const Shape &idx) const { return owner_->at(flat_index(idx)); }
  T &at(const Shape &idx) {
    require(writable_, "view is read-only", "ValueError");
    return owner_->at(flat_index(idx));
  }
  TensorView slice(std::size_t axis, std::size_t start, std::size_t count,
                   std::ptrdiff_t step = 1) const {
    require(axis < shape_.size() && step != 0, "invalid slice axis or step");
    require(start < shape_[axis] || (count == 0 && start <= shape_[axis]),
            "slice start out of bounds");
    require(start <= static_cast<std::size_t>(
                         std::numeric_limits<std::ptrdiff_t>::max()) &&
                count <= static_cast<std::size_t>(
                             std::numeric_limits<std::ptrdiff_t>::max()),
            "slice dimension overflow");
    auto last = signed_add(
        static_cast<std::ptrdiff_t>(start),
        count ? signed_multiply(static_cast<std::ptrdiff_t>(count - 1), step)
              : 0);
    require(count == 0 ||
                (last >= 0 && static_cast<std::size_t>(last) < shape_[axis]),
            "slice end out of bounds");
    auto new_stride = signed_multiply(strides_[axis], step);
    auto new_offset =
        count ? signed_add(offset_,
                           signed_multiply(static_cast<std::ptrdiff_t>(start),
                                           strides_[axis]))
              : offset_;
    auto s = shape_;
    auto st = strides_;
    s[axis] = count;
    st[axis] = static_cast<std::ptrdiff_t>(new_stride);
    return {owner_, s, st, static_cast<std::ptrdiff_t>(new_offset), writable_};
  }
  TensorView readonly() const {
    return {owner_, shape_, strides_, offset_, false};
  }
  DenseTensor<T> copy() const;
};
template <class T> class DenseTensor {
  Shape shape_;
  std::shared_ptr<std::vector<T>> owner_;

public:
  explicit DenseTensor(Shape s)
      : shape_(std::move(s)),
        owner_(std::make_shared<std::vector<T>>(size(shape_))) {}
  DenseTensor(Shape s, std::vector<T> v)
      : shape_(std::move(s)),
        owner_(std::make_shared<std::vector<T>>(std::move(v))) {
    require(size(shape_) == owner_->size(), "shape and data length differ");
  }
  DenseTensor(const DenseTensor &other)
      : shape_(other.shape_),
        owner_(std::make_shared<std::vector<T>>(*other.owner_)) {}
  DenseTensor &operator=(const DenseTensor &other) {
    if (this != &other) {
      auto storage = std::make_shared<std::vector<T>>(*other.owner_);
      shape_ = other.shape_;
      owner_ = std::move(storage);
    }
    return *this;
  }
  DenseTensor(DenseTensor &&) = default;
  DenseTensor &operator=(DenseTensor &&) = default;
  const Shape &shape() const { return shape_; }
  std::span<T> values() { return *owner_; }
  std::span<const T> values() const { return *owner_; }
  TensorView<T> view() {
    auto st = api::strides(shape_);
    return {owner_, shape_, {st.begin(), st.end()}};
  }
  TensorView<T> view() const {
    auto st = api::strides(shape_);
    return {owner_, shape_, {st.begin(), st.end()}, 0, false};
  }
  T &at(const Shape &idx) { return view().at(idx); }
  const T &at(const Shape &idx) const {
    const auto v = view();
    return v.at(idx);
  }
};
template <class T> DenseTensor<T> TensorView<T>::copy() const {
  std::vector<T> values;
  values.reserve(size(shape_));
  for (std::size_t i = 0; i < size(shape_); ++i)
    values.push_back(at(coords(i, shape_)));
  return {shape_, values};
}
using RuntimeTensorF = DenseTensor<float>;
using RuntimeTensorD = DenseTensor<double>;
using RuntimeTensorC = DenseTensor<std::complex<float>>;
using RuntimeTensorZ = DenseTensor<std::complex<double>>;
} // namespace sage_cpp::api
