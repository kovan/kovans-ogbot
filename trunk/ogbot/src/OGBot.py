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
#sys.path.append('lib')
#sys.path.append('src')

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
    

#class PlanetPair(object):
#    def __init__(self, sourcePlanet,targetPlanet):
#        self.sourcePlanet = sourcePlanet
#        self.targetPlanet = targetPlanet    
#    def __repr__(self):
#        return self.targetPlanet.__repr__()


class Bot(threading.Thread):
    """Contains the bot logic, independent from the communications with the server.
    Theorically speaking if ogame switches from being web-based to being p.e. telnet-based
    this class should not be touched, only Controller """
    class EventManager(BaseEventManager):
        ''' Displays events in console, logs them to a file or tells the gui about them'''
        def __init__(self, gui = None):
            self.gui = gui
        
        def solarSystemAnalyzed(self, galaxy, solarSystem):
            self.logAndPrint('|       Analyzed solar system [%s:%s:]' % (galaxy, solarSystem))
            self.dispatch("solarSystemAnalyzed", galaxy, solarSystem)              
        def planetAttacked(self, planet, fleet, resources):
            self.logAndPrint('|       Planet %s attacked by %s for %s' % (planet, fleet, resources))
            self.dispatch("planetAttacked", planet, fleet, resources)              
        def errorAttackingPlanet(self, planet, reason):
            self.logAndPrint('|**    Error attacking planet %s ( %s )' % (planet, reason))
            self.dispatch("errorAttackingPlanet", planet, reason)              
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
        def fatalException(self, exception):
            self.logAndPrint("| Fatal error found, terminating. %s" % exception)
            self.dispatch("fatalException", exception)
        # new GUI messages:
        def simulationsUpdate(self,simulations,rentabilities):
            self.dispatch("simulationsUpdate",simulations,rentabilities)
        def activityMsg(self,msg):
            
            self.logAndPrint(msg)
            self.dispatch("activityMsg",msg)

            
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
        self.config.load()
        self.allTranslations = Translations()
        self.simulations = {}   
        self.targetPlanets = []
    
            
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
        self._saveFiles()
        if self._web:
            self._web.saveState()
            
    def _saveFiles(self):
        file = open(FILE_PATHS['gamedata'], 'w')
        pickle.dump(self.targetPlanets, file)
        pickle.dump(self.simulations, file)
        pickle.dump(self.reachableSolarSystems, file)
        file.close()
                
    def _connect(self):
        self._web = WebAdapter(self.config, self.allTranslations, self.gui)
        self.myPlanets, serverTime = self._web.getMyPlanetsAndServerTime()
        self.serverTimeDelta = datetime.now() - serverTime
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
                    

    def serverTime(self):
        return _calculateServerTime(self.serverTimeDelta)
    
    def _start(self): 
        self._checkThreadQueue()
        #initializations
        probesToSend, attackRadio = self.config.probesToSend, int(self.config.attackRadio)
        notArrivedEspionages = {}
        planetsToSpy = []


                
        # load previous simulations and planets

        try:
            file = open(FILE_PATHS['gamedata'], 'r')
            self.targetPlanets = pickle.load(file)            
            self.simulations = pickle.load(file)
            self.reachableSolarSystems = pickle.load(file)
            file.close()    
            self._eventMgr.activityMsg("Loading previous espionage data...") 
        except (EOFError, IOError):
            self.simulations = {}
            self.targetPlanets = []
            self.reachableSolarSystems = []
            try:
                os.remove(FILE_PATHS['gamedata'])              
            except Exception : pass
            
        # generate reachable solar systems list
        newReachableSolarSystems = [] # contains tuples of (galaxy,solarsystem)
        for sourcePlanet in self.sourcePlanets:
            galaxy = sourcePlanet.coords.galaxy
            for solarSystem in range(sourcePlanet.coords.solarSystem - attackRadio, sourcePlanet.coords.solarSystem + attackRadio):
                tuple = (galaxy, solarSystem)
                if tuple not in newReachableSolarSystems:
                    newReachableSolarSystems.append(tuple)
        
        if newReachableSolarSystems != self.reachableSolarSystems: # something changed in configuration (attack radio or attack sources), reinitialize everything
            self.simulations = {}
            self.targetPlanets = []
            self.reachableSolarSystems = newReachableSolarSystems
            del(newReachableSolarSystems)            
            self._eventMgr.activityMsg("Searching inactive planets in range...")            
            self.targetSolarSystemsIter = itertools.cycle(self.reachableSolarSystems)            
            for dummy in self.reachableSolarSystems: 
                self._scanNextSolarSystem()       
            if not self.targetPlanets:
                raise BotFatalError("No inactive planets found in range. Increase range.")            
            self._saveFiles()
        else: # initialize iterator anyway
            self.targetSolarSystemsIter = itertools.cycle(self.reachableSolarSystems)

        
                
