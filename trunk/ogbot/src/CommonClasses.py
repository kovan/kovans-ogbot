#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#          Kovan's OGBot
#          Copyright (c) 2006 by kovan 
#
#          *************************************************************************
#          *                                                                                                                                             *
#          * This program is free software; you can redistribute it and/or modify  *
#          * it under the terms of the GNU General Public License as published by  *
#          * the Free Software Foundation; either version 2 of the License, or          *
#          * (at your option) any later version.                                                                      *
#          *                                                                                                                                             *
#          *************************************************************************
#


import re
import shelve
import copy
import pickle
import logging
import time
import ConfigParser
from datetime import datetime
import sys
import math
import os.path
import random



class BotError(Exception): pass
class BotFatalError (BotError): pass
class FleetSendError(BotError): pass
class NotEnoughShipsError (FleetSendError): pass
class NoFreeSlotsError(FleetSendError): pass
class ManuallyTerminated(BotError): pass

    
class ThreadMsg(object):    pass

class BotToGuiMsg(ThreadMsg):
    def __init__(self,methodName,*args):
             self.methodName = methodName
             self.args = args
             
class GuiToBotMsg(ThreadMsg):
    stop,pause,resume = range(3)
    def __init__(self,type):
             self.type = type

             
class PlanetDb(object): 
    def __init__(self,fileName):
             self._fileName = fileName
             self._openMode = 'c'
             
    def _open(self,writeback=False):
             self._db = shelve.open(self._fileName,self._openMode,pickle.HIGHEST_PROTOCOL,writeback)
             
    def write(self,planet):
             self._open()
             self._db[str(planet.coords)] = planet
             self._db.close()
             
    def writeMany(self,planetList):    
             self._open(True)
             for planet in planetList:
                      self._db[str(planet.coords)] = planet                      
             self._db.close()
                                        
    def read(self,coordsStr):
             self._open()             
             planet = self._db.get(coordsStr)
             self._db.close()    
             return planet
    
    def readAll(self):
             self._open()    
             list = self._db.values()    
             self._db.close()             
             return list
    
    
class BaseEventManager(object):
             ''' Displays events in console, logs them to a file or tells the gui about them'''
             def logAndPrint(self,msg):
                      msg = datetime.now().strftime("%X %x ") + msg
                      print msg
                      logging.info(msg)    
             def dispatch(self,methodName,*args):
                      if self.gui:
                               msg = BotToGuiMsg(methodName,*args)
                               self.gui.msgQueue.put(msg)
                               
             
class Configuration(dict):
    def __init__(self,file):
             self.file = file
             self.configParser = ConfigParser.SafeConfigParser()
             self.configParser.optionxform = str # prevent ini parser from converting vars to lowercase             
             self.loadDefaults()
    def loadDefaults(self):
             self['universe'] = 0
             self['username'] = ''
             self['password'] = ''
             self['webpage'] = 'ogame.com.es'
             self['attackRadio'] = 20
             self['probesToSend'] = 3
             self['attackingShip'] = 'smallCargo'
    def __getattr__(self,attrName):
             return self[attrName]
             
    def load(self):
             if not os.path.isfile(self.file):
                      raise BotError("File %s does not exist" % self.file)
                      
             # parse file
             self.configParser.read(self.file)

             # quit Bot if mandatory parameters are missing in the .ini
             if not self.configParser.has_option('options','universe') \
             or not self.configParser.has_option('options','username') \
             or not self.configParser.has_option('options','password') \
             or not self.configParser.has_option('options','webpage'):             
                      raise BotError("Mandatory parameter(s) missing in config.ini file")

             for section in self.configParser.sections():
                      self.update(self.configParser.items(section))
                      
             self['webpage'] = self['webpage'].replace("http://","")
             from Constants import INGAME_TYPES_BY_NAME
             if self['attackingShip'] not in INGAME_TYPES_BY_NAME.keys():
                      raise BotError("Invalid attacking ship type in config.ini file")
             
    def save(self):
             if not self.configParser.has_section('options'):
                      self.configParser.add_section('options')
             
             for key,value in self.items():
                      self.configParser.set('options', key,str(value))
             self.configParser.write(open(self.file,'w'))

    
class Enum(object):
    @classmethod
    def toStr(self,type):
             return [i for i in self.__dict__ if getattr(self,i) == type][0]    
    

def sleep(seconds):
    for dummy in range(0,random.randrange(seconds-5,seconds+5)):
             time.sleep(1)