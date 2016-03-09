# -*- coding: utf-8 -*-

"""
Multiple operations on data or modeling results (e.g. aligning, convolution, ...)

Author: R. Lombaert

"""

from scipy import mean, std, sqrt, log, isfinite
from scipy import array, zeros, arange
from scipy.stats import tmean, tstd
from scipy.optimize import leastsq
from scipy.integrate import trapz
from scipy.special import erf
from astropy import units as u
import numpy as np

from cc.tools.numerical import Interpol


def alignY(datalists,xmin,xmax,zeropoint=0,p0=[1,0,1.5,-2.5],func='power'):

    """

    *** WILL BE REWRITTEN ***

    Align two datasets by shifting Y coordinate.

    Works on multiple data lists at a time. Each dataset is shifted to match
    with the previous dataset AFTER the previous one has already been shifted.

    e.g. for the third dataset y_new = zeropoint + shifts[1]*shifts[2]*y

    The shifts between datasets are multiplicative, the first dataset is
    shifted additively by the keyword zeropoint.

    At least 3 points of overlap are required!

    @param datalists: two or more 2d lists of data giving (x,y)
    @type datalists: list[list[(.,.)]]
    @param xmin: the lower boundar(y)(ies) of the overlapping region, used for
                 alignment. Must be 1 value for 2 datasets, n-1 values for more
    @type xmin: float or list
    @param xmax: the upper boundar(y)(ies) of the overlapping region, used for
                 alignment. Must be 1 value for 2 datasets, n-1 values for more
    @type xmax: float or list

    @keyword zeropoint: The first dataset is shifted additively with this value

                        (default: 0)
    @type zeropoint: float
    @keyword p0: initial parameters for fitting function definition

                 (default: [1,0,1.5,-2.5])
    @type p0: list

    @return: The datasets are returned as given, but with shifted Y-values, and
             the shifts used (first value additively, rest multiplicatively)
    @rtype: (list[list[(.,.)]], list)

    """

    #- zeropoint correction
    shifts = [zeropoint]
    current_data = array(datalists[0])
    corrected = [[coord + array([0,zeropoint]) for coord in current_data]]

    #- Power law is fitted to overlapping xrange for both datasets with leastsq
    #- x of second list is evaluated with both functions
    #- second list's y values are corrected by the mean of the ratios of the
    #- two function evaluations

    for i in xrange(len(datalists)-1):
        p_lsqlist1 = leastsq(Interpol.getResiduals,p0,\
                             args=([x
                                    for x in array(corrected[i])[:,0]
                                    if x >= xmin[i] and x <= xmax[i]],\
                                   [coord[1]
                                    for coord in array(corrected[i])
                                    if coord[0] >= xmin[i] and coord[0] <= xmax[i]],\
                                   func),\
                             maxfev=2000)[0]
        p_lsqlist2 = leastsq(Interpol.getResiduals,p0,\
                             args=([x
                                    for x in array(datalists[i+1])[:,0]
                                    if x >= xmin[i] and x <= xmax[i]],\
                                   [coord[1]
                                    for coord in array(datalists[i+1])
                                    if coord[0] >= xmin[i] and coord[0] <= xmax[i]],\
                                   func),\
                             maxfev=2000)[0]
        f1x2 = Interpol.pEval([x
                               for x in array(datalists[i+1])[:,0]
                               if x >= xmin[i] and x <= xmax[i]],
                              p_lsqlist1,func)
        f2x2 = Interpol.pEval([x
                               for x in array(datalists[i+1])[:,0]
                               if x >= xmin[i] and x <= xmax[i]],\
                              p_lsqlist2,func)
        shifts.append(mean(f1x2/f2x2))
        corrected.append([coord*array([1,shifts[i+1]])
                          for coord in array(datalists[i+1])])
    return corrected,shifts



