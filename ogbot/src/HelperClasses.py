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
import time
import ConfigParser
from datetime import datetime
import sys
import math
import os.path
import random

class IngameType(object):
    def __init__(self,name,fullName,code):
        self.name = name        
        self.fullName = fullName
        self.code = code    
    def __repr__(self):
        return self.fullName    
    
class Ship(IngameType):
    def __init__(self,name,fullName,code,capacity,consumption):
        IngameType.__init__(self,name,fullName,code)
        self.capacity = capacity        
        self.consumption = consumption
class Building(IngameType):
    def __init__(self,name,fullName, code):
        IngameType.__init__(self,name,fullName,code)        
class Defense(IngameType):
    def __init__(self,name,fullName, code):
        IngameType.__init__(self,name,fullName,code)        
class Research(IngameType):
    def __init__(self,name,fullName, code):
        IngameType.__init__(self,name,fullName,code)        
    


INGAME_TYPES = [
    Ship('smallCargo',_('Nave pequeña de carga'), 'ship202', 5000, 20),
    Ship('largeCargo',_('Nave grande de carga'), 'ship203', 25000, 50),
    Ship('lightFighter',_('Cazador ligero'),'ship204', 50, 20),
    Ship('heavyFighter',_('Cazador pesado'),'ship205', 100, 75),
    Ship('cruiser',_('Crucero'),'ship206', 800, 300),
    Ship('battleShip',_('Nave de batalla'),'ship207', 1500, 500),
    Ship('colonyShip',_('Colonizador'),'ship208', 7500,1000), 
    Ship('recycler',_('Reciclador'),'ship209', 20000, 300),
    Ship('espionageProbe',_('Sonda de espionaje'),'ship210', 5, 1),
    Ship('bomber',_('Bombardero'),'ship211', 500,1000),
    Ship('solarSatellite',_('Satélite solar'),'ship212', 0,0), 
    Ship('destroyer',_('Destructor'),'ship213', 2000,1000),
    Ship('deathStar',_('Estrella de la muerte'),'ship214', 1000000,1),
    
    Building('metalMine',_("Mina de metal"),1), 
    Building('crystalMine',_("Mina de cristal"),2), 
    Building('deuteriumSynthesizer',_("Sintetizador de deuterio"),3), 
    Building('solarPlant',_("Planta de energía solar"),4), 
    Building('fusionReactor',_("Planta de fusión"),12),
    Building('roboticsFactory',_("Fábrica de Robots"),14),
    Building('naniteFactory',_("Fábrica de nanobots"),15), 
    Building('shipyard',_("Hangar"),21), 
    Building('metalStorage',_("Almacén de metal"),22), 
    Building('crystalStorage',_("Almacén de cristal"),23), 
    Building('deuteriumTank',_("Contenedor de deuterio"),24), 
    Building('researchLab',_("Laboratorio de investigación"),31), 
    Building('terraformer',_("Terraformer"),33), 
    Building('allianceDepot',_("Depósito de la alianza"),34), 
    Building('lunarBase',_("Base lunar"),41), 
    Building('sensorPhalanx',_("Sensor Phalanx"),42), 
    Building('jumpGate',_("Salto cuántico"),43), 
    Building('missileSilo',_("Silo"),44), 
    
    Defense('rocketLauncher',_('Lanzamisiles'),401), 
    Defense('lightLaser',_('Láser pequeño'),402),
    Defense('heavyLaser',_('Láser grande'),403), 
    Defense('gaussCannon',_('Cañón Gauss'),404), 
    Defense('ionCannon',_('Cañón iónico'),405), 
    Defense('plasmaTurret',_('Cañón de plasma'),406), 
    Defense('smallShieldDome',_('Cúpula pequeña de protección'),407),
    Defense('largeShieldDome',_('Cúpula grande de protección'),408), 
    Defense('antiBallisticMissile',_('Misil de intercepción'),502), 
    Defense('interplanetaryMissile',_('Misil interplanetario'),503),
    
    Research('espionageTechnology',_('Tecnología de espionaje'),106),
    Research('computerTechnology',_('Tecnología de computación'),108),
    Research('weaponsTechnology',_('Tecnología militar'),109),
    Research('shieldingTechnology',_('Tecnología de defensa'),110),
    Research('armourTechnology',_('Tecnología de blindaje'),111),
    Research('energyTechnology',_('Tecnología de energía'),113),
    Research('hyperspaceTechnology',_('Tecnología de hiperespacio'),114),
    Research('combustionDrive',_('Motor de combustión'),115),
    Research('impulseDrive',_('Motor de impulso'),117),
    Research('hyperspaceDrive',_('Propulsor hiperespacial'),118),
    Research('laserTechnology',_('Tecnología láser'),120),
    Research('ionTechnology',_('Tecnología iónica'),121),
    Research('plasmaTechnology',_('Tecnología de plasma'),122),
    Research('intergalacticResearchNetwork',_('Red de investigación intergaláctica'),123),
    Research('gravitonTechnology',_('Tecnología de gravitón'),199),
]

