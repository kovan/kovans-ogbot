#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2006 by kovan 
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

import sys
sys.path.append('lib')
sys.path.append('src')

import logging, logging.handlers
import threading
import traceback
from Queue import *
import copy
import time

import pickle
import urllib2
import itertools
import os

if os.getcwd().endswith("src"):
    os.chdir("..")	
    
from datetime import datetime, timedelta
from optparse import OptionParser
# bot classes:

from GameEntities import *
from CommonClasses import *
from WebAdapter import WebAdapter
from Constants import *


            
def _calculateServerTime(delta):
    return delta + datetime.now()

class ResourceSimulation(object):
    def __init__(self, baseResources, mines):
        self.simulatedResources = copy.copy(baseResources)

        if mines is not None:
            self._metalMine = mines.get('metalMine', 0)
            self._crystalMine = mines.get('crystalMine', 0)
            self._deuteriumSynthesizer = mines.get('deuteriumSynthesizer', 0)
        else:
            self._metalMine, self._crystalMine, self._deuteriumSynthesizer = 22, 19, 10
            
    def _setResources(self, resources):
        self._resourcesSimulationTime = datetime.now() # no need to use server time because it's use is isolated to inside this class
        self._baseResources = resources         
        
    def _calculateResources(self):
        productionTime = datetime.now() - self._resourcesSimulationTime
        productionHours = productionTime.seconds / 3600.0
        produced = Resources()
        produced.metal      = 30 * self._metalMine      * 1.1 ** self._metalMine      * productionHours
        produced.crystal   = 20 * self._crystalMine   * 1.1 ** self._crystalMine   * productionHours
        produced.deuterium = 10 * self._deuteriumSynthesizer * 1.1 ** self._deuteriumSynthesizer * productionHours * (-0.002 * 60 + 1.28) # 60 is the temperature of a planet in position 7
        return self._baseResources + produced
            
    simulatedResources = property(_calculateResources, _setResources)         
    