def doConvolution(x_in,y_in,x_out,widths,factor=5,oversampling=1):

    '''
    Perform convolution on lists with a Gaussian filter.

    Reduce the input grid to the target grid by integration.

    @param x_in: The input x-values
    @type x_in: array
    @param y_in: The input y-values
    @type y_in: array
    @param x_out: The target x-grid
    @type x_out: array
    @param widths: The full width/half maximum spectral resolution as a
                   function of wavelength, i.e. the fwhm of the gaussian
    @type widths: array

    @keyword factor: the sigma factor for determining the window pushed through
                     the gaussian filter. This avoids having to convolve the
                     whole input grid, which takes a lot of time. Beyond
                     sigma*factor the contribution of the y values is assumed
                     to be negligible.

                     (default: 5)
    @type factor: int
    @keyword oversampling: oversampling factor of the target x-grid with
                           respect to the given spectral resolution.

                           (default: 1)
    @type oversampling: int

    @return: The resulting y-values
    @rtype: list

    '''

    x_in,y_in,x_out,widths = array(x_in),array(y_in),array(x_out),array(widths)
    y_out = []
    print 'Convolving for x_out between %.2f micron and %.2f micron with oversampling %i.' \
          %(x_out[0],x_out[-1],int(oversampling))
    #- Convert FWHM's to sigma for the gaussians
    sigma = [fwhm/(2.*sqrt(2.*log(2.))) for fwhm in widths]
    #- Define the binsizes of the bins that will be integrated, i.e. the
    #- apparent resolution of x_out
    binsize = [w/oversampling for w in widths]
    for delta_bin,sigi,xi_out in zip(binsize,sigma,x_out):
        yi_in = y_in[abs(x_in-xi_out)<=factor*sigi]
        #- if not empty: continue, else add 0
        if list(yi_in) and set(yi_in) != set([0.0]):
            #- all relevant xi's for the bin around xi_out, ie in this bin the
            #- y-values will be integrated
            xi_in = x_in[abs(x_in-xi_out)<=delta_bin]
            #- The window for the convolution itself, outside this window the
            #- data are assumed to be negligible, ie for a gaussian
            window = x_in[abs(x_in-xi_out)<=factor*sigi]
            convolution = convolveArray(window,yi_in,sigi)
            #- if one value in the bin, out of the window selection: add value
            if len(list(convolution[abs(window-xi_out)<=delta_bin])) == 1:
                y_out.append(convolution[abs(window-xi_out)<=delta_bin][0])
                print 'Convolution has a window of only one element at xi_out %f.'%xi_out
            #- If more than one value: integrate
            elif list(convolution[abs(window-xi_out)<=delta_bin]):
                y_out.append(trapz(y=convolution[abs(window-xi_out)<=delta_bin],x=xi_in)/(xi_in[-1]-xi_in[0]))
            #- If no values in the bin from the window: add average of the window
            #- This should not occur ideally!
            else:
                print 'Convolution has a window of no elements at x_out ' + \
                      '%f. Careful! Average is taken of '%(xi_out) + \
                      'sigma*factor window! This should not be happening...'
                y_out.append(sum(convolution)/float(len(convolution)))
        else:
            y_out.append(0.0)
    return y_out



def convolveArray(xx, yy=None, sigma=3):

    """
    Convolves an intensity-versus-velocity profile with
    an instrumental Gaussian profile of width 'sigma'

    by Kristof Smolders

    @param xx: x values
    @type xx: array

    @keyword yy: y values, if None, the y values are assumed to be included in
                 xx, in its second dimension.

                 (default: None)
    @type yy: array
    @keyword sigma: width of the gaussian profile

                    (default: 3)
    @type sigma: float

    @return: The new y values after convolution
    @rtype: array

    """

    if yy is None and xx.shape[0] > 1:
        yy = xx[1,:]
        xx = xx[0,:]

    if xx == array([]):
        out = array([0.0])
    elif len(xx)==1:
        out = xx
    else:
        nn  = len(xx)
        out = zeros(nn)

    # Begin: half a pixel
    C   = yy[0]
    xb  = xx[0]
    xe  = 0.5*(xx[1]+xx[0])
    out = yy[0] + C/2 * (erf((xe-xx)/(sqrt(2)*sigma)) - 1)

    # End: half a pixel
    C   = yy[nn-1]
    xb  = 0.5*(xx[nn-1]+xx[nn-2])
    xe  = xx[nn-1]
    out = out + C/2 * (1 - erf((xb-xx)/(sqrt(2)*sigma)))

    # Middle
    for jj in arange(1,nn-1):
        C   = yy[jj]
        xb  = 0.5*(xx[jj]+xx[jj-1])
        xe  = 0.5*(xx[jj]+xx[jj+1])
        out = out + C/2 * (erf((xe-xx)/(sqrt(2)*sigma)) -
                           erf((xb-xx)/(sqrt(2)*sigma)))
    return out



