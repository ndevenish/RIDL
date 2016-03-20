# -*- coding: utf-8 -*-
from struct import unpack,calcsize
from classHolder import MapInfo
import os
import sys
import mmap
import numpy as np
from logFile import logFile

def readMap(dirIn,dirOut,pdbname,mapfilename,maptype,atom_indices,log):
    # read .map file of either density or atom-tagged type

    # define 'rho' electron map object
    rho = MapInfo()

    # open electron density .map file here (bmf for binary map file)
    # bmf = open(where+mapfilename,'rb')
    mapName = dirIn+mapfilename
    with open( mapName ) as f:
        bmf = mmap.mmap( f.fileno(), 0, prot = mmap.PROT_READ, flags = mmap.MAP_PRIVATE )
    
    # start adding header information into MapInfo class format. 
    # Note the unpacking of a struct for each byte, read as a long 'l'
    for n in ('nx','ny','nz'):
        rho.nxyz[n] = unpack('=l',bmf.read(4))[0]

    rho.type = unpack('=l',bmf.read(4))[0]

    for s in ('1','2','3'):
        rho.start[s] = unpack('=l',bmf.read(4))[0] 

    for g in ('1','2','3'):
        rho.gridsamp[g] = unpack('=l',bmf.read(4))[0] 

    for d in ('a','b','c','alpha','beta','gamma'):
        rho.celldims[d] = unpack('f',bmf.read(4))[0] # cell dims stored as float not long int

    for a in ('fast','med','slow'): 
        rho.axis[a] = unpack('=l',bmf.read(4))[0] 
        
    for d in ('min','max','mean'): 
        rho.density[d] = unpack('f',bmf.read(4))[0] 

    s = rho.getHeaderInfo()

    # write to log file if specified 
    if log != '':
        if os.path.exists(log.logFile):
            for l in s.split('\n'): log.writeToLog(l)
    else: print s

    # next find .map file size, to calculate the last nx*ny*nz bytes of 
    # file (corresponding to the position of the 3D electron density 
    # array). Note factor of 4 is included since 4-byte floats used for 
    # electron density array values.
    filesize = os.path.getsize(dirIn+mapfilename)
    densitystart = filesize - 4*(reduce(lambda x, y: x*y, rho.nxyz.values()))
    
    # next seek start of electron density data
    bmf.seek(densitystart,0)
    
    # if electron density written in shorts (I don't think it will be 
    # but best to have this case)
    if rho.type is 1:  
        print 'Untested .map type --> 1 (type 2 expected). Values read' 
        + 'as int16 ("i2?") - consult .map header in MAPDUMP(CCP4) to check'
  
        struct_fmt = '=i2'
        struct_len = calcsize(struct_fmt)
        density = []
       
        while True:
            data = bmf.read(struct_len)
            if not data: break
            s = unpack(struct_fmt,data)[0]
            density.append(s)    

    # if electron density written in floats (which is to be expected 
    # from FFT-CCP4 outputted .map file of electron density)
    if rho.type is 2:  
        struct_fmt = '=f4'
        struct_len = calcsize(struct_fmt)
        density = []
        appenddens = density.append
        
        if maptype in ('atom_map'):
            atom_indices = []
            appendindex = atom_indices.append
            counter = -1
            while True:
                data = bmf.read(struct_len)
                if not data: break
                s = unpack(struct_fmt,data)[0]
                counter += 1
                if int(s) == 0:
                    continue
                else:    
                    appenddens(s)
                    appendindex(counter)
            print '# voxels in total : {}'.format(counter+1)

        # efficient way to read through density map file using indices of atoms
        # from atom map file above
        elif maptype in ('density_map'):
            for i in range(0,len(atom_indices)):
                if i != 0:
                    bmf.read(struct_len*(atom_indices[i]-atom_indices[i-1] - 1))
                else:
                    bmf.read(struct_len*(atom_indices[0]))
                    
                data = bmf.read(struct_len)
                s = unpack(struct_fmt,data)[0]
                appenddens(s)

            # check that resulting list of same length as atom_indices
            if len(density) != len(atom_indices):
                print 'Error in processing of density map using atom-tagged map'
                sys.exit()           
        else:
            print 'Unknown map type --> terminating script'
            sys.exit()
    bmf.close()
    
    # as a check that file has been read correctly, check that the min 
    # and max electron density stated in .map file header correspond to 
    # calculated min and max here
    # Note for the case of atom map, the min voxel val will be 0 (no atom present)
    # --> since these voxels are removed during the filtering of the map, only 
    # the map value is tested.
    # For density map, cannot currently perform a check, since there is no 
    # guarantee that the max and min voxel values may be non atom voxels and
    # thus removed
    if maptype in ('atom_map'):      
        if max(density) == rho.density['max']:
            print 'calculated max voxel value match value stated in file header'
        else:
            print 'calculated max voxel value:{} does NOT match value stated in file header:{}'.format(max(density),rho.density['max'])
            sys.exit()
    
    # if each voxel value is an atom number, then want to convert to integer
    if maptype in ('atom_map'):
        density_final = [int(dens)/100 for dens in density]
    elif maptype in ('density_map'):
        density_final = density
    else:
        print 'Unknown map type --> terminating script'
        sys.exit()

    rho.vxls_val = density_final

    if maptype in ('atom_map'):
        return rho,atom_indices
    else:
        return rho

