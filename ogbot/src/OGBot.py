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

# python library:

import sys,os

sys.path.insert(0,'src')
sys.path.insert(0,'lib')

if os.getcwd().endswith("src"):
    os.chdir("..")    

import logging, logging.handlers
import threading
import traceback
from Queue import *
import copy
import shutil
import cPickle
import urllib2
import itertools
import random
import warnings
import math
from datetime import *
from optparse import OptionParser
from itertools import * 

# bot classes:

from GameEntities import *
from CommonClasses import *
from WebAdapter import WebAdapter
from Constants import *
            

from datetime import time


class Bot(object):
    """Contains the bot logic, independent from the communications with the server.
    Theorically speaking if ogame switches from being web-based to being p.e. telnet-based
    this class should not be touched, only WebAdapter """
    class EventManager(BaseEventManager):
        ''' Displays events in console, logs them to a file or tells the gui about them'''
        def __init__(self, gui = None):
            self.gui = gui
        def fatalException(self, exception):
            self.logAndPrint("Fatal error found, terminating. %s" % exception)
            self.dispatch("fatalException", exception)
        # new GUI messages:
        def connected(self):
            self.logAndPrint("Connected")
            self.dispatch("connected")
        def simulationsUpdate(self,rentabilities):
            self.dispatch("simulationsUpdate",rentabilities)
        def activityMsg(self,msg):
            self.logAndPrint(msg)
            msg = datetime.now().strftime("%X %x ") + msg
            self.dispatch("activityMsg",msg)
        def statusMsg(self,msg):
            self.dispatch("statusMsg",msg)
            
    def __init__(self, gui = None):   #only non-blocking tasks should go in constructor
        self.gui = gui
        self.msgQueue = Queue()
        self.eventMgr = Bot.EventManager(gui)
        self._planetDb = PlanetDb(FILE_PATHS['planetdb'])
        self.config = Configuration(FILE_PATHS['config'])                   
        self.web = None
        self.myPlanets = []
        self.researchLevels = {}
        self.config.load()
        self.allTranslations = Translations()
        self.inactivePlanets = []
        self.sourcePlanetsDict = {}
        self.reachableSolarSystems = []
        self._notArrivedEspionages = {}

        self.attackingShip = INGAME_TYPES_BY_NAME[self.config.attackingShip]
        if self.attackingShip.name == 'smallCargo':
            self.secondaryAttackingShip = INGAME_TYPES_BY_NAME['largeCargo']
        else:
            self.secondaryAttackingShip = INGAME_TYPES_BY_NAME['smallCargo']

                                                
    def run(self):
        while True:
            try:
                self._connect()              
                self._start()
            except (KeyboardInterrupt, SystemExit, ManuallyTerminated):
                self.stop()
                print "Bot stopped."              
                break
            except BotFatalError, e:
                self.stop()
                self.eventMgr.fatalException(e)
                break
            except Exception:
                traceback.print_exc()
                self.eventMgr.activityMsg("Something unexpected occured, see log file. Restarting bot.")        
            mySleep(5)
    
    def stop(self):
        if self.web:
            self.web.saveState()
  
         
    def _connect(self):
        self.eventMgr.activityMsg("Connecting...")        
        self.web = WebAdapter(self.config, self.allTranslations, self.gui)
        self.myPlanets = self.web.getMyPlanets()
        self.web.goToPlanet(self.myPlanets[0])
        self.researchLevels = self.web.getResearchLevels()
        
        largeCargos = INGAME_TYPES_BY_NAME['largeCargo']
        smallCargos = INGAME_TYPES_BY_NAME['smallCargo']


        largeCargos.speed =  int(7500 * (1 + (self.researchLevels['combustionDrive'] * 0.1)))
        if self.researchLevels['combustionDrive'] < 5:
            smallCargos.speed =  int(5000  * (1 + (self.researchLevels['combustionDrive'] * 0.1)))
        else:
            smallCargos.speed =  int(10000 * (1 + (self.researchLevels['impulseDrive'] * 0.2)))

               

        ownedCoords = [repr(planet.coords) for planet in self.myPlanets]
        for coords in self.config.sourcePlanets:
            if str(coords) not in ownedCoords:
                raise BotFatalError("You do not own one or more planets selected as sources of attacks.")        
        
        self.sourcePlanets = []
        for planet in self.myPlanets:
            for coords in self.config.sourcePlanets:
                if planet.coords == coords:
                    self.sourcePlanets.append(planet)
        if not self.sourcePlanets:
            self.sourcePlanets.append(self.myPlanets[0]) # the user did not select any source planet, so use the main planet as source
        self.eventMgr.connected()            

  
    
    def _start(self):
        
        self.loadFiles()

        # remove planets to avoid from target list
        for planet in self.inactivePlanets[:]:
            if planet.owner in self.config.playersToAvoid or planet.alliance in self.config.alliancesToAvoid:
                self.inactivePlanets.remove(planet)
                            
        # generate reachable solar systems list
        attackRadius = int(self.config.attackRadius)
        newReachableSolarSystems = [] # contains tuples of (galaxy,solarsystem)
        for sourcePlanet in self.sourcePlanets:
            galaxy = sourcePlanet.coords.galaxy
            firstSystem = max(1,sourcePlanet.coords.solarSystem - attackRadius)
            lastSystem = min(int(self.config.systemsPerGalaxy),sourcePlanet.coords.solarSystem + attackRadius)
            for solarSystem in range(firstSystem,lastSystem +1):
                tuple = (galaxy, solarSystem)
                if tuple not in newReachableSolarSystems:
                    newReachableSolarSystems.append(tuple)
        self.updateSourcePlanetsDict()
                
        if newReachableSolarSystems != self.reachableSolarSystems: # something changed in configuration (attack radius or attack sources)
            self.reachableSolarSystems = newReachableSolarSystems
            del(newReachableSolarSystems)            
            # remove planets that are not in range anymore            
            for planet in self.inactivePlanets[:]:
                if (planet.coords.galaxy,planet.coords.solarSystem) not in self.reachableSolarSystems:
                    self.inactivePlanets.remove(planet)
            self.scanGalaxies()

        self.updateSourcePlanetsDict()
        self.eventMgr.activityMsg("Bot started.")


        

        # main loop:
        while True:
            self._checkThreadQueue() 
            serverTime = self.web.serverTime()

            if self.lastInactiveScanTime.date() != serverTime.date() and serverTime.time() >=  self.config.inactivesAppearanceTime:
                oldInactivesList = self.inactivePlanets
                newInactives = self.scanGalaxies()
                if serverTime.time() < time(3,30):#(datetime.combine(serverTime.date(),self.config.inactivesAppearanceTime) + timedelta(hours=3)).time():
                    self.rushMode(newInactives.values(),oldInactivesList)
                self.spyPlanets(self.inactivePlanets,EspionageReport.DetailLevels.buildings) 
            else:
                
                if serverTime.time() > self.config.preMidnightPauseTime or serverTime.time() < self.config.inactivesAppearanceTime:
                    self.eventMgr.statusMsg("Pre-midnight pause")                
                    mySleep(5)
                else:
                    self.spyPlanets(self.inactivePlanets,EspionageReport.DetailLevels.buildings)    # spy pending planets:
                    undefendedPlanets = [p for p in self.inactivePlanets if not p.getBestEspionageReport().isDefended()]
                    if not undefendedPlanets:
                        raise BotFatalError("There are no inactive and undefended planets in range. Increase range.")
                    
                                                
                    self.attackMode()
    
    def scanGalaxies(self):
        self.eventMgr.activityMsg("Searching inactive planets in range...")

        startTime = datetime.now()           
        if self.config.deuteriumSourcePlanet:
            deuteriumSourcePlanet = (p for p in self.myPlanets if p.coords == self.config.deuteriumSourcePlanet).next()
        else:
            deuteriumSourcePlanet = None
        allInactives = self.web.getSolarSystems(self.reachableSolarSystems,deuteriumSourcePlanet)
        seconds = (datetime.now() - startTime).seconds
        systems = len(self.reachableSolarSystems)
        
        self._planetDb.writeMany(allInactives)
        allInactives = [p for p in allInactives if 'inactive' in p.ownerStatus and p.owner not in self.config.playersToAvoid and p.alliance not in self.config.alliancesToAvoid]
    
        oldInactivePlanetsByCoords = dict([(str(p.coords),p) for p in self.inactivePlanets])                
        newInactives = PlanetList()
        for newPlanet in allInactives:
            oldPlanet = oldInactivePlanetsByCoords.get(str(newPlanet.coords))
            if oldPlanet:
                newPlanet.espionageHistory = oldPlanet.espionageHistory
                newPlanet.simulation = oldPlanet.simulation
            else:
                if __debug__: print >>sys.stderr, "New inactive planet found: " + str(newPlanet)
                newInactives.append(newPlanet)

        self.lastInactiveScanTime = self.web.serverTime()
        self.inactivePlanets = allInactives        
        self.updateSourcePlanetsDict()

        self.eventMgr.activityMsg("Inactive search finished. %s inactives (%s new) found in %s solar sytems (%s secs. per solar system)." % (len(allInactives),len(newInactives),systems,seconds/float(systems)))

        newInactives.save(FILE_PATHS['newinactives'])
        self.saveFiles()          
        return newInactives


    def attackMode(self):   
        self.eventMgr.activityMsg("Changing to attack mode." )
        planetsWithoutShips = {}
        notArrivedAttacks = []
        
        while self.web.serverTime().time() < self.config.preMidnightPauseTime:
            
            self._checkThreadQueue()            
            serverTime = self.web.serverTime()
            self.checkIfEspionageReportsArrived()
            
            
            rentabilities = self.generateRentabilityTable(self.inactivePlanets)
            self.eventMgr.simulationsUpdate(rentabilities)
            
            # update lists of own planets with no ships
            for planet,checkedTime in planetsWithoutShips.items():
                if serverTime - checkedTime > timedelta(minutes=5):
                    del planetsWithoutShips[planet]
                    
            # update list of flying attacks that have not yet arrived to target planet
            for attack in notArrivedAttacks[:]:
                if serverTime >= attack.arrivalTime:
                    notArrivedAttacks.remove(attack)

            selectedAttacks = [x for x in rentabilities if x.targetPlanet not in self._notArrivedEspionages and x.rentability > 0 and x.sourcePlanet not in planetsWithoutShips]
                               
            if not selectedAttacks:
                self.eventMgr.statusMsg("Not enough ships")
                mySleep(10)
                continue
            
            try:
                targetPlanet,sourcePlanet = selectedAttacks[0].targetPlanet, selectedAttacks[0].sourcePlanet
                rentabilityTreshold = selectedAttacks[1].rentability

                try:                    
                    if targetPlanet.espionageHistory[-1].getAge(serverTime).seconds < 900 or targetPlanet in [attack.targetPlanet for attack in notArrivedAttacks]:
                        sentMission = self.attackPlanet(sourcePlanet, targetPlanet, self.attackingShip)
                        notArrivedAttacks.append(sentMission)
                    elif targetPlanet not in self._notArrivedEspionages:    #planet's espionage report timed out, re-spy.
                        self._spyPlanet(sourcePlanet,targetPlanet)
                except NotEnoughShipsError, e1:
                    
                    
                    factor = e1.available / float(e1.requested.values()[0])
                    resourcesToSteal = targetPlanet.simulation.simulatedResources.half() * factor
                    newRentability = (resourcesToSteal * 2).rentability(sourcePlanet.coords.flightTimeTo(targetPlanet.coords,self.attackingShip.speed),self.config.rentabilityFormula)
                    if newRentability > rentabilityTreshold:
                        try:
                        
                            sentMission = self.attackPlanet(sourcePlanet, targetPlanet, self.attackingShip,False)
                            notArrivedAttacks.append(sentMission)
                        except NotEnoughShipsError, e2:
                            planetsWithoutShips[sourcePlanet] = serverTime
                            self.eventMgr.activityMsg("Not enough ships for mission from %s to %s. %s" %(sourcePlanet,targetPlanet,e1))
                    else:
                        planetsWithoutShips[sourcePlanet] = serverTime
                        self.eventMgr.activityMsg("Not enough ships for mission from %s to %s. %s" %(sourcePlanet,targetPlanet,e1))
            except NoFreeSlotsError: 
                self.eventMgr.statusMsg("Fleet limit hit")
                mySleep(8)
            except FleetSendError, e: 
                self.eventMgr.activityMsg("Error sending mission to planet %s. Reason: %s" %(targetPlanet,e))
                self.inactivePlanets.remove(targetPlanet)
        
            mySleep(1)            
            
    def rushMode(self,newInactives,oldInactivesList = []):
        self.eventMgr.activityMsg("Changing to rush mode." )
        planetsWithoutShips = {}   
        oldInactives = PlanetList(oldInactivesList)

        rentabilityTreshold = self.generateRentabilityTable(self.inactivePlanets)[0].rentability
        
        self.spyPlanets(newInactives)
