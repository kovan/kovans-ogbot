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


import math
import re
from datetime import timedelta
from CommonClasses import Enum, addCommas


class IngameType(object):
    def __init__(self, name, code):
        self.name = name         
        self.code = code    
    def __repr__(self):
        return self.name    
    
class Ship(IngameType):
    def __init__(self, name, code, capacity, consumption):
        super(Ship, self).__init__(name, code)
        self.capacity = capacity         
        self.consumption = consumption
class Building(IngameType): pass
class Defense(IngameType): pass
class Research(IngameType): pass

class Coords(object):
    class Types(Enum):
        unknown = 0
        planet  = 1
        debris  = 2
        moon = 3
    
    PLANETS_PER_SYSTEM = 15
    REGEXP_COORDS    = re.compile(r"([1-9]{1,2}):([0-9]{1,3}):([0-9]{1,2})")
    
    def __init__(self, galaxyOrStr, solarSystem=0, planet=0, coordsType=Types.planet):
        ''' 
            First parameter can be a string to be parsed e.g: [1:259:12] or the galaxy. 
            If it's the galaxy, solarSystem and planet must also be supplied.
        '''
        self.coordsType = coordsType        
        try: self.parse(galaxyOrStr)
        except Exception:
            self.galaxy = galaxyOrStr
            self.solarSystem = solarSystem
            self.planet = planet
            self.convertToInts()              
            
    def isMoon(self):
        return self.coordsType == self.Types.moon
        
    def parse(self, newCoords):
        match = self.REGEXP_COORDS.search(newCoords)
        if not match:
            raise Exception("Error parsing coords: " + newCoords)
        self.galaxy, self.solarSystem, self.planet = match.groups()
        if 'moon' in newCoords: self.coordsType = self.Types.moon
        self.convertToInts()
        
    def tuple(self):
        return self.galaxy, self.solarSystem, self.planet
    
    def convertToInts(self):
        self.galaxy, self.solarSystem, self.planet = int(self.galaxy), int(self.solarSystem), int(self.planet)
        
    def __str__(self):
        return "[%s:%s:%s]" % (self.galaxy, self.solarSystem, self.planet)                   
    
    def __repr__(self):
        repr = str(self)
        if not self.coordsType == self.Types.planet:
            repr += " " + self.Types.toStr(self.coordsType)
        return  repr

    def __eq__(self, otherCoords):
        return self.tuple() == otherCoords.tuple() and self.coordsType == otherCoords.coordsType 
    
    def __ne__(self, otherCoords):
        return not self.__eq__(otherCoords)
    
    def __lt__(self,otherCoords):
        if self.galaxy < otherCoords.galaxy:
            return True
        elif self.galaxy == otherCoords.galaxy:
            if self.solarSystem < otherCoords.solarSystem:
                return True
            elif self.solarSystem == otherCoords.solarSystem:
                if self.planet < otherCoords.planet:
                    return True
        return False
    
    def distanceTo(self, coords):
        
        distance = 0
        if   coords.galaxy - self.galaxy != 0:
            distance = abs(coords.galaxy - self.galaxy) * 20000
        elif coords.solarSystem - self.solarSystem != 0:
            distance = abs(coords.solarSystem - self.solarSystem) * 5 * 19 + 2700
        elif coords.planet - self.planet != 0:
            distance = abs(coords.planet - self.planet) * 5 + 1000
        else:
            distance = 5
        return distance
    
    def flightTimeTo(self, coords, speed, speedPercentage=100):
        seconds = 350000.0/speedPercentage * math.sqrt(self.distanceTo(coords) * 10.0 / float(speed)) + 10.0
        return timedelta(seconds=int(seconds))


class Resources(object):
    compiledFormula = None
    def __init__(self, metal=0, crystal=0, deuterium=0):
        self.metal = int(metal)
        self.crystal = int(crystal)
        self.deuterium = int(deuterium)
        
    def total(self):
        return self.metal + self.crystal + self.deuterium
    def half(self):
        return Resources(self.metal/2, self.crystal/2, self.deuterium/2)
    def tuple(self):
        return self.metal, self.crystal, self.deuterium
    def __eq__(self, otherResources):
        return self.tuple() == otherResources.tuple()
    def __ne__(self, otherResources):
        return not self.__eq__(otherResources)
    def __repr__(self):
        return "M: %s C: %s D: %s (total: %s)" % (addCommas(self.metal), addCommas(self.crystal), addCommas(self.deuterium), addCommas(self.total()))
    def __add__(self, toAdd):
        return Resources(self.metal + toAdd.metal, self.crystal + toAdd.crystal, self.deuterium + toAdd.deuterium)
    def __sub__(self, toSub):
        return Resources(self.metal - toSub.metal, self.crystal - toSub.crystal, self.deuterium - toSub.deuterium) 
    def __mul__(self, toMul):
        return Resources(self.metal * toMul, self.crystal * toMul, self.deuterium * toMul) 
    def rentability(self, flightTime,rentabilityFormula):
        if not Resources.compiledFormula:
            for var in ['metal','crystal','deuterium']:
                rentabilityFormula = rentabilityFormula.replace(var,'self.' + var)
            rentabilityFormula = rentabilityFormula.replace('flightTime','float(flightTime)')        
            Resources.compiledFormula = compile(rentabilityFormula,'<string>','eval')     
                   
        flightTime = flightTime.seconds
        return  eval(Resources.compiledFormula)
   
    
