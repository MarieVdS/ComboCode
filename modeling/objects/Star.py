# -*- coding: utf-8 -*-

"""
Module including functions for stellar parameters, and the STAR class and 
its methods and attributes.

Author: R. Lombaert

"""

import types
from glob import glob
import os
from scipy import pi, log, sqrt
from scipy import array, exp, zeros
from scipy import integrate, linspace
from scipy import argmin,argmax
import operator
from numpy import savetxt

from cc.data import Data
from cc.tools.io import Database
from cc.tools.io import DataIO, Atmosphere
from cc.tools.numerical import Interpol
from cc.modeling.objects import Molecule
from cc.modeling.objects import Transition
from cc.modeling.tools import ColumnDensity
from cc.modeling.codes import MCMax


def getStar(star_grid,modelid,idtype='GASTRONOOM'):
    
    '''
    Grab a Star() object from a list of such objects, given a model id.
    
    If no modelid is found, an empty list is returned. If Star() objects are 
    found (even only one), a list of them is returned.
    
    Based on the cooling modelid.
    
    @param star_grid: the Star() objects
    @type star_grid: list[Star()]
    @param modelid: the given modelid for which the selection is made.
    @type modelid: string
    
    @keyword idtype: The type of model id
                    
                     (default: GASTRONOOM)    
    @type idtype: string

    @return: The models matching the modelid
    @rtype: list[Star()]
    
    '''
    
    modelid, idtype = str(modelid), str(idtype)
    return [s for s in star_grid if s['LAST_%s_MODEL'%idtype] == modelid]
    
    
    
def powerRfromT(T,T_STAR,R_STAR=1.0,power=0.5):
    
    """
    Inverse of a T-power law.
    
    Returns the radius in the same units as R_STAR, if given.
    
    If not given, R is given in stellar radii.
       
    @param T: temperature for which radius is calculated assuming a power law:
              T = T_STAR * (R_STAR/R)**(power)
    @type T: float or array
    @param T_STAR: stellar effective temperature
    @type T_STAR: float or array
    
    @keyword R_STAR: stellar radius, default for a returned value in stellar
                     radii
                     
                     (default: 1.0)
    @type R_STAR: floar or array
    @keyword power: power in the power law, default is given by goldreich 
                    & Scoville 1976, approximation gas kinetic temperature in 
                    optically thin medium, in the inner CSE
                    
                    (default: 0.5)
    @type power: float or array
    
    @return: radius at temperature T according to the power law, in the same 
             units as R_STAR
    @rtype: float or array
    
    """
    
    return (float(T_STAR)/float(T))**(1/float(power))*float(R_STAR)



def makeStars(models,id_type,path,code,\
              path_combocode=os.path.join(os.path.expanduser('~'),\
                                          'ComboCode')):
    
    '''
    Make a list of dummy Star() objects.

    @param models: model_ids for the new models
    @type models: list[string]
    @param id_type: The type of id (PACS, GASTRONOOM, MCMAX)
    @type id_type: string
    @param path: Output folder in the code's home folder
    @type path: string
    @param code: The code (which is not necessarily equal to id_type, such as 
                 for id_type == PACS)
    @type code: string
    @param path_combocode: CC home folder
                           
                           (default: '~/ComboCode/')
    @type path_combocode: string
    
    @return: The parameter sets, mostly still empty!
    @rtype: list[Star()]
    
    '''
    
    extra_pars = dict([('path_'+code.lower(),path)])
    star_grid = [Star(example_star={'LAST_%s_MODEL'%id_type.upper():model},\
                      path_combocode=path_combocode,**extra_pars) 
                 for model in models]
    return star_grid
      

    
