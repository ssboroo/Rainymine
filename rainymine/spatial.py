"""Shared ENU rotations for search, covariance and block geometry."""
import numpy as np
from .core import finite

def search_basis(azimuth=90., dip=0., roll=0.):
    """Columns are local X/Y/Z in world ENU; azimuth clockwise from north.
    Dip is positive upwards. Roll rotates local Y towards local Z about local X.
    The default (90, 0, 0) preserves the historical world-axis search.
    """
    finite(azimuth, dip, roll)
    if not -90 <= dip <= 90:
        raise ValueError('Search dip −90…90 градус байна.')
    a,d,r=np.radians([azimuth,dip,roll])
    x=np.array([np.sin(a)*np.cos(d),np.cos(a)*np.cos(d),np.sin(d)])
    y=np.array([-np.cos(a),np.sin(a),0.])
    z=np.cross(x,y)
    return np.column_stack((x,np.cos(r)*y+np.sin(r)*z,-np.sin(r)*y+np.cos(r)*z))


def model_basis(model):
    return search_basis(*model.get("grid_angles", [90., 0., 0.]))
