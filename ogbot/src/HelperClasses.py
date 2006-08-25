#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#     Kovan's OGBot
#     Copyright (c) 2006 by kovan 
#
#     *************************************************************************
#     *                                                                       *
#     * This program is free software; you can redistribute it and/or modify  *
#     * it under the terms of the GNU General Public License as published by  *
#     * the Free Software Foundation; either version 2 of the License, or     *
#     * (at your option) any later version.                                   *
#     *                                                                       *
#     *************************************************************************
#

import re
import shelve
import copy
import pickle
import logging
import ConfigParser
from datetime import datetime
import sys
import os.path

class Spaceship(object):
    def __init__(self,name,capacity, code, consumption):
        self.name = name
        self.capacity = capacity
        self.code = code
        self.consumption = consumption
    def __repr__(self):
        return self.name
    
class BotError(Exception): pass
class BotFatalError (BotError): pass
class FleetSendError(BotError): pass
class ZeroShipsError (FleetSendError): pass
class NoFreeSlotsError(FleetSendError): pass
class ManuallyTerminated(BotFatalError): pass


SHIP_TYPES = {
    'smallCargo' :     Spaceship('smallCargo', 5000, 'ship202', 20),
    'largeCargo' :     Spaceship('largeCargo', 25000, 'ship203', 50),
    'lightFighter' :   Spaceship('lightFighter',50,'ship204', 20),
    'heavyFighter' :   Spaceship('heavyFighter',100,'ship205', 75),
    'cruiser' :        Spaceship('cruiser',800,'ship206', 300),
    'battleShip' :     Spaceship('battleship',1500,'ship207', 500),
    'colonyShip' :     Spaceship('colonyShip',7500,'ship208',1000),    
    'recycler' :       Spaceship('recycler',20000,'ship209', 300),
    'espionageProbe' : Spaceship('espionageProbe',5,'ship210', 1),
    'bomber' :         Spaceship('bomber',500,'ship211',1000),
    'destroyer' :      Spaceship('destroyer',2000,'ship213',1000),
    'deathStar' :      Spaceship('deathStar',1000000,'ship214',1)
}

class MissionTypes(object):
    unknown   = 0
    attack    = 1
    transport = 3    
    deploy    = 4
    spy       = 6
    # colonize, recycle, 
class PlanetTypes(object):
    unknown = 0
    normal  = 1
    debris  = 2
    moon    = 3

    
class ThreadMsgTypes(object): 
    stop,pause,resume = range(3)

class Coords(object):
    GALAXIES = 9
    SOLAR_SYSTEMS = 499
    PLANETS_PER_SYSTEM = 15
    REGEXP_COORDS    = re.compile(r"([1-9]):([0-9]{1,3}):([0-9]{1,2})")
    
    def __init__(self,galaxy=0,solarSystem=0,planet=0,planetType=PlanetTypes.normal):
        self.galaxy = int(galaxy)
        self.solarSystem = int(solarSystem)
        self.planet = int(planet)
        self.planetType = planetType

    def parse(self,newCoords):
        match = self.REGEXP_COORDS.search(newCoords)
        if not match:
            raise BotError("Error parsing coords: " + newCoords)
        self.galaxy,self.solarSystem,self.planet = match.groups()

    def __repr__(self):
        return "%-10s" % ("[%s:%s:%s]" % (self.galaxy,self.solarSystem,self.planet))
    
    def __eq__(self,otherCoords):
        return str(self) == str(otherCoords)
    
    def __ne__(self,otherCoords):
        return str(self) != str(otherCoords)

    def increment(self):
        self.planet += 1
        if self.planet > self.PLANETS_PER_SYSTEM:
            self.planet = 1
            self.incrementSolarSystem()
    def incrementSolarSystem(self):
        self.solarSystem += 1
        if self.solarSystem > self.SOLAR_SYSTEMS:
            self.solarSystem = 1
            self.incrementGalaxy()
    def incrementGalaxy(self):
        self.galaxy += 1
        if self.galaxy > self.GALAXIES:
            self.galaxy = 1

class Resources(object):
    def __init__(self,metal=0, crystal=0, deuterium=0):
        self.metal = int(metal)
        self.crystal = int(crystal)
        self.deuterium = int(deuterium)

    def total(self):
        return self.metal + self.crystal + self.deuterium
    def metalEquivalent(self):
        return int(self.metal + 1.5 * self.crystal + 3 * self.deuterium)
    def half(self):
        return Resources(self.metal/2, self.crystal/2, self.deuterium/2)
    def __repr__(self):
        return "M: %s C: %s D: %s" % (self.metal, self.crystal, self.deuterium)

class Planet(object):
    def __init__(self,coords, code=0, name=""):
        self.coords = coords
        self.name = name
        self.code = code

    def __repr__(self):
        return self.name + " " + str(self.coords)



class EnemyPlanet (Planet):
    def __init__(self,coords,owner="",ownerstatus="",name="",alliance="",code=0):# CUIDADO SE CREA UNA LISTA COMUN PARA TODOS: spyReports = [] !!!!!!!):
        Planet.__init__(self,coords, code, name)
        self.owner = owner
        self.alliance = alliance
        self.ownerStatus = ownerstatus
        self.spyReports = []
        

        
    def toStringList(self):
        return [str(self.coords),self.name,self.owner,self.alliance]
        