#        # scan solar systems in range for which no inactive planets were found,
#        # mostly to deal with range changes in the configuration
#        for sourcePlanet,solarSystem in reachableSolarSystems: 
#            galaxy = sourcePlanet.coords.galaxy
#            found = [p for p in self.targetPlanets if p.targetPlanet.coords.galaxy == galaxy and p.targetPlanet.coords.solarSystem == solarSystem ]
#            if not found:
#                self._scanNextSolarSystem((sourcePlanet,solarSystem))




                
#        else:
#            # restore simulation and planet data for old planets
#            for planetPair in loadedTargetPlanets:
#                #search the equivalent planet in the restored list
#                found = [pair for pair in loadedTargetPlanets if planet.coords == pair.targetPlanet.coords]
#                if len(found): #if found
#                    planet.spyReportHistory = found[0].spyReportHistory # copy spy reports to newly created planet object
#                    self.simulations[planetPair] = loadedSimulations[found[0]] # insert restored simulations into simulations dict
#                    self.targetPlanets += planetPair #insert planet pair into main planet list
#                else: newPlanets.append(planetPair) # otherwise the planet has became inactive recently, queue for initial espionage
            
#        # spy planets that have become inactive since last bot execution
#        self._spyPlanets(newPlanets, probesToSend)
#        # initialize simulations for these new planets
#        for planet in newPlanets:
#            lastReport = planet.spyReportHistory[-1] 
#            self.simulations[planet] = ResourceSimulation(lastReport.resources, lastReport.buildings) # insert the planet into main simulations list
#            self.targetPlanets += planetPair    #insert planet pair into main planet list
#
#        


               
        self._eventMgr.activityMsg("Bot started.")
        ## -------------- MAIN LOOP --------------------------
        while True:
            self._saveFiles()             
            self._checkThreadQueue()
            
            
            if self.targetPlanets:  # just in case there are no planets
                print "tick"
                
                # generate rentability table
                rentabilities = [] # list of the form (planet,rentability)
                for planet in self.targetPlanets:
                    sourcePlanet = self._calculateNearestSourcePlanet(planet)
                    flightTime = sourcePlanet.coords.flightTimeTo(planet.coords)
                    if  self.simulations.has_key(repr(planet.coords)):
                        rentability = self.simulations[repr(planet.coords)].simulatedResources.rentability(flightTime.seconds)
                        if not planet.spyReportHistory[-1].isUndefended():
                            rentability = -1
                    else: rentability = -1

                    rentabilities.append((planet,rentability))
                    
                rentabilities.sort(key=lambda x:x[1], reverse=True) # sorty by rentability
                 
                # show planet table    
                self._eventMgr.simulationsUpdate(self.simulations,rentabilities)