def angularSize(distance): 

    '''
    Equivalency for the astropy.units module for converting angular size to 
    physical length and vice versa. 
    
    Requires the distance to be given in pc.
    
    Can be used to convert angular sizes and lengths using the units module. 
    >>> equiv = angularSize(1000.)
    >>> rad = (0.001*u.arcsec).to(u.au,equivalencies=equiv)
    gives the length in astronomical units.
    
    Note that you don't have to give arcsec or au. You can also ask for u.cm, 
    u.arcminute, etc. The astropy unit conversion module takes care of these 
    conversions as long as no equivalency is needed.
    
    @param distance: The distance to the object in parsec
    @type distance: float
    
    @return: list of (unit in, unit out, forward conversion, reverse conversion)
    @rtype: list(tuple)
    
    '''
    
    #- 1 AU at 1 pc is 1 as on the sky, hence 1 AU at x pc is 1/x as on the sky
    #- hence [real_rad/1 AU] = [angrad/1 as] * [distance/1 pc]
    distance = float(distance)
    return [(u.arcsec,u.au, lambda x: x*distance, lambda x: x/distance)]



def reduceArray(arr,stepsize,cutoff=None,mode='average'):

    '''
    Reduce the size of a 1d-array.

    Two modes are available:
        - average: subsequent n=stepsize elements are averaged
        - remove: keep one element every n=stepsize elements

    The average mode can be used when, e.g., reading MCMax output, where the
    density/temperature/... grids are given for radial and angular coordinates.
    In case only the radial points are needed, the stepsize would then be the
    number of angular grid cells.

    @param arr: The array to be reduced
    @type arr: np.array
    @param stepsize: The number of subsequent elements to average/frequency of
                     element removal.
    @type stepsize: int

    @keyword cutoff: A cutoff value below which no reduction is done. Default
                     if the full array is to be reduced. Only relevant for
                     mode == 'remove'.

                     (default: None)
    @type cutoff: float
    @keyword mode: The reduction mode, either 'average' or 'remove'. If the
                   mode is not recognized, it is assumed to be 'average'.

                   (default: 'average')
    @type mode: string

    @return: The reduced array
    @rtype: np.array

    '''

    arr, stepsize, mode = array(arr), int(stepsize), str(mode).lower()

    if mode == 'remove':
        if cutoff <> None:
            cutoff = float(cutoff)
            arrkeep = arr[arr<=cutoff]
            arrsel = arr[arr>cutoff]
        else:
            arrkeep = np.empty(0)
            arrsel = arr

        arrsel = arrsel[::stepsize]
        redarr = np.concatenate((arrkeep,arrsel))

    else:
        redarr = np.mean(arr.reshape(-1,stepsize),axis=1)

    return redarr



def getRMS(flux,limits=(None,None),wave=None,wmin=None,wmax=None,minsize=20):

    '''
    Get the RMS of a flux array in a given wavelength range. If no wavelengths
    are given, the RMS of the whole array is given.

    If the array used for RMS calculation is too small, None is returned.

    The mean should already be subtracted!

    A 1-sigma clipping of the flux array can be done by providing limits.

    @param flux: The wavelength array
    @type flux: array

    @keyword limits: Flux limits if flux clipping (1 sigma!) is needed before
                     RMS calculation. None for both limits implies no clipping.
                     None for one of the limits implies a half-open interval.
                     (lower limit,upper limit)

                     (default: (None,None))
    @type limits: (float,float)
    @keyword wave: The wavelength array. If default, the RMS is calculated of
                   the whole flux array
    @type wave: array
    @keyword wmin: The minimum wavelength. If not given, the minimum wavelength
                   is the first entry in the wave array

                   (default: None)
    @type wmin: float
    @keyword wmin: The maximum wavelength. If not given, the maximum wavelength
                   is the last entry in the wave array

                   (default: None)
    @type wmax: float
    @keyword minsize: The minimum size of the selected array before proceeding
                      with the noise calculation. 0 if no min size is needed.

                      (default: 20)
    @type minsize: int

    @return: The flux RMS between given wavelengths
    @rtype: float

    '''

    fsel = selectArray(flux,wave,wmin,wmax)
    if fsel.size <= minsize:
        return None
    if limits == (None,None):
        return sqrt((fsel**2).sum()/float(len(fsel)))
    else:
        fsel2 = fsel[(fsel>limits[0])*(fsel<limits[1])]
        if fsel.size == 0:
            return None
        else:
            return sqrt((fsel2**2).sum()/float(len(fsel2)))


