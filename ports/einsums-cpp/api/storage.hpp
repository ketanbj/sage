#pragma once
#include "array.hpp"
#include <filesystem>
#include <map>
namespace sage_cpp::api {
class TiledTensor {
  std::map<Shape, Array> tiles_;

public:
  DType dtype;
  std::vector<Shape> partitions;
  TiledTensor(DType d, std::vector<Shape> p)
      : dtype(d), partitions(std::move(p)) {
    shape();
  }
  Shape shape() const {
    Shape out;
    for (const auto &axis : partitions) {
      std::size_t s = 0;
      for (auto n : axis)
        s = checked_add(s, n);
      out.push_back(s);
    }
    return out;
  }
  void insert(const Shape &index, const Array &a) {
    a.validate();
    require(index.size() == partitions.size() && a.dtype == dtype,
            "tile rank/dtype mismatch");
    Shape expected;
    for (std::size_t i = 0; i < index.size(); ++i) {
      require(index[i] < partitions[i].size(), "tile index out of bounds");
      expected.push_back(partitions[i][index[i]]);
    }
    require(a.shape == expected, "tile shape disagrees with partition");
    tiles_.insert_or_assign(index, a);
  }
  const Array *tile(const Shape &index) const {
    auto it = tiles_.find(index);
    return it == tiles_.end() ? nullptr : &it->second;
  }
  Array to_dense() const {
    auto out = Array::zeros(dtype, shape());
    auto st = strides(out.shape);
    for (const auto &[index, tile] : tiles_) {
      Shape offset(index.size());
      for (std::size_t i = 0; i < index.size(); ++i)
        for (std::size_t j = 0; j < index[i]; ++j)
          offset[i] += partitions[i][j];
      for (std::size_t f = 0; f < tile.values.size(); ++f) {
        auto c = coords(f, tile.shape);
        std::size_t dst = 0;
        for (std::size_t i = 0; i < c.size(); ++i)
          dst += (c[i] + offset[i]) * st[i];
        out.values[dst] = tile.values[f];
      }
    }
    return out;
  }
  static TiledTensor from_dense(const Array &a,
                                const std::vector<Shape> &parts) {
    TiledTensor out(a.dtype, parts);
    require(out.shape() == a.shape, "partitions must sum to tensor shape");
    Shape counts;
    for (const auto &p : parts)
      counts.push_back(p.size());
    auto st = strides(a.shape);
    for (std::size_t f = 0; f < size(counts); ++f) {
      auto idx = coords(f, counts);
      Shape s, offset(idx.size());
      for (std::size_t i = 0; i < idx.size(); ++i) {
        s.push_back(parts[i][idx[i]]);
        for (std::size_t j = 0; j < idx[i]; ++j)
          offset[i] += parts[i][j];
      }
      auto tile = Array::zeros(a.dtype, s);
      for (std::size_t i = 0; i < tile.values.size(); ++i) {
        auto c = coords(i, s);
        std::size_t src = 0;
        for (std::size_t j = 0; j < c.size(); ++j)
          src += (c[j] + offset[j]) * st[j];
        tile.values[i] = a.values[src];
      }
      out.insert(idx, tile);
    }
    return out;
  }
};
class BlockTensor {
  TiledTensor tiled_;

public:
  BlockTensor(DType d, std::size_t rank, const Shape &blocks)
      : tiled_(d, std::vector<Shape>(rank, blocks)) {}
  void insert(std::size_t i, const Array &a) {
    tiled_.insert(Shape(tiled_.partitions.size(), i), a);
  }
  const Array *block(std::size_t i) const {
    return tiled_.tile(Shape(tiled_.partitions.size(), i));
  }
  Array to_dense() const { return tiled_.to_dense(); }
};
void write_hdf5(const std::filesystem::path &, const std::string &,
                const Array &, bool overwrite = false);
Array read_hdf5(const std::filesystem::path &, const std::string &);
struct DiskTensor {
  std::filesystem::path path;
  std::string name;
  Array tensor;
  DiskTensor(std::filesystem::path p, std::string n)
      : path(std::move(p)), name(std::move(n)), tensor(read_hdf5(path, name)) {}
  void flush() const { write_hdf5(path, name, tensor, true); }
};
} // namespace sage_cpp::api