class Star(dict):
    
    """
    Star class maintains information about a stellar model and its properties.

    Inherits from dict.
    
    """



    def __init__(self,path_gastronoom=None,path_mcmax=None,extra_input=None,\
                 path_combocode=os.path.join(os.path.expanduser('~'),\
                                             'ComboCode'),
                 example_star=dict()):
        
        """
        Initiate an instance of the STAR class.
        
        @keyword path_gastronoom: path in ~/GASTRoNOoM/ for modeling out/input
                                  
                                  (default: None)
        @type path_gastronoom: string
        @keyword path_mcmax: the folder in ~/MCMax/ for modeling out/input
        
                             (default: None)
        @type path_mcmax: string
        @keyword path_combocode: full path to ComboCode
        
                                 (default: '/home/robinl/ComboCode')
        @type path_combocode: string
        @keyword example_star: if not None the STAR object is exact duplicate 
                               of example_star. Can be a normal dictionary as 
                               well. Paths are not copied and need to be given 
                               explicitly.
                                    
                               (default: None)
        @type example_star: dict or Star()                                  
        @keyword extra_input: extra input that you wish to add to the dict
        
                              (default: None)
        @type extra_input: dict or Star()
        
        @return: STAR object in the shape of a dictionary which includes all 
                 stellar data available, if None are passed for both options it
                 is an empty dictionary; if an example star is passed it has a 
                 dict that is an exact duplicate of the example star's dict
        @rtype: Star()
        
        """    
            
        super(Star, self).__init__(example_star)
        if extra_input <> None: self.update(extra_input)
        self.Rsun = 6.95508e10         #in cm  Harmanec & Prsa 2011
        self.Msun = 1.98547e33      #in g   Harmanec & Prsa 2011
        self.Tsun = 5779.5747            #in K   Harmanec & Psra 2011
        self.Lsun = 3.846e33           #in erg/s
        self.year = 31557600.            #julian year in seconds
        self.au = 149598.0e8             #in cm
        self.c = 2.99792458e10          #in cm/s
        self.h = 6.62606957e-27         #in erg*s, Planck constant
        self.k = 1.3806488e-16          #in erg/K, Boltzmann constant
        self.sigma = 5.67040040e-5         #in erg/cm^2/s/K^4   Harmanec & Psra 2011
        self.pc = 3.08568025e16         #in cm
        self.mh = 1.672661e-24           #in g, mass hydrogen atom
        self.G = 6.674e-8               # in cm^3 g^-1 s^-2
        
        self.path_combocode = path_combocode
        dust_path = os.path.join(self.path_combocode,'Data')
        self.species_list = DataIO.getInputData(path=dust_path,\
                                         keyword='SPECIES_SHORT',\
                                         filename='Dust.dat')
        self.path_gastronoom = path_gastronoom        
        self.path_mcmax = path_mcmax
        self.convertRadialUnit()
        


    def __getitem__(self,key):

        """
        Overriding the standard dictionary __getitem__ method.
        
        @param key: Star()[key] where key is a string for which a corresponding
                    dictionary value is searched. If the key is not present in 
                    the dictionary, an attempt is made to calculate it from 
                    already present data; if it fails a KeyError is still 
                    raised. 
        @type key: string            
        
        @return: The value from the Star() dict for key
        @rtype: any
        
        """
        
        if not self.has_key(key):
            self.missingInput(key)
            return super(Star,self).__getitem__(key)
        elif super(Star,self).__getitem__(key) == '%':
            del self[key]
            self.missingInput(key)
            value = super(Star,self).__getitem__(key)
            self[key] = '%'
            return value 
        else:
            return super(Star,self).__getitem__(key)



    def __cmp__(self,star):
        
        """
        Overriding the standard dictionary __cmp__ method.
        
        A parameter set (dictionary of any type) is compared with this instance
        of Star(). 
        
        An attempt is made to create keys with values in each dict, if the 
        other has keys that are not present in the first. If this fails, False
        is returned.     
        
        @param star: A different parameter set. 
        @type star: dict or Star()             
        
        @return: The comparison between this object and star
        @rtype: bool
        
        """
        
        try:
            all_keys = set(self.keys() + star.keys())
            for k in all_keys:
                if not self.has_key(): 
                    self[k]
                if not star.has_key():
                    star[k]
            #if len(self) > len(star):
                #changed_keys = [star[k] 
                                #for k in self.keys() 
                                #if not star.has_key(k)]
                #print "Initialized keys in STAR2 from STAR1 == STAR2 comparison : \n" + str(changed_keys)
            #if len(self) < len(star):
                #changed_keys = [self[k] for k in star.keys() if not self.has_key(k)]
                #print "Initialized keys in STAR1 from STAR1 == STAR2 comparison : \n" + str(changed_keys)
        except KeyError:
            print 'Comparison error: Either STAR1 or STAR2 contains a key ' + \
                  'that cannot be initialized for the other.'
            print 'Both STAR instances are considered to be unequal.'
        finally:
            if isinstance(star, super(Star)):
                return cmp(super(Star,self), super(Star,star))
            else:
                return cmp(super(Star,self), star)                 

                      
                            
    def addCoolingPars(self):
        
        '''
        Add Star parameters from the cooling database. 
        
        Any existing parameters are overwritten!
        
        '''
        
        cooling_path = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                    self.path_gastronoom,\
                                    'GASTRoNOoM_cooling_models.db')
        cool_db = Database.Database(cooling_path)
        cooling_dict = cool_db[self['LAST_GASTRONOOM_MODEL']].copy()
        cooling_keys = ['T_STAR','R_STAR','TEMDUST_FILENAME','MDOT_GAS']
        for k in cooling_dict.keys():
            if k not in cooling_keys: del cooling_dict[k]            
        cooling_dict['R_STAR'] = float(cooling_dict['R_STAR'])/self.Rsun
        self.update(cooling_dict)



    def writeDensity(self):
        
        '''
        Write dust mass density and n(h2) profile (in Rstar).
        
        Only if MCMax or GASTRoNOoM model_id is available! 
        
        '''
        
        if self['LAST_MCMAX_MODEL']:    
            filename = os.path.join(os.path.expanduser('~'),'MCMax',\
                                    self.path_mcmax,'models',\
                                    self['LAST_MCMAX_MODEL'],'denstemp.dat')
            incr = int(self['NTHETA'])*int(self['NRAD'])
            dens = DataIO.getMCMaxOutput(incr=incr,filename=filename,\
                                        keyword='DENSITY')
            rad = array(DataIO.getMCMaxOutput(incr=int(self['NRAD']),\
                                              filename=filename))\
                        /self.Rsun/self['R_STAR']
            dens = Data.reduceArray(dens,self['NTHETA'])
            DataIO.writeCols(os.path.join(os.path.expanduser('~'),'MCMax',\
                                        self.path_mcmax,'models',\
                                        self['LAST_MCMAX_MODEL'],\
                                        'density_profile_%s.dat'%\
                                        self['LAST_MCMAX_MODEL']),[rad,dens])
        if self['LAST_GASTRONOOM_MODEL']:
            filename = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                    self.path_gastronoom,'models',\
                                    self['LAST_GASTRONOOM_MODEL'],\
                                    'coolfgr_all%s.dat'\
                                    %self['LAST_GASTRONOOM_MODEL'])
            dens = DataIO.getGastronoomOutput(filename,keyword='N(H2)')  
            rad = array(DataIO.getGastronoomOutput(filename,keyword='Radius'))\
                        /self.Rsun/self['R_STAR']
            DataIO.writeCols(os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                        self.path_gastronoom,'models',\
                                        self['LAST_GASTRONOOM_MODEL'],\
                                        'nh2_density_profile_%s.dat'%\
                                        self['LAST_GASTRONOOM_MODEL']),\
                             [rad,dens])


    def readKappas(self):
        
        '''
        Read the kappas.dat file of an MCMax model.
    
        '''
        
        opas = DataIO.readCols(os.path.join(os.path.expanduser('~'),'MCMax',\
                                            self.path_mcmax,'models',\
                                            self['LAST_MCMAX_MODEL'],\
                                            'kappas.dat'))
        return opas.pop(0),opas
                            


    def convertRadialUnit(self):
        
        '''
        Convert any radial unit for shell parameters to R_STAR.
        
        '''
        
        if self['R_SHELL_UNIT'] != 'R_STAR':
            shell_units = ['CM','M','KM','AU']
            unit_index = shell_units.index(self['R_SHELL_UNIT'].upper())
            unit_conversion = [1./(self.Rsun*self['R_STAR']),\
                               10.**2/(self.Rsun*self['R_STAR']),\
                               10.**5/(self.Rsun*self['R_STAR']),\
                               self.au/(self.Rsun*self['R_STAR'])]
            for par in ['R_INNER_GAS','R_INNER_DUST','R_OUTER_GAS',\
                        'R_OUTER_DUST'] \
                    + ['R_MAX_' + species for species in self.species_list] \
                    + ['R_MIN_' + species for species in self.species_list]:
                if self.has_key(par):
                    self[par] = self[par]*unit_conversion[unit_index]
        else:
            pass
                                             

    
    def removeMutableMCMax(self,mutable,var_pars):
        
        """
        Remove mutable parameters after an MCMax run.
    
        @param mutable: mutable keywords
        @type mutable: list[string]
        @param var_pars: parameters that are varied during gridding, these will
                         not be removed and are kept constant throughout the 
                         iteration
        @type var_pars: list[string]
        
        """
        
        #- remove keys which should be changed by output of new mcmax model, 
        #- but only the mutable input!!! 
        for key in self.keys():
            if key in mutable \
                       + ['R_MAX_' + species for species in self['DUST_LIST']]\
                       + ['T_DES_' + species for species in self['DUST_LIST']]\
                       + ['R_DES_' + species for species in self['DUST_LIST']]\
                    and key not in var_pars:
                del self[key]
        
        #- Check the effective destruction temperature of every species, and 
        #- see if max and min T's are as requested.
        self.checkT()
        
        #- No point in keeping zeroes around for T_DES or T_MIN
        for species in self['DUST_LIST']:
            for par in ('T_DES_' + species, 'T_MIN_' + species):
                if self.has_key(par):
                    if not float(self[par]):
                        del self[par]
                    
  

    def removeMutableGastronoom(self,mutable,var_pars):
        
        """
        Remove mutable parameters after a GASTRoNOoM run.
    
        @param mutable: mutable parameters
        @type mutable: list[string]
        @param var_pars: parameters that are varied during gridding, these will
                         not be removed and are kept constant throughout the 
                         iteration
        @type var_pars: list[string]
        
        """
        
        for key in self.keys():
            if key in mutable and key not in var_pars:
                del self[key]
                    
 
    
    def updateMolecules(self,parlist):
        
        '''
        Update variable information in the molecule instances of this star.
        
        @param parlist: parameters that have to be updated.
        @type parlist: list[string]
        
        '''
        
        for molec in self['GAS_LIST']:
            molec.updateParameters(pardict=dict([(k,self[k]) 
                                                 for k in parlist]))
    


    def normalizeDustAbundances(self):
        
        """
        Normalize the dust abundances such that they add up to a total of 1.
        
        If the MRN_DUST keyword for MCMax is nonzero, all nonzero abundances 
        are set to 1. The abundance given in the inputfile does not matter in 
        this case.
        
        """
        
        abun_ori = [self['A_%s'%sp] for sp in self['DUST_LIST']]
        self['A_DUST_ORIGINAL'] = abun_ori
        if int(self['MRN_DUST']): 
            self['A_NO_NORM'] = 1
            print 'WARNING! Take care when extracting output in MCMax using '+\
                  'these scripts, if MRN_DUST == 1! Especially if some ' + \
                  'abundances are set manually and some according to MRN: ' + \
                  'these are not normalized to 1, since this depends on the '+\
                  'MRN distributed dust species.'
            for sp in self['DUST_LIST']:
                mrn_count = 0
                if self['MRN_NGRAINS'] != len(self['DUST_LIST']) \
                        and self.has_key('RGRAIN_%s'%sp):
                    self.__setitem__('A_%s'%sp,2)
                    mrn_count += 1
                elif self['MRN_NGRAINS'] == len(self['DUST_LIST']):
                    self.__setitem__('A_%s'%sp,2)        
                    mrn_count += 1
                if mrn_count != self['MRN_NGRAINS']:
                    raise IOError('MRN_NGRAINS not equal to amount of RGRAIN_sp keywords.')
        total = sum(abun_ori)
        if not int(self['A_NO_NORM']) and '%.3f'%total != '1.000':
            print 'Normalizing dust abundances to 1, from a total of %f.'%total
            abun_new = [a/total for a in abun_ori]
            print ', '.join(['%.2f'%a for a in abun_ori]), ' is changed to ', \
                  ', '.join(['%.2f'%a for a in abun_new]), ' for ', \
                  ', '.join(self['DUST_LIST']), '.'
            [self.__setitem__('A_%s'%sp,a) for a,sp in zip(abun_new,\
                                                           self['DUST_LIST'])]



    def calcA_NO_NORM(self):
        
        """
        Set the default value of A_NO_NORM to 0.
        
        """
        
        if not self.has_key('A_NO_NORM'):
            self['A_NO_NORM'] = 0
        else:
            pass
    
        

    def __addLineList(self):
        
        """ 
        Take molecular transitions from a line list and wavelength range.
        
        Based on the GASTRoNOoM radiat and indices data files. See Molecule.py
        for more info.
        
        """
        
        gas_list = []
        if type(self['LL_TELESCOPE']) is types.StringType:
            self['LL_TELESCOPE'] = [self['LL_TELESCOPE']]
        if not self['LL_NO_VIB']:
            self['LL_NO_VIB'] = []
        elif type(self['LL_NO_VIB']) is types.StringType:
            self['LL_NO_VIB'] = [self['LL_NO_VIB']]
        for molec in self['GAS_LIST']:
            for telescope in self['LL_TELESCOPE']:
                nl = Transition.makeTransitionsFromRadiat(molec=molec,\
                            telescope=telescope,ll_min=self['LL_MIN'],\
                            ll_max=self['LL_MAX'],ll_unit=self['LL_UNIT'],\
                            n_quad=self['N_QUAD'],offset=self['LL_OFFSET'],\
                            use_maser_in_sphinx=self['USE_MASER_IN_SPHINX'],\
                            path_gastronoom=self.path_gastronoom,\
                            no_vib=molec.molecule in self['LL_NO_VIB'])
            gas_list.extend(nl)
        self['GAS_LINES'].extend(gas_list)


    
    def calcLL_NO_VIB(self):
        
        """
        Set the default value of LL_NO_VIB (remove vibrational states from the
        calculation and plots) to zero.        
        
        """
        
        if not self.has_key('LL_NO_VIB'):
            self['LL_NO_VIB'] = []
        else:
            pass
    
    
        
    def calcN_QUAD(self):
        
        """
        Set the default value of N_QUAD to 100. 
        
        Only used when auto selecting transition based on a wavelength range.
        
        """
        
        if not self.has_key('N_QUAD'):
            self['N_QUAD'] = 100
        else:
            pass
    
    
    
    def calcLL_OFFSET(self):
        
        """
        Set the default value of LL_OFFSET to 0.0. 
        
        Only used when auto selecting transitions based on a wavelength range.
        
        """
        
        if not self.has_key('LL_OFFSET'):
            self['LL_OFFSET'] = 0.0
        else:
            pass
    
        

    def checkT(self):
        
        """
        Search input list for minimum temperature.
    
        Method prints the actual minimum T for which the model was calculated.
        
        Note that the density drops to zero gradually and that the criterium
        has to be sudden change of slope. Check criterium if the printed T is 
        not good enough as determination of max radius IS correct.
        
        """
        
        coldens = ColumnDensity.ColumnDensity(self)
        self.calcT_INNER_DUST()
        for index,species in enumerate(self['DUST_LIST']):
            self['T_DES_%s'%species] = coldens.t_des[species]
            self['R_DES_%s'%species] = coldens.r_des[species]\
                                        /self.Rsun/self['R_STAR']
            print 'The EFFECTIVE maximum temperature for species %s '%species+\
                  'is %.2f K, at radius %.2f R_STAR.'\
                  %(self['T_DES_%s'%species],self['R_DES_%s'%species])
        
        species_list_min = [species 
                            for species in self.species_list 
                            if self.has_key('T_MIN_%s'%species) \
                                or self.has_key('R_MAX_%s'%species)]
        for species in species_list_min:
            print 'The EFFECTIVE minimum temperature for species'+\
                  ' %s is %.2f K at maximum radius %.2f R_STAR.'\
                  %(species,coldens.t_min[species],\
                    coldens.r_max[species]/self.Rsun/self['R_STAR'])
            if self.has_key('T_MIN_%s'%species):
                print 'The REQUESTED minimum temperature for species '+\
                      '%s is %.2f K.'%(species,self['T_MIN_%s'%species])
            if self.has_key('R_MAX_%s'%species):
                print 'The REQUESTED maximum radius for species'+\
                      '%s is %.2f R_STAR.'%(species,self['R_MAX_%s'%species])
            print 'The EFFECTIVE outer radius of the shell is %.2f R_STAR.'\
                  %(coldens.r_outer/self.Rsun/self['R_STAR'])
            print 'Note that if R_MAX is ~ the effective outer radius, the ' +\
                  'requested minimum temperature may not be reached.'
        return
    

    
    def getFullNameMolecule(self,short_name):
        
        '''
        Get the full name of a molecule, based on it's short name, 
        if it is present in the GAS_LIST.
                
        @return: Name the name. None if not available.
        @rtype: string
        
        '''
        
        molecule = [molec.molecule_full 
                    for molec in self['GAS_LIST'] 
                    if molec.molecule == short_name]
        if not molecule:
            return None
        #- Return first only, if multiple there's multiple requested molecules 
        #- of the same type (fi different abundance)
        else:
            return molecule[0]     



    def getShortNameMolecule(self,full_name):
        
        '''
        Get the short name of a molecule, based on it's full name, 
        if it is present in the GAS_LIST.
        
        @param full_name: The full name of a molecule from Molecule.dat
        @type full_name: string
        
        @return: None if not available, otherwise the short hand name.
        @rtype: string
        
        '''
        
        molecule = [molec.molecule 
                    for molec in self['GAS_LIST'] 
                    if molec.molecule_full == full_name]
        if not molecule:
            return None
        #- Return first only, if multiple there's multiple requested molecules 
        #- of the same type (fi different abundance)
        else:
            return molecule[0]     
      

     
    def getMolecule(self,molec_name):
        
        '''
        Get a Molecule() object based on the molecule name. 
        
        A Star() object always has only one version of one molecule.
        
        @param molec_name: short name of the molecule
        @type molec_name: string
        
        @return: The molecule
        @rtype: Molecule()
        
        '''
        
        try:
            return [molec 
                    for molec in self['GAS_LIST'] 
                    if molec.molecule == molec_name][0]
        except IndexError:
            return None
    
    
    
    def getTransition(self,sample):
        
        '''
        Return a Transition() object that has the same parameters as sample. 
        
        The actual model ids are not included in this comparison! 
        
        None is returned if no match is found. 
        
        @param sample: A sample transition to be cross referenced with the 
                       transitions in this Star() object. If a match is found, 
                       it is returned.
        @type sample: Transition()
        @return: If a match is found, this transition is returned.
        @rtype: Transition()
        
        '''
         
        i = 0
        while i < len(self['GAS_LINES']) and sample != self['GAS_LINES'][i]:
            i += 1
        if i == len(self['GAS_LINES']):
            return None
        else:
            return self['GAS_LINES'][i]
        
    
     
    def getTransList(self,**kwargs):
        
        '''
        Return a list of (transmodelid, molecmodelid, dictionary) for every 
        transition in the Star model.
        
        '''
        
        trl = Transition.extractTransFromStars([self],**kwargs)
        trl_info = [(trans.getModelId(),\
                     trans.molecule.getModelId(),\
                     trans.makeDict())
                    for trans in trl]
        return trl_info



    def getTransitions(self,molec):
        
        '''
        Return a list of all transitions associated with a single molecule.
        
        @param molec: the shorthand notation of the molecule
        @type molec: string
        
        @return: All transitions for this molecule
        @rtype: list[Transition()]
        
        '''
        
        return [trans 
                for trans in self['GAS_LINES'] 
                if trans.molecule.molecule==molec]



    def getDustTemperature(self,add_key=0):
         
        '''
        Return the dust temperature profile from the file made for GASTRoNOoM.
        
        This is the total dust temperature without separate components for the 
        different dust species.
        
        @keyword add_key: Add a key for a legend to the ouput as third tuple
                          element.
                          
                          (default: 0)
        @type add_key: bool
        
        @return: Two lists including the radial grid (in cm) and the
                 temperature (K) as well as a key.
        @rtype: (list,list,string)
        
        '''
        
        
        try:
            data = DataIO.readCols(self['DUST_TEMPERATURE_FILENAME'])
            rad = data[0]*self['R_STAR']*self.Rsun
            temp = data[1]
        except IOError:
            rad = []
            temp = []
        if add_key:
            key = '$T_{\mathrm{d, avg}}$'
                    #self['LAST_MCMAX_MODEL'].replace('_','\_')
            return rad,temp,key
        else: 
            return rad,temp
         
         
    def getDustTemperaturePowerLaw(self,power,add_key=0):
        
        '''
        Return a dust temperature power law of the form as suggested by 
        observational evidence. 
        
        See Thesis p32, where power is p in 
        T(r) = T_eff*(2*r/R_STAR)**(-p)
        
        @param power: The power in the power law T(r) given above.
        @type power: float
        
        @keyword add_key: Add a key for a legend to the ouput as third tuple
                          element.
                          
                          (default: 0)
        @type add_key: bool

        @return: Two lists including the radial grid (in cm) and the temperature
                    (K) as well as a key.
        @rtype: (list,list,string)
        
        '''
        
        power = float(power)
        filename = os.path.join(os.path.expanduser('~'),'MCMax',\
                                self.path_mcmax,'models',\
                                self['LAST_MCMAX_MODEL'],'denstemp.dat')
        try:
            rad = array(DataIO.getMCMaxOutput(filename=filename,\
                                              incr=int(self['NRAD'])))
            temp = self['T_STAR']*(2*rad/self.Rsun/self['R_STAR'])**(-power)
        except IOError:
            rad = []
            temp = []
            #key = '$T_\mathrm{d} = %i\ K*(2r/R_*)^{-%.1f}$'\
            #     %(power,int(self['T_STAR']))
            
        if add_key:
            key = 'Power law ($p = %.2f$) for $T_\mathrm{eff} = %i\ K$'\
                  %(power,int(self['T_STAR']))
            return rad, temp, key
        else: 
            return rad,temp
    
    
    def getDustTemperatureSpecies(self,add_key=0):
         
        ''' 
        Return the temperature profiles of all species included in Star object.
        
        This information is taken from the denstempP## files for each species.
        
        @keyword add_key: Add a key for a legend to the ouput as third tuple
                          element.
                          
                          (default: 0)
        @type add_key: bool

        
        @return: Three lists: one for all radial grids (lists in cm) of the 
                 species, one for all temperature profiles (lists in K) and 
                 one for all keys (strings)
        @rtype: (list(lists),list(lists),list(strings))
        
        '''
        
        fp = os.path.join(os.path.expanduser('~'),'MCMax',self.path_mcmax,\
                          'models',self['LAST_MCMAX_MODEL'])
        radii = [array(DataIO.getMCMaxOutput(incr=int(self['NRAD']),\
                                             filename=os.path.join(fp,\
                                                   'denstempP%.2i.dat'%(i+1))))
                 for i in xrange(len(self['DUST_LIST']))]
        incr = int(self['NRAD'])*int(self['NTHETA'])
        temps = [DataIO.getMCMaxOutput(incr=incr,keyword='TEMPERATURE',\
                                       filename=os.path.join(fp,\
                                                    'denstempP%.2i.dat'%(i+1)))
                 for i in xrange(len(self['DUST_LIST']))]      
        temps = [Data.reduceArray(t,self['NTHETA'])
                 for t in temps]
        radii = [r[t<=self['T_DES_%s'%sp]] 
                 for r,t,sp in zip(radii,temps,self['DUST_LIST'])]
        temps = [t[t<=self['T_DES_%s'%sp]] 
                 for t,sp in zip(temps,self['DUST_LIST'])]
        if add_key:
            return radii,temps,list(self['DUST_LIST'])
        else: 
            return radii,temps
    
    
    def getGasVelocity(self):
        
        '''
        Give the velocity profile of the gas read from a GASTRoNOoM model.
        
        @return: The radius (in cm) and velocity (in cm/s) profile
        @rtype: (array,array)
        
        '''
                
        fgr_file = self.getCoolFn('fgr_all')
        rad = DataIO.getGastronoomOutput(filename=fgr_file,keyword='RADIUS',\
                                         return_array=1)
        vel = DataIO.getGastronoomOutput(filename=fgr_file,keyword='VEL',\
                                         return_array=1)
        return (rad,vel)
        
    
    
    def getCoolFn(self,ftype,mstr=''):
        
        '''
        Return the cooling output filename.
        
        You can define the type of cooling file you want, as well as an 
        additional identification string for the molecule/sampling.
        
        @param ftype: The cooling output file type. Either '1', '2', '3', 'fgr'
                      'fgr_all', or 'rate'.
        @type ftype: str
        
        @keyword mstr: The additional identication string. Not applicable to 
                       'fgr' or 'fgr_all'. Can be any molecule, or 'sampling'.
                       File must exist to be used further!
                       
                       (default: '')
        @type mstr: str
        
        @return: The filename of the requested cooling output file.
        @rtype: str
        
        '''
        
        mid = self['LAST_GASTRONOOM_MODEL']
        ftype = str(ftype)
        if ftype == 'fgr' or ftype == 'fgr_all':
            mstr = ''
        if mstr:
            mstr = '_' + mstr
        fn = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                          self.path_gastronoom,'models',mid,\
                          'cool%s%s%s.dat'%(ftype,mid,mstr))
        return fn
        
        

    def calcTLR(self):  
        
        """
        Stefan-Boltzmann's law.
            
        Star() object needs to have at least 2 out of 3 parameters (T,L,R), 
        with in L and R in solar values and T in K.
    
        The one missing parameter is calculated. 
    
        This method does nothing if all three are present.
        
        """
        
        if not self.has_key('T_STAR'):
            self['T_STAR']=(float(self['L_STAR'])/float(self['R_STAR'])**2.)\
                                **(1/4.)*self.Tsun
        elif not self.has_key('L_STAR'):
            self['L_STAR']=(float(self['R_STAR']))**2.*\
                                (float(self['T_STAR'])/self.Tsun)**4.
        elif not self.has_key('R_STAR'):
            self['R_STAR']=(float(self['L_STAR'])*\
                                (self.Tsun/float(self['T_STAR']))**4)**(1/2.)
        else:
            pass 



    def calcLL_GAS_LIST(self):
        
        '''
        Define Molecule() objects for the molecules requested in the LineList
        mode.
        
        '''
        
        if not self.has_key('LL_GAS_LIST'):
            if type(self['LL_MOLECULES']) is types.StringType:
                self['LL_GAS_LIST'] = [Molecule.Molecule(linelist=1,\
                                            molecule=self['LL_MOLECULES'],\
                                            path_combocode=self.path_combocode)]
            else:
                self['LL_GAS_LIST'] = [Molecule.Molecule(molecule=molec,
                                            linelist=1,\
                                            path_combocode=self.path_combocode) 
                                       for molec in self['LL_MOLECULES']]
        else:
            pass
        
   
    
    def calcUSE_MASER_IN_SPHINX(self):
        
        '''
        Set the default value of USE_MASER_IN_SPHINX parameter.
        
        '''
        
        if not self.has_key('USE_MASER_IN_SPHINX'):
            self['USE_MASER_IN_SPHINX']=0
        else:
            pass


    
    def calcLOGG(self):
        
        """
        Set the default value of LOGG to 0.
        
        """
        
        if not self.has_key('LOGG'):
            self['LOGG']=0
        else:
            pass


    def calcFD2_CONT_63(self):
        
        """
        If F_CONT_63 is available, that value is multiplied by distance^2 for 
        this key. 
        
        """
        
        if not self.has_key('FD2_CONT_63'):
            if self['F_CONT_63'] <> None: 
                self['FD2_CONT_63'] = self['F_CONT_63']*self['DISTANCE']**2
            else:
                self['FD2_CONT_63'] = None
        else:
            pass


    def calcFD2M_CONT_63(self):
        
        """
        If F_CONT_63 is available, that value is multiplied by distance^2 and 
        divided by MDOT_GAS for this key. 
        
        """
        
        if not self.has_key('FD2M_CONT_63'):
            if self['F_CONT_63'] <> None: 
                self['FD2M_CONT_63'] = self['F_CONT_63']*self['DISTANCE']**2 \
                                            /self['MDOT_GAS']
            else:
                self['FD2M_CONT_63'] = None
        else:
            pass


    def calcF_CONT_63(self):
        
        """
        Set the default value of F_CONT_63 to the monochromatic flux calculated
        by MCMax. If no MCMax model is available, it is set to None.
        
        If set in the inputfile, it is assumed to be the measured monochromatic
        flux. A difference between measured and modeled currently is not 
        available. 
        
        """
        
        if not self.has_key('F_CONT_63'):
            if self['LAST_MCMAX_MODEL']: 
                dpath = os.path.join(os.path.expanduser('~'),'MCMax',\
                                     self.path_mcmax,'models',\
                                     self['LAST_MCMAX_MODEL'])
                w,f = MCMax.readModelSpectrum(dpath,rt_sed=1)
                fi = f[argmin(abs(w-6.3))]
                self['F_CONT_63'] = fi
            else:
                self['F_CONT_63'] = None
        else:
            pass


    def calcF_CONT_63_TYPE(self):
        
        """
        Set the default value of F_CONT_63_TYPE to MCMax. This is the type of 
        derivation of the measured 6.3 mic flux. Can be: ISO, MSX, PHOT, MCMax
        
        """
        
        if not self.has_key('F_CONT_63_TYPE'):
            self['F_CONT_63_TYPE'] = 'MCMax'
        else:
            pass
        
        
    def calcT_INNER_DUST(self):
        
        """
        Find the dust temperature at the inner radius in Kelvin.
        
        Taken from last mcmax model, and defined by the dust species able to 
        exist at the highest temperature; if no mcmax model is present, the 
        temperature is taken to be zero, indicating no inner radius T is 
        available.
        
        """        
        
        filename = os.path.join(os.path.expanduser('~'),'MCMax',\
                                self.path_mcmax,'models',\
                                self['LAST_MCMAX_MODEL'],'denstemp.dat')
        if not self.has_key('T_INNER_DUST'):
            try:
                rad = array(DataIO.getMCMaxOutput(incr=int(self['NRAD']),\
                                                  filename=filename))
                incr = int(self['NRAD'])*int(self['NTHETA'])
                temp_ori = DataIO.getMCMaxOutput(incr=incr,\
                                                 keyword='TEMPERATURE',\
                                                 filename=filename)
                temp = Data.reduceArray(temp_ori,self['NTHETA'])
                rin = self['R_INNER_DUST']*self['R_STAR']*self.Rsun
                self['T_INNER_DUST'] = temp[argmin(abs(rad-rin))]
            except IOError:
                self['T_INNER_DUST'] = 0
        else:
            pass
        


    def calcTEMPERATURE_EPSILON_GAS(self):
        
        """
        If not present in input, TEMPERATURE_EPSILON_GAS is equal to 0.5.
        
        """
        
        if not self.has_key('TEMPERATURE_EPSILON_GAS'):
            self['TEMPERATURE_EPSILON_GAS'] = 0.5
        else:
            pass



    def calcTEMPERATURE_EPSILON2_GAS(self):
        
        """
        If not present in input, TEMPERATURE_EPSILON2_GAS is equal to 0, 
        in which case it will be ignored when making input file.
        
        """
        
        if not self.has_key('TEMPERATURE_EPSILON2_GAS'):
            self['TEMPERATURE_EPSILON2_GAS'] = 0
        else:
            pass



    def calcRADIUS_EPSILON2_GAS(self):
        
        """
        If not present in input, RADIUS_EPSILON2_GAS is equal to 0, \
        in which case it will be ignored when making input file.
        
        """
        
        if not self.has_key('RADIUS_EPSILON2_GAS'):
            self['RADIUS_EPSILON2_GAS'] = 0
        else:
            pass



    def calcTEMPERATURE_EPSILON3_GAS(self):
        
        """
        If not present in input, TEMPERATURE_EPSILON3_GAS is equal to 0, 
        in which case it will be ignored when making input file.
        
        """
        
        if not self.has_key('TEMPERATURE_EPSILON3_GAS'):
            self['TEMPERATURE_EPSILON3_GAS'] = 0
        else:
            pass



    def calcRADIUS_EPSILON3_GAS(self):
        
        """
        If not present in input, RADIUS_EPSILON3_GAS is equal to 0, 
        in which case it will be ignored when making input file.
        
        """
        
        if not self.has_key('RADIUS_EPSILON3_GAS'):
            self['RADIUS_EPSILON3_GAS'] = 0
        else:
            pass



    def calcDUST_TO_GAS_CHANGE_ML_SP(self):
        
        """
        Set default value of sphinx/mline specific d2g ratio to the 
        semi-empirical d2g ratio, ie based on MDOT_DUST and MDOT_GAS. 
        
        In order to turn this off, set this parameter to 0 in the input file, 
        in which case the iterated acceleration d2g ratio is used.
        
        Both MDOT_GAS and MDOT_DUST have to be defined explicitly if this 
        parameter is not. 
        
        This parameter has to be defined explicitly if one of MDOT_GAS and 
        MDOT_DUST is not defined explicitly. 
        
        Note that the DUST_TO_GAS keyword is the internal representation of the
        dust_to_gas ratio and should never be explicitly defined. For all 
        practical purposes, use DUST_TO_GAS_CHANGE_ML_SP.
        
        """
        
        if not self.has_key('DUST_TO_GAS_CHANGE_ML_SP'):
            if not self.has_key('MDOT_DUST'):
                raise IOError('Both MDOT_DUST and DUST_TO_GAS_CHANGE_ML_SP '+\
                              'are undefined.')
            if not self.has_key('MDOT_GAS'):
                raise IOError('Both MDOT_GAS and DUST_TO_GAS_CHANGE_ML_SP '+\
                              'are undefined.')
            self['DUST_TO_GAS_CHANGE_ML_SP'] = self['DUST_TO_GAS']
        else:
            pass



    def calcR_INNER_GAS(self):
        
        """
        If not present in input, R_INNER_GAS is equal to R_INNER_DUST
    
        """
        
        if not self.has_key('R_INNER_GAS'):
            self['R_INNER_GAS'] = self['R_INNER_DUST']
        else:
            pass



    def calcUSE_DENSITY_NON_CONSISTENT(self):
        
        """
        Set USE_DENSITY_NON_CONSISTENT off by default.
        
        """
        
        if not self.has_key('USE_DENSITY_NON_CONSISTENT'):
            self['USE_DENSITY_NON_CONSISTENT'] = 0
        else:
            pass        



    def calcR_OUTER_DUST(self):
        
        """
        If not present in input, R_OUTER_DUST is calculated from 
        R_OUTER_DUST_AU.
            
        """
        
        if not self.has_key('R_OUTER_DUST'):
            if self.has_key('R_OUTER_DUST_AU'):
                self['R_OUTER_DUST'] = self['R_OUTER_DUST_AU']*self.au\
                                            /self['R_STAR']/self.Rsun
            elif self.has_key('R_OUTER_MULTIPLY'):
                self['R_OUTER_DUST'] = self['R_INNER_DUST']\
                                            *self['R_OUTER_MULTIPLY']
        else:
            pass
        


    def calcR_INNER_DUST(self):
    
        """
        Calculate the inner radius from MCMax output in stellar radii.
        
        If no MCMax model is calculated yet, R_{i,d} is the stellar radius.
        
        Else, the inner dust radius is taken where the density reaches a 
        threshold, defined by R_INNER_DUST_MODE:
        
            - MAX: Density reaches a maximum value, depends on the different 
                   condensation temperatures of the dust species taken into 
                   account 
            - ABSOLUTE: Density becomes larger than 10**(-30)
            - RELATIVE: Density becomes larger than 1% of maximum density
        
        Unless defined in the CC input file, the dust radius is updated every 
        time a new iteration starts.
        
        If no MCMax model is known, and destruction temperature iteration is 
        off, the inner radius is 2 stellar radii for calculation time reasons.
        
        """
    
        if not self.has_key('R_INNER_DUST'):
            if self.has_key('R_INNER_DUST_AU'):
                self['R_INNER_DUST'] = self['R_INNER_DUST_AU']*self.au\
                                                /self['R_STAR']/self.Rsun
            else:
                try:
                    filename = os.path.join(os.path.expanduser('~'),'MCMax',\
                                            self.path_mcmax,'models',\
                                            self['LAST_MCMAX_MODEL'],\
                                            'denstemp.dat')
                    incr = int(self['NRAD'])*int(self['NTHETA'])
                    dens_ori = array(DataIO.getMCMaxOutput(filename=filename,\
                                                           incr=incr,\
                                                           keyword='DENSITY'))
                    rad = array(DataIO.getMCMaxOutput(incr=int(self['NRAD']),\
                                                      keyword='RADIUS',\
                                                      filename=filename))
                    dens = Data.reduceArray(dens_ori,self['NTHETA'])
                    if self['R_INNER_DUST_MODE'] == 'MAX':
                        ri_cm = rad[argmax(dens)]
                    elif self['R_INNER_DUST_MODE'] == 'ABSOLUTE':
                        ri_cm = rad[dens>10**(-30)][0]
                    else:
                        ri_cm = rad[dens>0.01*max(dens)][0]
                    self['R_INNER_DUST'] = ri_cm/self.Rsun\
                                                /float(self['R_STAR'])
                except IOError:
                    self['R_INNER_DUST'] = 1.0
        else:
            pass



    def calcR_INNER_DUST_MODE(self):
         
        """
        The mode of calculating the inner radius from MCMax output, if present.
        
        Can be ABSOLUTE (dens>10**-50) or RELATIVE (dens[i]>dens[i+1]*0.01).
        
        CLASSIC reproduces the old method. 
        
        Set here to the default value of ABSOLUTE.
        
        """
        
        if not self.has_key('R_INNER_DUST_MODE'):
            self['R_INNER_DUST_MODE'] = 'ABSOLUTE'
        else:
            pass        



    def calcRID_TEST(self):
         
        """
        The mode of determining the dust temp profile. 
        
        Only for testing purposes.
        
            - Default is 'R_STAR', ie the temperature is taken from the stellar
              radius onward, regardless of what the inner radius is. 
        
            - 'R_INNER_GAS' is used for taking the dust temperature from the 
              inner gas radius onward. 
        
            - 'BUGGED_CASE' is the old version where r [R*] > R_STAR [Rsun]. 
        
        """
        
        if not self.has_key('RID_TEST'):
            self['RID_TEST'] = 'R_STAR'
        else:
            pass 



    def calcSPEC_DENS_DUST(self):
        
        """
        Calculating average specific density of dust shell.
        
        This is based on the input dust species abundances and their specific 
        densities.
    
        """
    
        if not self.has_key('SPEC_DENS_DUST'):
            data_path = os.path.join(self.path_combocode,'Data')
            sd_list = DataIO.getInputData(path=data_path,keyword='SPEC_DENS',\
                                          filename='Dust.dat')
            if int(self['MRN_DUST']):
                these_sd = [sd
                            for sp in self['DUST_LIST']
                            for sps,sd in zip(self.species_list,sd_list)
                            if sp == sps and self.has_key('RGRAIN_%s'%sp)]
                sd_mrn = sum(these_sd)/len(these_sd)
                a_sd = sum([float(self['A_' + sp])*sd
                            for sp in self['DUST_LIST']
                            for sps,sd in zip(self.species_list,sd_list)
                            if sp == sps and self['A_%s'%sp] != 2.])
                self['SPEC_DENS_DUST'] = (sd_mrn + a_sd)/2.
            else:
                these_sd = [float(self['A_' + sp])*sd
                            for sp in self['DUST_LIST']
                            for sps,sd in zip(self.species_list,sd_list)
                            if sp == sps]
                self['SPEC_DENS_DUST'] = sum(these_sd)
        else:
            pass
            


    def calcLAST_MCMAX_MODEL(self):
        
        """
        Creates empty string if not present yet.
    
        """
        
        if not self.has_key('LAST_MCMAX_MODEL'):
            self['LAST_MCMAX_MODEL'] = ''
        else:
            pass
        


    def calcLAST_PACS_MODEL(self):
        
        """
        Sets to None if not present yet.
    
        """
        
        if not self.has_key('LAST_PACS_MODEL'):
            self['LAST_PACS_MODEL'] = None
        else:
            pass
        


    def calcLAST_SPIRE_MODEL(self):
        
        """
        Sets to None if not present yet.
        
        Note that this is an index if it IS present, and can be zero. Always 
        check with None instead of boolean. 
    
        """
        
        if not self.has_key('LAST_SPIRE_MODEL'):
            self['LAST_SPIRE_MODEL'] = None
        else:
            pass
        


    def calcLAST_GASTRONOOM_MODEL(self):
        
        """
        Creates empty string if not present yet.
    
        """
        
        if not self.has_key('LAST_GASTRONOOM_MODEL'):
            self['LAST_GASTRONOOM_MODEL'] = ''
        else:
            pass
    

    
    def calcDRIFT(self):
        
        """
        Find terminal drift velocity from last calculated GASTRoNOoM model.
        
        Units are km/s and is given for grain size 0.25 micron.
        
        If no GASTRoNOoM model exists, the drift is taken to be 0.
        
        """
        
        if not self.has_key('DRIFT'):
            try:
                #- The last 10 entries should be roughly constant anyway, 
                #- ~terminal values
                self['DRIFT'] = self.getAverageDrift()[-5]/10.**5    
            except IOError:
                self['DRIFT'] = 0
                print 'No GASTRoNOoM model has been calculated yet, drift ' + \
                      'is unknown and set to the default of 0.'
        else:
            pass
        


    def calcM_DUST(self):
        
        """
        Find total dust mass, based on sigma_0 in the case of a power law.
    
        """
        
        if not self.has_key('M_DUST'):
            if self['DENSTYPE'] == 'POW':
                if self['DENSPOW'] == 2:
                    self['M_DUST']  \
                        = 2*pi*self['DENSSIGMA_0']\
                        *(self['R_INNER_DUST']*self['R_STAR']*self.Rsun)**2\
                        *log(self['R_OUTER_DUST']/float(self['R_INNER_DUST']))\
                        /self.Msun
                else:
                    self['M_DUST'] \
                        = 2*pi*self['DENSSIGMA_0']\
                        *(self['R_INNER_DUST']*self['R_STAR']*self.Rsun)**2\
                        /(2.-self['DENSPOW'])/self.Msun\
                        *((self['R_OUTER_DUST']/float(self['R_INNER_DUST']))\
                        **(2.-self['DENSPOW'])-1.)
            else:
                pass
        else:
            pass
        

    
    def calcMDOT_DUST(self): 
        
        '''
        Calculate the value of MDOT_DUST from the DUST_TO_GAS_RATIO_ML_SP. 
        
        Requires MDOT_GAS and VEL_INFINITY_GAS to be defined. 
        
        This parameter is recalculated after every iteration and updates
        V_EXP_DUST in the equation.
        
        MDOT_DUST can be given explicitly in the inputfile in which case it 
        remains unchanged.
        
        MDOT_DUST is used to calculate the real DUST_TO_GAS ratio parameter. So
        through explicit definition of 2 parameters out of MDOT_GAS, MDOT_DUST  
        and DUST_TO_GAS_CHANGE_ML_SP you can control what the internal 
        dust-to-gas ratio should be.
        
        If DUST_TO_GAS_CHANGE_ML_SP is not given, MDOT_DUST and MDOT_GAS have 
        to be defined explicitly.
        
        '''
        
        if not self.has_key('MDOT_DUST'):
            if not self.has_key('DUST_TO_GAS_CHANGE_ML_SP'):
                raise IOError('Both MDOT_DUST and DUST_TO_GAS_CHANGE_ML_SP '+\
                              'are undefined.')
            if not self.has_key('MDOT_GAS'):
                raise IOError('Both MDOT_DUST and MDOT_GAS are undefined.')
            self['MDOT_DUST'] = float(self['DUST_TO_GAS_CHANGE_ML_SP'])\
                                /float(self['VEL_INFINITY_GAS'])\
                                *float(self['V_EXP_DUST'])\
                                *float(self['MDOT_GAS'])
        else:
            pass


    def calcMDOT_GAS(self): 
        
        '''
        Calculate the value of MDOT_GAS from the DUST_TO_GAS_RATIO_ML_SP.
        
        Requires MDOT_DUST and VEL_INFINITY_GAS to be defined. 
        
        This parameter is recalculated after every iteration and updates
        V_EXP_DUST in the equation.
        
        MDOT_GAS can be given explicitly in the inputfile in which case it 
        remains unchanged.
        
        MDOT_GAS is used to calculate the real DUST_TO_GAS ratio parameter. So
        through explicit definition of 2 parameters out of MDOT_GAS, MDOT_DUST  
        and DUST_TO_GAS_CHANGE_ML_SP you can control what the internal 
        dust-to-gas ratio should be.
        
        If DUST_TO_GAS_CHANGE_ML_SP is not given, MDOT_GAS has to be defined 
        explicitly.
        
        '''
        
        if not self.has_key('MDOT_GAS'):
            if not self.has_key('DUST_TO_GAS_CHANGE_ML_SP'):
                raise IOError('Both MDOT_GAS and DUST_TO_GAS_CHANGE_ML_SP '+\
                              'are undefined.')
            if not self.has_key('MDOT_DUST'):
                raise IOError('Both MDOT_DUST and MDOT_GAS are undefined.')
            self['MDOT_GAS'] = float(self['VEL_INFINITY_GAS'])\
                               /float(self['V_EXP_DUST'])\
                               *float(self['MDOT_DUST'])\
                               /float(self['DUST_TO_GAS_CHANGE_ML_SP'])
        else:
            pass

        
    def calcMDOT_MODE(self):
        
        '''
        Set the default value of MDOT_MODE to constant.
        
        '''
        
        if not self.has_key('MDOT_MODE'):
            self['MDOT_MODE'] = 'CONSTANT'
        else:
            pass



    def calcMDOT_GAS_START(self):
        
        '''
        Set the default value of MDOT_GAS_START equal to MDOT_GAS.
        
        '''
        
        if not self.has_key('MDOT_GAS_START'):
            self['MDOT_GAS_START'] = self['MDOT_GAS']
        else:
            pass
        

    def calcMDOT_CLASS(self):
        
        '''
        Set the order of magnitude of MDOT. 
        0: Mdot < 1e-6
        1: 1e-6 <= Mdot < 3e-6
        2: 3e-6 <= Mdot < 1e-5
        3: 1e-5 <= Mdot
        
        '''
        
        if not self.has_key('MDOT_CLASS'):
            if self['MDOT_GAS'] < 1e-6: 
                self['MDOT_CLASS'] = (0,r'$\dot{M}_\mathrm{g} < 1 \times 10^{-6}\ \mathrm{M}_\odot\ \mathrm{yr}^{-1}$')
            elif self['MDOT_GAS'] >= 1e-5: 
                self['MDOT_CLASS'] = (3,r'$\dot{M}_\mathrm{g} \geq 1 \times 10^{-5}\ \mathrm{M}_\odot\ \mathrm{yr}^{-1}$')
            elif self['MDOT_GAS'] >= 1e-6 and self['MDOT_GAS'] < 3e-6: 
                self['MDOT_CLASS'] = (1,r'$1 \times 10^{-6}\ \mathrm{M}_\odot\ \mathrm{yr}^{-1}$ $\leq \dot{M}_\mathrm{g} < 3 \times 10^{-6}\ \mathrm{M}_\odot\ \mathrm{yr}^{-1}$') 
            else: 
                self['MDOT_CLASS'] = (2,r'$3 \times 10^{-6}\ \mathrm{M}_\odot\ \mathrm{yr}^{-1}$ $\leq \dot{M}_\mathrm{g} < 1 \times 10^{-5}\ \mathrm{M}_\odot\ \mathrm{yr}^{-1}$') 
        else:
            pass
        
        
    def calcQ_STAR(self):
        
        ''' 
        Set the stellar pulsation constant (che1992).
        
        '''
        
        if not self.has_key('Q_STAR'):
            self['Q_STAR'] = self['P_STAR']*self['M_STAR']**0.5\
                                    *self['R_STAR']**(-3/2.)
        else:
            pass
        
    
    def calcSCD_CLASS(self):
        
        '''
        Set the order of magnitude of SHELLCOLDENS. 
        0: scd < 0.06
        1: 0.06 <= scd < 0.15
        2: 0.15 <= scd < 0.4
        3: 0.4 <= scd
        
        '''
        
        if not self.has_key('SCD_CLASS'):
            if self['SHELLCOLDENS'] < 0.07: 
                self['SCD_CLASS'] = (0,r'$\bar{m} < 0.07\ \mathrm{g\;cm}^{-2}$')
            elif self['SHELLCOLDENS'] >= 0.07 and self['SHELLCOLDENS'] < 0.15: 
                self['SCD_CLASS'] = (1,r'$0.07\ \mathrm{g\;cm}^{-2}$ $\leq \bar{m} < 0.15\ \mathrm{g\;cm}^{-2}$')
            elif self['SHELLCOLDENS'] >=0.4: 
                self['SCD_CLASS'] = (3,r'$\bar{m} \geq 0.4\ \mathrm{g\;cm}^{-2}$')
            else: 
                self['SCD_CLASS'] = (2,r'$0.15\ \mathrm{g\;cm}^{-2}$ $\leq \bar{m} < 0.4\ \mathrm{g\;cm}^{-2}$')
        else:
            pass
            
    
    def calcL_CLASS(self):
        
        '''
        Set the order of magnitude of L_STAR.
        
        0: lstar < 6000
        1: 6000 <= lstar < 8000
        2: 8000 <= lstar < 10000
        3: 10000 <= lstar
        
        '''
        
        if not self.has_key('L_CLASS'):
            if self['L_STAR'] < 6000: 
                self['L_CLASS'] = (0,r'$L_\star < 6000$ $\mathrm{L}_\odot$')
            elif self['L_STAR'] >= 10000: 
                self['L_CLASS'] = (3,r'$L_\star \geq 10000$ $\mathrm{L}_\odot$')
            elif self['L_STAR'] >= 8000 and self['L_STAR'] < 10000: 
                self['L_CLASS'] = (2,r'$8000$ $\mathrm{L}_\odot$ $\leq L_\star < 10000$ $\mathrm{L}_\odot$')
            else: 
                self['L_CLASS'] = (1,r'$6000$ $\mathrm{L}_\odot$ $\leq L_\star < 8000$ $\mathrm{L}_\odot$')
        else:
            pass
        
        
    
    def calcT_CLASS(self):
        
        '''
        Set the order of magnitude of T_STAR.
        
        0: tstar < 2000
        1: 2000 <= tstar < 2200
        2: 2200 <= tstar < 2500
        3: 2500 <= tstar
        
        '''
        
        if not self.has_key('T_CLASS'):
            if self['T_STAR'] < 2000: 
                self['T_CLASS'] = (0,r'$T_\star < 2000\ \mathrm{K}$')
            elif self['T_STAR'] >= 2500: 
                self['T_CLASS'] = (3,r'$T_\star \geq 2500\ \mathrm{K}$')
            elif self['T_STAR'] >= 2250 and self['T_STAR'] < 2500: 
                self['T_CLASS'] = (2,r'$2250\ \mathrm{K}$ $\leq T_\star < 2500\ \mathrm{K}$') 
            else: 
                self['T_CLASS'] = (1,r'$2000\ \mathrm{K}$ $\leq T_\star < 2250\ \mathrm{K}$')
        else:
            pass
    
    
    def calcVG_CLASS(self):
        
        '''
        Set the order of magnitude of VEL_INFINITY_GAS
        
        0: vg < 10
        1: 10 <= vg < 15
        2: 15 <= vg < 20
        3: 20 <= vg
        
        '''
        
        if not self.has_key('VG_CLASS'):
            if self['VEL_INFINITY_GAS'] < 10.: 
                self['VG_CLASS'] = (0,r'$v_{\infty\mathrm{,g}} < 10\ \mathrm{km\;s}^{-1}$')
            elif self['VEL_INFINITY_GAS'] >= 20.: 
                self['VG_CLASS'] = (3,r'$v_{\infty\mathrm{,g}} \geq 20\ \mathrm{km\;s}^{-1}$')
            elif self['VEL_INFINITY_GAS'] >= 15. and self['VEL_INFINITY_GAS'] < 20.: 
                self['VG_CLASS'] = (2,r'$15\ \mathrm{km\;s}^{-1}$ $\leq v_{\infty\mathrm{,g}} < 20\ \mathrm{km\;s}^{-1}$') 
            else: 
                self['VG_CLASS'] = (1,r'$10\ \mathrm{km\;s}^{-1}$ $\leq v_{\infty\mathrm{,g}} < 15\ \mathrm{km\;s}^{-1}$') 
        else:
            pass
        
        
    
    def calcV_EXP_DUST(self):
        
        """
        Calculate dust terminal velocity from gas terminal velocity and drift.
        
        Given in km/s.
        
        """

        if not self.has_key('V_EXP_DUST'):
            self['V_EXP_DUST']= float(self['VEL_INFINITY_GAS']) \
                                    + float(self['DRIFT'])
        else:
            pass    



    def calcRT_SED(self):
        
        '''
        Set the default value of MCMax ray-tracing of the SED to False.
        
        '''
        
        if not self.has_key('RT_SED'):
            self['RT_SED']= 0
        else:
            pass         



    def calcIMAGE(self):
        
        '''
        Set the default value of MCMax image to False.
        
        '''
        
        if not self.has_key('IMAGE'):
            self['IMAGE']= 0
        else:
            pass    


    def calcVISIBILITIES(self):
        
        '''
        Set the default value of MCMax visibilities to False.
        
        '''
        
        if not self.has_key('VISIBILITIES'):
            self['VISIBILITIES']= 0
        else:
            pass    

    def calcREDO_OBS(self):
        
        '''
        Set the default value of redoing observation files to False.
        
        '''
        
        if not self.has_key('REDO_OBS'):
            self['REDO_OBS']= 0
        else:
            pass    
        
 
    
    def calcR_MAX(self,missing_key):
        
        """
        Calculate the maximum existence radii for dust species.
        
        Based on T_MIN_SPECIES for the species, and derived from mcmax output.
        
        If not MCMax model available, a power law is assumed. If T_MIN is not 
        given, no boundaries are assumed. 
        
        Is given in solar radii.
        
        @param missing_key: the missing max radius for a species that is needed
                            Of the format R_MAX_SPECIES.
        @type missing_key: string
        
        """
        
        if not self.has_key(missing_key):
            #- R_MAX is for T_MIN
            try: 
                temp = float(self[missing_key.replace('R_MAX','T_MIN',1)])
                try:
                    #- if T_CONTACT: no specific species denstemp files, 
                    #- so denstemp.dat is taken
                    fp = os.path.join(os.path.expanduser('~'),'MCMax',\
                                      self.path_mcmax,'models',\
                                      self['LAST_MCMAX_MODEL'])
                    inputname = float(self['T_CONTACT']) \
                                    and 'denstemp.dat' \
                                    or 'denstempP%.2i.dat' \
                                      %self['DUST_LIST'].index(missing_key[6:])
                    inputname = os.path.join(fp,inputname)
                    rad_list = DataIO.getMCMaxOutput(incr=int(self['NRAD']),\
                                                     keyword='RADIUS',\
                                                     filename=inputname)
                    incr = int(self['NRAD'])*int(self['NTHETA'])
                    temp_list = DataIO.getMCMaxOutput(incr=incr,\
                                                      keyword='TEMPERATURE',\
                                                      filename=inputname)
                    temp_list = Data.reduceArray(temp_list,self['NTHETA'])
                    
                    i = 0
                    #- if tmin is larger than temp_list[0], indexerror raises, 
                    #- and vice versa: no dust
                    #- if tmin is smaller than temp_list[len], indexerror 
                    #- raises, and vice versa: all dust
                    try:
                        while temp_list[i] < temp or temp_list[i+1] > temp:
                            i += 1
                        rad = Interpol.linInterpol([temp_list[i],\
                                                    temp_list[i+1]],\
                                                   [rad_list[i],\
                                                    rad_list[i+1]],\
                                                   temp)\
                                                 /(self.Rsun*self['R_STAR'])
                    except IndexError:

                        #- if T_MIN (for R_MAX) > temp_list[0] then no dust can
                        #- be present of the species
                        #- for TMIN RMAX should be made very small, ie R*
                        if temp > temp_list[0]:
                            rad = self['R_STAR']

                        #- on the other hand, if TMIN < temp_list[len-1]
                        #- all dust is allowed, so raise KeyError, such that no
                        #- R_MAX is entered in STAR
                        elif temp < temp_list[-1]:
                            raise KeyError
                        
                        else:
                            print 'Something went wrong when searching for ' +\
                                  'R_MAX corresponding to T_MIN... Debug!'    
                    self[missing_key] = rad
                
                except IOError:
                    self[missing_key] = powerRfromT(float(temp),\
                                                    float(self['T_STAR']),\
                                                    power=float(self\
                                                            ['POWER_T_DUST']))\
                                                   /2.
            except KeyError:
                self[missing_key] = ''
        else:
            pass        


                            
    def calcT_DES(self,species):
        
        """
        Find the max temperature at which a dust species can exist.
        
        First, the CC inputfile is searched for T_MAX_SPECIES, in which case
        the sublimation temperature is constant. T_MAX is never made by Star()!
        
        If not present, Dust.dat info is taken, being either a sublimation 
        temperature, or the coefficients to calculate a pressure dependent
        sublimation temperature. These are set using T_DESA_ and T_DESB_SPECIES
        
        This assumes TDESITER to be on.
        
        @param species: The dust species
        @type species: string
        
        """
        
        if not self.has_key('T_DESA_' + species) \
                or not self.has_key('T_DESB_' + species):
            try:
                if not self['T_MAX_' + species]:
                    del self['T_MAX_' + species]
                self['T_DESA_' + species] = 10.0**(4)/self['T_MAX_' + species]
                self['T_DESB_' + species] = 10.0**(-4)
            except KeyError:
                species_index = self.species_list.index(species)
                species_tdesa = DataIO.getInputData(path=os.path.join(\
                                                  self.path_combocode,'Data'),\
                                             keyword='T_DESA',\
                                             filename='Dust.dat')\
                                            [species_index]
                if species_tdesa:
                    self['T_DESA_' + species] = 10.0**(4)\
                        *DataIO.getInputData(path=os.path.join(self.path_combocode,\
                                                        'Data'),\
                                     keyword='T_DESB',filename='Dust.dat')\
                                    [species_index]/species_tdesa
                    self['T_DESB_' + species] = 10.0**(4)/species_tdesa
                else:
                    self['T_DESA_' + species] = 10.0**(4)\
                        /DataIO.getInputData(path=os.path.join(self.path_combocode,\
                                                        'Data'),\
                                      keyword='T_DES',filename='Dust.dat')\
                                     [species_index]
                    self['T_DESB_' + species] = 10.0**(-4)
        else:
            pass




    def calcR_SHELL_UNIT(self):
        
        '''
        Set default value of R_SHELL_UNIT to R_STAR.
        
        '''
        
        if not self.has_key('R_SHELL_UNIT'):
            self['R_SHELL_UNIT'] = 'R_STAR'
        else:
            pass



    def getAverageDrift(self):
        
        '''
        Return an array with the average drift velocity as a function of 
        radius, from coolfgr_all, in cm/s.
        
        '''

        inputfile = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                self.path_gastronoom,'models',self['LAST_GASTRONOOM_MODEL'],\
                'coolfgr_all' + self['LAST_GASTRONOOM_MODEL'] + '.dat')
        drift = DataIO.getGastronoomOutput(inputfile,keyword='VDRIFT')  
        opa_gs_max = 2.5e-1
        opa_gs_min = 5.0e-3
        return array(drift)/sqrt(0.25)*1.25\
                            *(opa_gs_max**(-2.)-opa_gs_min**(-2.))\
                            /(opa_gs_max**(-2.5)-opa_gs_min**(-2.5))
        


    def calcDENSTYPE(self):
        
        """
        Define the type of density distribution.
        
        Default is 'MASSLOSS' for first iteration, otherwise SHELLFILE.
        
        If second iteration, a DENSFILE is created taking into account the 
        acceleration zone. This file is only created if not already present. 
        
        The dust density profile is calculated from the h2 number density, 
        after scaling to the dust mass-loss rate and correcting for the dust
        velocity profile. 
        
        """
        
        if not self.has_key('DENSTYPE') or not self.has_key('DENSFILE'):
            if self['MDOT_MODE'] != 'CONSTANT':
                exstr = '_var'
            else:
                exstr = ''
            filename = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                    self.path_gastronoom,'data_for_mcmax',\
                                    '_'.join(['dens',\
                                              self['LAST_GASTRONOOM_MODEL'],\
                                    'mdotd%s%.2e.dat'%(exstr,\
                                                       self['MDOT_DUST'])]))
            if os.path.isfile(filename):
                self['DENSFILE'] = filename
                self['DENSTYPE'] = "SHELLFILE"
            else:
                try:
                    if self.has_key('DENSTYPE'):
                        if self['DENSTYPE'] == "MASSLOSS": 
                            raise IOError
                    inputfile = os.path.join(os.path.expanduser('~'),\
                                             'GASTRoNOoM',\
                                             self.path_gastronoom,'models',\
                                             self['LAST_GASTRONOOM_MODEL'],\
                                             'coolfgr_all%s.dat'\
                                             %self['LAST_GASTRONOOM_MODEL'])
                    rad = DataIO.getGastronoomOutput(inputfile,return_array=1)
                    #-- Grab the velocity profile so the gas velocity can be 
                    #   converted to the dust velocity.
                    vg = DataIO.getGastronoomOutput(inputfile,keyword='VEL',\
                                                    return_array=1)
                    #-- Use the H2 density profile to take into account any 
                    #   type of variable mass loss (including exponents in 
                    #   r_points_mass_loss.
                    nh2 = DataIO.getGastronoomOutput(inputfile,keyword='N(H2',\
                                                     return_array=1)
                    #-- Get the drift profile, corrected for the average grain 
                    #   size
                    drift = self.getAverageDrift()     
                    self['DENSTYPE'] = "SHELLFILE"
                    #-- Calc dust density based on md/mg instead of d2g to take
                    #   into account velocity profiles instead of terminal vels
                    dens = nh2*self.mh*2.*self['MDOT_DUST']/self['MDOT_GAS']\
                            *vg/(vg+drift)
                    #-- GASTRoNOoM calculates smoother density profiles than 
                    #   this formula ever can accomplish
                    #dens = float(self['MDOT_DUST'])*self.Msun\
                    #        /((vg+drift)*4.*pi*rad**2.*self.year)
                    self['DENSFILE'] = filename
                    DataIO.writeCols(filename,[rad/self.au,dens])        
                    print '** Made MCMax density input file at %s.'%filename
                except IOError:
                    print '** Writing and/or reading DENSFILE output and/or '+\
                          'input failed. Assuming standard mass-loss density'+\
                          ' distribution.'
                    self['DENSTYPE'] = "MASSLOSS"
                    self['DENSFILE'] = ''
        else:
            pass



    def calcSHELLMASS(self):
        
        """
        Calculate the average mass per shell of the circumstellar envelope. 

        Calculated by Mdot_gas/vexp.
    
        """
        
        if not self.has_key('SHELLMASS'):
            self['SHELLMASS'] = float(self['MDOT_GAS'])*self.Msun\
                                  /((self['VEL_INFINITY_GAS']*10**5)*self.year)
        else:
            pass


    def calcSHELLDENS(self):
        
        """
        Calculate the average density of the circumstellar envelope. 
    
        """
        
        if not self.has_key('SHELLDENS'):
            self['SHELLDENS'] = float(self['MDOT_GAS'])*self.Msun\
                                  /((self['VEL_INFINITY_GAS']*10**5)*self.year\
                                    *(self['R_STAR']*self.Rsun)**2*4.*pi)
        else:
            pass
        
        
        
    def calcSHELLCOLDENS(self):
        
        """
        Calculate a proxy for the average column density of the circumstellar 
        shell. 
        
        This is (intuitively) rho * R_STAR, which is important for radiative 
        excitation (density tracing the source of the radiation, R_STAR setting
        the scale of the envelope). Two types of radiative excitation can be 
        related to this: direct stellar light, and thermal dust emission.
        
        Especially important for water, but in a balance with other excitation
        mechanisms.
        
        Note that this quantity is also related to the optical depth through
        tau = kappa*coldens.
    
        """
        
        if not self.has_key('SHELLCOLDENS'):
            self['SHELLCOLDENS'] = self['SHELLDENS']\
                                    *self['R_STAR']*self.Rsun
        else:
            pass
        
        
    def calcSHELLDENS2(self):
        
        """
        Calculate a proxy for the average degree of collisional excitation in 
        the circumstellar shell.
        
        This is (intuitively) sqrt(rho * rho * R_STAR): two density factors 
        tracing both collisional partners, and R_STAR setting the scale of the 
        envelope.
        
        Sqrt is taken for easy comparison between this and the mass-loss rate
        to which it is directly proportional.
        
        Especially important for CO, but also to some degree for water where it 
        is in balance with other excitation mechanisms.
        
        Calculated by taking SHELLDENS**2*R_STAR ~ R_STAR^3/2.
        
        """
        
        if not self.has_key('SHELLDENS2'):
            self['SHELLDENS2'] = sqrt(self['SHELLDENS']**2\
                                         *self['R_STAR']*self.Rsun)
        else:
            pass

        
    def calcDENSFILE(self):
        
        """
        Pointer to the calcDENSTYPE method in case DENSFILE is missing.
    
        """
        
        self.calcDENSTYPE()
        
                            
                                                        
    def calcDUST_LIST(self):
        
        """
        List all non-zero abundances for this star.
    
        """
        
        if not self.has_key('DUST_LIST'):
            self['DUST_LIST'] = [species 
                                 for species in self.species_list 
                                 if self.has_key('A_' + species)]
            self['DUST_LIST'] = tuple([species 
                                       for species in self['DUST_LIST'] 
                                       if float(self['A_' + species]) != 0])
            print '=========='
            print 'Dust species that are taken into account during modeling '+\
                  'are %s.'%(', '.join(self['DUST_LIST']))
            print 'The specific density is %.2f g/cm^3.' \
                  %(self['SPEC_DENS_DUST'],)
        else:
            pass
            
    
    def calcMRN_DUST(self):
        
        '''
        Set the default value for MRN_DUST to 0.
        
        '''
        
        if not self.has_key('MRN_DUST'):
            self['MRN_DUST'] = 0
        else:
            pass
    
    
    
    def calcMRN_INDEX(self):
    
        '''
        Set the default value for MRN_INDEX to 3.5 (standard power law in ISM
        dust grain size distribution).
        
        '''
        
        if not self.has_key('MRN_INDEX'):
            self['MRN_INDEX'] = 3.5
        else:
            pass
        
        
    
    def calcMRN_NGRAINS(self):
        
        '''
        Set the default balue for MRN_NGRAINS to the max number of dust species
        involved. 
        
        This means that all dust species are treated in the mrn treatment of 
        MCMax. 
        
        If the max is set to less species, then the extra species are treated 
        as normal, with manually set abundances. 
        
        '''
        
        if not self.has_key('MRN_NGRAINS'):
            self['MRN_NGRAINS'] = len(self['DUST_LIST'])
        else:
            pass
        
        
    
    def calcMRN_RMAX(self):
        
        '''
        Set the default value for the maximum grain size in micron. 
        
        Abundances of bigger grains will be set to 0.
        
        '''
        
        if not self.has_key('MRN_RMAX'):
            self['MRN_RMAX'] = 1000.
        else:
            pass
        
        
    
    def calcMRN_RMIN(self):
        
        '''
        Set the default value for the minimum grain size in micron. 
        
        Abundances of smaller grains will be set to 0.
        
        '''
        
        if not self.has_key('MRN_RMIN'):
            self['MRN_RMIN'] = 0.01
        else:
            pass
        
    
    def calcSCSET(self):
        
        '''
        Set default of self-consistent settling to False.
        
        '''
        
        if not self.has_key('SCSET'):
            self['SCSET'] = 0
        else:
            pass
        
    
    def calcSCSETEQ(self):
        
        '''
        Set default of self-consistent settling to True.
        
        Only relevant if SCSET == 1.
        
        '''
        
        if not self.has_key('SCSETEQ'):
            self['SCSETEQ'] = 1
        else:
            pass
        
        
        
    def calcALPHATURB(self):
        
        '''
        Set default of the turbulent mixing strenght to 1e-4.
                
        '''
        
        if not self.has_key('ALPHATURB'):
            self['ALPHATURB'] = 1e-4
        else:
            pass
        
        
    
    def calcMOLECULE(self):
        
        '''
        Set the MOLECULE keyword to empty list if not given in the input.
        
        '''
        
        if not self.has_key('MOLECULE'):
            self['MOLECULE'] = []
        else:
            pass
            


    def calcGAS_LIST(self):
        
        """
        Set the GAS_LIST keyword based on the MOLECULE keyword. 
        
        The input MOLECULE format from the CC input is converted into 
        Molecule() objects.
        
        """
        
        if not self.has_key('GAS_LIST') and self['MOLECULE']:
            if len(self['MOLECULE'][0]) == 2:
                #- First convert the long GASTRoNOoM input molecule names to 
                #- the short names, since if len() is 2, it comes from 
                #- PlottingSession.setPacsFromDb
                molec_indices \
                    = [DataIO.getInputData(path=os.path.join(self.path_combocode,\
                                                      'Data'),\
                                    keyword='MOLEC_TYPE',\
                                    filename='Molecule.dat',make_float=0)\
                                   .index(molec[0]) 
                       for molec in self['MOLECULE']]
                molecules_long = [molec[0] for molec in self['MOLECULE']]
                self['MOLECULE'] \
                    = [[DataIO.getInputData(path=os.path.join(self.path_combocode,\
                                                       'Data'),\
                                     keyword='TYPE_SHORT',\
                                     filename='Molecule.dat')[index]] \
                        + [molec[1]] 
                       for molec,index in zip(self['MOLECULE'],molec_indices)]
                self['TRANSITION'] \
                    = [[DataIO.getInputData(path=os.path.join(self.path_combocode,\
                                                       'Data'),\
                                     keyword='TYPE_SHORT',\
                                     filename='Molecule.dat')\
                            [molec_indices[molecules_long.index(trans[0])]]] \
                        + trans[1:]
                       for trans in self['TRANSITION']]
                #- Pull the info from the db
                self['GAS_LIST'] = []
                for molec,model_id in self['MOLECULE']:
                    self['GAS_LIST'].append(Molecule.makeMoleculeFromDb(\
                                        path_combocode=self.path_combocode,\
                                        model_id=model_id,molecule=molec,\
                                        path_gastronoom=self.path_gastronoom))
            else:
                for key,index in zip(['R_OUTER','CHANGE_FRACTION_FILENAME',\
                                             'SET_KEYWORD_CHANGE_ABUNDANCE',\
                                             'NEW_TEMPERATURE_FILENAME',\
                                             'SET_KEYWORD_CHANGE_TEMPERATURE',\
                                             'ENHANCE_ABUNDANCE_FACTOR',\
                                             'ABUNDANCE_FILENAME'],\
                                            [13,16,17,18,19,15,14]):
                    if self['%s_H2O'%key]:
                        self['MOLECULE'] = \
                            [[(i==index and molec[0] in ['1H1H16O','p1H1H16O',\
                                                         '1H1H17O','p1H1H17O',\
                                                         '1H1H18O','p1H1H18O']) 
                                    and self['%s_H2O'%key] 
                                    or str(entry) 
                              for i,entry in enumerate(molec)]
                             for molec in self['MOLECULE']]                        
                #-- Check if startype is not BB, because if starfile is given 
                #   while BB is requested, the starfile cannot be given to the
                #   Molecule class. 
                starfile = self['STARTYPE'] != 'BB' and self['STARFILE'] or ''
                self['GAS_LIST'] = \
                    [Molecule.Molecule(\
                        molecule=molec[0],ny_low=int(molec[1]),\
                        ny_up=int(molec[2]),nline=int(molec[3]),\
                        n_impact=int(molec[4]),n_impact_extra=int(molec[5]),\
                        abun_molec=float(molec[6]),\
                        abun_molec_rinner=float(molec[7]),\
                        abun_molec_re=float(molec[8]),\
                        rmax_molec=float(molec[9]),itera=int(molec[10]),\
                        lte_request=int(molec[11]),\
                        use_collis_radiat_switch=int(molec[12]),\
                        abundance_filename=molec[14],\
                        enhance_abundance_factor=float(molec[15]),\
                        path_combocode=self.path_combocode,opr=self['OPR'],\
                        ratio_12c_to_13c=self['RATIO_12C_TO_13C'],\
                        ratio_16o_to_18o=self['RATIO_16O_TO_18O'],\
                        ratio_16o_to_17o=self['RATIO_16O_TO_17O'],\
                        r_outer=float(molec[13]) \
                                    and float(molec[13]) \
                                    or self['R_OUTER_GAS'],\
                        outer_r_mode=float(molec[13]) \
                                        and 'FIXED' \
                                        or self['OUTER_R_MODE'],\
                        dust_to_gas_change_ml_sp=self\
                                                 ['DUST_TO_GAS_CHANGE_ML_SP'],\
                        set_keyword_change_abundance=int(molec[17]),\
                        change_fraction_filename=molec[16],\
                        set_keyword_change_temperature=int(molec[19]),\
                        new_temperature_filename=molec[18],\
                        starfile=starfile)
                     
                     for molec in self['MOLECULE']]
            
            #- safety check
            requested_molecules = set([molec.molecule 
                                      for molec in self['GAS_LIST']])
            if not len(self['GAS_LIST']) == len(requested_molecules): 
                raise IOError('Multiple parameter sets for a single molecule'+\
                              ' passed. This is impossible! Contact Robin...')     
            print 'Gas molecules that are taken into account are ' + \
                  ', '.join(sorted([molec[0] for molec in self['MOLECULE']]))+\
                  '.'        
        elif not self.has_key('GAS_LIST') and not self['MOLECULE']:
            self['GAS_LIST'] = []
        else:
            pass



    def calcR_OUTER_H2O(self):
        
        '''
        Set default value of R_OUTER_H2O to 0.
        
        '''
        
        if not self.has_key('R_OUTER_H2O'):
            self['R_OUTER_H2O'] = 0
        else:
            pass 
      


    def calcNEW_TEMPERATURE_FILENAME_H2O(self):
        
        '''
        Set default value of NEW_TEMPERATURE_FILENAME_H2O to ''.
        
        '''
        
        if not self.has_key('NEW_TEMPERATURE_FILENAME_H2O'):
            self['NEW_TEMPERATURE_FILENAME_H2O'] = ''
        else:
            pass 



    def calcCHANGE_FRACTION_FILENAME_H2O(self):
        
        '''
        Set default value of CHANGE_FRACTION_FILENAME_H2O to ''.
        
        '''
        
        if not self.has_key('CHANGE_FRACTION_FILENAME_H2O'):
            self['CHANGE_FRACTION_FILENAME_H2O'] = ''
        else:
            pass 
      


    def calcSET_KEYWORD_CHANGE_TEMPERATURE_H2O(self):
        
        '''
        Set default value of SET_KEYWORD_CHANGE_TEMPERATURE_H2O to ''.
        
        '''
        
        if not self.has_key('SET_KEYWORD_CHANGE_TEMPERATURE_H2O'):
            self['SET_KEYWORD_CHANGE_TEMPERATURE_H2O'] = 0
        else:
            pass 



    def calcSET_KEYWORD_CHANGE_ABUNDANCE_H2O(self):
        
        '''
        Set default value of SET_KEYWORD_CHANGE_ABUNDANCE_H2O to ''.
        
        '''
        
        if not self.has_key('SET_KEYWORD_CHANGE_ABUNDANCE_H2O'):
            self['SET_KEYWORD_CHANGE_ABUNDANCE_H2O'] = 0
        else:
            pass 
      


    def calcENHANCE_ABUNDANCE_FACTOR_H2O(self):
        
        '''
        Set default value of ENHANCE_ABUNDANCE_FACTOR_H2O to ''.
        
        '''
        
        if not self.has_key('ENHANCE_ABUNDANCE_FACTOR_H2O'):
            self['ENHANCE_ABUNDANCE_FACTOR_H2O'] = 0
        else:
            pass 
      


    def calcABUNDANCE_FILENAME_H2O(self):
        
        '''
        Set default value of ABUNDANCE_FILENAME_H2O to ''.
        
        '''
        
        if not self.has_key('ABUNDANCE_FILENAME_H2O'):
            self['ABUNDANCE_FILENAME_H2O'] = ''
        else:
            pass 
      

    
    def calcR_OUTER_EFFECTIVE(self):
        
        '''
        Get the effective outer radius (either from Mamon, or a fixed value).
        
        '''
        
        filename = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                self.path_gastronoom,'models',\
                                self['LAST_GASTRONOOM_MODEL'],\
                                'input%s.dat'%self['LAST_GASTRONOOM_MODEL'])
        
        if not self.has_key('R_OUTER_EFFECTIVE'):
            self['R_OUTER_EFFECTIVE'] \
                = float(DataIO.readFile(filename=filename,delimiter=' ')[0][4])
        else:
            pass



    def calcKEYWORD_DUST_TEMPERATURE_TABLE(self):
        
        '''
        Set KEYWORD_DUST_TEMPERATURE_TABLE to False for now. 
        
        If it was not yet defined, there is not ftemperature file anyway.
        
        '''
        
        if not self.has_key('KEYWORD_DUST_TEMPERATURE_TABLE'):
            if self['DUST_TEMPERATURE_FILENAME']:
                self['KEYWORD_DUST_TEMPERATURE_TABLE'] = 1
            else:
                self['KEYWORD_DUST_TEMPERATURE_TABLE'] = 0
        else:
            pass
    

    
    def calcNUMBER_INPUT_DUST_TEMP_VALUES(self):
        
        '''
        Set NUMBER_INPUT_DUST_TEMP_VALUES to length of input file for dust temp 
        
        If it does not exist set to 0.
        
        '''
        
        if not self.has_key('NUMBER_INPUT_DUST_TEMP_VALUES'):
            if self['DUST_TEMPERATURE_FILENAME']:
                self['NUMBER_INPUT_DUST_TEMP_VALUES'] \
                    = len([1 
                           for line in DataIO.readFile(\
                                            self['DUST_TEMPERATURE_FILENAME']) 
                           if line])
            else:
                self['NUMBER_INPUT_DUST_TEMP_VALUES'] = 0
        else:
            pass  

    
                            
    def calcDUST_TEMPERATURE_FILENAME(self):
        
        """
        Look for the temperature stratification of the star.
    
        If a last mcmax model is available, the filename is given, (for now 2d). 
        
        Else an empty string is given, and a power law is used in GASTRoNOoM.
        
        """
        
        if not self.has_key('DUST_TEMPERATURE_FILENAME'):
            filename = self['RID_TEST'] != 'R_STAR' \
                            and os.path.join(os.path.expanduser('~'),'MCMax',\
                                             self.path_mcmax,\
                                             'data_for_gastronoom',\
                                             '_'.join(['Td',\
                                                     self['LAST_MCMAX_MODEL'],\
                                                     self['RID_TEST']\
                                                      +'.dat']))\
                            or os.path.join(os.path.expanduser('~'),'MCMax',\
                                            self.path_mcmax,\
                                            'data_for_gastronoom',\
                                            '_'.join(['Td',\
                                                      self['LAST_MCMAX_MODEL']\
                                                      + '.dat']))
            if os.path.isfile(filename):
                self['DUST_TEMPERATURE_FILENAME'] = filename
            else:
                try:
                    iofile = os.path.join(os.path.expanduser('~'),'MCMax',\
                                          self.path_mcmax,'models',\
                                          self['LAST_MCMAX_MODEL'],\
                                          'denstemp.dat')
                    rad_list = array(DataIO.getMCMaxOutput(\
                                                incr=int(self['NRAD']),\
                                                filename=iofile))\
                                     /self.Rsun/float(self['R_STAR'])
                    incr = int(self['NRAD'])*int(self['NTHETA'])
                    temp_list = DataIO.getMCMaxOutput(incr=incr,\
                                                      keyword='TEMPERATURE',\
                                                      filename=iofile)
                    t_strat = Data.reduceArray(temp_list,self['NTHETA'])
                    if self['RID_TEST'] == 'R_STAR':
                         t_strat = t_strat[rad_list > 1]
                         rad_list = rad_list[rad_list > 1]
                    elif self['RID_TEST'] == 'R_INNER_GAS':
                         t_strat = t_strat[rad_list > self['R_INNER_GAS']]
                         rad_list = rad_list[rad_list > self['R_INNER_GAS']]
                    elif self['RID_TEST'] == 'BUGGED_CASE':
                         t_strat = t_strat[rad_list > self['R_STAR']]
                         rad_list = rad_list[rad_list > self['R_STAR']]
                    self['DUST_TEMPERATURE_FILENAME'] = filename
                    DataIO.writeCols(filename,[array(rad_list),t_strat])
                    self['KEYWORD_DUST_TEMPERATURE_TABLE'] = 1
                    self['NUMBER_INPUT_DUST_TEMP_VALUES'] = len(rad_list)
                    print '** Made dust temperature stratifaction file at %s.'\
                          %filename
                    if self['NUMBER_INPUT_DUST_TEMP_VALUES'] > 999:
                        ss = '** WARNING! The dust temperature file contains'+\
                             ' more than 999 grid points. GASTRoNOoM will '+\
                             'fail because it requires less than 1000 points.'
                        print ss
                except IOError:
                    self['DUST_TEMPERATURE_FILENAME'] = ''
        else:
            pass                        
                              
  
    def calcGAS_LINES(self):
        
        """
        Making transition line input for gas data (auto search) 
        and additional no-data lines.
        
        The Transition() objects are created then for these lines and added
        to the GAS_LINES list.
    
        """
        
        if not self.has_key('GAS_LINES'):
            self['GAS_LINES'] = list()
            #-- To make sure the GAS_LIST is done, and the conversion of 
            #   TRANSITION to the right molecule names is done 
            #   (in case of PlottingSession.setPacsFromDb is used)
            self.calcGAS_LIST()     
            
            #-- Check if specific transition were requested in addition to data            
            #   Note that these include autosearch transitions if requested
            #   (See ComboCode.py)
            if self.has_key('TRANSITION'):
                self['TRANSITION'] = [trans 
                                      for trans in self['TRANSITION'] 
                                      if trans[0] in [molec[0] 
                                                      for molec in self\
                                                                 ['MOLECULE']]]
                new_lines = [Transition.makeTransition(star=self,trans=trans) 
                             for trans in self['TRANSITION']]
                new_lines = [trans for trans in new_lines if trans]
                self['GAS_LINES'].extend(new_lines)
                
            #- Check if molecular line catalogues have to be browsed to create 
            #- line lists in addition to the data
            if self['LINE_LISTS']:
                if self['LINE_LISTS'] == 1: 
                    self.__addLineList()
                elif self['LINE_LISTS'] == 2: 
                    ll_path = os.path.split(self['LL_FILE'].strip())[0]
                    if not ll_path:
                        ll_path = os.path.join(os.path.expanduser('~'),\
                                               'GASTRoNOoM','LineLists')
                    ll_file = os.path.split(self['LL_FILE'].strip())[1]
                    llf = os.path.join(ll_path,ll_file)
                    nt = Transition.makeTransitionsFromTransList(filename=llf,\
                                                                 star=self) 
                    nt = [trans for trans in nt if trans]
                    self['GAS_LINES'].extend(nt)
            
            #-- Sort the transitions.
            self['GAS_LINES'] = sorted(list(self['GAS_LINES']),\
                                       key=lambda x: str(x))
            #-- Check uniqueness.
            self['GAS_LINES'] = Transition.checkUniqueness(self['GAS_LINES'])
            
            #-- Is this still needed? 
            requested_transitions = set([str(trans) 
                                         for trans in self['GAS_LINES']]) 
            if not len(self['GAS_LINES']) == len(requested_transitions):
                print 'Length of the requested transition list: %i'\
                      %len(self['GAS_LINES'])
                print 'Length of the requested transition list with only ' + \
                      'the "transition string" parameters: %i'\
                      %len(requested_transitions)
                print 'Guilty transitions:'
                trans_strings = [str(trans) for trans in self['GAS_LINES']]
                print '\n'.join([str(trans) 
                                 for trans in self['GAS_LINES'] 
                                 if trans_strings.count(str(trans))>1])
                raise IOError('Multiple parameter sets for a single ' + \
                              'transition requested. This is impossible! '+ \
                              'Check code/contact Robin.')
        else:
            pass
    


    def calcSTARTYPE(self):
        
        """
        Set the default value for STARTYPE, which is the blackbody 
        assumption (BB). 
        
        """
        
        if not self.has_key('STARTYPE'):
            self['STARTYPE'] = 'BB'
        else:
            pass



    def calcSTARFILE(self):
        
        """
        Set the default value for STARFILE, which is an empty string 
        (ie STARTYPE is BB, no inputfile). 
        
        """
        
        if not self.has_key('STARFILE'):
            if self['STARTYPE'] == 'BB':
                self['STARFILE'] = ''
            elif self['STARTYPE'] == 'ATMOSPHERE':
                modeltypes = ['comarcs','marcs','kurucz']
                modeltype = None
                for mt in modeltypes:
                    if mt in self['ATM_FILENAME']:
                        modeltype = mt
                        continue
                if modeltype is None: 
                    raise IOError('Atmosphere model type is unknown.')
                path = os.path.join(os.path.expanduser('~'),\
                                    self.path_combocode,'StarFiles')
                DataIO.testFolderExistence(path)
                atmfile = self['ATM_FILENAME']
                atmos = Atmosphere.Atmosphere(modeltype,filename=atmfile)
                atmosmodel = atmos.getModel(teff=self['T_STAR'],\
                                            logg=self['LOGG'])
                starfile = os.path.join(path,'%s_teff%s_logg%s.dat'\
                                        %(os.path.splitext(atmos.filename)[0],\
                                        str(atmos.teff_actual),\
                                        str(atmos.logg_actual)))
                if not os.path.isfile(starfile):
                    savetxt(starfile,atmosmodel,fmt=('%.8e'))
                print 'Using input model atmosphere at '
                print starfile
                self['STARFILE'] = starfile
            elif self['STARTYPE'] == 'TABLE':
                if not os.path.split(self['STARTABLE'])[0]:
                    self['STARFILE'] = os.path.join(os.path.expanduser('~'),\
                                                    self.path_combocode,\
                                                    'StarFiles',\
                                                    self['STARTABLE'])
                else:
                    self['STARFILE'] = self['STARTABLE']
                print 'Using input star spectrum at '
                print self['STARFILE']
        else:
            pass



    def calcLINE_LISTS(self):
        
        ''' 
        If the LINE LISTS keyword is not present, set to False.
        
        '''
        
        if not self.has_key('LINE_LISTS'):
            self['LINE_LISTS'] = 0
        else:
            pass



    def calcDUST_TO_GAS(self):
        
        '''
        Calculate the empirical value oft he dust to gas ratio.
        
        '''
        
        if not self.has_key('DUST_TO_GAS'):
            self['DUST_TO_GAS'] = float(self['MDOT_DUST'])\
                                    *float(self['VEL_INFINITY_GAS'])\
                                    /float(self['MDOT_GAS'])\
                                    /float(self['V_EXP_DUST'])
        else:
            pass


  
    def calcDUST_TO_GAS_INITIAL(self):
        
        '''
        Set a default value for the initial dust-to-gas ratio at 0.002.
        
        '''
        
        if not self.has_key('DUST_TO_GAS_INITIAL'):
            self['DUST_TO_GAS_INITIAL'] = 0.002
        else:
            pass  



    def calcDUST_TO_GAS_ITERATED(self):
        
        '''
        Fetch the iterated result of the dust-to-gas ratio from cooling.
        
        '''
        
        if not self.has_key('DUST_TO_GAS_ITERATED'):
            try:
                filename = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                        self.path_gastronoom,'models',\
                                        self['LAST_GASTRONOOM_MODEL'],\
                                        'input%s.dat'\
                                        %self['LAST_GASTRONOOM_MODEL'])
                self['DUST_TO_GAS_ITERATED'] = float(DataIO.readFile(\
                                                        filename=filename,\
                                                        delimiter=' ')[0][6])
            except IOError:
                self['DUST_TO_GAS_ITERATED'] = None
        else:
            pass  



    def getOpticalDepth(self,wavelength=0):
        
        '''
        Calculate the optical depth.
        
        If wavelength keyword is given, tau at wavelength is returned. 
        
        Otherwise, the full wavelength array is returned.
        
        @keyword wavelength: the wavelength in micron. If 0, the whole 
                             wavelength array is returned.
                             
                             (default: 0)
        @type wavelength: float
        
        @return: The optical depth at requested wavelength or the full
                 wavelength and optical depth arrays
        @rtype: float or (array,array)
        
        '''
        
        wavelength = float(wavelength)
        filename = os.path.join(os.path.expanduser('~'),'MCMax',\
                                self.path_mcmax,'models',\
                                self['LAST_MCMAX_MODEL'],'denstemp.dat')
        radius = array(DataIO.getMCMaxOutput(incr=int(self['NRAD']),\
                                             filename=filename))
        incr = int(self['NRAD'])*int(self['NTHETA'])
        dens = DataIO.getMCMaxOutput(filename=filename,incr=incr,\
                                     keyword='DENSITY')
        dens = Data.reduceArray(dens,self['NTHETA'])
        wave_list,kappas = self.readWeightedKappas()
        if wavelength:
            wave_index = argmin(abs(wave_list-wavelength))
            return integrate.trapz(y=dens*kappas[wave_index],x=radius)
        else:
            return (wave_list,array([integrate.trapz(y=dens*kappas[i],x=radius)
                                     for i in xrange(len(wave_list))]))
        
    
    def calcINCLUDE_SCAT_GAS(self):
        
        '''
        Set the keyword INCLUDE_SCAT_GAS to 0.
        
        The keyword decides whether to take into account the scattering 
        coefficients in GASTRoNOoM as if they contributed to the absorption
        coefficients. 
        
        '''
        
        if not self.has_key('INCLUDE_SCAT_GAS'):  
            self['INCLUDE_SCAT_GAS'] = 0
        else:
            pass
        
    
    def readWeightedKappas(self):
        
        '''
        Return the wavelength and kappas weighted with their respective dust 
        mass fractions.
        
        Typically you only want the absorption coefficients because GASTRoNOoM
        does not take into account scattering. You could try approximating 
        the effect of scattering on the acceleration, but at this point this is 
        not taken into account accurately.
        
        @return: The wavelength and weighted kappas grid
        @rtype: (array,array)
        
        '''
        
        wave_list,kappas = self.readKappas()
        if self['INCLUDE_SCAT_GAS']:
            #-- First the absorption coefficients of all dust species are given 
            #   Then the scattering coefficients. So iterate twice over the 
            #   dust list.
            wkappas = [sum([float(self['A_%s'%(species)])*float(kappas[i][j])
                            for i,species in enumerate(self['DUST_LIST']*2)])
                       for j in xrange(len(kappas[0]))]
        else: 
            #-- Only iterate once over the dust list to just take the 
            #   absorption coefficients.
            wkappas = [sum([float(self['A_%s'%(species)])*float(kappas[i][j])
                            for i,species in enumerate(self['DUST_LIST'])])
                       for j in xrange(len(kappas[0]))]
        return array(wave_list),array(wkappas)
        
        
    
    def calcRATIO_12C_TO_13C(self):
        
        '''
        Set default value for ratio_12c_to_13c to 0.
        
        '''
        
        if not self.has_key('RATIO_12C_TO_13C'):  
            self['RATIO_12C_TO_13C'] = 0
        else:
            pass
    


    def calcRATIO_16O_TO_17O(self):
        
        '''
        Set default value for ratio_16o_to_17o to 0.
        
        '''
        
        if not self.has_key('RATIO_16O_TO_17O'):  
            self['RATIO_16O_TO_17O'] = 0
        else:
            pass
            


    def calcRATIO_16O_TO_18O(self):
        
        '''
        Set default value for ratio_16o_to_18o to 0.
        
        '''
        
        if not self.has_key('RATIO_16O_TO_18O'):  
            self['RATIO_16O_TO_18O'] = 0
        else:
            pass    
        


    def calcOPR(self):
        
        '''
        Set default value for opr to 0.
        
        '''
        
        if not self.has_key('OPR'):  
            self['OPR'] = 0
        else:
            pass                
        


    def calcUSE_NEW_DUST_KAPPA_FILES(self):
        
        '''
        Set the default value of USE_NEW_DUST_KAPPA_FILES to 1.
        
        '''
        
        if not self.has_key('USE_NEW_DUST_KAPPA_FILES'):  
            self['USE_NEW_DUST_KAPPA_FILES'] = 1
        else:
            pass         



    def calcTEMDUST_FILENAME(self):
        
        """
        Making extinction efficiency input files for GASTRoNOoM from MCMax 
        output mass extinction coefficients.
        
        If no MCMax output available, this file is temdust.kappa, the standard.
        
        In units of cm^-1, Q_ext/a.
        
        """
        
        if not self.has_key('TEMDUST_FILENAME'):
            if self['NLAM'] > 2000:
                #- For now not supported, GASTRoNOoM cannot take more than 2000
                #- wavelength opacity points
                raise IOError('NLAM > 2000 not supported due to GASTRoNOoM '+\
                              'opacities!')    
            filename = os.path.join(os.path.expanduser('~'),'GASTRoNOoM',\
                                    'src','data','temdust_%s.dat'\
                                    %self['LAST_MCMAX_MODEL'])
            if not int(self['USE_NEW_DUST_KAPPA_FILES']) \
                    or not self['LAST_MCMAX_MODEL']:
                self['TEMDUST_FILENAME'] = 'temdust.kappa'
            elif os.path.isfile(filename):
                self['TEMDUST_FILENAME'] = os.path.split(filename)[1]
            else:
                try:
                    wavelength,q_ext = self.readWeightedKappas()
                    q_ext *= self['SPEC_DENS_DUST']*(4.0/3)
                    wavelength = list(wavelength)
                    wavelength.reverse()
                    q_ext = list(q_ext)
                    q_ext.reverse()
                    self['TEMDUST_FILENAME'] = os.path.split(filename)[1]
                    DataIO.writeCols(filename,[wavelength,q_ext])
                    print '** Made opacity file at ' + filename + '.'
                except IOError:
                    self['TEMDUST_FILENAME'] = 'temdust.kappa'
        else:
            pass    
     
    
    
    def calcR_OH1612_AS(self):
         
        '''
        Set the R_OH1612_AS to the default value of 0 as.
        
        '''
        
        if not self.has_key('R_OH1612_AS'):  
            self['R_OH1612_AS'] = 0
        else:
            pass


    
    def calcR_OH1612(self):
         
        '''
        Calculate the R_OH1612 in R_STAR.
        
        '''
        
        if not self.has_key('R_OH1612'):  
            self['R_OH1612'] = Data.convertAngular(self['R_OH1612_AS'],\
                                                   self['DISTANCE'])\
                                    /self['R_STAR']/self.Rsun
        else:
            pass         


    
    def calcR_OH1612_NETZER(self):
         
        '''
        Calculate the radial OH maser peak distance in cm.
        
        Taken from Netzer & Knapp 1987, eq. 29. 
        
        The interstellar radiation factor is taken as A = 5.4 
        (avg Habing Field)

        '''
        
        if not self.has_key('R_OH1612_NETZER'):  
            mg = self['MDOT_GAS']/1e-5
            vg = self['VEL_INFINITY_GAS']
            self['R_OH1612_NETZER'] = ((5.4*mg**0.7/vg**0.4)**-4.8\
                                        + (74.*mg/vg)**-4.8)**(-1/4.8)*1e16\
                                        /self['R_STAR']/self.Rsun
        else:
            pass         
    
    
    
    def getBlackBody(self):
        
        '''
        Calculate the black body intensity profile.
        
        @return: The wavelength and black body intensity grid
        @rtype: (array,array)
        
        '''
        
        #- Define wavelength grid in cm
        w = 10**(linspace(-9,2,5000))
        freq = self.c/w
        #- Calculate the blackbody
        bb = 2*self.h*freq**3/self.c**2 * \
             (1/(exp((self.h*freq)/(self.k*self['T_STAR']))-1))
        return w*10**(4),bb*10**(23)
    
    
    
    def getObservedBlackBody(self):
        
        '''
        Scale the blackbody intensity following the distance and stellar radius.
        
        This is not the flux!
        
        @return: The wavelength grid and rescaled blackbody intensity
        @rtype: (array,array)
        
        '''
        
        w,bb = self.getBlackBody()
        return w,bb*(self['R_STAR']*self.Rsun)**2\
                   /(self['DISTANCE']*self.pc)**2
        


    def missingInput(self,missing_key):
        
        """
        Try to resolve a missing key.
        
        @param missing_key: the missing key for which an attempt will be made 
                            to calculate its value based on already present 
                            parameters
        @type missing_key: string
        
        """
        
        if missing_key in ('T_STAR','L_STAR','R_STAR'):
            self.calcTLR()
        elif missing_key in ['R_MAX_' + species 
                             for species in self.species_list]:
            self.calcR_MAX(missing_key)
        elif missing_key in ['R_DES_' + species 
                             for species in self.species_list]:
            self.checkT()
        elif missing_key in ['T_DESA_' + species 
                             for species in self.species_list] + \
                            ['T_DESB_' + species 
                             for species in self.species_list]:
            self.calcT_DES(missing_key[7:])
        elif missing_key in ['T_DES_' + species 
                             for species in self.species_list]:
            self.checkT()
        elif hasattr(self,'calc' + missing_key):
            getattr(self,'calc' + missing_key)()
        else:
            pass

 