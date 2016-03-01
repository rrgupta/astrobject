#! /usr/bin/env python
# -*- coding: utf-8 -*-

from sncosmo import get_bandpass
from astropy import coordinates
from astropy.table.table import Table,TableColumns

import pyfits as pf
import numpy as np
from ...utils.decorators import _autogen_docstring_inheritance
from ...utils.tools import kwargs_update,mag_to_flux,load_pkl,dump_pkl
from ...utils import shape

from .. import astrometry
from ...astrobject.photometry import Image,photopoint,photomap
from ..baseobject import BaseObject,astrotarget
__all__ = ["Instrument"]



class Instrument( Image ):
    """
    """
    def __build__(self,data_index=0):
        """This is a slightly advanced Image object"""
        super(Instrument,self).__build__(data_index=data_index)

    # ----------- #
    #  PhotoPoint #
    # ----------- #
    @_autogen_docstring_inheritance(Image.get_stars_aperture,"Image.get_stars_aperture")
    def get_stars_photomap(self, r_pixels,aptype="circle",
                            isolated_only=True,
                            **kwargs):
        #
        # Get the photopoints instead of aperture
        #
        idx, cat_idx, [counts,errs,flags] = self.get_stars_aperture(r_pixels=r_pixels,aptype=aptype,
                                                            isolated_only=isolated_only,**kwargs)
        idx,cat_idx = idx.tolist(),cat_idx.tolist()
        
        # -- Data Map
        fluxes = self.count_to_flux(counts)
        vares  = self.count_to_flux(errs)**2
        ra_all,dec_all = self.sepobjects.radec
        ra     = ra_all[idx]
        dec     = dec_all[idx]
        pmap = photomap(fluxes,vares,ra,dec,lbda=self.lbda)
        
        # -- Catalogue Map
        catmap = self.catalogue.get_photomap(idx_only=cat_idx)
        # -- Setting
        sepinfo = {
            "a": self.sepobjects.data['a'][idx],
            "b": self.sepobjects.data['b'][idx],
            "theta": self.sepobjects.data['theta'][idx]
            }
        pmap.set_refmap(catmap)
        pmap.set_wcs(self.wcs)
        pmap.set_sep_params(sepinfo)
        return pmap
        
        
        
    @_autogen_docstring_inheritance(Image.get_aperture,"Image.get_aperture")
    def get_photopoint(self,x,y,r_pixels=None,
                       aptype="circle",
                       **kwargs):
        #
        # Be returns a PhotoPoint
        #
        count,err,flag  = self.get_aperture(x,y,r_pixels=r_pixels,aptype=aptype,
                                           **kwargs)
        flux = self.count_to_flux(count)
        var  = self.count_to_flux(err)**2
        return photopoint(self.lbda,flux,var,
                          source="image",mjd=self.mjd_obstime,
                          zp=self.mab0,bandname=self.bandpass.name,
                          instrument_name=self.instrument_name)
    
    @_autogen_docstring_inheritance(Image.get_target_aperture,
                                    "Image.get_target_aperture")
    def get_target_photopoint(self,r_pixels=None,
                              aptype="circle",**kwargs):
        #
        # Be returns a PhotoPoint
        #
        if not self.has_target():
            return AttributeError("No 'target' loaded")
        
        xpix,ypix = self.coords_to_pixel(self.target.ra,self.target.dec)
        pp = self.get_photopoint(xpix,ypix,r_pixels=r_pixels,
                                   aptype="circle",**kwargs)
        pp.set_target(self.target)
        return pp
    # =========================== #
    # = Main Methods            = #
    # =========================== #
    def count_to_flux(self,counts):
        return counts* 10**(-(2.406+self.mab0) / 2.5 ) / (self.lbda**2)

    # =========================== #
    # = Internal Catalogue      = #
    # =========================== #
    
    # =========================== #
    # = Properties and Settings = #
    # =========================== #
    # ------------------
    # - Band Information
    @property
    def bandname(self):
        raise NotImplementedError("'band' must be implemented")
    
    @property
    def bandpass(self):
        return get_bandpass(self.bandname)
    
    @property
    def lbda(self):
        return self.bandpass.wave_eff

    # -- Derived values
    @property
    def mab0(self):
        raise NotImplementedError("'mab0' must be implemented")

    @property
    def _gain(self):
        raise NotImplementedError("'_gain' must be implemented (even for None)")

    @property
    def _dataunits_to_election(self):
        """The gain converts ADU->electron. The Data are in ADU/s"""
        return self._gain * self.exposuretime
    
    @property
    def mjd_obstime(self):
        raise NotImplementedError("'obstime' must be implemented")

