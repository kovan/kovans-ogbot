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
import time
import shutil
import cPickle
import urllib2
import itertools
import gc
import random

    
from datetime import datetime, timedelta
from optparse import OptionParser
# bot classes:

from GameEntities import *
from CommonClasses import *
from WebAdapter import WebAdapter
from Constants import *
            



class Bot(threading.Thread):
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
        threading.Thread.__init__(self, name="BotThread")
        self.gui = gui
        self.msgQueue = Queue()
        self._eventMgr = Bot.EventManager(gui)
        self._planetDb = PlanetDb(FILE_PATHS['planetdb'])
        self.config = Configuration(FILE_PATHS['config'])                   
        self._web = None
        self.myPlanets = []
        self.config.load()
        self.allTranslations = Translations()
        self.targetPlanets = []
        self.reachableSolarSystems = []
        self.scanning = False
            
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
                self._eventMgr.activityMsg("Something unexpected occured, see log file. Restarting bot.")        
            sleep(5)
    
    def stop(self):
        
        if self._web:
            self._web.saveState()
            
    def _saveFiles(self):
        path = FILE_PATHS['gamedata']
        try:
            shutil.move(path,path + ".bak")
        except IOError: pass
        
        file = open(path, 'wb')
        pickler = cPickle.Pickler(file,2)
        for i in [self.targetPlanets,self.reachableSolarSystems,self.lastInactiveScanTime,
                  self.config.webpage,self.config.universe,self.config.username]:
                  pickler.dump(i)
        file.close()
         
    def _connect(self):
        self._eventMgr.activityMsg("Connecting...")        
        self._web = WebAdapter(self.config, self.allTranslations, self._checkThreadQueue,self.gui)
        self.myPlanets = self._web.getMyPlanets()

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
        self._eventMgr.connected()            

    
    def _start(self): 

        #initializations
        attackRadius = int(self.config.attackRadius)
        self.attackingShip = INGAME_TYPES_BY_NAME[self.config.attackingShip]           
        notArrivedEspionages = {}
        planetsToSpy = []

                
        # load previous planets
        try:
            file = open(FILE_PATHS['gamedata'], 'rb')
            u = cPickle.Unpickler(file)
            self.targetPlanets = u.load()
            self.reachableSolarSystems = u.load()
            self.lastInactiveScanTime = u.load()
            storedWebpage = u.load()
            storedUniverse = u.load()
            storedUsername = u.load()
            file.close()
                 
            if storedWebpage != self.config.webpage \
            or storedUniverse != self.config.universe \
            or storedUsername != self.config.username:
                raise BotError() # if any of those has changed, invalidate stored espionages

            self._eventMgr.activityMsg("Loading previous espionage data...") 
        except (EOFError, IOError,BotError,ImportError,AttributeError):
            try: file.close()            
            except UnboundLocalError: pass
            self.targetPlanets = []
            self.reachableSolarSystems = []
            self._eventMgr.activityMsg("Invalid or missing gamedata, respying planets.")
            try:
                path = FILE_PATHS['gamedata']
                os.remove(path)              
            except Exception : pass


            
        # generate reachable solar systems list
        newReachableSolarSystems = [] # contains tuples of (galaxy,solarsystem)
        for sourcePlanet in self.sourcePlanets:
            galaxy = sourcePlanet.coords.galaxy
            first = max(1,sourcePlanet.coords.solarSystem - attackRadius)
            last = min(int(self.config.systemsPerGalaxy),sourcePlanet.coords.solarSystem + attackRadius)
            for solarSystem in range(first,last +1):
                tuple = (galaxy, solarSystem)
                if tuple not in newReachableSolarSystems:
                    newReachableSolarSystems.append(tuple)
        
        if newReachableSolarSystems != self.reachableSolarSystems: # something changed in configuration (attack radio or attack sources)
            self.reachableSolarSystems = newReachableSolarSystems
            del(newReachableSolarSystems)            
            # remove planets that are not in range anymore            
            for planet in self.targetPlanets[:]:
                if (planet.coords.galaxy,planet.coords.solarSystem) not in self.reachableSolarSystems:
                    self.targetPlanets.remove(planet)
            self._eventMgr.activityMsg("Searching inactive planets in range... This might take a while, but will only be done once.")            
            
            # re-scan for inactive planets
            for galaxy,solarSystem in self.reachableSolarSystems: 
                self._scanSolarSystem(galaxy,solarSystem)      
                self._eventMgr.simulationsUpdate(self.targetPlanets)
            self.lastInactiveScanTime = self._web.serverTime()

        if not self.targetPlanets:
            raise BotFatalError("No inactive planets found in range. Increase range.")    
        
        # remove planets to avoid from target list
        for planet in self.targetPlanets[:]:
            if planet.owner in self.config.playersToAvoid or planet.alliance in self.config.alliancesToAvoid:
                self.targetPlanets.remove(planet)

        
        self._eventMgr.activityMsg("Bot started.")

        # -------------- MAIN LOOP ---------------
        while True:
            self._saveFiles()

            # background inactive search    
            serverTime = self._web.serverTime()

            if (serverTime.hour == 0 and serverTime.minute >= 6 and serverTime.minute <= 15)\
            or serverTime - self.lastInactiveScanTime >= timedelta(days = 1, hours = 1):
                if not self.scanning: # trigger scan
                    self._targetSolarSystemsIter = iter(self.reachableSolarSystems)             
                    self.scanning = True
                    self._eventMgr.activityMsg("Performing inactives scan.")                                        

            if self.scanning:
                try:
                    for dummy in range(4):
                        galaxy, solarSystem = self._targetSolarSystemsIter.next()
                        self._scanSolarSystem(galaxy, solarSystem);                        
                except StopIteration:
                    self.lastInactiveScanTime = serverTime                        
                    self._eventMgr.activityMsg("Inactives scan finished.")                                                            
                    self.scanning = False
            


            # check for newly arrived espionages
            if len(notArrivedEspionages) > 0:
                displayedReports = self._web.getEspionageReports()
                for planet, espionage in notArrivedEspionages.items():
                    report = self._didEspionageArrive(espionage, displayedReports)
                    if  report:
                        report.probesSent = espionage.fleet['espionageProbe']
                        del notArrivedEspionages[planet]
                        planet.simulation = ResourceSimulation(report.resources, report.buildings)                            
                        planet.espionageHistory.append(report)
                        self._planetDb.write(planet)
                    elif self._web.serverTime() > espionage.arrivalTime + timedelta(minutes=5):
                        # probably due to buggy espionage report (containing only N;)
                        del notArrivedEspionages[planet]
                        self.targetPlanets.remove(planet)
                        self._eventMgr.activityMsg("Espionage report from %s never arrived. Deleting planet." % espionage.targetPlanet)

            
            # generate rentability table
            rentabilities = [] # list of the form (planet,rentability)
            for planet in self.targetPlanets:
                sourcePlanet = self._calculateNearestSourcePlanet(planet.coords)
                flightTime = sourcePlanet.coords.flightTimeTo(planet.coords)
                if planet.espionageHistory:
                    if not planet.espionageHistory[-1].isUndefended():
                        rentability = -1
                    else:
                        resources  = planet.simulation.simulatedResources
                        rentability = resources.rentability(flightTime.seconds,self.config.rentabilityFormula)
                else: 
                    rentability = 0
                rentabilities.append((planet,rentability))
                
            rentabilities.sort(key=lambda x:x[1], reverse=True) # sorty by rentability
             
            self._eventMgr.simulationsUpdate(rentabilities)

            try:
                # check for missing and expired reports and add them to spy queue
                allSpied = True
                for planet in self.targetPlanets:
                    if not planet.espionageHistory  \
                    or planet.espionageHistory[-1].hasExpired(self._web.serverTime())  \
                    or not planet.espionageHistory[-1].hasAllNeededInfo():
                        allSpied = False
                        if planet not in planetsToSpy and planet not in notArrivedEspionages.keys():
                            if planet.espionageHistory and not planet.espionageHistory[-1].hasAllNeededInfo():
                                planetsToSpy.insert(0,planet)
                            else:                             
                                planetsToSpy.append(planet)
 

                if allSpied and not planetsToSpy: # attack if there are no unespied planets remaining
                    found = [x for x in rentabilities if x[1] > 0]
                    if not found:
                        self._eventMgr.simulationsUpdate(rentabilities)
                        raise BotFatalError("There are no undefended planets in range.")
                    # ATTACK
                    for finalPlanet, rentability in rentabilities:
                        if rentability <= 0: # ensure undefended
                            continue
                        if finalPlanet in notArrivedEspionages:
                            continue
                        if finalPlanet.espionageHistory[-1].getAge(self._web.serverTime()).seconds < 600:                            
                            resourcesToSteal = finalPlanet.simulation.simulatedResources.half()
                            ships = int((resourcesToSteal.total() + 5000) / self.attackingShip.capacity)
                            sourcePlanet = self._calculateNearestSourcePlanet(finalPlanet.coords)
                            fleet = { self.attackingShip.name : ships }
                            mission = Mission(Mission.Types.attack, sourcePlanet, finalPlanet, fleet)
                            try:
                                self._web.launchMission(mission,False,self.config.slotsToReserve)        
                                self._eventMgr.activityMsg( "Attacking  %s from %s with %s" % (finalPlanet, sourcePlanet,fleet))
                                shipsSent = mission.fleet[self.attackingShip.name]                                        
                                if shipsSent < ships:
                                    factor = shipsSent / float(ships)
                                    finalPlanet.simulation.simulatedResources -= resourcesToSteal * factor
                                    self._eventMgr.activityMsg("There were not enough ships for the previous attack. Needed %s but sent only %s" % (fleet,mission.fleet))
                                else:
                                    finalPlanet.simulation.simulatedResources -= resourcesToSteal                                        
                                sleep(30)
                                self._eventMgr.simulationsUpdate(rentabilities)

                                break
                            except NotEnoughShipsError, e:
                                self._eventMgr.activityMsg("No ships in planet %s to attack %s. %s" %(sourcePlanet,finalPlanet,e))
                                sleep(15)
                        else: # planet's espionage report timed out, re-spy.
                            if finalPlanet not in planetsToSpy and finalPlanet not in notArrivedEspionages:
                                planetsToSpy.append(finalPlanet)
                            break
                        
                if planetsToSpy:
                    # SPY
                    finalPlanet = planetsToSpy.pop(0)
                    sourcePlanet = self._calculateNearestSourcePlanet(finalPlanet.coords)
                    action = "Spying"                        
                    
                    if not finalPlanet.espionageHistory:
                        # send no. of probes equal to the average no. of probes sent until now.
                        probes = [planet.espionageHistory[-1].probesSent for planet in self.targetPlanets if planet.espionageHistory]
                        if len(probes) > 8: probesToSend = int(sum(probes) / len(probes)) 
                        else: pass #TODO: temporary fix
                        probesToSend = self.config.probesToSend
                        action = "Spying for the 1st time"
                    else:
                        probesToSend = finalPlanet.espionageHistory[-1].probesSent    
                        if not finalPlanet.espionageHistory[-1].hasAllNeededInfo():
                            # we need to send more probes to get the defense or buildings data
                            action = "Re-spying with more probes"
                            probesToSend = max(int (1.5 * probesToSend),probesToSend +2) # non-linear increase in the number of probes

                    samePlayerProbes = [planet.espionageHistory[-1].probesSent for planet in self.targetPlanets if planet.espionageHistory and planet.owner == finalPlanet.owner]                                                
                    probesToSend = max(samePlayerProbes + [probesToSend])
                    ships = {'espionageProbe':probesToSend}
                    
                    espionage = Mission(Mission.Types.spy, sourcePlanet, finalPlanet, ships)
                    try:
                        self._web.launchMission(espionage)
                        self._eventMgr.activityMsg("%s %s from %s with %s" % (action,finalPlanet, sourcePlanet, ships))
                        notArrivedEspionages[finalPlanet] = espionage
                    except NotEnoughShipsError, e:
                        planetsToSpy.append(finalPlanet) # re-locate planet at the end of the list for later
                        self._eventMgr.activityMsg("Not enough ships in planet %s to spy %s. %s" %(sourcePlanet,finalPlanet,e))             
                    sleep(5)                        
            except NoFreeSlotsError: 
                self._eventMgr.statusMsg("Fleet limit hit")
                sleep(8)
            except FleetSendError, e: 
                self._eventMgr.activityMsg("Error sending fleet for planet %s: %s" %(finalPlanet,e))
                self.targetPlanets.remove(finalPlanet)
        
        
            sleep(1)            

    def _scanSolarSystem(self,galaxy,solarSystem): # inactive planets background search
        solarSystem = self._web.getSolarSystem(galaxy, solarSystem)                        

        self._planetDb.writeManyKeepReports(solarSystem.values())        
        for planet in solarSystem.values():

            found = [p for p in self.targetPlanets if p.coords == planet.coords]
            if 'inactive' in planet.ownerStatus:
                if not found and not planet.owner in self.config.playersToAvoid and not planet.alliance in self.config.alliancesToAvoid:
                    # we found a new inactive planet
                    if __debug__: 
                        print >>sys.stderr, "New inactive planet found: " + str(planet)
                    self.targetPlanets.append(planet) 
            elif found: # no longer inactive
                if __debug__: 
                    print >>sys.stderr, "Planet no longer inactive: " + str(found[0])
                self.targetPlanets.remove(found[0])
    
    def _calculateNearestSourcePlanet(self,coords):
        minDistance = sys.maxint
        for sourcePlanet in self.sourcePlanets:
            distance = sourcePlanet.coords.distanceTo(coords)
            if distance < minDistance:
                nearestSourcePlanet = sourcePlanet
                minDistance = distance
        if nearestSourcePlanet.coords.galaxy != coords.galaxy:
            BotFatalError("You own no planet in the same galaxy of %s, the planet could not be attacked (this should never happen)" % coords)
            
        return nearestSourcePlanet

    def _didEspionageArrive(self, espionage, displayedReports):
        reports = [report for report in displayedReports if report.coords == espionage.targetPlanet.coords and report.date >= espionage.launchTime]
        reports.sort(key=lambda x:x.date, reverse=True)
        if len(reports) > 0:
            self._web.deleteMessage(reports[0])
            return reports[0]
        return None

        
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

class GalaxyScanner(object):
    def __init__(self,webAdapter):
        self._web = webAdapter
    def scanNext(self):
        pass
    
if __name__ == "__main__":
    
    parser = OptionParser()
    parser.add_option("-c", "--console", action="store_true", help="Run in console mode'") # not working
    parser.add_option("-a", "--autostart", action="store_true", help="Auto start bot, no need to click Start button")
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

    try: os.makedirs ('debug')
    except OSError, e: 
        if "File exists" in e: pass      
            
    logging.getLogger().setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(os.path.abspath(FILE_PATHS['log']), 'a', 100000, 10)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(handler)

    if options.console:
        bot = Bot()
        bot.start()
        bot.join()
    else:
        from gui import guiMain
        guiMain(options.autostart)

            
        
