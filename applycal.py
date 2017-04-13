#!/usr/bin/python
# apply tec in one direction

import os, sys, optparse
from numpy import sin, cos
import tables
import casacore.tables as pt
import numpy as np

opt = optparse.OptionParser()
opt.add_option('-i','--inms',help='Input MS',default='')
opt.add_option('--incol',help='Input column',default='DATA')
opt.add_option('--outcol',help='Output column',default='CORRECTED_DATA')
opt.add_option('--inh5',help='Input H5parm',default='')
opt.add_option('-d','--dir',help='Direction (int)',default=0)
opt.add_option('-c','--corrupt',action="store_true",default=False,help='Corrupt')
o, args = opt.parse_args()

t = pt.table(o.inms, readonly=False)
h5 = tables.open_file(o.inh5)
direction = o.dir
soltab_tec = h5.root.sol000.tec000
#soltab_csp = h5.root.sol000.scalarphase000

print "Applying dir %s" % h5.root.sol000.tec000.dir[direction]
#print "CSP HAVE A MINUS TO COMPENSATE NDPPP BUG"

sols_tec = soltab_tec.val
wgts_tec = soltab_tec.weight
#sols_csp = soltab_csp.val
#sols_csp = -1.*np.array(sols_csp)
#wgts_csp = soltab_csp.weight

times = soltab_tec.time
freqs = pt.table(sys.argv[1]+"/SPECTRAL_WINDOW",ack=False)[0]["CHAN_FREQ"]

for timestep, buf in enumerate(t.iter("TIME")):
    if timestep % 10 == 0: print "Timestep", timestep

    assert buf.getcell("TIME",0) == times[timestep]

    data = buf.getcol(o.incol)
    flag = buf.getcol("FLAG")

    for rownr, row in enumerate(buf):
        ant1 = row["ANTENNA1"]
        ant2 = row["ANTENNA2"]
        if wgts_tec[ant1,direction,0,timestep] == 0 or wgts_tec[ant2,direction,0,timestep] == 0 or \
           wgts_csp[ant1,direction,0,timestep] == 0 or wgts_csp[ant2,direction,0,timestep] == 0:
            flag[rownr,:,:] = True
            continue

        #g1 = sols_csp[ant1,direction,0,timestep] - sols_tec[ant1,direction,0,timestep] * 8.44797245e9 / freqs
        g1 = -1. * sols_tec[ant1,direction,0,timestep] * 8.44797245e9 / freqs
        g1 = cos(g1) + 1j*sin(g1)
        #g2 = sols_csp[ant2,direction,0,timestep] - sols_tec[ant2,direction,0,timestep] * 8.44797245e9 / freqs
        g2 = -1. * sols_tec[ant2,direction,0,timestep] * 8.44797245e9 / freqs
        g2 = cos(g2) + 1j*sin(g2)
        for pol in range(4):
            if corrupt:
                data[rownr,:,pol] *= ( g1 * np.conj(g2) )
            else:
                data[rownr,:,pol] /= ( g1 * np.conj(g2) )

    buf.putcol(o.outcol, data)
    buf.putcol("FLAG", flag) 

h5.close()
t.close()