INGAME_TYPES_BY_NAME = dict([ (type.name,type) for type in INGAME_TYPES  ])
INGAME_TYPES_BY_CODE = dict([ (type.code,type) for type in INGAME_TYPES  ])
INGAME_TYPES_BY_FULLNAME = dict([ (type.fullName,type) for type in INGAME_TYPES  ])

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

class Planet(object):
    def __init__(self,coords, code=0, name=""):
        self.coords = coords
        self.name = name
        self.code = code

    def __repr__(self):
        return self.name + " " + str(self.coords)


class Coords(object):
    class Types(object):
        unknown = 0
        normal  = 1
        debris  = 2
        moon    = 3
    
    GALAXIES = 9
    SOLAR_SYSTEMS = 499
    PLANETS_PER_SYSTEM = 15
    REGEXP_COORDS    = re.compile(r"([1-9]):([0-9]{1,3}):([0-9]{1,2})")
    
    def __init__(self,galaxy=0,solarSystem=0,planet=0,planetType=Types.normal):
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
        
    
    def calculateRentability(self,systemsAway): 
        referenceFlightTime = 3500 * math.sqrt((systemsAway * 5 * 19 + 2700) * 10 / 20000) + 10
        return self.metalEquivalent() / referenceFlightTime
    
    def total(self):
        return self.metal + self.crystal + self.deuterium
    def metalEquivalent(self):
        return int(self.metal + 1.5 * self.crystal + 3 * self.deuterium)
    def half(self):
        return Resources(self.metal/2, self.crystal/2, self.deuterium/2)
    
    def __repr__(self):
        return "M: %s C: %s D: %s (total: %s)" % (self.metal, self.crystal, self.deuterium,self.total())
    def __add__(self, toAdd):
        return Resources(self.metal + toAdd.metal, self.crystal + toAdd.crystal, self.deuterium + toAdd.deuterium)
    def __sub__(self, toSub):
        return Resources(self.metal - toSub.metal, self.crystal - toSub.crystal, self.deuterium - toSub.deuterium) 
   

class EnemyPlanet (Planet):
    def __init__(self,coords,owner="",ownerstatus="",name="",alliance="",code=0):
        Planet.__init__(self,coords, code, name)
        self.owner = owner
        self.alliance = alliance
        self.ownerStatus = ownerstatus

        self.workingSpyReport = None
        self.spyReportHistory = []
        self.attackTime = None
        self.activeMissions = []
        
    def setWorkingSpyReport(self,spyReport):
        self.spyReportHistory.append(spyReport)
        self.workingSpyReport = spyReport

    def toStringList(self):
        return [str(self.coords),self.name,self.owner,self.alliance]
    


        
class GameMessage(object):
    def __init__(self,code):
        self.code = code

