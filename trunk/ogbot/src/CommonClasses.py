#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2010 by kovan 
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
import ConfigParser
import sys
import math
import os.path
import random
import threading
from time import strptime,sleep
from datetime import *


class BotError(Exception): pass
class BotFatalError (BotError): pass
class ManuallyTerminated(BotError): pass
class FleetSendError(BotError): pass
class FleetLaunchAbortedError(FleetSendError): pass 
class NoFreeSlotsError(FleetSendError):    
    def __str__(self): return "No fleet slots available"
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
    stop, pause, resume, attackLargeCargo,attackSmallCargo, spy = range(6)
    def __init__(self, type, param = None):
        self.type = type
        self.param = param

        
class PlanetDb(object): 
    _lock = threading.Lock()
    def __init__(self, fileName):
        self._fileName = fileName
        self._openMode = 'c'
        
        
    def _open(self):
        PlanetDb._lock.acquire()                
        self.db = shelve.open(self._fileName, self._openMode, 2, True)
    def _close(self):
        self.db.close()
        PlanetDb._lock.release()      
                  
    def write(self, planet):
        self._open()
        self.db[str(planet.coords)] = planet
        self._close()
    
    def writeMany(self, planetList):   
        self._open()
        for planet in planetList:
            self.db[str(planet.coords)] = planet              
        self._close()
        
    def read(self, coordsStr):
        self._open()         
        planet = self.db.get(coordsStr)
        self._close()          
        return planet
    
    def readAll(self):
        self._open()    
        list = self.db.values()    
        self._close()         
        return list
    
    def search(self,predicate):
        list = []
        self._open()    
        for planet in self.db.itervalues():
            if predicate(planet):
                list.append(planet)
        self._close()         
        return list    
    
class BaseEventManager(object):
        ''' Displays events in console, logs them to a file or tells the gui about them'''
        def __init__(self,gui = None):
            self.loginsInARow = 0
            self.gui = gui
            
        def logAndPrint(self, msg):
            msg = datetime.now().strftime("%c ") + msg
            print msg
            logging.info(msg)    
        def dispatch(self, methodName, *args):
            if self.gui:
                msg = BotToGuiMsg(methodName, *args)
                self.gui.msgQueue.put(msg)
                            
            # Hack to detect login loop
            if 'activityMsg' in methodName and 'Logged in' in args[0]:
                self.loginsInARow += 1
                if self.loginsInARow >= 3:
                    raise BotError("Infinite login loop (This is not a bug).")
            else: self.loginsInARow = 0
            

                
        
class Configuration(dict):
    def __init__(self, file):
        self.file = file
        self.configParser = ConfigParser.SafeConfigParser()
        self.configParser.optionxform = str # prevent ini parser from converting vars to lowercase         
        self.loadDefaults()
        
    def loadDefaults(self): 
        pass
    def __getattr__(self, attrName):
        return self[attrName]
    
    def load(self):
        if not os.path.isfile(self.file):
            raise BotFatalError("File %s does not exist" % self.file)
            
        self.configParser.read(self.file)
        for section in self.configParser.sections():
            self.update(self.configParser.items(section))
        
    def _parseListOfDictionary(self, dictionaryStr):
        dictionaryStr = dictionaryStr.replace('\n','')[1:-1]
        list = []
        dictionary = {}
        for dict in dictionaryStr.split('}'):
            if len(dict) > 1: 
                dictionary = self._parseDictionary(dict)
                list.append(dictionary) 
        return list  

    def _parseDictionary(self, listStr):
        dictionary = {}
        value = None
        for item in listStr.split(','):
                for subitem in item.split(':'):
                        subitem = subitem.strip('''{} ,'"''') # "
                        if value:
                                dictionary[value] = subitem
                                value = None
                        else: value = subitem
        return dictionary

    def _parseList(self,listStr):
        mylist = []
        for item in listStr.split(','):
            item = item.strip('''[] ,'"''') #"
            if item : mylist.append(item)
        return mylist

    def _parseTime(self,timeStr):
        return time(*strptime(timeStr,"%H:%M:%S")[3:6])
        
    def save(self):    
        if not self.configParser.has_section('options'):
            self.configParser.add_section('options')

        for key, value in self.items():
            self.configParser.set('options', key, str(value))
        self.configParser.write(open(self.file, 'w'))

                
