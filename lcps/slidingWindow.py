# -*- coding: utf-8 -*-
"""
Created on Thu Jun  9 18:10:47 2016

@author: mschleck
"""

import numpy as np
from astropy.table import Table, vstack


def get_localMedian(flux, iWinStart, winSize, Nneighb):
    """ Find the local median of fluxes, ignoring the current window.
    
    get_localMedian computes the median flux in the neighboring windows. The fluxes
    in the current window is ignored.
    
    Parameters
    ----------
    flux : narray
        A numpy array with the flux data
    iWinStart : int
        Index of the first datum in the current window
    winSize : int
        Size of a window
    Nneighb : int
        Number of neighboring windows to be considered for the averaging (At
        the boundaries of the time series, the considered data extends to the
        beginning or end of the array, respectively)
    
    Returns
    -------
    localMedian : float
        Median of the flux in the windows neighboring the current one
        
    Example
    -------
    >>> flux = np.array([1.00,1.01,0.99,0.80,0.75,0.95,0.99,0.99,1.00,0.80,1.01])
    >>> get_localMedian(flux, 4, 4, Nneighb=1)
    1.0
    """
    
    # At the boundaries, expand neighborhood towards center
    if (iWinStart < winSize) or (iWinStart > len(flux) - winSize):
        Nneighb *= 2

    # construct neighborhood without current window        
    iMin = max(0, iWinStart - Nneighb*winSize)
    iMax = min(len(flux), iWinStart + (1 + Nneighb)*winSize)
    neighborhood = np.append(flux[iMin:iWinStart],\
        flux[iWinStart + winSize:iMax + 1])
        
    return np.median(neighborhood)


def findDip(timeWindow, fluxWindow, minDur=1, maxDur=5, localMedian=1.00, detectionThresh=0.995):
    """ Search for negative deviations, i.e. dips, in an array.
    
    findDip counts the number of entries in fluxWindow that fall short of a 
    threshold in relative flux specified in detectionThresh. If this number
    lies between minDur and maxDur, a dip is detected and findDip returns the
    time of egress and the minimum flux relative to localMedian.
    
    Parameters
    ----------
    timeWindow : array
        Numpy array containing time data
    fluxWindow : array
        Numpy array containing flux data
    minDur : int
        minimum dip duration in # of data points
    maxDur : int
        maximum dip duration in # of data points
    localMedian : float
        local median flux
    detectionThresh : float
        fraction of flux, below which a deviation is registered
    
    Returns
    -------
#    dip : bool
#        True, if dip of length between [minDur, maxDur] detected
    
    t_egress : float
        time at end of detected dip 
    minFlux : float
        Minimum flux relative to localMedian
        
    Example
    -------
    >>> timeWindow = np.array([0.,1.,2.,3.,4.,5.])
    >>> fluxWindow = np.array([1.00,1.01,0.99,0.80,0.75,0.95])
    >>> findDip(timeWindow, fluxWindow, detectionThresh=0.90)
    (5.0, 0.75)
    """
    
    fluxThresh =  detectionThresh*localMedian
    if len(fluxWindow[fluxWindow < fluxThresh]) >= minDur:
        # There are low fluxes, check for coherence
            NloFlux = 0
            for i, datum in enumerate(fluxWindow):
                if datum < fluxThresh:
                    NloFlux += 1
                else:                    
                    # End of dip, check if length falls between limits
                    if minDur <= NloFlux <= maxDur:
                        # return time of egress and min. flux rel. to median
                        return timeWindow[i], \
                            np.min(fluxWindow[:i])/localMedian
                    else:
                        # look for additional dips in the window
                        NloFlux = 0
                        continue    
    # No dips found
    return None, None