###----------------###----------------###----------------###----------------###
###############################################################################
def densmap2class_readheader(mapfilename):
    
    # define 'rho' electron map object
    rho = electron_map_info()

    # open electron density .map file here 
    binarymapfile = open(mapfilename,'rb')
    
    # start adding header information into electron_map_info class format. 
    # Note the unpacking of a struct for each byte, read as a long 'l'
    # rho.nx = struct.unpack('=l',binarymapfile.read(4))[0]
    rho.ny = struct.unpack('=l',binarymapfile.read(4))[0]
    rho.nz = struct.unpack('=l',binarymapfile.read(4))[0]
    rho.type = struct.unpack('=l',binarymapfile.read(4))[0]
    print 'Num. Col, Row, Sec: '
    print '%s %s %s' %(rho.nx,rho.ny,rho.nz)
    
    # currently can't handle type 1 maps:
    if rho.type == 1:
        print 'Map type 1 found... can only handle type 2'
        print '---> terminating script...'
        sys.exit()
        
    rho.start1 = struct.unpack('=l',binarymapfile.read(4))[0] 
    rho.start2 = struct.unpack('=l',binarymapfile.read(4))[0] 
    rho.start3 = struct.unpack('=l',binarymapfile.read(4))[0] 
    print 'Start positions: '
    print '%s %s %s' %(rho.start1,rho.start2,rho.start3)

    rho.gridsamp1 = struct.unpack('=l',binarymapfile.read(4))[0] 
    rho.gridsamp2 = struct.unpack('=l',binarymapfile.read(4))[0] 
    rho.gridsamp3 = struct.unpack('=l',binarymapfile.read(4))[0]
    print 'Grid sampling:'
    print '%s %s %s' %(rho.gridsamp1,rho.gridsamp2,rho.gridsamp3)

    # for cell dimensions, stored in header file as float not long 
    # integer so must account for this
    rho.celldim_a = struct.unpack('f',binarymapfile.read(4))[0]
    rho.celldim_b = struct.unpack('f',binarymapfile.read(4))[0]
    rho.celldim_c = struct.unpack('f',binarymapfile.read(4))[0]
    rho.celldim_alpha = struct.unpack('f',binarymapfile.read(4))[0]
    rho.celldim_beta = struct.unpack('f',binarymapfile.read(4))[0]
    rho.celldim_gamma = struct.unpack('f',binarymapfile.read(4))[0]
    print 'Cell dimensions:'
    print '%s %s %s' %(rho.celldim_a,rho.celldim_b,rho.celldim_c)
    print '%s %s %s' %(rho.celldim_alpha,rho.celldim_beta,rho.celldim_gamma)


    rho.fast_axis = struct.unpack('=l',binarymapfile.read(4))[0] 
    rho.med_axis = struct.unpack('=l',binarymapfile.read(4))[0] 
    rho.slow_axis = struct.unpack('=l',binarymapfile.read(4))[0] 
    print 'Fast,med,slow axes: '
    print '%s %s %s' %(rho.fast_axis,rho.med_axis,rho.slow_axis)

    rho.mindensity = struct.unpack('f',binarymapfile.read(4))[0] 
    rho.maxdensity = struct.unpack('f',binarymapfile.read(4))[0] 
    rho.meandensity = struct.unpack('f',binarymapfile.read(4))[0]
    print 'Density values: '
    print '%s %s %s' %(rho.mindensity,rho.maxdensity,rho.meandensity)

    # next find .map file size, to calculate the last nx*ny*nz bytes of 
    # file (corresponding to the position of the 3D electron density 
    # array). Note factor of 4 is included since 4-byte floats used for 
    # electron density array values.
    filesize = os.path.getsize(mapfilename)
    densitystart = filesize - 4*(rho.nx*rho.ny*rho.nz)
    
    return rho, densitystart    
    
