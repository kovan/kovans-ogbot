#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2007 by kovan 
#
#      *************************************************************************
#      *                                                                       *
#      * This program is free software; you can redistribute it and/or modify  *
#      * it under the terms of the GNU General Public License as published by  *
#      * the Free Software Foundation; either version 2 of the License, or     *
#      * (at your option) any later version.                                   *
#      *                                                                       *
#      *************************************************************************
#
import codecs

import re
import shelve, bsddb,anydbm,dbhash,dumbdbm
import copy
import cPickle
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
class ManuallyTerminated(BotError): pass
class FleetSendError(BotError): pass
class NoFreeSlotsError(FleetSendError): pass
class NotEnoughShipsError (FleetSendError):
    def __init__(self,allFleetAvailable,requested,available = None):
        self.allFleetAvailable = allFleetAvailable
        self.requested = requested
        self.available = available
    def __str__(self):
        return 'Requested: %s. Available: %s' %(self.requested,self.available)


    
class ThreadMsg(object):    pass

class BotToGuiMsg(ThreadMsg):
    def __init__(self, methodName, *args):
        self.methodName = methodName
        self.args = args
        
class GuiToBotMsg(ThreadMsg):
    stop, pause, resume = range(3)
    def __init__(self, type):
        self.type = type

        
class PlanetDb(object): 
    def __init__(self, fileName):
        self._fileName = fileName
        self._openMode = 'c'
        
    def _open(self, writeback=False):
        self._db = shelve.open(self._fileName, self._openMode, 2, writeback)
        
    def write(self, planet):
        self._open()
        self._db[str(planet.coords)] = planet
        self._db.close()
    
    def writeMany(self, planetList):   
        self._open(True)
        for planet in planetList:
            self._db[str(planet.coords)] = planet              
        self._db.close()
        
    def writeManyKeepReports(self, planetList):   
        self._open(True)
        for planet in planetList:
            coordsStr = str(planet.coords)
            planetRead = self._db.get(coordsStr)
            saved = planet.espionageHistory            
            if planetRead:
                planet.espionageHistory = planetRead.espionageHistory
            self._db[coordsStr] = planet
            planet.espionageHistory = saved
        self._db.close()    
        
    def read(self, coordsStr):
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
        def logAndPrint(self, msg):
            msg = datetime.now().strftime("%X %x ") + msg
            print msg
            logging.info(msg)    
        def dispatch(self, methodName, *args):
            if self.gui:
                msg = BotToGuiMsg(methodName, *args)
                self.gui.msgQueue.put(msg)
                
        
class Configuration(dict):
    def __init__(self, file):
        self.file = file
        self.configParser = ConfigParser.SafeConfigParser()
        self.configParser.optionxform = str # prevent ini parser from converting vars to lowercase         
        self.loadDefaults()
    def loadDefaults(self):
        self['universe'] = 0
        self['username'] = ''
        self['password'] = ''
        self['webpage'] = 'ogame.com.es'      
        self['attackRadius'] = 10
        self['slotsToReserve'] = 0
        self['attackingShip'] = 'smallCargo'
        self['sourcePlanets'] = []
        self['playersToAvoid'] = []       
        self['probesToSend'] = 1
        self['alliancesToAvoid'] = []       
        self['systemsPerGalaxy'] = 499
        self['proxy'] = ''
        self['userAgent'] = 'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)'
        self['rentabilityFormula'] = '(metal + 1.5 * crystal + 3 * deuterium) / flightTime'
        
    def __getattr__(self, attrName):
        return self[attrName]
        
    def load(self):
        if not os.path.isfile(self.file):
            raise BotFatalError("File %s does not exist" % self.file)
            
        self.configParser.read(self.file)
        for section in self.configParser.sections():
            self.update(self.configParser.items(section))
        
        self['webpage'] = self['webpage'].replace("http://", "")
        self['proxy'] = self['proxy'].replace("http://", "")        
        
        from GameEntities import Coords
        sourcePlanets = []
        if self.configParser.has_option('options', 'sourcePlanets'):
            if '[]' not in self['sourcePlanets']:
                for coordsStr in self['sourcePlanets'].split(','):
                    coords = Coords(coordsStr)
                    sourcePlanets.append(coords)
        self['sourcePlanets'] = sourcePlanets



        if isinstance(self['playersToAvoid'],str):
            self['playersToAvoid'] = self._parseList(self['playersToAvoid'])
        if isinstance(self['alliancesToAvoid'],str):            
            self['alliancesToAvoid'] = self._parseList(self['alliancesToAvoid'])        

        try:
            if not self.username or not self.password or not self.webpage or not self.universe:
                raise BotError("Empty username, password, universe or webpage.")
        except Exception:
                raise BotError("Missing username, password, universe or webpage.")            
        
        from Constants import INGAME_TYPES_BY_NAME
        if self['attackingShip'] not in INGAME_TYPES_BY_NAME.keys():
            raise BotError("Invalid attacking ship type.")
        
        from GameEntities import Resources
        resources = Resources(10000,8000,7000)
        try:
            resources.rentability(10000,self.rentabilityFormula)
        except Exception, e:
            raise BotError("Invalid rentability formula: " + str(e))
        
        if 'ogame.com.es' in self.webpage and self.universe == 42:
            raise BotError("Bot doesn't work in that universe.")
            
    def _parseList(self,listStr):
        list = []
        for item in listStr.split(','):
            item = item.strip('''[] ,'"''')
            if item : list.append(item)
        return list
        
    def save(self):      
        if not self.configParser.has_section('options'):
            self.configParser.add_section('options')

        for key, value in self.items():
            self.configParser.set('options', key, str(value))
        self.configParser.write(open(self.file, 'w'))

    
