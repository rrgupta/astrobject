#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Assorted functions for setting up the skyplots, e.g. prepating an axis with
projection, transforming coordinates from degrees to radians and reverse
longitude direction to get a celestial plot.
"""

import numpy as np
import matplotlib.pyplot as mpl
import warnings

_d2r = np.pi / 180 

__all__ = ["ax_skyplot"]

# ============================== #
# = Axis setup                 = #
# ============================== #
def ax_skyplot(fig=None, figsize=(12, 6), rect=[0.1, 0.1, 0.8, 0.8], 
               projection='mollweide', xlabelpad=None): 
    """
    Initialize axis for skyplot and make grid and labels nicer.
    [Fill in kwargs]
    """
    # Work around to get correct xlabel position in older matplotlib
    import matplotlib as m
    mv = m.__version__.split('.')
    if int(mv[0]) < 2 and int(mv[1]) < 5:
        warnings.warn('You are using matplotlib version < 1.5.0. '+
                      'The padding of the xlabel has been adjusted. '+
                      'You can use the option "xlabelpad" to adjust.')
        if xlabelpad is None:
            xlabelpad = 165
        else:
            xlabelpad += 165

    allowed_proj = ['mollweide', 'hammer']

    if fig is None:
        fig = mpl.figure(figsize=figsize)

    if projection not in allowed_proj:
        raise ValueError("Projection not supported; allowed values: %s"
                         %','.join(allowed_proj))

    ax = fig.add_axes(rect, projection=projection)
    ax.grid(True)
    xlabels = [u'%i\xb0'%ra for ra in range(150,-1,-30) + range(330,209,-30)]
    ax.set_xticklabels(xlabels)

    ax.set_xlabel(r"$\mathrm{RA\ [deg]}$", fontsize="x-large", 
                  labelpad=xlabelpad)
    ax.set_ylabel(r"$\mathrm{Dec\ [deg]}$", fontsize="x-large")

    return fig, ax

# ============================== #
# = Conversion                 = #
# ============================== #
def convert_radec_azel(ra, dec, edge=0):
    """
    Convert ra, dec to azimuth and elavation in radians as used in matplotlib 
    projections and switch sign of ra to get celestial plot.
    
    edge -- can be used to set move points at exactly ra = -180 or 180
            slightly off that
    
    [This could be extended to also convert between cooridinate systems.]
    """
    #Make sure RA is between -180 and 180, then invert axis
    if edge > 0:
        if type(ra) == float:
            if ra < -180 + edge:
                ra = -180 + edge
            elif ra > 180 - edge:
                ra = 180 - edge
        else:
            ra[ra < -180 + edge] = -180 + edge
            ra[ra > 180 - edge] = 180 - edge

    ra = ((ra + 180) % 360) - 180
    ra *= -1

    az = _d2r * ra
    el = _d2r * dec

    return az, el

