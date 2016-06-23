# -*- coding: utf-8 -*-

"""
A tool set for reading all kinds of output/input/data.

Author: R. Lombaert

"""

from cc.tools.io import DataIO



class Reader(object):
    
    ''' 
    The Reader class.
    
    Will read in the /data/input/outputfiles that are given to this class and 
    store them.
    
    '''
    
    def __init__(self):
        
        ''' 
        Initialize an Reader object by setting the contents dict.
        
        '''
        
        self.contents = dict()
        
    
    
    def readFile(self, filename, delimiter = ' ', replace_spaces=1):
        
        '''
        Read a filename and store its contents in the Reader object.
        
        The contents are stored in a dictionary, with the filename as key.
        
        The contents can be returned when running getFile.
        
        @param filename: The filename of the outputfile, including filepath
        @type filename: string
        @keyword delimiter: The delimiter character used in this file. 
        
                            (default: ' ')
        @type delimiter: string
        @keyword replace_spaces: Replace any number of spaces or tabs by just 1
                                 space. If delimiter == ' ', then replace_spaces
                                 is always active.
                             
                                 (default: 1)
        @type replace_spaces: bool 
    
        '''
        try:
            self.contents[filename] = DataIO.readFile(filename, delimiter, \
                                                      replace_spaces)
        except IOError:
            self.contents[filename] = None
            
    
    
    def getFile(self,filename):
        
        '''
        Return the contents of the filename. 
        
        @param filename: the full filename including filepath
        @type filename: string
        @return: a list of lines in the file, each line represented by a list 
                 of strings, which were seperated by the chosen delimiter. 
        @rtype: list
        
        '''
        
        if not self.contents.has_key(filename):
            self.readFile(filename)
        return self.contents[filename]