class Translations(dict):
    def __init__(self):
        for fileName in os.listdir('languages'):
            fileName, extension = os.path.splitext(fileName)

            if not fileName or fileName.startswith('.') or extension != '.ini':
                continue
            parser = ConfigParser.SafeConfigParser()
            parser.optionxform = str # prevent ini parser from converting names to lowercase           
            try:
                #file = codecs.open('languages/'+fileName+extension, "r", "utf-8" ) # language files are codified in UTF-8
                parser.read('languages/'+fileName+extension)
                translation = {}
                for section in parser.sections():
                    translation.update((key, value) for key, value in parser.items(section))
                self[translation['languageCode']] = translation 
            except Exception, e: 
                raise BotError("Malformed languaje file (%s%s): %s"%(fileName,extension,e))
        # after all this access to a translated string is obtained thru p.e.: self['es']['smallCargo']
        
class ResourceSimulation(object):
    def __init__(self, baseResources, mines):
        self.simulatedResources = copy.copy(baseResources)

        if mines is not None:
            self._metalMine = mines.get('metalMine', 0)
            self._crystalMine = mines.get('crystalMine', 0)
            self._deuteriumSynthesizer = mines.get('deuteriumSynthesizer', 0)
        else:
            self._metalMine, self._crystalMine, self._deuteriumSynthesizer = 22, 19, 11
            
    def _setResources(self, resources):
        self._resourcesSimulationTime = datetime.now() # no need to use server time because it's use is isolated to inside this class
        self._baseResources = resources         
        
    def _calculateResources(self):
        productionTime = datetime.now() - self._resourcesSimulationTime
        productionHours = productionTime.seconds / 3600.0
        from GameEntities import Resources
        produced = Resources()
        produced.metal      = 30 * self._metalMine      * 1.1 ** self._metalMine      * productionHours
        produced.crystal   = 20 * self._crystalMine   * 1.1 ** self._crystalMine   * productionHours
        produced.deuterium = 10 * self._deuteriumSynthesizer * 1.1 ** self._deuteriumSynthesizer * productionHours * (-0.002 * 60 + 1.28) # 60 is the temperature of a planet in position 7
        return self._baseResources + produced
            
    simulatedResources = property(_calculateResources, _setResources)         
    
        
class Enum(object):
    @classmethod
    def toStr(self, type):
        return [i for i in self.__dict__ if getattr(self, i) == type][0]    
    

def sleep(seconds):
    
    for dummy in range(0, random.randrange(seconds, seconds+4)):
        time.sleep(1)
        
def addCommas(number):
    return re.sub(r"(\d{3}\B)", r"\1,", str(number)[::-1])[::-1]