class SpyReport(GameMessage):
    def __init__(self,coords,planetName,date,resources,code,fleet=None,defense=None,buildings=None,research=None):
        GameMessage.__init__(self,code)
        self.coords = coords
        self.planetName = planetName
        self.date = date # always server time not local time
        self.resources = resources
        self.fleet = fleet
        self.defense = defense
        self.buildings = buildings
        self.research = research
        self.probesSent = 0
        self.actionTook = 'None'
        self.rentability = 0
            
    def __repr__(self):
        return "%s %s %s %s %s %s %s %s" % (self.planetName, self.coords, self.date, self.resources, self.fleet, self.defense, self.buildings, self.research)
    
    def hasFleet(self):
        return self.fleet != None and len(self.fleet) > 0
    
    def hasDefense(self):
        return self.defense != None and len(self.defense) > 0
    
    def getAge(self,serverTime):
        return serverTime - self.date
    
    def hasExpired(self,serverTime):
        age = self.getAge(serverTime)
        if self.hasNonMissileDefense():
            return age.days >= 2
        elif self.hasFleet():
            return age.days >= 1
        else: 
            return False
    
    def hasNonMissileDefense(self):
        if self.defense is None:
            return True
        for defense in self.defense.keys():
            if  defense is not 'antiBallisticMissile' and defense is not 'interplanetaryMissile':
                return True
        return False
    
    def hasInfoAbout(self,info):
        if info not in ["fleet","defense","buildings","research"]:
            raise BotError()
        var = getattr(self, info)
        if  var is None:   return "Unknown"
        elif len(var): return "Yes"
        else: return "No"        
        
    def updateRentability(self,ownSystem,serverTime):        
        systemsAway = abs(ownSystem - int(self.coords.solarSystem))
        resourcesByNow = self.resourcesByNow(serverTime)
        self.rentability = resourcesByNow.calculateRentability(systemsAway)
        
    def resourcesByNow(self,serverTime):

        if self.buildings:
            metalMine = self.buildings.get('metalMine',0)
            crystalMine = self.buildings.get('crystalMine',0)
            deuteriumMine = self.buildings.get('deuteriumSynthesizer',0)
        else:
            metalMine,crystalMine,deuteriumMine = 22,19,10
        
        hoursPassed = self.getAge(serverTime).seconds / 3600.0
        produced = Resources()
        produced.metal     = 30 * metalMine     * 1.1 ** metalMine     * hoursPassed
        produced.crystal   = 20 * crystalMine   * 1.1 ** crystalMine   * hoursPassed
        produced.deuterium = 10 * deuteriumMine * 1.1 ** deuteriumMine * hoursPassed * (-0.002 * 60 + 1.28) # 60 is the temperature of a planet in position 7

        return self.resources + produced
                
        
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
        if self['attackingShip'] not in INGAME_TYPES_BY_NAME.keys():
            raise BotError("Invalid attacking ship type in config.ini file")
        
    def save(self):
        for section in 'general','automated attacks':
            if not self.configParser.has_section(section):
                self.configParser.add_section(section)
        for option in 'universe','webpage','username','password':
            self.configParser.set('general', option, str(self[option]))
        for option in 'attackRadio','probesToSend','attackingShip':
            self.configParser.set('automated attacks', option, str(self[option]))        
        self.configParser.write(open(self.file,'w'))
        
class PlanetDb(object): # not used
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
                


class Mission(object):
    sendFleetMethod = None    
    class Types(object):
        unknown   = 0
        attack    = 1
        transport = 3    
        deploy    = 4
        spy       = 6
        # colonize, recycle, 
    
    def __init__(self,type,targetPlanet,fleet):
        self.targetPlanet = targetPlanet
        self.fleet = fleet
        self.missionType = type
        
        self.distance = 0
        self.speed = 0
        self.consumption = 0
        self.sourceCoords = Coords()
        self.launchTime = None
        self.arriveTime = None
        self.returnTime = None
        
    def launch(self):    
        result = self.sendFleetMethod(self.targetPlanet.coords,self.missionType,self.fleet,False)

    def hasArrived(self):
        pass
    def hasReturned(self):
        pass
    def __repr__(self):
        return str(self.targetPlanet)
    
class Espionage(object):
    sendFleetMethod = None
    deleteMessageMethod = None
    
    def __init__(self,targetPlanet,probes):
        self.targetPlanet = targetPlanet
        self.probes = probes
        self.launchTime = None
        self.spyReport = None
    def hasArrived(self,displayedReports):
        if self.spyReport:
            return True
        
        reports = [report for report in displayedReports if report.coords == self.targetPlanet.coords and report.date >= self.launchTime]
        reports.sort(key=lambda x:x.date,reverse=True)
        if len(reports) > 0:
            self.spyReport = reports[0]
            self.deleteMessageMethod(reports[0])
            return True
        return False
    
    def launch(self,currentTime):
        fleet = { 'espionageProbe' : self.probes}
        self.sendFleetMethod(self.targetPlanet.coords,Mission.Types.spy,fleet,False)
        self.launchTime = currentTime      
    def __repr__(self):
        return str(self.targetPlanet)
        
    
    
def sleep(seconds):
    for dummy in range(0,random.randrange(seconds-5,seconds+5)):
        time.sleep(1)