def getMean(flux,limits=(None,None),wave=None,wmin=None,wmax=None,minsize=20):

    '''
    Get the mean of a flux array in a given wavelength range. If no wavelengths
    are given, the mean of the whole array is given.

    If the array used for mean calculation is too small, None is returned.

    A 1-sigma clipping of the flux array can be done by providing limits.

    @param flux: The wavelength array
    @type flux: array

    @keyword limits: Flux limits if flux clipping (1 sigma!) is needed before
                     Meancalculation. None for both limits implies no clipping.
                     None for one of the limits implies a half-open interval.

                     (default: (None,None))
    @type limits: (float,float)
    @keyword wave: The wavelength array. If default, the Mean is calculated of
                   the whole flux array
    @type wave: array
    @keyword wmin: The minimum wavelength. If not given, the minimum wavelength
                   is the first entry in the wave array

                   (default: None)
    @type wmin: float
    @keyword wmin: The maximum wavelength. If not given, the maximum wavelength
                   is the last entry in the wave array

                   (default: None)
    @type wmax: float
    @keyword minsize: The minimum size of the selected array before proceeding
                      with the noise calculation. 0 if no min size is needed.

                      (default: 20)
    @type minsize: int

    @return: The flux mean between given wavelengths
    @rtype: float

    '''

    fsel = selectArray(flux,wave,wmin,wmax)
    if fsel.size <= minsize:
        return None
    if limits == (None,None):
        return mean(fsel)
    else:
        return tmean(fsel,limits=limits)



def getStd(flux,limits=(None,None),wave=None,wmin=None,wmax=None,minsize=20):

    '''
    Get the std of a flux array in a given wavelength range. If no min/max
    wavelengths are given, the std of the whole array is given.

    If the array used for std calculation is too small, None is returned.

    A 1-sigma clipping of the flux array can be done by providing limits.

    @param flux: The wavelength array
    @type flux: array

    @keyword limits: Flux limits if flux clipping (1 sigma!) is needed before
                     STD calculation. None for both limits implies no clipping.
                     None for one of the limits implies a half-open interval.

                     (default: (None,None))
    @type limits: (float,float)
    @keyword wave: The wavelength array. If default, the STD is calculated of
                   the whole flux array
    @type wave: array
    @keyword wmin: The minimum wavelength. If not given, the minimum wavelength
                   is the first entry in the wave array

                   (default: None)
    @type wmin: float
    @keyword wmin: The maximum wavelength. If not given, the maximum wavelength
                   is the last entry in the wave array

                   (default: None)
    @type wmax: float
    @keyword minsize: The minimum size of the selected array before proceeding
                      with the noise calculation. 0 if no min size is needed.

                      (default: 20)
    @type minsize: int

    @return: The flux std between given wavelengths
    @rtype: float

    '''

    fsel = selectArray(flux,wave,wmin,wmax)
    if fsel.size <= minsize:
        return None
    if limits == (None,None):
        return std(fsel)
    else:
        return tstd(fsel,limits=limits)



def selectArray(flux,wave=None,wmin=None,wmax=None):

    """
    Select the sub array of a flux, given a wavelength range. If no range is
    given, return the full array.

    @param flux: The wavelength array
    @type flux: array

    @keyword wave: The wavelength array. If default, no wavelength selection is
                   done.
    @type wave: array
    @keyword wmin: The minimum wavelength. If not given, the minimum wavelength
                   is the first entry in the wave array

                   (default: None)
    @type wmin: float
    @keyword wmin: The maximum wavelength. If not given, the maximum wavelength
                   is the last entry in the wave array

                   (default: None)
    @type wmax: float

    @return: The flux in given wavelengths
    @rtype: array

    """

    flux = array(flux)
    fsel = flux[isfinite(flux)]
    if wave <> None:
        wave = array(wave)
        wsel = wave[isfinite(flux)]
        if wmin is None:
            wmin = wsel[0]
        if wmax is None:
            wmax = wsel[-1]
        wmin, wmax = float(wmin), float(wmax)
        fsel = fsel[(wsel>=wmin)*(wsel<=wmax)]
    return fsel