#                for planetPair, rentability in rentabilities:
#                    planet = planet
#                    if planet.spyReportHistory and planet.spyReportHistory[-1].isUndefended():
#                        defendedStr = "-->"
#                    else: defendedStr = "   "
#                    try:
#                        simulatedResources = self.simulations[repr(planet.coords)].simulatedResources
#                    except KeyError: simulatedResources = '?'
#
#                    print defendedStr, planetPair.sourcePlanet,planet, rentability, simulatedResources

                

                try:
                    # check for missing and expired reports and add them to spy queue
                    for planet in self.targetPlanets:
                        if (not planet.spyReportHistory \
                        or planet.spyReportHistory[-1].hasExpired(self.serverTime())  )\
                        and planet not in planetsToSpy \
                        and planet not in notArrivedEspionages.keys():
                            planetsToSpy.append(planet)
                             
                    if not planetsToSpy:
                        print "no planets to spy"
                        
                        found = [x for x in rentabilities if x[1] > 0]
                        if not found:
                            raise BotFatalError("There are no undefended planets in range.")


                        print "attacking"
                        # ATTACK
                        iterator = itertools.cycle(rentabilities)
                        retry = True
                        while retry == True:                            
                            retry = False                            
                            finalPlanet, rentability = iterator.next()
                            if rentability > 0 
                                if finalPlanet.spyReportHistory[-1].getAge(self.serverTime()).seconds < 600:                            
                                    simulation =  self.simulations[repr(finalPlanet.coords)]
                                    resourcesToSteal = simulation.simulatedResources.half()
                                    ships = int((resourcesToSteal.total() + 5000) / self.attackingShip.capacity)
                                    sourcePlanet = self._calculateNearestSourcePlanet(finalPlanet)
                                    mission = Mission(Mission.Types.attack, sourcePlanet, finalPlanet, { self.attackingShip.name : ships })
                                    try:
                                        self.launchMission(mission)        
                                        simulation.simulatedResources -= resourcesToSteal
                                        self._eventMgr.activityMsg( "%s: attacking  %s from %s" % (datetime.now(), finalPlanet, sourcePlanet))
                                    except NotEnoughShipsError, e:
                                        retry = True
                            else:
                                print "report old so re-spying"
                                planetsToSpy.append(finalPlanet)
                            
                    if planetsToSpy:
                        print "spying"
                        # SPY
                        retry = True
                        while retry == True:
                            retry = False                            
                            targetPlanet = planetsToSpy.pop(0)
                            sourcePlanet = self._calculateNearestSourcePlanet(targetPlanet)
                            espionage = Mission(Mission.Types.spy, sourcePlanet, targetPlanet, {'espionageProbe':probesToSend})
                            try:
                                self.launchMission(espionage)
                                self._eventMgr.activityMsg("%s: spying  %s from %s" % (datetime.now(), targetPlanet, sourcePlanet))
                                notArrivedEspionages[targetPlanet] = espionage
                            except NotEnoughShipsError, e:
                                planetsToSpy.append(targetPlanet) # re-locate planet at the end of the list for later
                                retry = True
                        
                except NoFreeSlotsError: 
                    self._scanNextSolarSystem();
                    print "no slots"
                except FleetSendError, e: 
                    print e
                    del self.simulations[repr(finalPlanet.coords)]
                    self.targetPlanets.remove(finalPlanet)
            

            # check for arrived espionages
            if len(notArrivedEspionages) > 0:
                displayedReports = self._web.getSpyReports()
                for planet, espionage in notArrivedEspionages.items():
                    spyReport = self._didEspionageArrive(espionage, displayedReports)
                    if  spyReport:
                        del notArrivedEspionages[planet]
                        if not planet.spyReportHistory:
                            self.simulations[repr(planet.coords)] = ResourceSimulation(spyReport.resources, spyReport.buildings)                            
                        planet.spyReportHistory.append(spyReport)
                        self.simulations[repr(planet.coords)].simulatedResources = spyReport.resources
                        

                   
            sleep(5)      

    def _scanNextSolarSystem(self,tuple = None): # inactive planets background search
        if tuple == None:
            galaxy, solarSystem = self.targetSolarSystemsIter.next()
        else: galaxy,solarSystem = tuple
        solarSystem = self._web.getSolarSystem(galaxy, solarSystem)                        
        for planet in solarSystem.values():
            found = [planet for planet in self.targetPlanets if planet.coords == planet.coords]
            if 'inactive' in planet.ownerStatus:
                if not found:
                    # we found a new inactive planet
                    self.targetPlanets.append(planet)    #insert planet into main planet list
            elif found: # no longer inactive
                for storedPlanet in self.targetPlanets[:]:
                    if storedPlanet.coords == planet.coords:
                        self.targetPlanets.remove(storedPlanet)
                        del self.simulations[repr(storedPlanet.coords)]
    
    def _calculateNearestSourcePlanet(self,enemyPlanet):
        minDistance = sys.maxint
        for sourcePlanet in self.sourcePlanets:
            if sourcePlanet.coords.distanceTo(enemyPlanet.coords) < minDistance:
                nearestSourcePlanet = sourcePlanet
        if nearestSourcePlanet.coords.galaxy != enemyPlanet.galaxy:
            BotFatalError("You own no planet in the same galaxy of %s, the planet could not be attacked (this should never happen)" % enemyPlanet)
            
        return nearestSourcePlanet

    def _didEspionageArrive(self, espionage, displayedReports):
        reports = [report for report in displayedReports if report.coords == espionage.targetPlanet.coords and report.date >= espionage.launchTime]
        reports.sort(key=lambda x:x.date, reverse=True)
        if len(reports) > 0:
            self._web.deleteMessage(reports[0])
            return reports[0]
        return None

        
