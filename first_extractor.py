#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 - Francesco de Gasperin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# read the ascii catalogue generated by PyBDSM, extract extended sources and make a small png image
# with some relevant information included

import sys, os
import fnmatch
import numpy as np
from lofar import bdsm
import aplpy
import lib_coordinates_mode as cm

#######################################
# NGC catalogue (magenta - circle)
def ngccatalog(ra,dec,maxsep):
    datafile='ngc_catalog.txt'

    types = np.dtype({'names':['ra', 'dec', 'name'], 'formats':[np.float,np.float,'S100']})
    data = np.loadtxt(datafile, comments='#', unpack=False, dtype=types)

    for d in data:
        if (cm.angsep2(ra,dec,d['ra'],d['dec']) < maxsep):
            yield d

#######################################
# 3C catalogue (magenta - box)
def threeccatalog(ra,dec,maxsep):
    datafile='3c_catalog.txt'

    types = np.dtype({'names':['ra', 'dec', 'name'], 'formats':[np.float,np.float,'S100']})
    data = np.loadtxt(datafile, comments='#', unpack=False, dtype=types)

    for d in data:
        if (cm.angsep2(ra,dec,d['ra'],d['dec']) < maxsep):
            yield d

# working dir
wdir = sys.argv[1].strip("/")

# load past ra/dec specifications, so to not re-image the same objects (even if present in different fits files)
radec = []
srcNum = 0

# recursively walk through all dirs
for j, dircontent in enumerate(os.walk(wdir)):
    root, dirnames, filenames = dircontent
    print "####################################################"
    print "dir num "+str(j)
    fits_files = []
    for fits_file in fnmatch.filter(filenames, '*.fits'):
        # DEBUG
        #if fits_file != '12300+12128R.fits': continue
        fits_files.append(os.path.join(root, fits_file))
    
    # remove duplicates using only highest letter (hepfully are the better images)
    for i, old_fits_file in enumerate(fits_files[:]):
        for fits_file in fits_files[i:]:
            if old_fits_file[:-6] == fits_file[:-6] and old_fits_file < fits_file:
                print "removing", old_fits_file, "<", fits_file
                fits_files.remove(old_fits_file)
                break
                
    for fits_file in fits_files:
        print "Working on "+fits_file

        if not os.path.exists(fits_file.replace('.fits','.pybdsm.srl')):
            img = bdsm.process_image({'filename':fits_file, 'adaptive_rms_box':True, 'thresh_isl':4., 'trim_box':(0,1550,0,1150)})
            img.write_catalog(format='ascii', catalog_type='gaul', clobber=True)
            img.write_catalog(format='ascii', catalog_type='srl', clobber=True)
    
        # read catalogue (skip if no sources are detected)
        if not os.path.exists(fits_file.replace('.fits','.pybdsm.srl')): continue
        types = np.dtype({'names':['idx', 'ra', 'dec', 'peak_flux', 'maj', 'flux', 'rms', 'S_code'], \
                'formats':[int,float,float,float,float,float,float,'S1']})
        data = np.loadtxt(fits_file.replace('.fits','.pybdsm.srl'), comments='#', usecols=(1,2,4,8,14,38,40,44), unpack=False, dtype=types).reshape((-1,))
        
        idxs = []
        for i, source in enumerate(data):

            # consider only extended objects
            if source['S_code'] != 'M': continue
            
            # don't consider stuff smaller than 10" (remove point-source-like)
            if source['maj'] < 10/60./60.: continue
            
            # don't consider too close (1') objects
            skip = False
            for past_source in radec:
                if cm.angsep2(past_source[0],past_source[1],source['ra'],source['dec']) < 1/60.:
                    skip = True
                    break
            if skip == True: continue

            # don't consider gaussians of the same object ()
            if source['idx'] in idxs: continue
            idxs.append(source['idx'])

            radec.append([source['ra'],source['dec']])

            srcNum += 1
            if srcNum % 100 == 0: print "source number "+str(srcNum)
            # skip if image already present
            if os.path.exists('./png/'+os.path.basename(fits_file.replace('.fits','-'+str(i)+'.png'))): continue

            gc = aplpy.FITSFigure(fits_file)
            gc.recenter(source['ra'], source['dec'], radius=2/60.)
            gc.show_colorscale(stretch='log', vmin=source['rms']/2., vmax=source['peak_flux'], interpolation='bicubic', cmap='YlOrRd')
            levels = np.logspace(np.log10(2*source['rms']),np.log10(source['peak_flux']),7)
            gc.show_contour(fits_file, levels=levels, colors='black', overlap=True)

            # add some info
            gal_lat = str(int(cm.eq_to_gal(source['ra'],source['dec'])[1]))
            gc.add_label(source['ra'], source['dec']+1.9/60., 'Gal lat: '+gal_lat, color='black')
            gc.add_label(source['ra'], source['dec']+1.8/60., 'RA: '+str(source['ra']), color='black')
            gc.add_label(source['ra'], source['dec']+1.7/60., 'DEC: '+str(source['dec']), color='black')

            # add 3c and NGC locations
            for threec in threeccatalog(source['ra'],source['dec'],3/60.):
                gc.show_markers(threec['ra'], threec['dec'], c='green')
                gc.add_label(threec['ra'], threec['dec']+0.1/60., '3C'+threec['name'], color='green')
            for ngc in ngccatalog(source['ra'],source['dec'],3/60.):
                gc.show_markers(ngc['ra'], ngc['dec'], c='blue')
                gc.add_label(ngc['ra'], ngc['dec']-0.1/60., 'NGC'+ngc['name'], color='blue')

            print "Saving: ./png/"+os.path.basename(fits_file.replace('.fits','-'+str(i)+'.png'))
            gc.save('./png/'+os.path.basename(fits_file.replace('.fits','-'+str(i)+'.png')))
            gc.close() # prevent run out of memory
