"""Explicit source axes/matrices -> ENU; no vendor Euler convention guessing."""
import numpy as np
from .spatial import search_basis


def checked_basis(value):
    matrix=np.asarray(value,dtype=float)
    if matrix.shape!=(3,3) or not np.isfinite(matrix).all() or not np.allclose(matrix.T@matrix,np.eye(3),atol=1e-8,rtol=0) or not np.isclose(np.linalg.det(matrix),1,atol=1e-8,rtol=0):
        raise ValueError('Orientation must be a right-handed orthonormal 3×3 ENU matrix; columns are local axes.')
    return matrix


def basis_angles(value):
    matrix=checked_basis(value);x,y=matrix[:,:2].T
    azimuth=float(np.degrees(np.arctan2(x[0],x[1]))%360)
    dip=float(np.degrees(np.arcsin(np.clip(x[2],-1,1))))
    zero=search_basis(azimuth,dip,0)
    roll=float(np.degrees(np.arctan2(y@zero[:,2],y@zero[:,1])))
    result=[azimuth,dip,roll]
    if not np.allclose(search_basis(*result),matrix,atol=1e-8,rtol=0):raise ValueError('Orientation reconstruction failed')
    return result


def source_orientation(spec):
    """Source vendor is provenance, not a mathematical convention.

    axes_azimuth_plunge: bearings CW from north, plunge positive downward;
    both exported axis directions must already be perpendicular.
    euler_explicit: scipy active right-handed rotation with explicit sequence;
    uppercase intrinsic, lowercase extrinsic. Never relabel vendor fields.
    """
    if not isinstance(spec,dict):raise ValueError('Orientation object required')
    mode=spec.get('representation');source=spec.get('source_software','Other')
    if not isinstance(source,str) or not source.strip() or len(source)>100:raise ValueError('Source software required')
    if mode=='rainymine_enu':
        angles=np.asarray(spec.get('angles'),dtype=float)
        if angles.shape!=(3,) or not np.isfinite(angles).all():raise ValueError('Three finite ENU angles required')
        matrix=search_basis(*angles)
    elif mode=='matrix_enu':matrix=checked_basis(spec['matrix'])
    elif mode=='axes_azimuth_plunge':
        axes=spec.get('axes',[])
        if len(axes)!=2:raise ValueError('Exported axis 1 and axis 2 directions required')
        vectors=[]
        for bearing,plunge in axes:
            vectors.append(search_basis(float(bearing),-float(plunge),0)[:,0])
        if abs(float(vectors[0]@vectors[1]))>1e-8:raise ValueError('Exported axes are not perpendicular')
        matrix=checked_basis(np.column_stack((*vectors,np.cross(*vectors))))
    elif mode=='euler_explicit':
        from scipy.spatial.transform import Rotation
        sequence=spec.get('sequence','')
        if len(sequence)!=3 or not (sequence.islower() or sequence.isupper()) or any(c.lower() not in 'xyz' for c in sequence):raise ValueError('Explicit intrinsic/extrinsic Euler sequence required')
        angles=np.asarray(spec.get('angles'),dtype=float)
        if angles.shape!=(3,) or not np.isfinite(angles).all():raise ValueError('Three finite Euler angles required')
        matrix=checked_basis(Rotation.from_euler(sequence,angles,degrees=True).as_matrix())
    else:raise ValueError('Unsupported orientation representation')
    return {'source_software':source,'representation':mode,'source_definition':spec,
            'matrix_enu':matrix.tolist(),'angles':basis_angles(matrix),
            'verified_against_vendor_fixture':False}