#    def _findInactivePlanets(self,sourcePlanet, solarSystems):
#        ''' returns list of PlanetPairs (sourcePlanet,foundPlanet)'''
#        inactivePlanets = []
#        
#        for solarSystemNumber in solarSystems:
#            solarSystem = self._web.getSolarSystem(sourcePlanet.coords.galaxy, solarSystemNumber)    
#            self._checkThreadQueue()
#            #self._planetDb.writeMany(solarSystem.values())       
#            for planet in solarSystem.values():
#                if "inactive" in planet.ownerStatus:
#                    inactivePlanets.append(PlanetPair(sourcePlanet,planet))
#        
#        return inactivePlanets
#    
#        
#    def _spyPlanets(self, planets, probesToSend):
#        notArrivedEspionages = {}
#        pendingPlanets = copy.copy(planets)
#
#        while len(notArrivedEspionages) or len(pendingPlanets):
#            self._checkThreadQueue()
#            if len(pendingPlanets):
#                try: 
#                    planet = pendingPlanets.pop()
#                    espionage = Mission(Mission.Types.spy, self.sourcePlanet, planet, {'espionageProbe':probesToSend})
#                    self.launchMission(espionage, False)
#                    print "spying %s" % planet
#                    notArrivedEspionages[planet]  = espionage
#                except NoFreeSlotsError: 
#                    self._onIdleTime()
#                    pendingPlanets.append(planet); print "slots full"
#                except FleetSendError, e:
#                    planets.remove(planet)
#                    print str(planet) + str(e)
#            
#            if len(notArrivedEspionages):
#                displayedReports = self._web.getSpyReports()
#                for planet, espionage in notArrivedEspionages.items():
#                    expired = self.serverTime() > espionage.launchTime + timedelta(minutes=5)
#                    spyReport = self._didEspionageArrive(espionage, displayedReports)
#                    if  spyReport:
#                        del notArrivedEspionages[planet]
#                        planet.spyReportHistory.append(spyReport)
#                    elif expired:    
#                        del notArrivedEspionages[planet]
#                        pendingPlanets.append(planet)
#            sleep(3)
        

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
    
    
    def launchMission(self, mission, waitForFreeSlot=False, waitIfNoShips=False):
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
        