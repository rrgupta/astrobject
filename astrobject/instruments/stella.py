#! /usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
import pyfits as pf
from .baseinstrument import Instrument
from ...utils.decorators import _autogen_docstring_inheritance

__all__ = ["stella","STELLA_INFO"]

STELLA_INFO = {"up":{"lbda":3580,"ABmag0":None},
               "gp":{"lbda":4754,"ABmag0":None},
               "rp":{"lbda":6204,"ABmag0":None},
               "ip":{"lbda":7698,"ABmag0":None},
               "zp":{"lbda":9665,"ABmag0":None},
                "telescope":{
                    "lon":28.3022822,
                    "lat":-16.5122172}
              }

def stella(*args,**kwargs):
    return STELLA(*args,**kwargs)

def is_stella_file(filename):
    """This tests if the input file is a SDSS one"""
    return True if "STELLA" in pf.getheader(filename,ext=1).get("TELESCOP")\
      else False

def which_band_is_file(filename):
    """This resuts the band of the given file if it is a
    stella one"""
    if not is_stella_file(filename):
        return None
    return pf.getheader(filename,ext=1).get("FILTER")

#######################################
#                                     #
#   SDSS Image Object                 #
#                                     #
#######################################
class STELLA( Instrument ):
    """
    This is the image object custom for STELLA data
    """
    instrument_name = "STELLA"
    
    def __build__(self,**kwargs):
        """
        """
        # -- Load the basic builds
        self._properties_keys.append("mab0")
        super(STELLA,self).__build__()
        # -- How to read the image
        self._build_properties = dict(
                data_index = 1,
                header_exptime = "EXPT"
                )

    @_autogen_docstring_inheritance(Instrument.set_catalogue,"Instrument.set_catalogue")
    def set_catalogue(self,catalogue,force_it=True,**kwargs):
        #
        # - Add the bandname key_mag setting
        #
        if catalogue.source_name =="SDSS":
            key_mag = "%smag"%self.bandname[0]
            key_magerr = "e_%smag"%self.bandname[0]
            if key_mag not in catalogue.data.keys():
                print "WARNING No %s in the catalogue data. Cannot assign a key_mag"%key_mag
            catalogue.set_mag_keys(key_mag,key_magerr)
                
            
        super(STELLA,self).set_catalogue(catalogue,force_it=force_it,**kwargs)

    @_autogen_docstring_inheritance(Instrument._get_sep_extract_threshold_,"Instrument._get_sep_extract_threshold_")
    def _get_sep_extract_threshold_(self,**kwargs):
        # Because Stella image are no per second
        return super(STELLA,self)._get_sep_extract_threshold_(**kwargs) / self.exposuretime
    # =========================== #
    # = Properties and Settings = #
    # =========================== #
    # --------------
    # - Image Data
    @property
    def data(self):
        # raw data in STELLA are in count
        return self._derived_properties["data"] / self.exposuretime
    
    @property
    def bandname(self):
        if self.header is None:
            raise AttributeError("no header loaded ")
        return self.header["FILTER"]

    @property
    def band_info(self):
        return STELLA_INFO[self.band]
    
    @property
    def mab0(self):
        if self._properties["mab0"] is None:
            self.mab0 = self.header["ZEROPNT"]
        return self._properties["mab0"]

    @mab0.setter
    def mab0(self,value):
        if value<10:
            raise ValueError("given mab0 lozer then 10 looks unlikely")
        self._properties["mab0"] = value
        
    
    @property
    def mjd_obstime(self):
        if self.header is None:
            raise AttributeError("no header loaded ")
        from astropy import time
        return time.Time(self.header["JD-OBS"],format="jd").mjd
    
    @property
    def _gain(self):
        return None

    # =========================== #
    # = Internal Tools          = #
    # =========================== #