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

import math
import re



class IngameType(object):
    def __init__(self,name,fullName,code):
        self.name = name        
        self.fullName = fullName
        self.code = code    
    def __repr__(self):
        return self.fullName    
    
class Ship(IngameType):
    def __init__(self,name,fullName,code,capacity,consumption):
        super(Ship,self).__init__(name,fullName,code)
        self.capacity = capacity        
        self.consumption = consumption
class Building(IngameType):
    def __init__(self,name,fullName, code):
        super(Building,self).__init__(name,fullName,code)        
class Defense(IngameType):
    def __init__(self,name,fullName, code):
        super(Defense,self).__init__(name,fullName,code)        
class Research(IngameType):
    def __init__(self,name,fullName, code):
        super(Research,self).__init__(name,fullName,code)        
    
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
        self.galaxy = galaxy
        self.solarSystem = solarSystem
        self.planet = planet
        self.planetType = planetType
        self.convertToInts()
        
    def parse(self,newCoords):
        match = self.REGEXP_COORDS.search(newCoords)
        if not match:
            raise "Error parsing coords: " + newCoords
        self.galaxy,self.solarSystem,self.planet = match.groups()
        self.convertToInts()
        
    def convertToInts(self):
        self.galaxy,self.solarSystem,self.planet = int(self.galaxy),int(self.solarSystem),int(self.planet)
        
    def __repr__(self):
        return "%-10s" % ("[%s:%s:%s]" % (self.galaxy,self.solarSystem,self.planet))
    
    def __eq__(self,otherCoords):
        return str(self) == str(otherCoords)
    
    def __ne__(self,otherCoords):
        return str(self) != str(otherCoords)
    
    def distanceTo(self,coords):
        
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
            if  'antiBallisticMissile' not in defense  and 'interplanetaryMissile' not in defense:
                return True
        return False
    
    def hasInfoAbout(self,info):
        if info not in ["fleet","defense","buildings","research"]:
            raise "No info about " + info
        var = getattr(self, info)
        if  var is None:   return "Unknown"
        elif len(var): return "Yes"
        else: return "No"        
        
    def updateRentability(self,ownCoords,serverTime):        
        distance = self.coords.distanceTo(ownCoords)
        referenceFlightTime = 3500 * math.sqrt(distance * 10 / 26000.0) + 10
        resourcesByNow = self.resourcesByNow(serverTime)
        rentability =  resourcesByNow.metalEquivalent() / referenceFlightTime
        
        if not self.hasFleet() and not self.hasNonMissileDefense():
            self.rentability = rentability
        else:
            self.rentability = -rentability
        
    def resourcesByNow(self,serverTime):

        if self.buildings is not None:
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
                


