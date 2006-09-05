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
# python library:
import sys
sys.path.append('lib')
sys.path.append('src')

import gc
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
        self._planetDb = PlanetDb(FILE_PATHS.planetdb)
        self.config = Configuration(FILE_PATHS.config)                
        self._web = None
        self.attackingShip = INGAME_TYPES_BY_NAME[self.config['attackingShip']]                        
        self.myPlanets = []
        self.planets = []
        
    
            
    def run(self):
        while True:
            try:
                self._connect()            
                self._start()
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
            sleep(5)
    
    def stop(self):
        file = open(FILE_PATHS.planets,'w')
        pickle.dump(self.planets,file)
        file.close()
        
        if self._web:
            self._web.saveState()        
        
    def _connect(self):
        try:
            self.config.load()
        except BotError, e: raise BotFatalError(e)

        self._web = WebAdapter(self.config,self._checkThreadQueue,self.gui)
        Espionage.sendFleetMethod = self.sendFleet
        Espionage.deleteMessageMethod = self._web.deleteMessage                
        self.myPlanets = self._web.getMyPlanetsAndServerTime()[0]

    def _start(self): 

        probesToSend, attackRadio = self.config['probesToSend'], int(self.config['attackRadio'])
        mySolarSystem = self.myPlanets[0].coords.solarSystem
        pendingEspionages = []        
        
        loadedPlanets = []
        try:
            file = open(FILE_PATHS.planets,'r')
            loadedPlanets = pickle.load(file)
            file.close()
        except (EOFError,IOError):
            try:
                os.remove(FILE_PATHS.planets)            
            except Exception : pass

        inactivePlanets = self._findInactivePlanets(range(mySolarSystem - attackRadio, mySolarSystem + attackRadio))
        
        # restore old list's working spy reports
        for planet in inactivePlanets:
            l = [p for p in loadedPlanets if planet.coords == p.coords]
            if len(l): 
                planet.workingSpyReport = l[0].workingSpyReport
        
        self._spyPlanets([planet for planet in inactivePlanets if not planet.workingSpyReport],probesToSend)
        for planet in inactivePlanets[:]:
            if not planet.workingSpyReport:
                inactivePlanets.remove(planet)
                
        planetsWithFleetOnly = [planet for planet in inactivePlanets if planet.workingSpyReport.hasFleet() and not planet.workingSpyReport.hasNonMissileDefense()]
        planetsWithDefense = [planet for planet in inactivePlanets if planet.workingSpyReport.hasNonMissileDefense()]
        
        file = open("defendedplanets.tmp",'w')
        pickle.dump(planetsWithFleetOnly,file)
        pickle.dump(planetsWithDefense,file)        
        file.close()
        
        interestingPlanets = [planet for planet in inactivePlanets if planet not in planetsWithDefense and planet not in planetsWithFleetOnly]
        self.planets = interestingPlanets
        
        file = open(FILE_PATHS.planets,'w')
        pickle.dump(self.planets,file)
        file.close()

        
        while True:
            self._checkThreadQueue()
            serverTime = self._web.getMyPlanetsAndServerTime()[1]

            for planet in self.planets:
                    planet.workingSpyReport.updateRentability(mySolarSystem,serverTime)
            self.planets.sort(key=lambda x: x.workingSpyReport.rentability,reverse=True)
            for planet in self.planets:
                print "%s\t%s\t\t%s\t\t\t%s\tMEU: %s\tDistance: %s\tSimulated: %s" % (planet.workingSpyReport.rentability, planet.workingSpyReport.getAge(serverTime), planet, planet.workingSpyReport.resources, planet.workingSpyReport.resources.metalEquivalent(),abs(planet.coords.solarSystem - mySolarSystem),planet.workingSpyReport.buildings is None)
            
            if len(self.planets) > 0: # launch attacking espionages/attacks
                targetPlanet = self.planets[0]
                age = targetPlanet.workingSpyReport.getAge(serverTime)
                
                gc.set_debug(gc.DEBUG_UNCOLLECTABLE)
                
                if age.seconds < 600:
                    try: self._attack(targetPlanet) ; print "    %s: attacking  %s" % (datetime.now(),targetPlanet)
                    except NoFreeSlotsError: print "no slots while attacking"
                    except FleetSendError: 
                        self.planets.remove(targetPlanet) 
                else:
                    try:
                        espionage = Espionage(targetPlanet,probesToSend)                
                        espionage.launch(serverTime) ; print  "    %s: spying  %s" % (datetime.now(),targetPlanet)
                    except NoFreeSlotsError: print "no slots while spying"
                    except FleetSendError: 
                        self.planets.remove(targetPlanet)                   
                    else:
                        self.planets.remove(targetPlanet) # so that is not spied again until this report arrives                        
                        pendingEspionages.append(espionage)
            

            # check for arrived espionages
            if len(pendingEspionages) > 0:
                displayedReports = self._web.getSpyReports()
                for espionage in pendingEspionages[:]:
                    if espionage.hasArrived(displayedReports):
                        espionage.targetPlanet.setWorkingSpyReport(espionage.spyReport)
                        pendingEspionages.remove(espionage)
                        self.planets.append(espionage.targetPlanet) # restore planet in general planet list
                        
            file = open(FILE_PATHS.planets,'w')
            pickle.dump(self.planets,file)
            file.close()                        
            sleep(5)     

                    
    def _findInactivePlanets(self,range):
        inactivePlanets = []
        
        for solarSystemNumber in range:
            solarSystem = self._web.getSolarSystem(self.myPlanets[0].coords.galaxy,solarSystemNumber,False)    
            #self._planetDb.writeMany(solarSystem.values())      
            for planet in solarSystem.values():
                if "inactive" in planet.ownerStatus:
                    inactivePlanets.append(planet)
        
        return inactivePlanets

    def _spyPlanets(self,planets,probesToSend):
        # planets with send error will be removed from list argument
        # no threading usage results in.... unmantainable algorith. Here it goes:
        pendingEspionages = []
        validPlanets = []

        while len(pendingEspionages) or len(planets):
            serverTime = self._web.getMyPlanetsAndServerTime()[1]            
            if len(planets):
                try: 
                    planet = planets.pop()
                    espionage = Espionage(planet,probesToSend)                                    
                    espionage.launch(serverTime)
                    pendingEspionages.append(espionage)                                    
                except NoFreeSlotsError: 
                    planets.append(planet)
                except FleetSendError, e:
                    print str(planet) + str(e)
            
            if len(pendingEspionages):
                displayedReports = self._web.getSpyReports()
                for espionage in pendingEspionages[:]:
                    horalimite = espionage.launchTime + timedelta(minutes=10)
                    caducado = serverTime > horalimite
                    if  espionage.hasArrived(displayedReports):
                        pendingEspionages.remove(espionage)
                        validPlanets.append(espionage.targetPlanet)
                        espionage.targetPlanet.setWorkingSpyReport(espionage.spyReport)
                    elif caducado:    
                        pendingEspionages.remove(espionage)
                        planets.append(espionage.targetPlanet)
                            
            
            sleep(5) 
                        
        return validPlanets
        
    def _attack(self,planet):
        resourcesToSteal = planet.workingSpyReport.resources.half()
        ships = int((resourcesToSteal.total() + 5000) / self.attackingShip.capacity)
        fleet = { self.attackingShip.name : ships }
        self.sendFleet(planet.workingSpyReport.coords,Mission.Types.attack,fleet,False)
        planet.workingSpyReport.actionTook = "Attacked"
        planet.workingSpyReport.resources = planet.workingSpyReport.resources - resourcesToSteal

    def waitForFreeSlot(self):
        waitingForSlot = False
        while True:
            freeSlots = self._web.getFreeSlots()
            if freeSlots > 0:
                break
            if not waitingForSlot:
                self._eventMgr.waitForSlotBegin()
                waitingForSlot = True
            sleep(10)
        else: sleep(10)
        if waitingForSlot: 
            self._eventMgr.waitForSlotEnd()
        return freeSlots
    
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
                    sleep(10)
            except NotEnoughShipsError, e:
                if not waitIfNoShips:
                    raise
                else:
                    if not waitingForShips:
                        self._eventMgr.waitForShipsBegin(e)
                        waitingForShips = True
                    sleep(10)
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
    
    
    def getControlUrl(self):
        return self._web.getControlUrl()


if __name__ == "__main__":

    createDirs()
    
    logging.basicConfig(level=logging.CRITICAL,format = '%(message)s') 
    handler = logging.handlers.RotatingFileHandler(os.path.abspath(FILE_PATHS.log),'a',100000,10)
    handler.setLevel(logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "console":
        bot = Bot()
        bot.start()
        bot.join()
    else:
        from gui import guiMain
        guiMain()
        