#        sourcePlanet = self.sourcePlanetsDict[planet]
#
#        rentability = planet.rentability(sourcePlanet.coords,self.attackingShip.speed,self.config.entabilityFormula)
       
        rentabilities =  self.generateRentabilityTable(newInactives,False)        
        newInactives = [x.targetPlanet for x in rentabilities if x.rentability > rentabilityTreshold]
        self.spyPlanets(newInactives,EspionageReport.DetailLevels.defense)
        newInactives = [(x.sourcePlanet,x.targetPlanet) for x in rentabilities]
        while True:
            serverTime = self.web.serverTime()            
            self._checkThreadQueue()
            rentabilities = self.generateRentabilityTable([x[1] for x in newInactives])
            self.eventMgr.simulationsUpdate(rentabilities)
            
            newInactives = [(x.sourcePlanet,x.targetPlanet) for x in rentabilities if x.rentability > rentabilityTreshold]
            if not newInactives:
                break
                        
            # update lists of own planets with no ships
            for planet,checkedTime in planetsWithoutShips.items():
                if serverTime - checkedTime > timedelta(minutes=5):
                    del planetsWithoutShips[planet] 
                    
            try: selectedAttack = (x for x in rentabilities if x.sourcePlanet not in planetsWithoutShips).next()
            except StopIteration:
                self.eventMgr.statusMsg("Not enough ships")
                mySleep(1)
                continue

            targetPlanet,sourcePlanet = selectedAttack.targetPlanet, selectedAttack.sourcePlanet
            try:
                self.attackPlanet(sourcePlanet, targetPlanet, self.attackingShip,False)
            except NotEnoughShipsError, e1:
                try:
                    self.attackPlanet(sourcePlanet, targetPlanet, self.secondaryAttackingShip,False)
                    self.eventMgr.simulationsUpdate(rentabilities)                                  
                except NotEnoughShipsError, e2:
                    planetsWithoutShips[sourcePlanet] = serverTime
                    self.eventMgr.activityMsg("Not enough ships for mission from %s to %s. %s" %(sourcePlanet,targetPlanet,e2))
                except NoFreeSlotsError: 
                    self.eventMgr.statusMsg("Fleet limit hit")
                    mySleep(1)
                except FleetSendError, e: 
                    self.eventMgr.activityMsg("Error sending mission to planet %s.Reason: %s" %(targetPlanet,e))
                    self.inactivePlanets.remove(targetPlanet)
                    newInactives.remove((sourcePlanet,targetPlanet))
                        
            except NoFreeSlotsError: 
                self.eventMgr.statusMsg("Fleet limit hit")
                mySleep(1)
            except FleetSendError, e: 
                self.eventMgr.activityMsg("Error sending mission to planet %s.Reason: %s" %(targetPlanet,e))
                self.inactivePlanets.remove(targetPlanet)
                newInactives.remove((sourcePlanet,targetPlanet))


    
    def spyPlanets(self, planetsToSpy, upToDetailLevel = None):
 
        remainingPlanets = [(self.sourcePlanetsDict[p],p) for p in planetsToSpy]
        remainingPlanets.sort(key=lambda x:x[1].coords) # sort by target coords
        remainingPlanets.sort(key=lambda x:x[0]) # sort by source planet        
        
        while True:
            self._checkThreadQueue()
            self.eventMgr.simulationsUpdate(self.generateRentabilityTable(planetsToSpy))
            self.checkIfEspionageReportsArrived()

            serverTime = self.web.serverTime()                        
            
            for source,target in remainingPlanets[:]:
                if target.espionageHistory and target.getBestEspionageReport().hasAllNeededInfo(upToDetailLevel) and not target.espionageHistory[-1].hasExpired(serverTime):
                    remainingPlanets.remove((source,target))
    
            if not remainingPlanets:
                break
            
            possibleTargets = [x for x in remainingPlanets if x[1] not in self._notArrivedEspionages]
            if not possibleTargets:
                mySleep(1)
                continue

            sourcePlanet,targetPlanet = possibleTargets[0]
            msg = "Spying"
            
            if upToDetailLevel == None:
                probesToSend = int(self.config.probesToSend)
            elif upToDetailLevel == EspionageReport.DetailLevels.resources:
                probesToSend = 1
            else:
                if not targetPlanet.espionageHistory:
                    # send no. of probes equal to the average no. of probes sent until now.
                    probes = [planet.getBestEspionageReport().probesSent for planet in self.inactivePlanets if planet.espionageHistory]
                    probesToSend = max (int(sum(probes) / len(probes)), int(self.config.probesToSend))
                    msg = "Spying for the 1st time"                            
                else:
                    probesToSend = targetPlanet.getBestEspionageReport().probesSent    
                    if not targetPlanet.getBestEspionageReport().hasAllNeededInfo(upToDetailLevel):
                        # we need to send more probes to get the defense or buildings data
                        msg = "Re-spying with more probes"
                        probesToSend = max(int (1.5 * probesToSend),probesToSend +2) # non-linear increase in the number of probes
        
                samePlayerProbes = [planet.getBestEspionageReport().probesSent for planet in self.inactivePlanets if planet.espionageHistory and planet.owner == targetPlanet.owner]
                probesToSend = max(samePlayerProbes + [probesToSend])
            
            try:
                self._spyPlanet(sourcePlanet,targetPlanet,True,msg,probesToSend)
            except NotEnoughShipsError, e:
                self.eventMgr.activityMsg("Not enough ships for mission from %s to %s. %s" %(sourcePlanet,targetPlanet,e))
                # move to the end all planets with this source planet
                for source,planet in remainingPlanets[:]:
                    if source == sourcePlanet:
                        remainingPlanets.remove((source,planet))
                        remainingPlanets.append((source,planet))
                mySleep(1)
            except NoFreeSlotsError: 
                self.eventMgr.statusMsg("Fleet limit hit")
                mySleep(3)
            except FleetSendError, e: 
                self.eventMgr.activityMsg("Error sending mission to planet %s.Reason: %s" %(targetPlanet,e))
                try: planetsToSpy.remove(targetPlanet)                
                except ValueError: pass
                remainingPlanets.remove((sourcePlanet,targetPlanet))

    def _spyPlanet(self,sourcePlanet,targetPlanet,useReservedSlots=False,msg = "Spying",probesToSend = 1):
        if useReservedSlots:
            slotsToReserve = 0
        else:
            slotsToReserve = self.config.slotsToReserve        
    
        ships = {'espionageProbe':probesToSend}
        mission = Mission(Mission.Types.spy, sourcePlanet, targetPlanet, ships)

        self.web.launchMission(mission,True,slotsToReserve)
        self._notArrivedEspionages[targetPlanet] = mission
        self.eventMgr.activityMsg("%s %s from %s with %s" % (msg,targetPlanet, sourcePlanet, ships))
    
        return mission                            
        
    
    def attackPlanet(self,sourcePlanet,targetPlanet,attackingShip,abortIfNoShips = True):
        resourcesToSteal = targetPlanet.simulation.simulatedResources.half()        
        producedMeanwhile = targetPlanet.simulation.calculateProduction(sourcePlanet.coords.flightTimeTo(targetPlanet.coords,attackingShip.speed))
        ships = math.ceil((resourcesToSteal + producedMeanwhile).total() / attackingShip.capacity)
        fleet = { attackingShip.name : ships }
        mission = Mission(Mission.Types.attack, sourcePlanet, targetPlanet, fleet)
        self.web.launchMission(mission,abortIfNoShips,self.config.slotsToReserve)
        targetPlanet.attackHistory.append(mission)
        self.eventMgr.activityMsg( "ATTACKING %s from %s with %s" % (targetPlanet, sourcePlanet,fleet))
        shipsSent = mission.fleet[attackingShip.name]
        if shipsSent < ships:
            factor = shipsSent / float(ships)
            targetPlanet.simulation.simulatedResources -= resourcesToSteal * factor
            self.eventMgr.activityMsg("There were not enough ships for the previous attack. Needed %s but sent only %s" % (fleet,mission.fleet))
        else:
            targetPlanet.simulation.simulatedResources -= resourcesToSteal       
        self.saveFiles()              
        mySleep(20)
        return mission
        
    def checkIfEspionageReportsArrived(self):
        arrivedReports = []
        if self._notArrivedEspionages:
            displayedReports = self.web.getEspionageReports()
            
            for planet, espionage in self._notArrivedEspionages.items():
                reports = [report for report in displayedReports if report.coords == espionage.targetPlanet.coords and report.date >= espionage.launchTime]
                reports.sort(key=lambda x:x.date, reverse=True)
                if  reports:
                    report = reports[0]
                    report.probesSent = espionage.fleet['espionageProbe']
                    del self._notArrivedEspionages[planet]
                    
                    planet.simulation = ResourceSimulation(report.resources, report.buildings)
                    planet.espionageHistory.append(report)
                    arrivedReports.append(report)
                    self._planetDb.write(planet)
                elif self.web.serverTime() > espionage.arrivalTime + timedelta(minutes=1):
                    # probably due to buggy espionage report (containing only N;) or translation errors.
                    del self._notArrivedEspionages[planet]
                    try: self.inactivePlanets.remove(planet)
                    except ValueError: pass
                    self.saveFiles()                         
                    self.eventMgr.activityMsg("Espionage report from %s never arrived. Deleting planet." % espionage.targetPlanet)
                        
        if arrivedReports:
            self.web.deleteMessages(arrivedReports)
            self.saveFiles()              
        return arrivedReports
                    
    def generateRentabilityTable(self,planetList,negativeIfDefended = True):
        rentabilities = []

        for planet in planetList:
            sourcePlanet = self.sourcePlanetsDict[planet]
            rentability = planet.rentability(sourcePlanet.coords,self.attackingShip.speed,self.config.rentabilityFormula)
            rentabilities.append(Struct(sourcePlanet=sourcePlanet,targetPlanet=planet,rentability=rentability))
        rentabilities.sort(key=lambda x:x.rentability, reverse=True)
        return rentabilities
    
    
    def updateSourcePlanetsDict(self):
        for targetPlanet in self.inactivePlanets:
            self.sourcePlanetsDict[targetPlanet] = self._calculateNearestSourcePlanet(targetPlanet.coords)
  
    def _calculateNearestSourcePlanet(self,coords):
        tmpSourcePlanets = self.sourcePlanets
        minDistance = sys.maxint
        random.shuffle(tmpSourcePlanets)
        for sourcePlanet in tmpSourcePlanets:
            distance = sourcePlanet.coords.distanceTo(coords)
            if distance < minDistance:
                nearestSourcePlanet = sourcePlanet
                minDistance = distance        
        return nearestSourcePlanet
    
    def _calculateSteal(self,resourcesToSteal,attackingFleet):
        pass
        
    def _checkThreadQueue(self):
        try:
            msg = self.msgQueue.get(False)
            if   msg.type == GuiToBotMsg.stop:
                raise ManuallyTerminated()
            elif msg.type == GuiToBotMsg.pause:
                print "Bot paused."
                while True: # we are in paused mode
                    msg = self.msgQueue.get()
                    if   msg.type == GuiToBotMsg.stop:
                        raise ManuallyTerminated()
                    elif msg.type == GuiToBotMsg.resume:
                        print "Bot resumed."                        
                        break
        except Empty: pass         

          
    def saveFiles(self):
        path = FILE_PATHS['gamedata']
        try:
            shutil.move(path,path + ".bak")
        except IOError: pass
        
        file = open(path, 'wb')
        pickler = cPickle.Pickler(file,2)
        for i in [self.inactivePlanets,self.reachableSolarSystems,self.lastInactiveScanTime,
                  self.config.webpage,self.config.universe,self.config.username]:
                  pickler.dump(i)
        file.close()
        
    def loadFiles(self):
        try:
            file = open(FILE_PATHS['gamedata'], 'rb')
            u = cPickle.Unpickler(file)
            self.inactivePlanets = u.load()
            self.reachableSolarSystems = u.load()
            self.lastInactiveScanTime = u.load()
            storedWebpage = u.load()
            storedUniverse = u.load()
            storedUsername = u.load()
            file.close()
                 
            if storedWebpage != self.config.webpage \
            or storedUniverse != self.config.universe:
                raise BotError() # if any of those has changed, invalidate stored espionages

        except (EOFError, IOError,BotError,ImportError,AttributeError):
            try: file.close()            
            except UnboundLocalError: pass
            self.inactivePlanets = []
            self.reachableSolarSystems = []
            self.eventMgr.activityMsg("Invalid or missing gamedata, respying planets.")
            try: os.remove(FILE_PATHS['gamedata'])              
            except Exception : pass
            