class Wave(object):
    def __init__(self,shipCount, resourcesToSteal):
        self.shipCount = shipCount
        self.resourcesToSteal = resourcesToSteal
        
class GameMessage(object):
    def __init__(self,code):
        self.code = code

class SpyReport(GameMessage):
    def __init__(self,coords,planetName,date,resources,code,fleet=None,defense=None,buildings=None,research=None):
        GameMessage.__init__(self,code)
        self.coords = coords
        self.planetName = planetName
        self.date = date
        self.resources = resources
        self.fleet = fleet
        self.defense = defense
        self.buildings = buildings
        self.research = research
        self.attackWaves = []
        self.probesSent = 0
        self.actionTook = 'None'
    
    def __repr__(self):
        return "%s %s %s %s %s %s %s %s" % (self.planetName, self.coords, self.date, self.resources, self.fleet, self.defense, self.buildings, self.research)
    
    def hasFleet(self):
        return self.fleet != None and len(self.fleet) > 0
    
    def hasDefense(self):
        return self.defense != None and len(self.defense) > 0
    
    def hasNonMissileDefense(self):
        if self.defense is None:
            return True
        for defense in self.defense.keys():
            if  defense != _("Misil de intercepción") \
            and defense != _("Misil interplanetario"):
                return True
        return False
    
    def hasInfoAbout(self,info):
        if info not in ["fleet","defense","buildings","research"]:
            raise BotError()
        var = getattr(self, info)
        if  var is None:   return "Unknown"
        elif len(var) == 0: return "No"
        else: return "Yes"        
        
    def calculateAttackWaves(self,attackingShip,minimumRobbery):
        self.attackWaves = []
        remainingResources = self.resources.total()
        
        while remainingResources/2 >= minimumRobbery :
            shipCount = ((remainingResources / 2) + 5000) // attackingShip.capacity # add 5000 for carring voyage fuel and for the resources the planet has produced till the attack arrives
            wave = Wave(shipCount,remainingResources // 2)            
            remainingResources /= 2
            self.attackWaves.append(wave)                    

# waves calculation with metal-equivalent units:
#        self.attackWaves = []
#        remainingResources = copy.copy(self.resources)
#        
#        while remainingResources.half().metalEquivalent() >= minimumRobbery :
#            half = remainingResources.half()
#            shipCount = (half.total() + 5000) / attackingShip.capacity # add 5000 for carring voyage fuel and for the resources the planet has produced till the attack arrives
#            wave = Wave(shipCount,half.total())    
#            remainingResources = half
#            self.attackWaves.append(wave)

    
    def calculateAge(self):
        return abs(datetime.now() - self.date)
            
    def calculateResourcesByNow(self,minTheft):

        if self.buildings:
            #mines:
            speculated = False
            metalMine = self.buildings.get(_("Mina de metal"))
            crystalMine = self.buildings.get(_("Mina de cristal"))
            deuteriumMine = self.buildings.get(_("Sintetizador de deuterio"))
            if not metalMine: metalMine = 0            
            if not crystalMine: crystalMine = 0                
            if not deuteriumMine: deuteriumMine = 0
        else:
            speculated = True
            metalMine,crystalMine,deuteriumMine = 20,17,10
        
        if "Attacked" in self.actionTook:
            previousResources = minTheft # at most we left that resources in the planet
        else : previousResources = self.resources.total()
        
        hoursPassed = self.calculateAge().seconds / 3600.0
        metalProduced     = 30 * metalMine     * 1.1 ** metalMine     * hoursPassed
        crystalProduced   = 20 * crystalMine   * 1.1 ** crystalMine   * hoursPassed
        deuteriumProduced = 10 * deuteriumMine * 1.1 ** deuteriumMine * hoursPassed * (-0.002 * 60 + 1.28) # 60 is the temperature of a planet in position 7
        maxResourcesByNow = previousResources + metalProduced + crystalProduced + deuteriumProduced
        return speculated,  int(maxResourcesByNow)
                
        
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
        self['minTheft'] = 30000 

                
    def load(self):
        if not os.path.isfile(self.file):
            raise BotError("File %s does not exist" % self.file)
            
        # parse file
        self.configParser.read(self.file)

        # quit Bot if mandatory parameters are missing in the .ini
        if not self.configParser.has_option('general','universe') \
        or not self.configParser.has_option('general','username') \
        or not self.configParser.has_option('general','password') \
        or not self.configParser.has_option('general','webpage'):        
            raise BotError("Mandatory parameter(s) missing in config.ini file")

        for section in self.configParser.sections():
            self.update(self.configParser.items(section))
            
        self['webpage'] = self['webpage'].replace("http://","")
        if self['attackingShip'] not in SHIP_TYPES.keys():
            raise BotError("Invalid attacking ship type in config.ini file")
        
    def save(self):
        for section in 'general','automated attacks':
            if not self.configParser.has_section(section):
                self.configParser.add_section(section)
        for option in 'universe','webpage','username','password':
            self.configParser.set('general', option, str(self[option]))
        for option in 'attackRadio','probesToSend','minTheft','attackingShip':
            self.configParser.set('automated attacks', option, str(self[option]))        
        self.configParser.write(open(self.file,'w'))
        
class PlanetDb(object): # not used
    def __init__(self,fileName):
        self._fileName = fileName
        self._openMode = 'c'
        
    def _open(self,writeback=False):
        self._db = shelve.open(self._fileName,self._openMode,pickle.HIGHEST_PROTOCOL)
        
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