class Planet(object):
    def __init__(self, coords, name=""):
        self.coords = coords
        self.name = name
    def __repr__(self):
        return self.name + " " + str(self.coords)
    
class OwnPlanet(Planet):
    def __init__(self, coords, name="", code=0):
        super(OwnPlanet, self).__init__(coords, name)
        self.code = code


class EnemyPlanet (Planet):
    compiledFormula = None
    def __init__(self, coords, owner="", ownerstatus="", name="", alliance=""):
        super(EnemyPlanet, self).__init__(coords, name)
        self.owner = owner
        self.alliance = alliance
        self.ownerStatus = ownerstatus
        self.espionageHistory = []
        self.simulation = None
                
    def getBestEspionageReport(self):
        if not self.espionageHistory:
            return None
        
        best = self.espionageHistory[0]
        for report in self.espionageHistory:
            if report.getDetailLevel() > best.getDetailLevel() and report.date >= best.date:
                best = report
        return best

    def rentability(self, fromCoords,speed, rentabilityFormula,negativeIfDefended = True):
        if not EnemyPlanet.compiledFormula:
            for var in ['metal','crystal','deuterium']:
                rentabilityFormula = rentabilityFormula.replace(var,'self.simulation.simulatedResources.' + var)
            rentabilityFormula = rentabilityFormula.replace('flightTime','float(flightTime)')        
            EnemyPlanet.compiledFormula = compile(rentabilityFormula,'<string>','eval')     
                        
        if not self.simulation:
            return 0
        
        flightTime = self.coords.flightTimeTo(fromCoords,speed).seconds # used inside formula
        rentability = eval( EnemyPlanet.compiledFormula)
        
        if negativeIfDefended and self.getBestEspionageReport().isDefended():
            return -rentability
        else:
            return  rentability

    def toStringList(self):
        return [str(self.coords), self.name, self.owner, self.alliance]

        
class GameMessage(object):
    def __init__(self, code):
        self.code = code

class EspionageReport(GameMessage):
    class DetailLevels(Enum):
        resources, fleet, defense, buildings, research = range(5)
            
    def __init__(self, coords, planetName, date, resources, code, fleet=None, defense=None, buildings=None, research=None):
        GameMessage.__init__(self, code)
        self.coords = coords
        self.planetName = planetName
        self.date = date # always server time not local time
        self.resources = resources
        self.fleet = fleet
        self.defense = defense
        self.buildings = buildings
        self.research = research
        self.probesSent = 0

            
    def __repr__(self):
        return "%s %s %s %s %s %s %s %s" % (self.planetName, self.coords, self.date, self.resources, self.fleet, self.defense, self.buildings, self.research)
    
    def hasFleet(self): 
        return self.fleet == None or len(self.fleet) > 0
    
    def hasDefense(self):
        return self.defense == None or len(self.defense) > 0
    
    def getAge(self, serverTime):
        return serverTime - self.date
    
    def getDetailLevel(self):
        if self.research != None:
            return self.DetailLevels.research
        if self.buildings != None:
            return self.DetailLevels.buildings
        if self.defense != None:
            return self.DetailLevels.defense
        if self.fleet != None:
            return self.DetailLevels.fleet
        return self.DetailLevels.resources
        
    def hasExpired(self, serverTime):
        age = self.getAge(serverTime)
        if self.hasNonMissileDefense():
            return age.days >= 7
        elif self.hasFleet():
            return age.days >= 4
        else: 
            return False
    
    def hasNonMissileDefense(self):
        if self.defense is None:
            return True
        for defense in self.defense.keys():
            if  'antiBallisticMissile' not in defense  and 'interplanetaryMissile' not in defense:
                return True
        return False
    
    def hasAllNeededInfo(self,detailLevel = DetailLevels.buildings):
        reportDetail = self.getDetailLevel()
        if detailLevel >= self.DetailLevels.fleet:
            if  reportDetail  == self.DetailLevels.fleet:
                if self.hasFleet():
                    return True
            elif reportDetail == self.DetailLevels.defense:
                if self.hasNonMissileDefense():
                    return True
        return self.getDetailLevel() >= detailLevel
        
    def isDefended(self):
        return self.hasFleet() or self.hasNonMissileDefense()
    
    def hasInfoAbout(self, info):
        if info not in ["fleet", "defense", "buildings", "research"]:
            raise Exception("No info about " + info)
        var = getattr(self, info)
        if  var is None:   return "Unknown"
        elif len(var): return "Yes"
        else: return "No"         
        
        


class Mission(object):
    class Types(Enum):
        unknown   = 0
        attack    = 1
        transport = 3    
        deploy    = 4
        spy        = 6
        # colonize, recycle, 
    
    def __init__(self, missionType, sourcePlanet, targetPlanet, fleet, resources=Resources(), speedPercentage=100):
        self.missionType = missionType              
        self.sourcePlanet = sourcePlanet              
        self.targetPlanet = targetPlanet
        self.fleet = fleet              
        self.resources = resources
        self.speedPercentage = speedPercentage

        # these will be automatically corrected (if needed) once the mission is sent
        self.distance = 0
        self.consumption = 0
        self.launchTime = None # type datetime
        self.flightTime = None
        
    def _arrivalTime(self):
        return self.launchTime + self.flightTime
    arrivalTime = property(_arrivalTime)         
    def _returnTime(self):
        return self.launchTime + self.flightTime * 2
    returnTime = property(_returnTime)         
        
    def __repr__(self):
        return "%s to %s with %s" % (self.Types.toStr(self.missionType).title() , self.targetPlanet, self.fleet)