# -- non-farming code: ---

    def fleetSearch(self):
        self._connect()

        points = dict([(player,points)  for player,alliance,points in self.web.getStats('flt')])
        
        list = []
        for planet in self._planetDb.readAll():
            player = planet.owner
            if player in points:
                sourcePlanet = self._calculateNearestSourcePlanet(planet.coords)
                if sourcePlanet.name != "Phatt Island":
                    continue
                flightTime = sourcePlanet.coords.flightTimeTo(planet.coords,25000)
                item = points[player],planet,player,planet.alliance,flightTime,sourcePlanet.name,points[player]/float(flightTime.seconds)
                list.append(item)
            
        list.sort(key=lambda x:x[6],reverse=True)
        file = open('output/fleetsearch.html','w')
        file.write('<table>')
        file.write('<th>Fleet points</th><th>Planet</th><th>Owner</th><th>Alliance</th><th>Flight time (aprox.)</th><th>Source planet</th><th>Rentability index</th>')        
        for line in list:
            file.write('<tr>')
            for item in line:
                file.write('<td>%s</td>' % item)
            file.write('</tr>')           
        file.write('</table>')
        file.close()
        print "DONE"

    
if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-c", "--console", action="store_true", help="Run in console mode'")
    parser.add_option("-a", "--autostart", action="store_true", help="Auto start bot, no need to click Start button")
    parser.add_option("-w", "--workdir", help="Specify working directory (useful to run various bots at once). If not specified defaults to 'files'")    
    parser.add_option("-f", "--fleetsearch", action="store_true", help="Find planets of people in the fleet ranking and then exit bot.")    
    (options, args) = parser.parse_args()
    
    if options.workdir:
        dirPrefix = options.workdir
    else:
        dirPrefix = 'files'
        
    for key, path in FILE_PATHS.items():
        path = dirPrefix + '/' + path
        FILE_PATHS[key] = path
        try: os.makedirs (os.path.dirname(path))
        except OSError, e: pass

    for dir in ('debug','output/reports'):
        try: os.makedirs (dir)
        except OSError, e: pass
            
    logging.getLogger().setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(os.path.abspath(FILE_PATHS['log']), 'a', 100000, 10)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(handler)

    if options.fleetsearch:
        bot = Bot()
        bot.fleetSearch()
    elif options.console:
        bot = Bot()
        bot.run()
    else:
        from gui import guiMain
        guiMain(options)
