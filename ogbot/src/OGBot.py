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
from HelperClasses import NoFreeSlotsError
from HelperClasses import FleetSendError

# python library:
import sys
sys.path.append('lib')
sys.path.append('src')

import bsddb,anydbm,dbhash,dumbdbm
import logging, logging.handlers
import threading
import traceback
from Queue import *
import copy
import time
import gettext
import pickle
import urllib2
import os
if os.getcwd().endswith("src"):
    os.chdir("..")	
gettext.install('ogbot')
# and libraries:
from datetime import datetime,timedelta
# bot classes:
from HelperClasses import *
from WebAdapter import WebAdapter


CONFIG_FILE = "config/config.ini"
STATE_FILE = 'botdata/bot.state.dat'
PLANETDB_FILE = 'botdata/planets.db'
LOG_FILE = 'log/ogbot.log'

LOG_FILE = os.path.abspath(LOG_FILE)

class Bot(threading.Thread):
    """Contains the bot logic, independent from the communications with the server.
     Theorically speaking if ogame switches from being web-based to being p.e. telnet-based
     this class should not be touched, only Controller """

    class EventManager(BaseEventManager):
        ''' Displays events in console, logs them to a file or tells the gui about them'''
        def __init__(self,gui = None):
            self.gui = gui
        
        def targetsSearchBegin(self,howMany):
            self.logAndPrint( ' / Looking for %s inactive planets to spy...' % howMany)
            self.dispatch("targetsSearchBegin",howMany)
        def solarSystemAnalyzed(self,galaxy,solarSystem):
            self.logAndPrint( '|      Analyzed solar system [%s:%s:]' % (galaxy,solarSystem)     )
            self.dispatch("solarSystemAnalyzed",galaxy,solarSystem)            
        def targetPlanetFound(self,planet):
            self.logAndPrint( '|      Target planet found: %s' % planet)
            self.dispatch("targetPlanetFound",planet)            
        def targetsSearchEnd(self):        
            self.logAndPrint( ' \\')
            self.dispatch("targetsSearchEnd")            
        def espionagesBegin(self,howMany): 
            self.logAndPrint( ' / Planet(s) found, starting espionage(s)')
            self.dispatch("espionagesBegin",howMany)            
        def probesSent(self,planet,howMany):
            self.logAndPrint( '|      %s probe(s) sent to planet %s' % (howMany,planet)         )
            self.dispatch("probesSent",planet,howMany)            
        def errorSendingProbes(self, planet, probesCount,reason):
            self.logAndPrint(  '|**    Error sending probes to planet %s (%s)' % (planet,reason))
            self.dispatch("errorSendingProbes",planet,probesCount,reason)             
        def espionagesEnd(self):
            self.logAndPrint( ' \  All espionage(s) launched')
            self.dispatch("espionagesEnd")            
        def waitForReportsBegin(self,howMany):
            self.logAndPrint( ' / Waiting for all %s spy report(s) to arrive...' % howMany)
            self.dispatch("waitForReportsBegin",howMany)
        def waitForReportsEnd(self):
            self.logAndPrint( ' \  All spy report(s) arrived')
            self.dispatch("waitForReportsEnd")            
        def reportsAnalysisBegin(self,howMany):
            self.logAndPrint( ' / Analyzing %s spy reports ' % howMany)
            self.dispatch("reportsAnalysisBegin",howMany)            
        def planetSkipped(self,planet,cause):
            self.logAndPrint( '|      Skipping planet %s because it has %s' % (planet, cause))
            self.dispatch("planetSkipped",planet,cause)            
        def reportsAnalysisEnd(self):
            self.logAndPrint( ' \  All spy report(s) analyzed')
            self.dispatch("reportsAnalysisEnd")            
        def attacksBegin(self,howMany):
            self.logAndPrint( ' / Starting %s attacks...' % howMany)
            self.dispatch("attacksBegin",howMany)            
        def planetAttacked(self,planet,fleet,resources):
            self.logAndPrint( '|      Planet %s attacked by %s for %s' % (planet,fleet,resources))
            self.dispatch("planetAttacked",planet,fleet,resources)            
        def errorAttackingPlanet(self, planet, reason):
            self.logAndPrint(  '|**    Error attacking planet %s (%s)' % (planet,reason))
            self.dispatch("errorAttackingPlanet",planet,reason)            
        def attacksEnd(self):
            self.logAndPrint( ' \ Attacks finished')
            self.dispatch("attacksEnd")            
        def waitForSlotBegin(self):
            self.logAndPrint( ' |         Simultaneous fleet limit reached. Waiting...')
            self.dispatch("waitForSlotBegin")            
        def waitForSlotEnd(self):
            self.logAndPrint( ' |')
            self.dispatch("waitForSlotEnd")            
        def waitForShipsBegin(self, shipType):
            self.logAndPrint( ' |         There are no available ships of type %s. Waiting...' % shipType)
            self.dispatch("waitForShipsBegin",shipType)            
        def waitForShipsEnd(self): 
            self.dispatch("waitForShipsEnd")            
        def planetSkippedByPrecalculation(self,planet,reason):
            self.logAndPrint( "|      Skipping planet %s because %s" % (planet, reason))
            self.dispatch("planetSkippedByPrecalculation",planet,reason)
        def fatalException(self,exception):
            self.logAndPrint("| Fatal error found, terminating. %s" % exception)
            self.dispatch("fatalException",exception)
        
    def __init__(self,gui = None):   #only non-blocking tasks should go in constructor
        threading.Thread.__init__(self,name="BotThread")
        self.gui = gui
        self.msgQueue = Queue()
        self._eventMgr = Bot.EventManager(gui)
        self._planetDb = PlanetDb(PLANETDB_FILE)
        self.config = Configuration(CONFIG_FILE)                
        self._web = None
        self._lastSpiedCoords = None
        self.attackingShip = SHIP_TYPES[self.config['attackingShip']]                        
        self.myPlanets = []
        
        
    def setLastSpiedCoords(self, value):
        self._lastSpiedCoords = copy.copy(value)
        self.saveState()

    def getLastSpiedCoords(self): 
        return self._lastSpiedCoords
    
    lastSpiedCoords = property(getLastSpiedCoords, setLastSpiedCoords)
    
            
    def run(self):
        while True:
            try:
                self._connect()            
                self._newStart()
            except (KeyboardInterrupt,SystemExit,ManuallyTerminated):
                self.stop()
                print "Bot stopped."            
                break
            except BotFatalError, e:
                self.stop()
                self._eventMgr.fatalException(e)
                break
            except Exception:
                traceback.print_exc()
            time.sleep(5)
    
    def stop(self):
        self.saveState()
        if self._web:
            self._web.saveState()        
        
    def _connect(self):
        try:
            self.config.load()
        except BotError, e: raise BotFatalError(e)

        self._web = WebAdapter(self.config,self._checkThreadQueue,self.gui)
        self.myPlanets = self._web.getMyPlanetsAndServerTime()[0]
        if not self.loadState():
             startCoords = copy.copy(self.myPlanets[0].coords)
             startCoords.solarSystem -= int(self.config['attackRadio'])
             startCoords.planet = 1
             self.lastSpiedCoords = startCoords

    def _newStart(self): # unused ATM
        sortByRentability = lambda planet: planet.rentability[1]
        probesToSend, attackRadio = self.config['probesToSend'], int(self.config['attackRadio'])
        Espionage.sendFleetMethod = self.sendFleet
        Espionage.deleteMessageMethod = self._web.deleteMessage
        mySolarSystem = self.myPlanets[0].coords.solarSystem
        pendingEspionages = []        
        