class Bot(threading.Thread):
    """Contains the bot logic, independent from the communications with the server.
    Theorically speaking if ogame switches from being web-based to being p.e. telnet-based
    this class should not be touched, only Controller """
    class EventManager(BaseEventManager):
        ''' Displays events in console, logs them to a file or tells the gui about them'''
        def __init__(self, gui = None):
            self.gui = gui
        
        def targetsSearchBegin(self, howMany):
            self.logAndPrint(' / Looking for %s inactive planets to spy...' % howMany)
            self.dispatch("targetsSearchBegin", howMany)
        def solarSystemAnalyzed(self, galaxy, solarSystem):
            self.logAndPrint('|       Analyzed solar system [%s:%s:]' % (galaxy, solarSystem))
            self.dispatch("solarSystemAnalyzed", galaxy, solarSystem)              
        def targetPlanetFound(self, planet):
            self.logAndPrint('|       Target planet found: %s' % planet)
            self.dispatch("targetPlanetFound", planet)              
        def targetsSearchEnd(self):         
            self.logAndPrint('')
            self.dispatch("targetsSearchEnd")              
        def espionagesBegin(self, howMany): 
            self.logAndPrint(' / Planet( s ) found, starting espionage( s )')
            self.dispatch("espionagesBegin", howMany)              
        def probesSent(self, planet, howMany):
            self.logAndPrint('|       %s probe( s ) sent to planet %s' % (howMany, planet))
            self.dispatch("probesSent", planet, howMany)              
        def errorSendingProbes(self, planet, probesCount, reason):
            self.logAndPrint('|**    Error sending probes to planegt %s ( %s )' % (planet, reason))
            self.dispatch("errorSendingProbes", planet, probesCount, reason)               
        def espionagesEnd(self):
            self.logAndPrint(' \  All espionage( s ) launched')
            self.dispatch("espionagesEnd")              
        def waitForReportsBegin(self, howMany):
            self.logAndPrint(' / Waiting for all %s spy report( s ) to arrive...' % howMany)
            self.dispatch("waitForReportsBegin", howMany)
        def waitForReportsEnd(self):
            self.logAndPrint(' \  All spy report( s ) arrived')
            self.dispatch("waitForReportsEnd")              
        def reportsAnalysisBegin(self, howMany):
            self.logAndPrint(' / Analyzing %s spy reports ' % howMany)
            self.dispatch("reportsAnalysisBegin", howMany)              
        def planetSkipped(self, planet, cause):
            self.logAndPrint('|       Skipping planet %s because it has %s' % (planet, cause))
            self.dispatch("planetSkipped", planet, cause)              
        def reportsAnalysisEnd(self):
            self.logAndPrint(' \  All spy report( s ) analyzed')
            self.dispatch("reportsAnalysisEnd")              
        def attacksBegin(self, howMany):
            self.logAndPrint(' / Starting %s attacks...' % howMany)
            self.dispatch("attacksBegin", howMany)              
        def planetAttacked(self, planet, fleet, resources):
            self.logAndPrint('|       Planet %s attacked by %s for %s' % (planet, fleet, resources))
            self.dispatch("planetAttacked", planet, fleet, resources)              
        def errorAttackingPlanet(self, planet, reason):
            self.logAndPrint('|**    Error attacking planet %s ( %s )' % (planet, reason))
            self.dispatch("errorAttackingPlanet", planet, reason)              
        def attacksEnd(self):
            self.logAndPrint(' \ Attacks finished')
            self.dispatch("attacksEnd")              
        def waitForSlotBegin(self):
            self.logAndPrint(' |          Simultaneous fleet limit reached. Waiting...')
            self.dispatch("waitForSlotBegin")              
        def waitForSlotEnd(self):
            self.logAndPrint(' |')
            self.dispatch("waitForSlotEnd")              
        def waitForShipsBegin(self, shipType):
            self.logAndPrint(' |          There are no available ships of type %s. Waiting...' % shipType)
            self.dispatch("waitForShipsBegin", shipType)              
        def waitForShipsEnd(self): 
            self.dispatch("waitForShipsEnd")              
        def planetSkippedByPrecalculation(self, planet, reason):
            self.logAndPrint("|       Skipping planet %s because %s" % (planet, reason))
            self.dispatch("planetSkippedByPrecalculation", planet, reason)
        def fatalException(self, exception):
            self.logAndPrint("| Fatal error found, terminating. %s" % exception)
            self.dispatch("fatalException", exception)
        
    def __init__(self, gui = None):   #only non-blocking tasks should go in constructor
        threading.Thread.__init__(self, name="BotThread")
        self.gui = gui
        self.msgQueue = Queue()
        self._eventMgr = Bot.EventManager(gui)
        self._planetDb = PlanetDb(FILE_PATHS['planetdb'])
        self.config = Configuration(FILE_PATHS['config'])                   
        self._web = None
        self.attackingShip = INGAME_TYPES_BY_NAME[self.config.attackingShip]                        
        self.myPlanets = []
        self.simulations = []
        self.config.load()
        self.allTranslations = Translations()

    
            
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
                self._eventMgr.fatalException(e)
                break
            except Exception:
                traceback.print_exc()
            sleep(5)
    
    def stop(self):
        file = open(FILE_PATHS['planets'], 'w')
        pickle.dump(self.simulations, file)
        file.close()
        
        if self._web:
            self._web.saveState()
        
    def _connect(self):
        self._web = WebAdapter(self.config, self.allTranslations, self.gui)
        self.myPlanets, serverTime = self._web.getMyPlanetsAndServerTime()
        self.serverTimeDelta = datetime.now() - serverTime

    def serverTime(self):
        return _calculateServerTime(self.serverTimeDelta)
    
    def _start(self): 
        self._checkThreadQueue()
        probesToSend, attackRadio = self.config.probesToSend, int(self.config.attackRadio)

        self.sourcePlanet = self.myPlanets[8]
        mySolarSystem = self.sourcePlanet.coords.solarSystem
        notArrivedEspionages = {}
        planetsToSpy = []
        self.simulations = {}

        try:
            file = open(FILE_PATHS['planets'], 'r')
            loadedSimulations = pickle.load(file)
            file.close()
        except (EOFError, IOError):
            loadedSimulations = {}
            try:
                os.remove(FILE_PATHS['planets'])              
            except Exception : pass

        inactivePlanets = self._findInactivePlanets(range(mySolarSystem - attackRadio, mySolarSystem + attackRadio))
        
        # spy and create a new simulation object for new ones, and
        # restore simulation and planet data for old ones

        newPlanets = []
        for planet in inactivePlanets:
            loadedPlanets = [p for p in loadedSimulations.keys() if planet.coords == p.coords]
            if len(loadedPlanets): 
                planet.spyReportHistory = loadedPlanets[0].spyReportHistory
                self.simulations[planet] = loadedSimulations[loadedPlanets[0]]
            else: newPlanets.append(planet)

        self._spyPlanets(newPlanets, probesToSend)
        for planet in newPlanets:
            lastReport = planet.spyReportHistory[-1]
            self.simulations[planet] = ResourceSimulation(lastReport.resources, lastReport.buildings)

        del(newPlanets, inactivePlanets)
        
        file = open(FILE_PATHS['planets'], 'w')
        pickle.dump(self.simulations, file)
        file.close()
        self.planets = dict([ (str(planet.coords), planet) for planet in self.simulations.keys() ])
        
        while True:
            self._checkThreadQueue()


            
            if len(self.simulations) > 0: # launch attacking espionages/attacks
                planets = [] # (planet,rentability) pairs
                for planet, simulation in self.simulations.items():
                    flightTime = self.sourcePlanet.coords.flightTimeTo(planet.coords)
                    rentability = simulation.simulatedResources.rentability(flightTime.seconds)
                    planets.append((planet, rentability))
                    
                planets.sort(key=lambda x:x[1], reverse=True)
                    
                for planet, rentability in planets:
                    if planet.spyReportHistory[-1].isUndefended():
                        defendedStr = "-->"
                    else: defendedStr = "xxx"
                    print defendedStr, planet, rentability, self.simulations[planet].simulatedResources
                    
                targetPlanet = (x[0] for x in planets if x[0] not in notArrivedEspionages and x[0].spyReportHistory[-1].isUndefended()).next()

                try:
#                    solarSystem = self._web.getSolarSystem(targetPlanet.coords.galaxy, targetPlanet.coords.solarSystem)                        
#                    for planet in solarSystem.values():
#                        storedPlanet = self.simulations.get(str(planet.coords))
#                        if 'inactive' in planet.ownerStatus:
#                            if not storedPlanet:
#                                # ha pasado a estar inactivo
#                                self.simulations[planet]
#                                planetsToSpy.append()
#                            else:
#                                # se mantiene inactivo
#                                pass
#                        else:
#                            if storedPlanet:
#                                # ha dejado de estar inactivo:                                
#                                del self.simulations[storedPlanet]
#                            else: 
#                                # se mantiene activo                       
#                                pass
                             
                    
                    if targetPlanet.spyReportHistory[-1].getAge(self.serverTime()).seconds < 600:
                        # ATTACK
                        simulation =  self.simulations[targetPlanet]
                        resourcesToSteal = simulation.simulatedResources.half()
                        ships = int((resourcesToSteal.total() + 5000) / self.attackingShip.capacity)
                        mission = Mission(Mission.Types.attack, self.sourcePlanet, targetPlanet, { self.attackingShip.name : ships })
                        self.launchMission(mission, False)
                        simulation.simulatedResources -= resourcesToSteal
                        print "    %s: attacking  %s" % (datetime.now(), targetPlanet)
                    else:
                        # SPY
                        for planet in self.simulations.keys():
                            if planet.spyReportHistory[-1].hasExpired(self.serverTime()):
                                planetsToSpy.append(planet)
                        if len(planetsToSpy) is 0:
                            planetsToSpy.append(targetPlanet)
                        espionage = Mission(Mission.Types.spy, self.sourcePlanet, planetsToSpy.pop(0), {'espionageProbe':probesToSend})
                        self.launchMission(espionage, False)
                        print  "    %s: spying  %s" % (datetime.now(), targetPlanet)
                        notArrivedEspionages[targetPlanet] = espionage
                except NoFreeSlotsError: 
                    self._onIdleTime();print "no slots"
                except FleetSendError, e: 
                    print e
                    del self.simulations[targetPlanet]
            

            # check for arrived espionages
            if len(notArrivedEspionages) > 0:
                displayedReports = self._web.getSpyReports()
                for planet, espionage in notArrivedEspionages.items():
                    spyReport = self._didEspionageArrive(espionage, displayedReports)
                    if  spyReport:
                        del notArrivedEspionages[planet]
                        planet.spyReportHistory.append(spyReport)
                        self.simulations[planet].simulatedResources = spyReport.resources
                        

                   
            sleep(5)      

    def _onIdleTime(self): # only short tasks should go here
        pass

    def _didEspionageArrive(self, espionage, displayedReports):
        reports = [report for report in displayedReports if report.coords == espionage.targetPlanet.coords and report.date >= espionage.launchTime]
        reports.sort(key=lambda x:x.date, reverse=True)
        if len(reports) > 0:
            self._web.deleteMessage(reports[0])
            return reports[0]
        return None

        
    def _findInactivePlanets(self, range):
        inactivePlanets = []
        
        for solarSystemNumber in range:
            solarSystem = self._web.getSolarSystem(self.sourcePlanet.coords.galaxy, solarSystemNumber)    
            self._checkThreadQueue()
            #self._planetDb.writeMany(solarSystem.values())       
            for planet in solarSystem.values():
                if "inactive" in planet.ownerStatus:
                    inactivePlanets.append(planet)
        
        return inactivePlanets
    
        
    def _spyPlanets(self, planets, probesToSend):
        notArrivedEspionages = {}
        pendingPlanets = copy.copy(planets)

        while len(notArrivedEspionages) or len(pendingPlanets):
            self._checkThreadQueue()
            if len(pendingPlanets):
                try: 
                    planet = pendingPlanets.pop()
                    espionage = Mission(Mission.Types.spy, self.sourcePlanet, planet, {'espionageProbe':probesToSend})
                    self.launchMission(espionage, False)
                    print "spying %s" % planet
                    notArrivedEspionages[planet]  = espionage
                except NoFreeSlotsError: 
                    self._onIdleTime()
                    pendingPlanets.append(planet); print "slots full"
                except FleetSendError, e:
                    planets.remove(planet)
                    print str(planet) + str(e)
            
            if len(notArrivedEspionages):
                displayedReports = self._web.getSpyReports()
                for planet, espionage in notArrivedEspionages.items():
                    expired = self.serverTime() > espionage.launchTime + timedelta(minutes=5)
                    spyReport = self._didEspionageArrive(espionage, displayedReports)
                    if  spyReport:
                        del notArrivedEspionages[planet]
                        planet.spyReportHistory.append(spyReport)
                    elif expired:    
                        del notArrivedEspionages[planet]
                        pendingPlanets.append(planet)
            sleep(3)
        

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
    
    
    def launchMission(self, mission, waitForFreeSlot=True, waitIfNoShips=True):
        waitingForShips = False
        waitingForSlot  = False
        result = None
        while True:
            try:
                result = self._web.launchMission(mission)
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
    
    parser = OptionParser()
    parser.add_option("-c", "--console", action="store_true", help="Run in console mode'")
    parser.add_option("-w", "--workdir", help="Specify working directory (useful to run various bots at once). If not specified defaults to 'files'")    
    (options, args) = parser.parse_args()
    
    if options.workdir:
        dirPrefix = options.workdir
    else:
        dirPrefix = 'files'
        
    for key, path in FILE_PATHS.items():
        path = dirPrefix + '/' + path
        FILE_PATHS[key] = path
        try: os.makedirs (os.path.dirname(path))
        except OSError, e: 
            if "File exists" in e: pass             
    if __debug__:
        try: os.makedirs ('debug')
        except OSError, e: 
            if "File exists" in e: pass      

    logging.basicConfig(level=logging.CRITICAL, format = '%(message)s') 
    handler = logging.handlers.RotatingFileHandler(os.path.abspath(FILE_PATHS['log']), 'a', 100000, 10)
    handler.setLevel(logging.INFO)
            
    if options.console:
        bot = Bot()
        bot.start()
        bot.join()
    else:
        from gui import guiMain
        guiMain()
        