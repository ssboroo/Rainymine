use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use numpy::{PyReadonlyArray1,PyReadonlyArray2,IntoPyArray,PyArray1,PyArray2};
use numpy::ndarray::Array2;
use nalgebra::{DMatrix,DVector};
use rayon::prelude::*;

extern "C" {fn rm_closure(n:i64,v:*const i64,m:i64,e:*const i64,nx:i64,ny:i64,nz:i64,rx:i64,ry:i64,out:*mut u8)->i32;}

#[pyfunction]
#[pyo3(signature=(values, edges, grid=None))]
fn closure<'py>(py:Python<'py>,values:PyReadonlyArray1<'py,i64>,edges:PyReadonlyArray2<'py,i64>,grid:Option<(i64,i64,i64,i64,i64)>)->PyResult<Bound<'py,PyArray1<u8>>> {
    // Own buffers before releasing GIL: callers cannot mutate borrowed NumPy storage.
    let v=values.as_array().to_owned().into_raw_vec_and_offset().0;
    let e=edges.as_array();if e.ncols()!=2 || v.is_empty() || v.len()>10_000_000 || e.nrows()>20_000_000 {return Err(PyValueError::new_err("Invalid graph dimensions"));}
    if v.iter().map(|x|(*x as i128).abs()).sum::<i128>() > (i64::MAX as i128)/4 {return Err(PyValueError::new_err("Graph excess may overflow int64"));}
    if e.iter().any(|x|*x<0 || *x>=v.len() as i64) {return Err(PyValueError::new_err("Invalid arc index"));}
    let e=e.to_owned().into_raw_vec_and_offset().0;
    let (nx,ny,nz,rx,ry)=grid.unwrap_or((0,0,0,0,0));
    if grid.is_some() && (nx<=0 || ny<=0 || nz<=0 || (nx as i128)*(ny as i128)*(nz as i128)!=v.len() as i128 || rx<0 || ry<0 || rx>100 || ry>100 || (2*rx+1)*(2*ry+1)>10000) {return Err(PyValueError::new_err("Invalid grid stencil"));}
    let result=py.allow_threads(move || {
        let mut out=vec![0u8;v.len()];
        let status=unsafe {rm_closure(v.len() as i64,v.as_ptr(),(e.len()/2) as i64,e.as_ptr(),nx,ny,nz,rx,ry,out.as_mut_ptr())};
        (status,out)
    });
    if result.0!=0 {return Err(PyValueError::new_err("MineFlow pseudoflow failed"));}
    Ok(result.1.into_pyarray(py))
}
fn gamma(d:f64,n:f64,s:f64,r:f64)->f64 {if d<=1e-12 {0.} else {let h=(d/r).min(1.);n+s*(1.5*h-0.5*h*h*h)}}
fn distance(a:&[f64],b:&[f64])->f64 {((a[0]-b[0]).powi(2)+(a[1]-b[1]).powi(2)+(a[2]-b[2]).powi(2)).sqrt()}

