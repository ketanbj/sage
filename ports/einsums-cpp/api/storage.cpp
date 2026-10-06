#include "storage.hpp"
#include <hdf5.h>
#include <mutex>
namespace sage_cpp::api {
namespace {
std::mutex hdf_mutex;
struct Handle {
  hid_t id;
  herr_t (*close)(hid_t);
  Handle(hid_t i, herr_t (*c)(hid_t)) : id(i), close(c) {
    require(id >= 0, "HDF5 operation failed", "OSError");
  }
  ~Handle() { close(id); }
  Handle(const Handle &) = delete;
  Handle &operator=(const Handle &) = delete;
  operator hid_t() const { return id; }
};
struct QuietErrors {
  H5E_auto2_t previous;
  void *data;
  QuietErrors() {
    H5Eget_auto2(H5E_DEFAULT, &previous, &data);
    H5Eset_auto2(H5E_DEFAULT, nullptr, nullptr);
  }
  ~QuietErrors() { H5Eset_auto2(H5E_DEFAULT, previous, data); }
};
struct Pair {
  double r, i;
};
hid_t complex_type(bool low) {
  auto t = H5Tcreate(H5T_COMPOUND, low ? 8 : 16);
  require(t >= 0, "HDF5 type failed", "OSError");
  if (H5Tinsert(t, "r", 0, low ? H5T_NATIVE_FLOAT : H5T_NATIVE_DOUBLE) < 0 ||
      H5Tinsert(t, "i", low ? 4 : 8,
                low ? H5T_NATIVE_FLOAT : H5T_NATIVE_DOUBLE) < 0) {
    H5Tclose(t);
    throw Error("OSError", "HDF5 type failed");
  }
  return t;
}
DType describe(hid_t t) {
  auto cls = H5Tget_class(t);
  if (cls == H5T_FLOAT) {
    auto n = H5Tget_size(t);
    require(n == 4 || n == 8, "unsupported HDF5 floating dtype", "TypeError");
    return n == 4 ? DType::Float32 : DType::Float64;
  }
  require(cls == H5T_COMPOUND && H5Tget_nmembers(t) == 2,
          "HDF5 must contain float32/64 or complex64/128", "TypeError");
  int r = H5Tget_member_index(t, "r"), i = H5Tget_member_index(t, "i");
  require(r >= 0 && i >= 0, "complex HDF5 requires r/i fields", "TypeError");
  Handle rt(H5Tget_member_type(t, r), H5Tclose),
      it(H5Tget_member_type(t, i), H5Tclose);
  auto width = H5Tget_size(rt);
  require(H5Tget_class(rt) == H5T_FLOAT && H5Tget_class(it) == H5T_FLOAT &&
              H5Tget_size(it) == width && (width == 4 || width == 8),
          "unsupported HDF5 complex dtype", "TypeError");
  return width == 4 ? DType::Complex64 : DType::Complex128;
}
Shape dataset_shape(hid_t d) {
  Handle sp(H5Dget_space(d), H5Sclose);
  int rank = H5Sget_simple_extent_ndims(sp);
  require(rank >= 0, "HDF5 rank failed", "OSError");
  std::vector<hsize_t> dims(rank);
  require(H5Sget_simple_extent_dims(sp, dims.data(), nullptr) >= 0,
          "HDF5 shape failed", "OSError");
  Shape out;
  for (auto n : dims) {
    require(n <= std::numeric_limits<std::size_t>::max(),
            "HDF5 dimension overflow");
    out.push_back(n);
  }
  size(out);
  return out;
}
} // namespace
void write_hdf5(const std::filesystem::path &path, const std::string &name,
                const Array &a, bool overwrite) {
  a.validate();
  require(!name.empty(), "dataset name must not be empty", "ValueError");
  std::lock_guard lock(hdf_mutex);
  QuietErrors quiet;
  Handle file(
      std::filesystem::exists(path)
          ? H5Fopen(path.c_str(), H5F_ACC_RDWR, H5P_DEFAULT)
          : H5Fcreate(path.c_str(), H5F_ACC_EXCL, H5P_DEFAULT, H5P_DEFAULT),
      H5Fclose);
  htri_t exists =
      H5Lexists(file, name.c_str(),
                H5P_DEFAULT); // Negative also means a missing parent group.
  require(exists <= 0 || overwrite,
          "dataset already exists; overwrite was not requested", "OSError");
  Handle type(
      is_complex(a.dtype)
          ? complex_type(is_low(a.dtype))
          : H5Tcopy(is_low(a.dtype) ? H5T_NATIVE_FLOAT : H5T_NATIVE_DOUBLE),
      H5Tclose);
  std::vector<hsize_t> dims(a.shape.begin(), a.shape.end());
  Handle space(a.shape.empty()
                   ? H5Screate(H5S_SCALAR)
                   : H5Screate_simple(dims.size(), dims.data(), nullptr),
               H5Sclose);
  Handle lcpl(H5Pcreate(H5P_LINK_CREATE), H5Pclose);
  require(H5Pset_create_intermediate_group(lcpl, 1) >= 0,
          "HDF5 link properties failed", "OSError");
  Handle dataset(exists > 0 ? H5Dopen2(file, name.c_str(), H5P_DEFAULT)
                            : H5Dcreate2(file, name.c_str(), type, space, lcpl,
                                         H5P_DEFAULT, H5P_DEFAULT),
                 H5Dclose);
  Handle actual(H5Dget_type(dataset), H5Tclose);
  require(dataset_shape(dataset) == a.shape && describe(actual) == a.dtype,
          "existing dataset has different shape/type");
  herr_t status;
  if (is_complex(a.dtype)) {
    std::vector<Pair> v;
    for (auto z : a.values)
      v.push_back({z.real(), z.imag()});
    Handle mem(complex_type(false), H5Tclose);
    status = H5Dwrite(dataset, mem, H5S_ALL, H5S_ALL, H5P_DEFAULT, v.data());
  } else {
    std::vector<double> v;
    for (auto z : a.values)
      v.push_back(z.real());
    status = H5Dwrite(dataset, H5T_NATIVE_DOUBLE, H5S_ALL, H5S_ALL, H5P_DEFAULT,
                      v.data());
  }
  require(status >= 0 && H5Fflush(file, H5F_SCOPE_GLOBAL) >= 0,
          "HDF5 write/flush failed", "OSError");
}
Array read_hdf5(const std::filesystem::path &path, const std::string &name) {
  std::lock_guard lock(hdf_mutex);
  QuietErrors quiet;
  Handle file(H5Fopen(path.c_str(), H5F_ACC_RDONLY, H5P_DEFAULT), H5Fclose),
      dataset(H5Dopen2(file, name.c_str(), H5P_DEFAULT), H5Dclose),
      type(H5Dget_type(dataset), H5Tclose);
  auto d = describe(type);
  auto out = Array::zeros(d, dataset_shape(dataset));
  herr_t status;
  if (is_complex(d)) {
    std::vector<Pair> v(out.values.size());
    Handle mem(complex_type(false), H5Tclose);
    status = H5Dread(dataset, mem, H5S_ALL, H5S_ALL, H5P_DEFAULT, v.data());
    for (std::size_t i = 0; i < v.size(); ++i)
      out.values[i] = cast(d, {v[i].r, v[i].i});
  } else {
    std::vector<double> v(out.values.size());
    status = H5Dread(dataset, H5T_NATIVE_DOUBLE, H5S_ALL, H5S_ALL, H5P_DEFAULT,
                     v.data());
    for (std::size_t i = 0; i < v.size(); ++i)
      out.values[i] = cast(d, v[i]);
  }
  require(status >= 0, "HDF5 read failed", "OSError");
  return out;
}
} // namespace sage_cpp::api