def dipsearch(EPICno, photometry, winSize=10, stepSize=1, Nneighb=2, minDur=2, maxDur=5,\
        detectionThresh=0.995):
    """ Use a sliding window technique to search for dips in photometric time series.
    
    dipsearch iteratively runs through a light curve with a window of N=`winSize`
    data points. The fluxes within the window are compared to a local median, which
    is computed from the neighboring `Nneighb` windows. The data in the current
    window is ignored for the median computation. 
    
    The window is scanned for `minDur` <= N <= `maxDur` consecutive data points 
    that fall short of a threshold flux of `detectionThresh`*`localMedian`. If
    such an event is detected, its time and minimum flux is returned.
    
    Parameters
    ----------
    EPICno : str
        EPIC number of the target
    photometry : Astropy Table
        A table with the whole photometric data containing columns 'TIME', 'FLUX'
    winSize : int
        Size of a window
    stepSize : int
        steps per slide (Default = 1, i.e. slide one data point per iteration).
    Nneighb : int
        Number of neighboring windows to be considered for the local median (At
        the boundaries of the time series, the considered data extends to the
        beginning or end of the array, respectively)    
    minDur : int
        minimum dip duration in # of data points
    maxDur : int
        maximum dip duration in # of data points
    detectionThresh : float
        fraction of flux, below which a deviation is registered
    
    Returns
    -------
    dips : Astropy table
        A table containing parameters of detected dips. Columns:
        EPICno : str
            EPIC number of the target
        t_egress : float
            time at end of detected dip 
        minFlux : float
            Minimum flux relative to localMedian
        
    Example
    -------
    >>> np.random.seed(99)
    >>> EPICno = '9999999'
    >>> photometry = Table([np.arange(1000.), np.random.normal(1.0, 0.005, 1000)],\
        names=['TIME','FLUX'], dtype=[float, float])
    >>> dips = dipsearch(EPICno, photometry)
    """            
                   
    # Check if parameters are consistent
    if minDur > maxDur:
        raise ValueError('min dip duration greater than max dip duration')
    if winSize <= maxDur:
        raise ValueError('max dip duration greater than or equal window size')

    # extract time and flux from `photometry` table
    t = np.array(photometry['TIME'])
    flux = np.array(photometry['FLUX'])
    
    # compute mean cadence
    cadence = (t[-1] - t[0])/len(t)

    # prepare results
    dips = Table(names=['EPIC','t_egress','minFlux'], dtype=['i8',float,float])    
    
    # Slide the window  
    prev_t_egress = 0.
    for i in xrange(0, len(flux) - winSize, stepSize):
        timeWindow = t[i:i + winSize]
        fluxWindow = flux[i:i + winSize]
        localMedian = get_localMedian(flux, i, winSize, Nneighb)
        t_egress, minFlux = findDip(timeWindow, fluxWindow, minDur, maxDur,\
            localMedian,detectionThresh)
        if t_egress:
            # check if detected dip is a new one
            if (t_egress - prev_t_egress) > 2*cadence:
                # save any found dips
                dips.add_row([EPICno, t_egress, minFlux])
                prev_t_egress = t_egress
    return dips
  
  
if __name__ == "__main__":
    import doctest
    doctest.testmod()
    
##############
#    #TEST
#fluxWindow = Table([[0.,1.,2.,3.,4.,5.], [1.00,1.01,0.99,0.80,0.75,0.95]],\
#        names=['TIME','FLUX'], dtype=[float, float])
#t_egress, minFlux = findDip(fluxWindow, detectionThresh=0.90) 
#print t_egress, minFlux
    
#photometry = Table([[0.,1.,2.,3.,4.,5.,6.,7.,8.,9.,10.],\
#        [1.00,1.01,0.99,0.80,0.75,0.95,0.99,0.99,1.00,0.80,1.01]],\
#        names=['TIME','FLUX'], dtype=[float, float])
#median = get_localMedian(photometry, 4, 4, Nneighb=1)
    
#np.random.seed(99)  
#photometry = Table([np.arange(3000.), np.random.normal(1.0, 0.005, 3000)],\
#        names=['TIME','FLUX'], dtype=[float, float]) 
#dips = dipsearch(photometry)
#print dips