class BotConfiguration (Configuration):
    def loadDefaults(self):
        super(BotConfiguration, self).loadDefaults() 
        self['username'] = ''
        self['password'] = ''
        self['waitBetweenAttackChecks'] = 45
        self['webpage'] = 'ogame.org'      
        self['attackRadius'] = 10
        self['slotsToReserve'] = 0
        self['attackingShip'] = 'smallCargo'
        self['sourcePlanets'] = ''
        self['playersToAvoid'] = ''       
        self['probesToSend'] = 1
        self['alliancesToAvoid'] = ''       
        self['systemsPerGalaxy'] = 499
        self['proxy'] = ''
        self['userAgent'] = 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
        self['rentabilityFormula'] = '(metal + 1.5 * crystal + 3 * deuterium) / flightTime'
        self['preMidnightPauseTime'] = '22:00:00'
        self['inactivesAppearanceTime'] = '0:06:00'        
        self['deuteriumSourcePlanet'] = ''
        self['maxProbes'] = 15  
        self['fleetPoint'] = '[{}]'
        self['buildingPoint'] = '[{}]'      
        self['defensePoint'] = '[{}]'
        self['researchPoint'] = '[{}]'
        
    def load(self):
        super(BotConfiguration, self).load()        

        for time in ('preMidnightPauseTime','inactivesAppearanceTime'):
            self[time] = self._parseTime(self[time])

        for url in ('webpage','proxy'):
            self[url] = self[url].replace("http://", "")

        for listName in ('buildingPoint','fleetPoint','defensePoint','researchPoint'):
            self[listName] = self._parseListOfDictionary(self[listName])

        for listName in ('playersToAvoid','alliancesToAvoid','sourcePlanets'):
            self[listName] = self._parseList(self[listName])

        from GameEntities import Coords
        for coordsStr in self['sourcePlanets'][:]:
            self['sourcePlanets'].remove(coordsStr)
            self['sourcePlanets'].append(Coords(coordsStr))

        try: self['deuteriumSourcePlanet'] =  Coords(self['deuteriumSourcePlanet'])
        except ValueError: pass

        try:
            if not self.username or not self.password or not self.webpage:
                raise BotError("Empty username, password or webpage.")
        except Exception:
            raise BotError("Missing username, password or webpage.")            
        
        
        if self['attackingShip'] not in ("smallCargo","largeCargo"):
            raise BotError("Invalid attacking ship type.")

        # needed for exec statement
        from GameEntities import EnemyPlanet

        try:
            metal, crystal, deuterium, flightTime = 1,1,1,1
            exec self.rentabilityFormula
        except Exception, e:
            raise BotError("Invalid rentability formula: " + str(e))

    
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
                raise BotError("Malformed language file (%s%s): %s"%(fileName,extension,e))
        # after all this access to a translated string is obtained thru p.e.: self['es']['smallCargo']
        
class ResourceSimulation(object):
    def __init__(self, baseResources, mines):
        self.simulatedResources = copy.copy(baseResources)

        if mines is not None:
            self._metalMine = mines.get('metalMine', 0)
            self._crystalMine = mines.get('crystalMine', 0)
            self._deuteriumSynthesizer = mines.get('deuteriumSynthesizer', 0)
        else:
            self._metalMine, self._crystalMine, self._deuteriumSynthesizer = 16, 14, 9
            
    def _setResources(self, resources):
        self._resourcesSimulationTime = datetime.now() # no need to use server time because it's use is isolated to inside this class
        self._baseResources = resources         
        
    def _getResources(self):
        productionTime = datetime.now() - self._resourcesSimulationTime
        return self._baseResources + self.calculateProduction(productionTime)
            
    simulatedResources = property(_getResources, _setResources)         
    
    def calculateProduction(self,timeInterval):
        productionHours = timeInterval.seconds / 3600.0
        from GameEntities import Resources        
        produced = Resources()
        produced.metal      = 30 * self._metalMine      * 1.1 ** self._metalMine      * productionHours
        produced.crystal   = 20 * self._crystalMine   * 1.1 ** self._crystalMine   * productionHours
        produced.deuterium = 10 * self._deuteriumSynthesizer * 1.1 ** self._deuteriumSynthesizer * productionHours * (-0.002 * 60 + 1.28) # 60 is the temperature of a planet in position 7
        return produced * 0.95
 

class PlanetList(dict):       
    def __init__(self,planets = None):
        if planets:
            if not isinstance(planets,dict):
                planets = dict([(str(p.coords),p) for p in planets])
            self.update(planets)
                
    
    def append(self,planet):
        self[str(planet.coords)] = planet
    
    def save(self,filePath):
        cPickle.dump(self,open(filePath, 'wb'),2)
    
    def load(self,filePath):
        self.clear()        
        try:
            loaded = cPickle.load(open(filePath, 'rb'))
        except (EOFError, IOError):
            loaded = {}
            try:os.remove(filePath)          
            except Exception : pass                
        self.update(loaded)
        
class Plugin(object):
    def __init__(self):
        pass

class Struct(object):
    def __init__(self, **entries): self.__dict__.update(entries)    
        
class Enum(object):
    @classmethod
    def toStr(klass, type):
        return [i for i in klass.__dict__ if getattr(klass, i) == type][0]    
    

def mySleep(seconds):
    for dummy in range(0, random.randrange(seconds, seconds+10)):
        sleep(1)
        
def addCommas(number):
    return re.sub(r"(\d{3}\B)", r"\1,", str(number)[::-1])[::-1]