#[pyfunction]
#[pyo3(signature=(xyz,values,targets,indices,nugget,partial_sill,range_m,target_values=None))]
fn ok_batch<'py>(py:Python<'py>,xyz:PyReadonlyArray2<'py,f64>,values:PyReadonlyArray1<'py,f64>,targets:PyReadonlyArray2<'py,f64>,indices:PyReadonlyArray2<'py,i64>,nugget:f64,partial_sill:f64,range_m:f64,target_values:Option<PyReadonlyArray2<'py,f64>>)->PyResult<Bound<'py,PyArray2<f64>>> {
    let x=xyz.as_array();let t=targets.as_array();let ids=indices.as_array();let v=values.as_array();
    if x.ncols()!=3 || t.ncols()!=3 || v.len()!=x.nrows() || t.nrows()!=ids.nrows() || ids.ncols()>64 || ids.ncols()==0 || t.nrows()>8192 || !nugget.is_finite() || !partial_sill.is_finite() || !range_m.is_finite() || nugget<0. || partial_sill<=0. || range_m<=0. || x.iter().chain(t.iter()).chain(v.iter()).any(|a|!a.is_finite()) || ids.iter().any(|i|*i < -1 || *i>=x.nrows() as i64) {return Err(PyValueError::new_err("Invalid kriging arrays / variogram"));}
    let overrides=if let Some(array)=target_values {let a=array.as_array();if a.nrows()!=t.nrows() || a.ncols()!=ids.ncols() || a.iter().any(|v|!v.is_finite()) {return Err(PyValueError::new_err("Invalid per-target capped values"));}Some(a.to_owned().into_raw_vec_and_offset().0)} else {None};
    let x=x.to_owned().into_raw_vec_and_offset().0;let t=t.to_owned().into_raw_vec_and_offset().0;let v=v.to_vec();let k=ids.ncols();let ids=ids.to_owned().into_raw_vec_and_offset().0;
    let output:Vec<[f64;5]>=py.allow_threads(move || {
        t.par_chunks(3).zip(ids.par_chunks(k)).enumerate().map(|(row,(target,neighbors))| {
            let ids:Vec<usize>=neighbors.iter().filter(|i|**i>=0).map(|i|*i as usize).collect();let n=ids.len();
            let local_values:Vec<f64>=neighbors.iter().enumerate().filter(|(_,i)|**i>=0).map(|(j,i)|if let Some(ref o)=overrides {o[row*k+j]} else {v[*i as usize]}).collect();
            let fail=|status:f64|[f64::NAN,f64::NAN,f64::NAN,f64::NAN,status];
            if n==0 {return fail(1.);}
            for (j,i) in ids.iter().enumerate() {if distance(&x[3*i..3*i+3],target)<1e-9 {return [local_values[j],0.,1.,1.,0.];}}
            let mut a=DMatrix::from_element(n+1,n+1,1.);a[(n,n)]=0.;let mut b=DVector::from_element(n+1,1.);
            for (i,si) in ids.iter().enumerate() {
                b[i]=gamma(distance(&x[3*si..3*si+3],target),nugget,partial_sill,range_m);
                for (j,sj) in ids.iter().enumerate() {a[(i,j)]=gamma(distance(&x[3*si..3*si+3],&x[3*sj..3*sj+3]),nugget,partial_sill,range_m);}
            }
            let singular=a.clone().svd(false,false).singular_values;
            if singular.min()<=singular.max()*1e-12 {return fail(2.);}
            let Some(w)=a.clone().lu().solve(&b) else {return fail(2.);};
            let grade=(0..n).map(|i|w[i]*local_values[i]).sum::<f64>();
            let variance=(0..n).map(|i|w[i]*b[i]).sum::<f64>()+w[n];
            if !grade.is_finite() || !variance.is_finite() || variance < -1e-8 {return fail(3.);}
            let variance=variance.max(0.);let sill=nugget+partial_sill;
            let cross=(0..n).map(|i|w[i]*(sill-b[i])).sum::<f64>();
            let mut prediction_variance=0.;for i in 0..n {for j in 0..n {prediction_variance+=w[i]*w[j]*(sill-a[(i,j)]);}}
            [grade,variance,1.-variance/sill,if prediction_variance>1e-12 {cross/prediction_variance} else {f64::NAN},0.]
        }).collect()
    });
    let result=Array2::from_shape_vec((output.len(),5),output.into_iter().flatten().collect()).unwrap();
    Ok(result.into_pyarray(py))
}
#[pymodule]
fn rainymine_core(m:&Bound<'_,PyModule>)->PyResult<()> {
    m.add_function(wrap_pyfunction!(closure,m)?)?;m.add_function(wrap_pyfunction!(ok_batch,m)?)?;
    m.add("ENGINE_VERSION","0.1.0")?;m.add("MINEFLOW_COMMIT","6f5dd7091070b1bd85457b3ce9fd95c4e345c983")?;Ok(())
}
