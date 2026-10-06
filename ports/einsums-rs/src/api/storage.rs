use super::{
    array::{coords, size, strides, Array, DType},
    ApiError, Result,
};
use hdf5::types::{CompoundField, CompoundType, FloatSize, H5Type, TypeDescriptor};
use num_complex::Complex64 as C;
use std::{collections::BTreeMap, path::Path};

/// Sparse tiles with independent per-axis partitions. Absent tiles are exactly zero.
#[derive(Clone, Debug)]
pub struct TiledTensor {
    pub dtype: DType,
    pub partitions: Vec<Vec<usize>>,
    tiles: BTreeMap<Vec<usize>, Array>,
}
impl TiledTensor {
    pub fn new(dtype: DType, partitions: Vec<Vec<usize>>) -> Result<Self> {
        for axis in &partitions {
            axis.iter().try_fold(0usize, |n, d| {
                n.checked_add(*d)
                    .ok_or_else(|| ApiError::shape("partition overflow"))
            })?;
        }
        Ok(Self {
            dtype,
            partitions,
            tiles: BTreeMap::new(),
        })
    }
    pub fn shape(&self) -> Vec<usize> {
        self.partitions
            .iter()
            .map(|axis| axis.iter().sum())
            .collect()
    }
    pub fn insert(&mut self, index: Vec<usize>, tile: Array) -> Result<()> {
        tile.validate()?;
        if index.len() != self.partitions.len() || tile.dtype != self.dtype {
            return Err(ApiError::shape("tile rank/dtype mismatch"));
        }
        let expected = index
            .iter()
            .enumerate()
            .map(|(a, &i)| {
                self.partitions[a]
                    .get(i)
                    .copied()
                    .ok_or_else(|| ApiError::shape("tile index out of bounds"))
            })
            .collect::<Result<Vec<_>>>()?;
        if tile.shape != expected {
            return Err(ApiError::shape("tile shape disagrees with partition"));
        }
        self.tiles.insert(index, tile);
        Ok(())
    }
    pub fn tile(&self, index: &[usize]) -> Option<&Array> {
        self.tiles.get(index)
    }
    pub fn to_dense(&self) -> Result<Array> {
        let shape = self.shape();
        let stride = strides(&shape)?;
        let mut out = Array::zeros(self.dtype, shape)?;
        for (index, tile) in &self.tiles {
            let offset: Vec<usize> = index
                .iter()
                .enumerate()
                .map(|(a, &i)| self.partitions[a][..i].iter().sum())
                .collect();
            for (flat, &v) in tile.values.iter().enumerate() {
                let c = coords(flat, &tile.shape);
                let dst = c
                    .iter()
                    .enumerate()
                    .map(|(a, &i)| (i + offset[a]) * stride[a])
                    .sum::<usize>();
                out.values[dst] = v;
            }
        }
        Ok(out)
    }
    pub fn from_dense(a: &Array, partitions: Vec<Vec<usize>>) -> Result<Self> {
        let mut out = Self::new(a.dtype, partitions)?;
        if out.shape() != a.shape {
            return Err(ApiError::shape("partitions must sum to tensor shape"));
        }
        let counts: Vec<_> = out.partitions.iter().map(Vec::len).collect();
        let stride = strides(&a.shape)?;
        for flat in 0..size(&counts)? {
            let idx = coords(flat, &counts);
            let shape: Vec<_> = idx
                .iter()
                .enumerate()
                .map(|(j, &i)| out.partitions[j][i])
                .collect();
            let offsets: Vec<usize> = idx
                .iter()
                .enumerate()
                .map(|(j, &i)| out.partitions[j][..i].iter().sum())
                .collect();
            let values = (0..size(&shape)?)
                .map(|f| {
                    let c = coords(f, &shape);
                    a.values[c
                        .iter()
                        .enumerate()
                        .map(|(j, &i)| (i + offsets[j]) * stride[j])
                        .sum::<usize>()]
                })
                .collect();
            out.insert(idx, Array::new(a.dtype, shape, values)?)?;
        }
        Ok(out)
    }
}
#[derive(Clone, Debug)]
pub struct BlockTensor {
    tiled: TiledTensor,
}
impl BlockTensor {
    pub fn new(dtype: DType, rank: usize, blocks: Vec<usize>) -> Result<Self> {
        Ok(Self {
            tiled: TiledTensor::new(dtype, vec![blocks; rank])?,
        })
    }
    pub fn insert(&mut self, index: usize, block: Array) -> Result<()> {
        self.tiled
            .insert(vec![index; self.tiled.partitions.len()], block)
    }
    pub fn block(&self, index: usize) -> Option<&Array> {
        self.tiled.tile(&vec![index; self.tiled.partitions.len()])
    }
    pub fn to_dense(&self) -> Result<Array> {
        self.tiled.to_dense()
    }
}
#[repr(C)]
#[derive(Clone, Copy)]
struct H5Complex64 {
    r: f64,
    i: f64,
}
#[repr(C)]
#[derive(Clone, Copy)]
struct H5Complex32 {
    r: f32,
    i: f32,
}
unsafe impl H5Type for H5Complex64 {
    fn type_descriptor() -> TypeDescriptor {
        TypeDescriptor::Compound(CompoundType {
            fields: vec![
                CompoundField::new("r", TypeDescriptor::Float(FloatSize::U8), 0, 0),
                CompoundField::new("i", TypeDescriptor::Float(FloatSize::U8), 8, 1),
            ],
            size: 16,
        })
    }
}
unsafe impl H5Type for H5Complex32 {
    fn type_descriptor() -> TypeDescriptor {
        TypeDescriptor::Compound(CompoundType {
            fields: vec![
                CompoundField::new("r", TypeDescriptor::Float(FloatSize::U4), 0, 0),
                CompoundField::new("i", TypeDescriptor::Float(FloatSize::U4), 4, 1),
            ],
            size: 8,
        })
    }
}
fn io(e: hdf5::Error) -> ApiError {
    ApiError::io(e.to_string())
}
fn write<T: H5Type>(file: &hdf5::File, name: &str, shape: &[usize], values: &[T]) -> Result<()> {
    if file.link_exists(name) {
        let d = file.dataset(name).map_err(io)?;
        if d.shape() != shape
            || d.dtype().map_err(io)?.to_descriptor().map_err(io)? != T::type_descriptor()
        {
            return Err(ApiError::shape("existing dataset has different shape/type"));
        }
        d.write_raw(values).map_err(io)
    } else {
        file.new_dataset::<T>()
            .shape(shape)
            .create(name)
            .map_err(io)?
            .write_raw(values)
            .map_err(io)
    }
}
pub fn write_hdf5(path: &Path, name: &str, a: &Array, overwrite: bool) -> Result<()> {
    a.validate()?;
    let file = if path.exists() {
        hdf5::File::open_rw(path)
    } else {
        hdf5::File::create(path)
    }
    .map_err(io)?;
    if file.link_exists(name) && !overwrite {
        return Err(ApiError::io(
            "dataset already exists; overwrite was not requested",
        ));
    }
    match a.dtype {
        DType::Float32 => write(
            &file,
            name,
            &a.shape,
            &a.values.iter().map(|z| z.re as f32).collect::<Vec<_>>(),
        )?,
        DType::Float64 => write(
            &file,
            name,
            &a.shape,
            &a.values.iter().map(|z| z.re).collect::<Vec<_>>(),
        )?,
        DType::Complex64 => write(
            &file,
            name,
            &a.shape,
            &a.values
                .iter()
                .map(|z| H5Complex32 {
                    r: z.re as f32,
                    i: z.im as f32,
                })
                .collect::<Vec<_>>(),
        )?,
        DType::Complex128 => write(
            &file,
            name,
            &a.shape,
            &a.values
                .iter()
                .map(|z| H5Complex64 { r: z.re, i: z.im })
                .collect::<Vec<_>>(),
        )?,
    };
    file.flush().map_err(io)
}
pub fn read_hdf5(path: &Path, name: &str) -> Result<Array> {
    let file = hdf5::File::open(path).map_err(io)?;
    let d = file.dataset(name).map_err(io)?;
    let ty = d.dtype().map_err(io)?.to_descriptor().map_err(io)?;
    let (dtype, values) = if ty == f32::type_descriptor() {
        (
            DType::Float32,
            d.read_raw::<f32>()
                .map_err(io)?
                .into_iter()
                .map(|x| C::new(x as f64, 0.))
                .collect(),
        )
    } else if ty == f64::type_descriptor() {
        (
            DType::Float64,
            d.read_raw::<f64>()
                .map_err(io)?
                .into_iter()
                .map(|x| C::new(x, 0.))
                .collect(),
        )
    } else if ty == H5Complex32::type_descriptor() {
        (
            DType::Complex64,
            d.read_raw::<H5Complex32>()
                .map_err(io)?
                .into_iter()
                .map(|z| C::new(z.r as f64, z.i as f64))
                .collect(),
        )
    } else if ty == H5Complex64::type_descriptor() {
        (
            DType::Complex128,
            d.read_raw::<H5Complex64>()
                .map_err(io)?
                .into_iter()
                .map(|z| C::new(z.r, z.i))
                .collect(),
        )
    } else {
        return Err(ApiError::dtype(
            "HDF5 dataset must contain float32/64 or complex64/128",
        ));
    };
    Array::new(dtype, d.shape(), values)
}
/// A disk-backed tensor with explicit flush errors; no hidden writes from Drop.
pub struct DiskTensor {
    pub path: std::path::PathBuf,
    pub name: String,
    pub tensor: Array,
}
impl DiskTensor {
    pub fn open(path: impl Into<std::path::PathBuf>, name: impl Into<String>) -> Result<Self> {
        let (path, name) = (path.into(), name.into());
        let tensor = read_hdf5(&path, &name)?;
        Ok(Self { path, name, tensor })
    }
    pub fn flush(&self) -> Result<()> {
        write_hdf5(&self.path, &self.name, &self.tensor, true)
    }
}