############################################
#                                          #
# Base Instrument: CATALOGUE               #
#                                          #
############################################

class Catalogue( BaseObject ):
    """
    """
    __nature__ = "Catalogue"
    source_name = "_not_defined_"
    
    _properties_keys = ["filename","data","header"]
    _side_properties_keys = ["wcs","fovmask","matchedmask","lbda"]
    _derived_properties_keys = ["fits","naround","contours"]

    
    def __init__(self, catalogue_file=None,empty=False,
                 data_index=0,
                 key_mag=None,key_magerr=None,
                 key_ra=None,key_dec=None):
        """
        """
        self.__build__(data_index=data_index,
                       key_mag=key_mag,key_magerr=key_magerr,
                       key_ra=key_ra,key_dec=key_dec)
        if empty:
            return
        
        if catalogue_file is not None:
            self.load(catalogue_file)

    def __build__(self,data_index=0,
                  key_mag=None,key_magerr=None,
                  key_ra=None,key_dec=None):
        """
        """
        super(Catalogue,self).__build__()
        self._build_properties = dict(
            data_index = data_index,
            )
        self.set_mag_keys(key_mag,key_magerr)
        self.set_coord_keys(key_ra,key_dec)
            
    # =========================== #
    # = Main Methods            = #
    # =========================== #
    
    # ------------------- #
    # - I/O Methods     - #
    # ------------------- #
    def load(self,catalogue_file,**kwargs):
        """
        kwargs can have any build option like key_ra, key_mag etc.
        """
        # ---------------------
        # - Parsing the input
        if catalogue_file.endswith(".fits"):
            # loading from fits file
            fits   = pf.open(catalogue_file)
            header = fits[self._build_properties["data_index"]].header
            data   = fits[self._build_properties["data_index"]].data
            if type(data) == pf.fitsrec.FITS_rec:
                from astrobject.utils.tools import fitsrec_to_dict
                data = TableColumns(fitsrec_to_dict(data))
                
        elif catalogue_file.endswith(".pkl"):
            # loading from pkl
            fits = None
            header = None
            data = load_pkl(catalogue_file)
            if not type(data) is TableColumns:
                try:
                    data = TableColumns(data)
                except:
                    print "WARNING Convertion of 'data' into astropy TableColumns failed"
        else:
            raise TypeError("the given catalogue_file must be a .fits or.pkl")

        # ---------------------
        # - Calling Creates
        self.create(data,header,**kwargs)
        self._properties["filename"] = catalogue_file
        self._derived_properties["fits"] = fits

        
    def create(self,data,header,force_it=True,**build):
        """
        This is a Central Method, this will set to the instance the fundamental
        parameters data, header upon which most of the instance functionnality is
        based.

        Parameters
        ----------

        data: [astropy.TableColumns, dictionnary or numpy.ndarray (withkey)]
                                   the data associated to the catalogue. It must have
                                   ra, dec, and magnitude entries. The keys associated
                                   to these are set in _build_properties (key_ra,
                                   key_dec, key_mag ...). See also set_mag_keys
        """
        if self.has_data() and force_it is False:
            raise AttributeError("'data' is already defined."+\
                    " Set force_it to True if you really known what you are doing")

        self._properties["data"] = Table(data)
        self._properties["header"] = header if header is not None \
          else pf.Header()
        self._build_properties = kwargs_update(self._build_properties,**build)
        # -------------------------------
        # - Try to get the fundamentals
        if self._build_properties['key_ra'] is None:
            self._automatic_key_match_("ra")
            
        if self._build_properties['key_dec'] is None:
            self._automatic_key_match_("dec")
    
        self._update_contours_()


    def extract(self,contours):
        """
        This method enables to get a (potential) sub part of the existing catalogue
        based on the given 'contours'.
        'contours' is a shapely.Polygon or a matplotlib.patches.Polygon
        (see shape.point_in_contours)
        """
        mask = shape.point_in_contours(self._ra,self._dec,contours) # WRONG
        copy_ = self.copy()
        copy_.create(self.data[mask],None,force_it=True)
        return copy_

    
    def join(self,datatable):
        """
        The Methods enable add data to the current catalogue.
        This is based on astropy.Table join:
          "
            The join() method allows one to merge these two tables into a single table
            based on matching values in the “key columns”.
          "
        We use the join_type='outer'
        (http://docs.astropy.org/en/stable/table/operations.html)
        """
        # ---------------------
        # - Input Test
        if type(datatable) is not Table:
            try:
                datatable = Table(datatable)
            except:
                raise TypeError("the given datatable is not an astropy. Table and cannot be converted into.")

        from astropy.table import join
        
        self._properties["data"] = join(self.data,datatable,join_type='outer')
        self._update_fovmask_()

    def merge(self,catalogue_):
        """
        """
        if "__nature__" not in dir(catalogue_) or catalogue_.__nature__ != "Catalogue":
            raise TypeError("the input 'catalogue' must be an astrobject catalogue")

        self.join(catalogue_.data)
        self._derived_properties["contours"] = self.contours.union(catalogue_.contours)
        
            
    def writeto(self,savefile,force_it=True):
        """
        The catalogue will be saved as pkl or fits files. The fits wil be used if this
        has a header, the pkl otherwise
        """
        if self.header is None or len(self.header.keys())==0:
            self._writeto_pkl_(savefile)
        else:
            self._writeto_fits_(savefile,force_it=force_it)

    # --------------------- #
    # Set Methods           #
    # --------------------- #
    def set_mag_keys(self,key_mag,key_magerr):
        """
        """
        self._build_properties["key_mag"] = key_mag
        self._build_properties["key_magerr"] = key_magerr

    def set_coord_keys(self,key_ra,key_dec):
        """
        """
        self._build_properties["key_ra"] = key_ra
        self._build_properties["key_dec"] = key_dec
        
    def set_wcs(self,wcs,force_it=False,update_fovmask=True):
        """
        """
        if self.has_wcs() and force_it is False:
            raise AttributeError("'wcs' is already defined."+\
                    " Set force_it to True if you really known what you are doing")
                    
        self._side_properties["wcs"] = astrometry.get_wcs(wcs)
        
        if update_fovmask:
            if self.has_wcs():
                self.set_fovmask(wcs=self.wcs,update=False)
            else:
                print "None wcs"
                self._load_default_fovmask_()

            
    def set_fovmask(self, wcs=None,
                    ra_range=None, dec_range=None,
                    update=True):
        """
        This methods enable to define the mask of catalgue objects within the
        given field of view.
        
        Parameters
        ----------
        - options -
        update: [bool]             True to have a consistent object. Set False
                                   only if you know what you are doing
        Return
        ------
        Void
        """
        if wcs is not None:
            if "coordsAreInImage" not in dir(wcs):
                raise TypeError("'wcs' solution not recognized")
            
            self.fovmask = np.asarray([wcs.coordsAreInImage(ra,dec)
                                       for ra,dec in zip(self._ra,self._dec)])
        elif ra_range is None or dec_range is None:
            raise AttributeError("please provide either 'wcs' and ra_range *and* dec_range")
        else:
            self.fovmask = (self.ra>ra_range[0]) & (self.ra<ra_range[1]) \
              (self.dec>dec_range[0]) & (self.dec<dec_range[1])
            self._fovmask_ranges = [ra_range,dec_range]
            
    def set_matchedmask(self,matchedmask):
        """This methods enable to set to matchedmask, this mask is an addon
        mask that indicate which point from the catalogue (after the fov cut)
        has been matched by for instance a sextractor/sep extraction
        """
        if matchedmask is None or len(matchedmask) == 0:
            return

        if type(matchedmask[0]) is bool:
            # - it already is a mask, good
            self._side_properties["matchedmask"] = np.asarray(matchedmask,dtype=bool)
            return

        if type(matchedmask[0]) in [int,np.int32,np.int64]:
            # - it must be a list of matched index (from SkyCoord matching fuction e.g.)
            self._side_properties["matchedmask"] = np.asarray([i in matchedmask for i in range(len(self.ra))],
                                                              dtype=bool)
            return
        raise TypeError("the format of the given 'matchedmask' is not recongnized. "+\
                        "You could give a booleen mask array or a list of accepted index")
                        
    # --------------------- #
    # Get Methods           #
    # --------------------- #
    def get_photomap(self,idx_only=None,lbda=None):
        """
        """
        mask = self.idx_to_mask(idx_only) if idx_only is not None \
          else np.ones(self.nobjects,dtype=bool)
        if lbda is not None:
            self.lbda = lbda
        elif self.lbda is None:
            raise ValueError("No known 'lbda' and no 'lbda' given")

        flux_fluxerr = self._flux_fluxerr
        """
        fluxes = [flux_fluxerr[0][i] for i in idx_only]
        variances = [flux_fluxerr[1][i]**2 for i in idx_only]
        ra = [self.ra[i] for i in idx_only]
        dec = [self.dec[i] for i in idx_only]
        """
        fluxes = flux_fluxerr[0][mask]
        variances = flux_fluxerr[1][mask]**2
        ra = self.ra[mask]
        dec = self.dec[mask]

        
        pmap = photomap(fluxes=fluxes,variances=variances,
                        ra=ra,dec=dec,lbda=self.lbda)
        pmap.set_wcs(self.wcs)
        return pmap
    
    def idx_to_mask(self,idx):
        mask = np.zeros(self.nobjects,dtype=bool)
        for i in idx:
            mask[i] = True
        return mask

    # --------------------- #
    # PLOT METHODS          #
    # --------------------- #
    def display(self,ax,wcs_coords=True,draw=True,
                apply_machedmask=True,draw_contours=True,
                show_nonmatched=True,propout={},
                **kwargs):
        """
        This methods enable to show all the known sources in the
        image's field of view.
        This will only works if a catalogue has been set

        Parameters
        ----------

        ax: [matplotlib.axes]      the axes where the catalogue should be
                                   displaid

        
        Return
        ------
        None (if no data) / ax.plot returns
        """
        if not self.has_data():
            print "Catalogue has no 'data' to display"
            return
                  
        if wcs_coords:
            x,y = self.ra,self.dec
        else:
            x,y = self.wcs_xy
        # -------------- #
        # - mask
        mask = self.matchedmask if self.has_matchedmask() \
          else np.ones(len(self.ra),dtype=bool)

        starmask = self.starmask if self.has_starmask() \
          else np.ones(len(self.ra),dtype=bool)
          
        # -- in / out star / notstar
        x_starin,y_starin = x[mask & starmask], y[mask & starmask]
        x_nostarin,y_nostarin = x[mask & ~starmask], y[mask & ~starmask]
        
        x_starout,y_starout = x[~mask & starmask],y[~mask & starmask]
        x_nostarout,y_nostarout = x[~mask & ~starmask], y[~mask & ~starmask]
        # -- Properties
        colorin = "b"
        colorout = "r"
        default_prop = dict(
            ls="None",marker="o",mfc="b",alpha=0.7,ms=6,mew=0,
            label="%s-catalgue"%self.source_name,
            )
        prop = kwargs_update(default_prop,**kwargs)

        # -- plot loop
        axout = []
        for x_,y_,show_,propextra in [[x_starin,  y_starin,True,
                                       {}],
                                      [x_nostarin,y_nostarin,True,
                                        dict(mfc="None",mec=colorin,mew=2,alpha=0.6)],
                                      [x_starout, y_starout, show_nonmatched,
                                        dict(mfc=colorout,ms=4,alpha=0.5)],
                                      [x_nostarout,y_nostarout,show_nonmatched,
                                        dict(mfc="None",mec=colorout,mew=1,ms=4,alpha=0.5)],
                                ]:
            prop_ = kwargs_update(prop,**propextra)
            if len(x_)>0 and show_:
                axout.append(ax.plot(x_,y_,**prop_))

        if self.contours is not None and wcs_coords and draw_contours:
            shape.draw_polygon(ax,self.contours,ec=None)
            
        if draw:
            ax.figure.canvas.draw()
            
        return axout
    
    # =========================== #
    # Internal Methods            #
    # =========================== #
    # ------------------
    # --  Save files
    def _writeto_pkl_(self,savefile,force_it=True):
        """This the current catalogue has a pkl file"""
        if not savefile.endswith(".pkl"):
            savefile +=".pkl"
            
        dump_pkl(self.data,savefile)
    
    def _writeto_fits_(self,savefile,force_it=True):
        raise NotImplementedError("to be done")
    # ------------------
    # --  Update
    def _update_fovmask_(self):
        """
        """
        if self.has_wcs():
            self.set_fovmask(wcs=self.wcs)
        elif "_fovmask_ranges" in dir(self):
            self.set_fovmask(ra_range=self._fovmask_ranges[0],
                             dec_range=self._fovmask_ranges[1])
        return
    
    def _update_contours_(self):
        """
        """
        if not shape.HAS_SHAPELY:
            self._derived_properties["contours"] = None
        # -- This roughly take 0.2s for 1e4 objects
        self._derived_properties["contours"] = \
          shape.get_contour_polygon(np.asarray(self._ra),
                                    np.asarray(self._dec))
        
    # ------------------
    # --  Key match
    def _automatic_key_match_(self, key,build_key=None):
        """
        """
        try:
            knownkeys = self.data.keys()
        except:
            print "WARNING no automatic key available (data.keys() failed)"
            return
        vkey = [k for k in knownkeys if key in k.lower() if not k.startswith("e_")]
        if len(vkey) >1:
            print "WARNING ambiguous %s key. Use set_coord_keys. "%key+", ".join(vkey)
            return
        if len(vkey) ==0:
            if key.lower() == "dec":
                return self._automatic_key_match_("de",build_key="dec")
            print "WARNING no match found for the %s key. Use set_coord_keys. "%key
            print "       known keys: "+", ".join(knownkeys)
            return

        if build_key is None:
            build_key = key
        self._build_properties['key_%s'%build_key] = vkey[0]


        
    def _automatic_key_ra_match_(self):
        """
        """
        self._automatic_key_match_("ra")

    def _automatic_key_dec_match_(self):
        """
        """
        self._automatic_key_match_("dec")

    
    # =========================== #
    # Properties and Settings     #
    # =========================== #
    # -------
    # - data
    @property
    def data(self):
        return self._properties["data"]
    
    def has_data(self):
        return False if self.data is None\
          else True
          
    @property
    def nobjects(self):
        if self.data is None:
            return 0
        
        if self.header is not None and "NAXIS2" in self.header:
            return self.header["NAXIS2"]

        if type(self.data) is dict:
            return len(self.data.values()[0])
        
        return len(self.data)

    @property
    def nobjects_in_fov(self):
        return len(self.ra)
    
    # ---------------
    # - header / wcs 
    @property
    def header(self):
        return self._properties["header"]
    
    @property
    def wcs(self):
        return self._side_properties["wcs"]
        
    def has_wcs(self):
        return False if self.wcs is None\
          else True
        
    @property
    def fovmask(self):
        if self._side_properties["fovmask"] is None:
            self._load_default_fovmask_()
            
        return self._side_properties["fovmask"]
    
    def _load_default_fovmask_(self):
        self._side_properties["fovmask"] = np.ones(self.nobjects,dtype=bool)
        
    @fovmask.setter
    def fovmask(self,newmask):
        if len(newmask) != self.nobjects:
            raise ValueError("the given 'mask' must have the size of 'ra'")
        self._side_properties["fovmask"] = newmask


    @property
    def matchedmask(self):
        return self._side_properties["matchedmask"]

    def has_matchedmask(self):
        return False if self.matchedmask is None\
          else True
          
    # ------------
    # - on flight
    # - coords
    @property
    def ra(self):
        """Barycenter position along world x axis"""
        return self._ra[self.fovmask]
    
    @property
    def _ra(self):
        if not self.has_data():
            raise AttributeError("no 'data' loaded")
        return self.data[self._build_properties["key_ra"]]
    
    @property
    def dec(self):
        """arycenter position along world y axis"""
        return self._dec[self.fovmask]
    
    @property
    def _dec(self):
        if not self.has_data():
            raise AttributeError("no 'data' loaded")
        return self.data[self._build_properties["key_dec"]]
        
    @property
    def sky_radec(self):
        """This is an advanced radec methods tight to astropy SkyCoords"""
        return coordinates.SkyCoord(ra=self.ra,dec=self.dec, unit="deg")
    
    # - mag
    @property
    def mag(self):
        """Generic magnitude"""
        return self._mag[self.fovmask]

    @property
    def _mag(self):
        if not self.has_data():
            raise AttributeError("no 'data' loaded")
        if not self._is_keymag_set_():
            raise AttributeError("no 'key_mag' defined. see self.set_mag_keys ")
        
        return self.data[self._build_properties["key_mag"]]
        
    @property
    def mag_err(self):
        """Generic magnitude RMS error"""
        return self._mag_err[self.fovmask]

    @property
    def _mag_err(self):
        """Generic magnitude RMS error"""
        if not self.has_data():
            raise AttributeError("no 'data' loaded")
        if not self._is_keymag_set_():
            raise AttributeError("no 'key_magerr' defined. see self.set_mag_keys ")
        
        return self.data[self._build_properties["key_magerr"]]
    
    # ----------------
    # - Fluxes
    @property
    def lbda(self):
        return self._side_properties["lbda"]

    @lbda.setter
    def lbda(self,value):
        self._side_properties["lbda"] = value
        
    @property
    def _flux_fluxerr(self):
        if self.lbda is None:
            raise AttributeError("set 'lbda' first (self.lbda = ...)")
        
        return mag_to_flux(self.mag,self.mag_err,self.lbda)
    
    @property
    def flux(self):
        return self._flux_fluxerr[0]
    
    @property
    def flux_err(self):
        return self._flux_fluxerr[1]
    
    def _is_keymag_set_(self,verbose=True):
        """this method test if the keymag has been set"""
        if self._build_properties["key_mag"] is None or \
          self._build_properties["key_magerr"] is None:
            if verbose:
                print "No 'key_mag'/'key_magerr' set ; call 'set_mag_keys'. List of potential keys: "\
                  +", ".join([k for k in self.data.keys() if "mag" in k or "MAG" in k])
            return False
        return True
    
    @property
    def objecttype(self):
        return self._objecttype[self.fovmask]

    @property
    def _objecttype(self):
        if "key_class" not in self._build_properties.keys():
            raise AttributeError("no 'key_class' provided in the _build_properties.")
        
        return self.data[self._build_properties["key_class"]]
    
    @property
    def starmask(self):
        """ This will tell which of the datapoints is a star
        Remark, you need to have defined key_class and value_star
        in the __build_properties to be able to have access to this mask
        """
        if "value_star" not in self._build_properties.keys():
            return None

        flag = self.objecttype == self._build_properties["value_star"]
        return flag.data  #not self.fovmask already in objecttype

    def has_starmask(self):
        return False if self.starmask is None \
          else True
          
    # ------------
    # - Derived
    @property
    def fits(self):
        return self._derived_properties["fits"]

    @property
    def wcs_xy(self):
        if self.has_wcs():
            return np.asarray([self.wcs.wcs2pix(ra_,dec_) for ra_,dec_ in zip(self.ra,self.dec)]).T
        raise AttributeError("no 'wcs' solution loaded")

    # ----------------------
    # - Alone Object
    def define_around(self,ang_distance):
        """
        """
        idxcatalogue = self.sky_radec.search_around_sky(self.sky_radec,
                                                        ang_distance)[0]
        self._derived_properties["naround"] = np.bincount(idxcatalogue)

    def _is_around_defined(self):
        return False if self._derived_properties["naround"] is None\
          else True
        
    @property
    def nobjects_around(self):
        """ """
        if not self._is_around_defined():
            print "INFORMATION: run 'define_around' to set nobject_around"
        return self._derived_properties["naround"]
    
    @property
    def isolatedmask(self):
        """
        """
        if not self._is_around_defined():
            raise AttributeError("no 'nobjects_around' parameter derived. Run 'define_around'")
        
        return (self.nobjects_around == 1)

    # ----------------------
    # - Shapely
    @property
    def contours(self):
        return self._derived_properties["contours"]