#        file = open("planets.tmp",'r')
#        planets = pickle.load(file)
#        file.close()
        
        planets  = self._findInactivePlanetsBis(range(mySolarSystem - attackRadio, mySolarSystem + attackRadio))
        self._spyPlanets([planet for planet in planets if len(planet.spyReports) == 0],probesToSend)

        file = open("planets.tmp",'w')
        pickle.dump(planets,file)
        file.close()
        
        targetPlanets = [planet for planet in planets if not planet.spyReports[-1].hasNonMissileDefense() and not planet.spyReports[-1].hasFleet()]
        planets = targetPlanets

        while True:
            for planet in planets:
                planet.updateRentability(abs(planet.coords.solarSystem - mySolarSystem))
            planets.sort(key=lambda x:x.rentability,reverse=True)            


            try:
                startTime = self._web.getMyPlanetsAndServerTime()[1]
                espionage = Espionage(planets[0],probesToSend)                
                espionage.launch(startTime)
                pendingEspionages.append(espionage)                
                del planets[0] # so that is not spied again until this report arrives
            except (NoFreeSlotsError,IndexError):
                time.sleep(2)
                displayedReports = self._web.getSpyReports()
                for espionage in pendingEspionages[:]:
                    if espionage.hasArrived(displayedReports):
                        report = espionage.spyReport
                        planet = espionage.targetPlanet
                        planet.spyReports.append(report)
                        pendingEspionages.remove(espionage)
                        planets.append(planet) # restore planet in general planet list
                        if not report.hasNonMissileDefense() and not report.hasFleet():
                            self._attack(planet)

                
    def _findInactivePlanetsBis(self,range):
        inactivePlanets = []
        
        for solarSystemNumber in range:
            solarSystem = self._web.getSolarSystem(self.myPlanets[0].coords.galaxy,solarSystemNumber)    
            #self._planetDb.writeMany(solarSystem.values())      
            for planet in solarSystem.values():
                if "inactive" in planet.ownerStatus:
                    inactivePlanets.append(planet)
        
        return inactivePlanets

    def _spyPlanets(self,planets,probesToSend):
        # no threading usage results in.... unmantainable algorith!!! here it goes:
        pendingEspionages = []
        startTime = self._web.getMyPlanetsAndServerTime()[1]
        for planet in planets:
            try:
                espionage = Espionage(planet,probesToSend)                
                espionage.launch(startTime)
                pendingEspionages.append(espionage)                
            except NoFreeSlotsError:
                displayedReports = self._web.getSpyReports()
                for espionage in pendingEspionages[:]:
                    if espionage.hasArrived(displayedReports):
                        espionage.targetPlanet.spyReports.append(espionage.spyReport)
                        pendingEspionages.remove(espionage)
                time.sleep(5)                        
                        
        while len(pendingEspionages)>0:
            displayedReports = self._web.getSpyReports()
            for espionage in pendingEspionages[:]:
                if espionage.hasArrived(displayedReports):
                    espionage.targetPlanet.spyReports.append(espionage.spyReport)
                    pendingEspionages.remove(espionage)       
            time.sleep(5)
        
    def _attack(self,planet):
        spyReport = planet.spyReports[-1]
        resourcesToSteal = spyReport.resources.half()
        ships = (resourcesToSteal.total() + 5000) / self.attackingShip.capacity
        fleet = { self.attackingShip.name : ships }
        try: 
            self.sendFleet(spyReport.coords,MissionTypes.attack,fleet)
        except FleetSendError, e:
            spyReport.actionTook = "Error when attacking"                    
            #self._eventMgr.errorAttackingPlanet(planet,e)
        else:
            spyReport.actionTook = "Attacked"
            spyReport.resources = spyReport.resources - resourcesToSteal
            #self._eventMgr.planetAttacked(planet,fleet,resourcesToSteal)        
    
    def _start(self):
        
        spyingFleet = {'espionageProbe':self.config['probesToSend']}
        probesToSend = int(self.config['probesToSend'])
        while True: # main application loop
            self.config.load()            
            spyStartTime = self._web.getMyPlanetsAndServerTime()[1]

            freeSlots = self.waitForFreeSlot()                        
            self._eventMgr.targetsSearchBegin(freeSlots)

            targetPlanets = self._findInactivePlanets(freeSlots)
            self._eventMgr.targetsSearchEnd()
            
            self._eventMgr.espionagesBegin(freeSlots)
            for planet in targetPlanets[:]: # loop that launches espionages
                try:
                    self.sendFleet(planet.coords,MissionTypes.spy,spyingFleet)
                    self._eventMgr.probesSent(planet,probesToSend)
                    self.lastSpiedCoords = planet.coords                    
                except FleetSendError, e:
                    self._eventMgr.errorSendingProbes(planet,probesToSend, e)
                    targetPlanets.remove(planet) # discard planet
                    self.lastSpiedCoords = planet.coords                                        
            self._eventMgr.espionagesEnd()
            
            self._eventMgr.waitForReportsBegin(len(targetPlanets))
            self._waitForSpyReports(targetPlanets,spyStartTime)
            self._eventMgr.waitForReportsEnd()
            
            minTheft = int(self.config['minTheft'])
            #filter:
            if len(targetPlanets) > 0:
                self._eventMgr.reportsAnalysisBegin(len(targetPlanets))
                for planet in targetPlanets[:]:
                    spyReport = planet.spyReports[-1]
                    spyReport.probesSent = probesToSend
                    skippedCause = None
                    if spyReport.hasNonMissileDefense() or spyReport.hasFleet():
                        skippedCause = "defenses or fleet"
                    elif not spyReport.resources.areRentable(minTheft):
                        skippedCause = "few resources: %s" % spyReport.resources
                    if skippedCause:
                        self._eventMgr.planetSkipped(planet,skippedCause)
                        spyReport.actionTook = "Skipped"
                        targetPlanets.remove(planet)
                self._eventMgr.reportsAnalysisEnd()
                
            if len(targetPlanets) > 0:
                #  definite attacking loop:
                self._eventMgr.attacksBegin(len(targetPlanets))
    
                for planet in targetPlanets:
                    while True: 
                        spyReport = planet.spyReports[-1] 
                        if not spyReport.resources.areRentable(minTheft):
                            break
                        resourcesToSteal = spyReport.resources.half()
                        ships = (resourcesToSteal.total() + 5000) / self.attackingShip.capacity
                        fleet = { self.attackingShip.name : ships }
                        try: 
                            self.sendFleet(spyReport.coords,MissionTypes.attack,fleet)
                        except FleetSendError, e:
                            spyReport.actionTook = "Error when attacking"                    
                            self._eventMgr.errorAttackingPlanet(planet,e)
                        else:
                            spyReport.actionTook = "Attacked"
                            spyReport.resources = spyReport.resources - resourcesToSteal
                            self._planetDb.write(planet)
                            self._eventMgr.planetAttacked(planet,fleet,resourcesToSteal)
                                                    
                self._eventMgr.attacksEnd()



    
    def waitForFreeSlot(self):
        waitingForSlot = False
        while True:
            freeSlots = self._web.getFreeSlots()
            if freeSlots > 0:
                break
            if not waitingForSlot:
                self._eventMgr.waitForSlotBegin()
                waitingForSlot = True
            time.sleep(10)
        else: time.sleep(10)
        if waitingForSlot: 
            self._eventMgr.waitForSlotEnd()
        return freeSlots
    
    def _findInactivePlanets(self,howMany):
        foundPlanets = []
        solarSystem = None
        attackRadio = int(self.config['attackRadio'])
        mySolarSystem = self.myPlanets[0].coords.solarSystem
        targetCoords = copy.copy(self.lastSpiedCoords)
        for dummy in range(howMany): 
            while True: # keep searching until we find an inactive planet
                previousSS = targetCoords.solarSystem
                targetCoords.increment()
                
                if targetCoords.solarSystem > mySolarSystem + attackRadio:
                    targetCoords.solarSystem = mySolarSystem - attackRadio
                    targetCoords.planet = 1
                if solarSystem is None or previousSS != targetCoords.solarSystem:
                    solarSystem = self._web.getSolarSystem(targetCoords.galaxy,targetCoords.solarSystem)                
                    self._eventMgr.solarSystemAnalyzed(targetCoords.galaxy,targetCoords.solarSystem)                    
                    for planet in solarSystem.values():
                        planetInDb = self._planetDb.read(str(planet.coords))
                        if planetInDb:
                            planet.spyReports = planetInDb.spyReports # keep old spy reports
                    self._planetDb.writeMany(solarSystem.values())
                            
                targetPlanet = solarSystem.get(str(targetCoords))
                if not targetPlanet or not 'inactive' in targetPlanet.ownerStatus: continue
                if len(targetPlanet.spyReports) == 0:
                    self._eventMgr.targetPlanetFound(targetPlanet)
                    break

                lastSpyReport = targetPlanet.spyReports[-1]
                if lastSpyReport.calculateAge().days >= 1: 
                    self._eventMgr.targetPlanetFound(targetPlanet)
                    break
                
                # speculation  based on last spy report:
          
                speculated, resourcesByNow = lastSpyReport.calculateResourcesByNow()                    
                if  not resourcesByNow.areRentable(int(self.config['minTheft'])):
                    if speculated: 
                        reason = "it has few resources: %s (speculated)" % resourcesByNow
                    else:
                        reason = "it has few resources: %s (calculated with last espionage)" % resourcesByNow
                    self._eventMgr.planetSkippedByPrecalculation(targetPlanet,reason)
                    continue
                
                if lastSpyReport.hasNonMissileDefense():
                    self._eventMgr.planetSkippedByPrecalculation(targetPlanet,"it had defenses less than 24h ago")
                    continue
                
                self._eventMgr.targetPlanetFound(targetPlanet)
                break
            
            foundPlanets.append(targetPlanet)
        return foundPlanets
    
    def _waitForSpyReports(self,targetPlanets,spyStartTime):
        unpairedPlanets = copy.copy(targetPlanets)
        waitingStartTime = datetime.now()
        while len(unpairedPlanets) > 0 and waitingStartTime + timedelta(minutes=5) > datetime.now():
            time.sleep(5)
            listedReports = self._web.getSpyReports()
            reportsDict  = dict([(str(report.coords),report) for report in listedReports if report.date >= spyStartTime])
            for planet in unpairedPlanets[:]:
                spyReport = reportsDict.get(str(planet.coords))
                if spyReport:
                    planet.spyReports.append(spyReport)
                    self._planetDb.write(planet)                    
                    unpairedPlanets.remove(planet)
                    self._web.deleteMessage(spyReport)
                    
    def sendFleet(self,destCoords,mission,fleet,waitForFreeSlot=True,waitIfNoShips=True,resources=Resources(),speed=100,sourcePlanetCode = 0):
        waitingForShips = False
        waitingForSlot  = False
        result = None
        while True:
            try:
                result = self._web.sendFleet(destCoords,mission,fleet,resources,speed,sourcePlanetCode)
            except NoFreeSlotsError:
                if not waitForFreeSlot:
                    raise
                else:
                    if not waitingForSlot:
                        self._eventMgr.waitForSlotBegin()
                        waitingForSlot = True
                    time.sleep(10)
            except ZeroShipsError, e:
                if not waitIfNoShips:
                    raise
                else:
                    if not waitingForShips:
                        self._eventMgr.waitForShipsBegin(e)
                        waitingForShips = True
                    time.sleep(10)
            else:
                break    
        if waitingForShips: self._eventMgr.waitForShipsEnd()
        if waitingForSlot: self._eventMgr.waitForSlotEnd()
        return result
        
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
    
    
    def saveState(self):
        file = open(STATE_FILE,'w')
        if self.lastSpiedCoords:
            pickle.dump(self.lastSpiedCoords,file)
        file.close()
        
    def loadState(self):
        try:
            file = open(STATE_FILE,'r')
            self._lastSpiedCoords = pickle.load(file)
            file.close()
        except (EOFError,IOError):
            try:
                os.remove(STATE_FILE)            
            except Exception : pass
            return False
        return True
    
    def getControlUrl(self):
        return self._web.getControlUrl()


if __name__ == "__main__":

    for i in "botdata","log","config":
        try: os.makedirs(i)
        except OSError, e: 
            if "File exists" in e: pass   
            
    logging.basicConfig(level=logging.CRITICAL,format = '%(message)s') 
    handler = logging.handlers.RotatingFileHandler(LOG_FILE,'a',100000,10)
    handler.setLevel(logging.INFO)
    logging.getLogger('').addHandler(handler)

    if len(sys.argv) > 1 and sys.argv[1] == "console":
        bot = Bot()
        bot.start()
        bot.join()
    else:
        from gui import guiMain
        guiMain()
        