###----------------###----------------###----------------###----------------###
###############################################################################
#todo: need to check both file sizes are same!
def densmap2class_readvoxels(densmapfilename,densitystart):
        
    # open electron density 'density' .map file here 
    binarymapfile_dens = open(densmapfilename,'rb')    
    
    # next seek start of electron density data
    binarymapfile_dens.seek(densitystart,0)

    # if electron density written in floats (which is to be expected 
    # from FFT-CCP4 outputted .map file of electron density). Type 2 
    # maps only as specified in map file header
    struct_fmt = '=f4'
    struct_len = struct.calcsize(struct_fmt)
            
    vxl_list = []
    # create list of voxel density values
    while True:
        data_dens = binarymapfile_dens.read(struct_len)

        if not data_dens: break
        s_dens = struct.unpack(struct_fmt,data_dens)[0]
        
        vxl_list.append(s_dens)        
    
    binarymapfile_dens.close()
    
    return vxl_list    
    
###----------------###----------------###----------------###----------------###
###############################################################################
def densmap2class_consistencycheck(vxl_list,
                                   atom_maxdensity,atom_mindensity,
                                   dens_maxdensity,dens_mindensity):                                
    # as a check that file has been read correctly, check that the min 
    # and max electron density stated in .map file header correspond to 
    # calculated min and max here
    atm_vals = [vxl.atmnum for vxl in vxl_list]
                           
    if max(atm_vals) == atom_maxdensity and min(atm_vals) == atom_mindensity:
        print 'calculated max and min density match values stated in'\
        + 'atom map file header'
    else:
        print 'calculated max and min density do NOT match values stated'\
        + 'in atom map file header'
        sys.exit()
    atm_vals = []
    
    dens_vals = [vxl.density for vxl in vxl_list] 
    if max(dens_vals) == dens_maxdensity and min(dens_vals) == dens_mindensity:
        print 'calculated max and min density match values stated in'\
        + 'density map file header'
    else:
        print 'calculated max and min density do NOT match values stated'\
        + 'in density map file header'
        sys.exit()
    dens_vals = []
    
    print '---> success!'
                    
###----------------###----------------###----------------###----------------### 
    
    


###----------------###----------------###----------------###----------------###
###############################################################################
def densmap2class_plot(voxel_list):
    
    # the following is designed to plot a histogram plot of the distibution 
    # of density values in the collection of voxels in voxel_list:
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    sns.set_palette("deep", desat=.6)
    sns.set_context(rc={"figure.figsize": (8, 4)})
    np.random.seed(9221999)
    
    # find densities from voxels
    density = [voxel.density for voxel in voxel_list]
        
    # plot a histogram of 'density' list containing all densities above:     
    plt.hist(density, 100, histtype="stepfilled", alpha=.7)
###############################################################################
###----------------###----------------###----------------###----------------###
