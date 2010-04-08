#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2010 by kovan
#      with a little help from King Vash 
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
from __future__ import with_statement

import locale
import threading
import re
import os
import urllib
import types
import cPickle
import socket
import urllib2
import copy
import sys
import traceback
import httplib
import warnings
import cookielib
import random
import time
from StringIO import StringIO
from datetime import *
from lxml import etree
from Queue import *

import keepalive
from ClientForm import HTMLForm, ParseFile, ControlNotFoundError
from CommonClasses import *
from Constants import *
from GameEntities import *




class WebPage(object):
    parser = etree.HTMLParser()
    def __init__(self,response):
        self.url = response.geturl()
        self.stringio = StringIO(response.read())
        self.stringio.seek(0)
        self.text = self.stringio.read()
        self.stringio.seek(0)
        self.etree = etree.parse(self.stringio,WebPage.parser)

    def saveToDisk(self):
        
        files = os.listdir('debug')
        if len(files) >= 30: #never allow more than 30 files
            files.sort()
            os.remove('debug/'+files[0])
        try: php = re.findall("/(\w+\.php.*)", self.url)[0].replace('?',',').replace('&',',')
        except IndexError: php = ''
        date = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
        f = open("debug/%s,%s.html" %(date, php), 'w')
        f.write(self.text.replace('<script', '<noscript').replace('</script>', '</noscript>').replace('http-equiv="refresh"', 'http-equiv="kovan-rulez"'))
        f.close()

    def __repr__(self):
        return "WebPage: " + self.url

class ServerData(object):
    def __init__(self):
        self.charset = ""
        self.version = 0
        self.language = ""
        self.timeDelta = None

    currentTime = property(lambda this: this.timeDelta + datetime.now())
         

class WebAdapter(object):
    """Encapsulates the details of the communication with the ogame servers. This involves
        HTTP protocol encapsulation and HTML parsing.
    """
    
        
    class EventManager(BaseEventManager):
        def __init__(self, gui = None):
            super(WebAdapter.EventManager, self).__init__(gui)

        def connectionError(self, reason):
            self.logAndPrint("** CONNECTION ERROR: %s" % reason)
            self.dispatch("connectionError", reason)              
        def loggedIn(self, username, session):
            msg = 'Logged in with user %s.' % username
            self.logAndPrint(msg)
            msg = datetime.now().strftime("%X %x ") + msg
            self.dispatch("activityMsg", msg)            
        def activityMsg(self, msg):
            self.logAndPrint(msg)
            msg = datetime.now().strftime("%X %x ") + msg
            self.dispatch("activityMsg", msg)

            
##########################################################################################        
    def __init__(self, config, allTranslations, checkThreadMsgsMethod, gui = None):
        self.config = config
        self.checkThreadMsgsMethod = checkThreadMsgsMethod
        self._eventMgr = WebAdapter.EventManager(gui)
        self.lastFetchedPage = None
        self.serverData = ServerData()
        self.session = ""
        self.cookies = cookielib.MozillaCookieJar(FILE_PATHS["cookies"])
        self.translationsByLocalText = {}
        self.loadState()

        

        # setup urllib2:
        socket.setdefaulttimeout(10.0)
        #httplib.HTTPConnection.debuglevel = 1

        # set up a class to handle http cookies, passes that to http processor

        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookies))
        # set us a class to keep connections open, passas that to the http processor
        self.keepAliveOpener = urllib2.build_opener(keepalive.HTTPHandler(),urllib2.HTTPCookieProcessor())
        
        if self.config.proxy:
            proxyHandler = urllib2.ProxyHandler({"http":"http://"+self.config.proxy})
            self.opener.add_handler(proxyHandler)
            self.keepAliveOpener.add_handler(proxyHandler)
        

        #defines what broswer your "using" and how long to keep http connections alive
        headers = [('User-agent', self.config.userAgent),('Keep-Alive', "300")]            
        self.opener.addheaders = headers
        self.keepAliveOpener.addheaders = headers
        
        url = '.'.join(self.config.webpage.split('.')[1:])
        page = self._fetchValidResponse("http://" + url, True)

        self.serverData.language = re.findall(r'<meta name="language" content="(\w+)"', page.text)[0]
        try:
            self.translations = allTranslations[self.serverData.language]
        except KeyError:
            raise BotFatalError("Server language (%s) not supported by bot" % self.serverLanguage)

        for englishName, localName in self.translations.iteritems ():
            self.translationsByLocalText [localName] = englishName
            if englishName in INGAME_TYPES_BY_NAME:
                INGAME_TYPES_BY_NAME [englishName].localName = localName
        self.generateRegexps(self.translations)

        page = self._fetchPhp ("index.php", page="overview")
        timestamp = re.findall("var serverTime = new Date\((\d+)\)",page.text)[0]
        serverTime = datetime.fromtimestamp(float(int(timestamp)/1000))
        self.serverData.timeDelta = serverTime - datetime.now()
        self.serverData.charset = re.findall('content="text/html; charset=(.*?)"', page.text, re.I)[0]
        self.serverData.version = float(page.etree.xpath("//a[@href=\"index.php?page=changelog&session=%s\"]//text()" % self.session)[-1].strip())
        self.saveState()





########################################################################################## 
    def _fetchPhp(self, php, **params):
        params['session'] = self.session
        url = "http://%s/game/%s?%s" % (self.config.webpage, php, urllib.urlencode(params))
        return self._fetchValidResponse(url)

    def _fetchPhpPost(self, php, postData, **params):
        params['session'] = self.session
        url = "http://%s/game/%s?%s" % (self.config.webpage, php, urllib.urlencode(params))
        request = urllib2.Request(url, urllib.urlencode(postData))
        return self._fetchValidResponse(request)
    
##########################################################################################     
    def _fetchValidResponse(self, request, skipValidityCheck = False):
        if isinstance(request, str):
            request = urllib2.Request(request)
        if self.lastFetchedPage:
            request.add_header('Referer',self.lastFetchedPage.url)
            
        valid = False
        while not valid:
            self.checkThreadMsgsMethod()

            valid = True
            try:
                page = WebPage(self.opener.open(request))
                page.saveToDisk()
                self.lastFetchedPage = page
                
                if __debug__: 
                    print >>sys.stderr, "\t " + datetime.now().strftime("%m-%d, %H:%M:%S") + " Fetched " + page.url
                
                if skipValidityCheck:
                    return page
                
                if self.translations['youAttemptedToLogIn'] in page.text:
                    raise BotFatalError("Invalid username and/or password.")
                
                if not page.text or 'errorcode=8' in page.text:
                    valid = False
                    
                #TODO \ FIX THIS if this fails then just comment it ???
#                if self.translations['dbProblem'] in page.text or self.translations['untilNextTime'] in page.text or "Grund 5" in page.text:
                if self.translations['dbProblem'] in page.text \
                        or "Grund 5" in page.text\
                        or re.search(r"^<(no)?script>document.location.href='http://.*?'</(no)?script>$", page.text):
                    oldSession = self.session
                    self.doLogin()
                    url =  request.get_full_url().replace(oldSession, self.session)
                    data = request.get_data()
                    if data:
                        data = data.replace(oldSession, self.session)                    
                    request = urllib2.Request(url,data)
                    valid = False
                    
            except urllib2.HTTPError, e:
                if e.code == 302: # happens once in a while when user and bot are playing simultaneusly.
                    raise BotError()
                else: raise
            except (urllib2.URLError, httplib.IncompleteRead, httplib.BadStatusLine), e:
                self._eventMgr.connectionError(e)
                valid = False
            except Exception, e:
                if "timed out" in str(e):
                    self._eventMgr.connectionError("timed out")
                    valid = False
                else: raise
            if not valid: 
                mySleep(1)
                
        return page
    
########################################################################################## 
    def doLogin(self):
        try:
            if self.serverData.currentTime.hour == 3 and self.serverData.currentTime.minute == 0: # don't connect immediately after 3am server reset
                mySleep(30)
        except TypeError:
            pass # the first time is normal not to have the server time
        url = '.'.join(self.config.webpage.split('.')[1:])
        page = self._fetchValidResponse("http://" + url)
        form = ParseFile(page.stringio, page.url, backwards_compat=False)[0]
        form["uni_url"] = [self.config.webpage]
        form["login"] = self.config.username
        form["pass"]  = self.config.password
        form.action = "http://"+self.config.webpage+"/game/reg/login2.php"
        page = self._fetchValidResponse(form.click())
        
        try:
            self.session = re.findall("[0-9A-Fa-f]{12}", page.text)[0]
            self.saveState ()
        except IndexError:
            raise BotFatalError(page)
        
        self._eventMgr.loggedIn(self.config.username, self.session)
        self._fetchPhp('index.php', lgn=1)
        mySleep(5)
        page = self._fetchPhp('index.php', page='overview', lgn=1)

########################################################################################## 
    def saveState(self):
        f = open(FILE_PATHS['webstate'], 'wb')
        pickler = cPickle.Pickler(f, 2)        
        pickler.dump(self.session)
        f.close()
        self.cookies.save()

##########################################################################################      
    def loadState(self):
        try:
            file = open(FILE_PATHS['webstate'], 'rb')
            u = cPickle.Unpickler(file)            
            self.session = u.load()
            file.close()
        except (EOFError, IOError):
            try:
                os.remove(FILE_PATHS['webstate'])              
            except Exception : pass
            self.session = '000000000000'

        if os.path.exists (FILE_PATHS ["cookies"]):
            self.cookies.load ()

##########################################################################################     
    def generateRegexps(self, translations):

        self.REGEXPS = \
        {
            'planet':
            {
                'buildingLevels':re.compile(r">(?P<buildingName>[^<]+)</a></a>\s*?\(level\s*(?P<level>[0-9]+)\)<br>",re.I|re.LOCALE),   
                'buildingFields':re.compile(r">([0-9]+)[\s]*</a>.*?>([0-9]+)[\s]*</a>[\s]*%s" %(translations['fields']),re.I),
                'currentlyUpgradingBuilding':re.compile(r'pp=\'([0-9]+)\';', re.I),
                'defense':re.compile(r'>(?P<name>[a-z ]*)</a></a> \((?P<quantity>[-0-9.]+) available\)', re.I),
                'durationRemaining':re.compile(r"%s:[\s]?(([ 0-9]*) d)?(([ 0-9]*) h)?([ 0-9]*) m ([ 0-9]*) s" %(translations['durationRemaining']), re.I),
                'ResearchLabPresent':re.compile(r'%s' %(translations['computerTechnology']), re.I),
                'resources':re.compile(r">(?P<quantity>[0-9.]+)</font></td>", re.I),
                'resourceEnergy':re.compile(r">([0-9-.]+)</font>/([0-9.]+)</td>", re.I)
            },
            'attack':re.compile(r"%s.*?\[(?P<targetPlanet>[0-9]+:[0-9]+:[0-9]+)\]</a>.[\s]*%s:[\s]*(?P<missionType>[a-z]+)" %(translations['aHostile'], translations['itsMissionIs']), re.I),
            'currentlyUpgradingResearch':re.compile(r'ss=([0-9]+);', re.I),
            'fleetSendError':re.compile(r'<span class="error">(?P<error>.*?)</span>', re.I), 
            'fleetSendResult':re.compile(r"<tr.*?>\s*<th.*?>(?P<name>.*?)</th>\s*<th.*?>(?P<value>.*?)</th>", re.I), 
            'stats': re.compile(r"style='color:lime;'.*?<!-- points -->.*?([0-9.]+).*?<!-- rank -->.*?([0-9.]+)", re.I|re.DOTALL),
            'statsOverview': re.compile(r"([0-9.]+)[\s]*\(%s.*?>([0-9.]+)</a>" %(translations['rank']), re.I)
        }
        
########################################################################################## 
    def goToPlanet(self, planet):
        self._fetchPhp('index.php', page='overview', cp=planet.code)


########################################################################################## 
    def getMyPlanets(self, player, alreadyFetchedPage = None):

        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='overview')
            
        player.colonies = []
        planetNames  = page.etree.xpath("//*[@class='planet-name']")
        planetCoords = page.etree.xpath("//*[@class='planet-koords']")
        for name, coord in zip(planetNames, planetCoords):
            coords = Coords(coord.text)
            for planet in player.colonies:
                if planet.coords == coords: # we found a moon for this planet
                    coords.coordsType = Coords.Types.moon
            player.colonies.append(OwnPlanet(coords, player, name.text))
            


##########################################################################################
# r371: function unused            
    def updateAllData(self, player):
        self.updatePlayerData(player)
        for planet in player.colonies:
            self.updatePlanetData(planet)

########################################################################################## 
    def updatePlayerData(self, player):
        overview = self._fetchPhp('index.php', page='overview')
        self.checkForAttack(player, overview)
        self.getMyPlanets(player, overview)
        # TODO: fix: self.getStats(player, "pts", overview)
        self.getResearchLevels(player)
        
########################################################################################## 
    def updatePlanetData(self, planet):
#        overview = self._fetchPhp('index.php', page='overview', mode='', gid='', messageziel='', re='0')
#        self.checkResourcesOnPlanet(planet, overview)
#        self.checkBuildingFields(planet, overview)
#        self.getBuildingLevels(planet)
        self.getDefense(planet)


########################################################################################## 
    def checkForAttack(self, player, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='overview', mode='', gid='', messageziel='', re='0')
        player.attacks = []
        for targetPlanet, missionType in self.REGEXPS['attack'].findall(page.text):
            if missionType == self.translations['attack']:   
                player.attacks.append(targetPlanet)


########################################################################################## 
# TODO: not working:        
    # def checkResourcesOnPlanet(self, planet, alreadyFetchedPage = None):
    #     page = alreadyFetchedPage
    #     if not page:
    #         page = self._fetchPhp('index.php', page='overview',cp=planet.code, mode='', gid='', messageziel='', re='0').read()
    #     resources       = self.REGEXPS['planet']['resources'].findall(text)
    #     planet.metal            = int(resources[0].replace('.', ''))
    #     planet.crystal          = int(resources[1].replace('.', ''))
    #     planet.deuterium        = int(resources[2].replace('.', ''))
    #     planet.availableEnergy  = int(self.REGEXPS['planet']['resourceEnergy'].search(text).group(1).replace('.', ''))


##########################################################################################
# TODO: not working:        
    # def checkBuildingFields(self, planet, alreadyFetchedPage = None):
    #     page = alreadyFetchedPage
    #     if not page:
    #         page = self._fetchPhp('index.php', page='overview',cp=planet.code, mode='', gid='', messageziel='', re='0').read()
    #     BuildingFields  = self.REGEXPS['planet']['buildingFields'].findall(text)
    #     planet.totalBuildingFields = int(BuildingFields[1])
    #     planet.freeBuildingFields = int(BuildingFields[1])


##########################################################################################
# TODO: not working:        
    # def getBuildingLevels(self, planet):
    #     pass 
        # page = self._fetchPhp('index.php', page='b_building',cp=planet.code)
        # self._checkEndTimeOfBuildingUpgrade(planet, page)
        # planet.buildings, planet.allBuildings = {}, {}
        # for fullName, level in self.REGEXPS['planet']['buildingLevels'].findall(page):
        #      planet.buildings[self.translationsByLocalText[fullName]] = int(level)
        # for item in ['solarPlant', 'metalMine', 'crystalMine', 'deuteriumSynthesizer', 'fusionReactor', 'roboticsFactory', 'naniteFactory', 'shipyard', 'metalStorage', 'crystalStorage', 'deuteriumTank', 'researchLab', 'terraformer', 'allianceDepot', 'missileSilo']:
        #     if item in player.buildings:
        #         planet.allBuildings[item] = building[item]      
        #     else:
        #         planet.allBuildings[item] = 0


########################################################################################## 
    def _checkEndTimeOfBuildingUpgrade(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='b_building', cp=planet.code)
        upgradeTime = self.REGEXPS['planet']['currentlyUpgradingBuilding'].search(page.text)
        if upgradeTime:
            planet.endBuildTime = datetime.now() + timedelta(seconds=int(upgradeTime.group(1)))
        else:
            #guarentuees all time comparisons will work
            planet.endBuildTime = datetime.now() - timedelta(days=10000)
        

########################################################################################## 
    def upgradeBuilding(self, planet, building):
        page = self._fetchPhp('index.php', page='b_building', modus='add', techid=building.code, cp=planet.code)
        mySleep(10)
        self._checkEndTimeOfBuildingUpgrade(planet, page)
    

########################################################################################## 
    def getResearchLevels(self, player, alreadyFetchedPage = None):

        # TODO: make automatic research work:
        # for planet in planetList:
        #     page = self._fetchPhp('index.php', page='research').read()

        #     player.research['CompletionTime'] = self._checkEndTimeOfResearchUpgrade(planet, page)
        #     for fullName, level in self.REGEXPS['researchLevels'].findall(page):
        #         player.research[self.translationsByLocalText[fullName]] = int(level)

        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='research')

        technologies = [t for t in INGAME_TYPES if isinstance(t,Research)]
        for technology in technologies:
            found =     page.etree.xpath("//*[@class='research%s']//*[@class='level']/text()" % technology.code)
            if not found: # it is being built, xpath changes:
                found = page.etree.xpath("//*[@class='b_research%s']//*[@class='level']/text()" % technology.code)

            level = int(found[0])
            player.researchLevels[technology.name] = level

        # TODO: uncomment this:
        # if player.researchLevels['impulseDrive'] == 0 or \
        #    player.researchLevels['combustionDrive'] == 0:
        #     raise BotFatalError("Not enough technologies researched to run the bot")
                

########################################################################################## 
    def _checkEndTimeOfResearchUpgrade(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
                page = self._fetchPhp('index.php', page='buildings', cp=planet.code)
        upgradeTime = self.REGEXPS['currentlyUpgradingResearch'].search(page.text)
        labPresent  = self.REGEXPS['planet']['ResearchLabPresent'].search(page.text)
        if labPresent:
            if upgradeTime:
                return datetime.now() + timedelta(seconds=int(upgradeTime.group(1)))
            else:
                #guarentuees all time comparisons will work
                return datetime.now() - timedelta(days=10000)


########################################################################################## 
    def upgradeResearch(self, planet, research):
        reply = self._fetchPhp('index.php', page='buildings', mode='Forschung', cp=planet.code, bau=research.code)
        mySleep(10)
        return self._checkEndTimeOfResearchUpgrade(planet, reply)


########################################################################################## 
    def getDefense(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='buildings', mode='Verteidigung', cp=planet.code)
        planet.defense = {}
        for name, quantity in self.REGEXPS['planet']['defense'].findall(page.text):
            planet.defense[name] = int(quantity.replace('.', ''))
        self.checkDefenseQueue(planet, page)

########################################################################################## 
    def checkDefenseQueue(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='buildings', mode='Verteidigung', cp=planet.code)
        time = self.REGEXPS['planet']['durationRemaining'].search(page.text)
        if time: 
            return True 
            planet.endDefenseWaitTime = datetime.now() + timedelta(days=time.group(2), hours=time.group(4), minutes=time.group(5), seconds=time.group(6))
        else: 
            return False    


########################################################################################## 
    def buildDefense(self, planet, defense):
        page = self._fetchPhp('index.php', page='buildings', mode='Verteidigung', cp=planet.code )
        form = ParseFile( page.reponse, page.url, backwards_compat=False )[-1]
        for defenseType, quantity in defense.iteritems():
            try:
                controlName = "fmenge[%s]" % INGAME_TYPES_BY_NAME[defenseType].code
                form[controlName] = str( quantity )
            except ControlNotFoundError:
                raise BotError( defenseType )
            
        reply = self._fetchValidResponse(form.click())
        self.checkDefenseQueue(planet, reply)

########################################################################################## 
    def getAvailableFleet(self, alreadyFetchedPage = None):    
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='fleet1') # TODO: management of various planets. cp=planet.code).read()

        if page.etree.xpath("//div[@id='warning']"): # no fleet
            return

        fleet = {}
        for ship in [t for t in INGAME_TYPES if isinstance(t,Ship)]:
            if ship.name == 'solarSatellite': # these don't count as fleet, and don't appear in the page
                continue
            quantity = page.etree.xpath("string(//*[@id='button%s']//*[@class='level']/text())" % ship.code)
            fleet[INGAME_TYPES_BY_CODE[ship.code].name] = int(quantity.replace('.', ''))
            
        return fleet


# ########################################################################################## 
#     def checkFleetQueue(self, planet, alreadyFetchedPage = None):
#         time = self.REGEXPS['planet']['durationRemaining'].search(page.text)
#         if time: 
#             return True 
#             planet.endFleetWaitTime = datetime.now() + timedelta(days=time.group(2), hours=time.group(4), minutes=time.group(5), seconds=time.group(6))
#         else: 
#             return False    


# ########################################################################################## 
#     def buildShips(self, planet, ships):
#         if not ships: return
#         page = self._fetchPhp('index.php', page='buildings', mode='Flotte', cp=planet.code )
#         form = ParseFile( page.response, page.url, backwards_compat=False )[-1]
#         for shipType, quantity in ships.iteritems():
#             try:
#                 controlName = "fmenge[%s]" % INGAME_TYPES_BY_NAME[shipType].code[-3:]
#                 form[controlName] = str( quantity )
#             except ControlNotFoundError:
#                 raise BotError( shipType )
#         reply = self._fetchValidResponse(form.click())
#         self.checkFleetQueue(planet, reply)

########################################################################################## 
    def getFreeFleetSlots(self, player, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='fleet1')
            
        used, total = re.findall("(\d+)/(\d+)",page.etree.xpath("string(//*[@id='slots'])"))[0]

        #TODO:
        # if "admiral_ikon.gif" in page:
        #     maxFleets += 2
        
        return int(total) - int(used)

########################################################################################## 
    def getEspionageReports(self):
        page = self._fetchPhp('index.php', page='messages')
        rawMessages = {}
        for match in self.REGEXPS['messages.php'].finditer(page.text):
            rawMessages[match.group('code')] = match.group(0) 
            
        reports = []              
        for code, rawMessage in rawMessages.items():
            if 'class="espionagereport"' not in rawMessage:
                continue
            
            m = self.REGEXPS['report']['all'].search(rawMessage)
            if m == None: #theorically should never happen
                warnings.warn("Error parsing espionage report.")
                continue
            planetName = m.group('planetName')
            coords = Coords(m.group('coords'))
            date = parseTime(m.group('date'), "%m-%d %H:%M:%S")
            resources = Resources(m.group('metal').replace('.', ''), m.group('crystal').replace('.', ''), m.group('deuterium').replace('.', ''))

            report = EspionageReport(coords, planetName, date, resources, code)
            
            for i in "fleet", "defense", "buildings", "research":
                dictionary = None
                match = self.REGEXPS['report'][i].search(rawMessage)
                if match:
                    dictionary, text = {}, match.group(1)
                    for fullName, quantity in self.REGEXPS['report']['details'].findall(text):
                        dictionary[self.translationsByLocalText[fullName.strip()]] = int(quantity.replace('.', ''))
                        
                    setattr(report, i, dictionary)
                
            report.rawHtml = rawMessage
            reports.append(report)
            
        return reports

    def getGameMessages(self, msgType = None):
        postData = { "ajax": "1" }
        page = self._fetchPhpPost('index.php', postData, page='messages')

        messages = []
        for message in page.etree.xpath("//table[@id='mailz']//tr[@class != 'first' and @class != 'last']"):
            code                   = message.xpath("string(td[@class='check']/input/@id)").strip ()
            sender                 = message.xpath("string(td[@class='from'])").strip ()
            subject                = message.xpath("td[@class='subject']//text()")[1].strip()
            date                   = parseTime(message.xpath("string(td[@class='date'])").strip())
            
            msgPage                = self._fetchPhp ("index.php", page="showmessage", ajax=1, msg_id=code)
            
#            rawContents            = msgPage.etree.xpath ("string(//*[@class='textWrapper'])").strip ()
            
#            espionageReportFields = msgPage.etree.xpath ("//*[@class='material spy' or @class='fleetdefbuildings spy']")

            resourcesTxt              = msgPage.etree.xpath ("//*[@class='fragment spy2']//td[not(@class)]")
            if resourcesTxt: # message is of type espionage
                msg = EspionageReport (code, date, Coords (subject))

                msg.resources.metal                  = int(resourcesTxt [0].text.replace ('.',''))
                msg.resources.crystal                = int(resourcesTxt [1].text.replace ('.',''))
                msg.resources.deuterium              = int(resourcesTxt [2].text.replace ('.',''))
                msg.resources.energy                 = int(resourcesTxt [3].text.replace ('.',''))


                keys   = msgPage.etree.xpath ("//*[@class='fleetdefbuildings spy']//td[@class='key']")
                values = msgPage.etree.xpath ("//*[@class='fleetdefbuildings spy']//td[@class='value']")
                for key, value in zip (keys, values):
                    englishName = self.translationsByLocalText [key.text]
                    itemType = INGAME_TYPES_BY_NAME [englishName]
                    quantity = int (value.text.replace ('.',''))
                    if   isinstance (itemType, Ship):
                        msg.fleet     [englishName] = quantity
                    elif isinstance (itemType, Defense):
                        msg.defense   [englishName] = quantity
                    elif isinstance (itemType, Building):
                        msg.buildings [englishName] = quantity
                    elif isinstance (itemType, Research):
                        msg.research  [englishName] = quantity
            else:
                msg = GameMessage (code, date, subject, sender)
            messages.append (msg)

        # apply filter:
        if msgType:
            messages = [msg for msg in messages if type (msg) == msgType]
        return messages

        
##########################################################################################         
    def launchMission(self, mission, abortIfNotEnough = True, fleetSlotsToReserve = 0):

        while True:
            # assure cuantities are integers
            for shipType, quantity in mission.fleet.items(): 
                mission.fleet[shipType] = int(quantity)

            # 1st step: select fleet
            page = self._fetchPhp('index.php', page='fleet1') # TODO: management of various planets cp=mission.sourcePlanet.code)

            freeFleetSlots = self.getFreeFleetSlots(page)
            availableFleet = self.getAvailableFleet(page)
            form = ParseFile(page.stringio, page.url, backwards_compat=False)[-1]        

            for shipType, requested in mission.fleet.iteritems():
                available = availableFleet.get(shipType, 0)
                if available == 0 or (abortIfNotEnough and available  < requested):
                    raise NotEnoughShipsError(mission.sourcePlanet.fleet, {shipType:requested}, available)
                shipCode = INGAME_TYPES_BY_NAME[shipType].code
                form["am" + str(shipCode)] = str(requested)

            if freeFleetSlots <= int(fleetSlotsToReserve):
                raise NoFreeSlotsError()

            mySleep(3)
            # 2nd step: select destination and speed  
            page = self._fetchValidResponse(form.click())

            forms = ParseFile(page.stringio, page.url, backwards_compat=False)
            if not forms or 'fleet3' not in forms[0].action:
                continue # unkown error, retry
            
            form = forms[0]
            destCoords = mission.targetPlanet.coords         
            form['galaxy']    = str(destCoords.galaxy)
            form['system']    = str(destCoords.solarSystem)
            form['position']  = str(destCoords.planet)
            form.find_control('type').readonly = False
            form['type']      = str(destCoords.coordsType)
            form['speed']     = [str(mission.speedPercentage / 10)]

            mySleep(3)
            # 3rd step:  select mission and resources to carry
            page = self._fetchValidResponse(form.click())
            form = ParseFile(page.stringio, page.url, backwards_compat=False)[0]
            try:
                form.find_control('mission').readonly = False
                form['mission'] = str(mission.missionType)
            except ControlNotFoundError:
                continue

            resources = mission.resources
            form['resource1'] = str(resources.metal)
            form['resource2'] = str(resources.crystal)
            form['resource3'] = str(resources.deuterium)                   

            hours, mins, secs = re.findall("(\d+):(\d+):(\d+)", page.etree.xpath("string(//*[@id='duration'])"))[0]
            flightTime = timedelta(0, int(secs), 0, 0, int(mins), int(hours))

            mySleep(3)
            # 4th and final step: check result
            page = self._fetchValidResponse(form.click())
            if self.translations['fleetCouldNotBeSent'] in page.text:
                continue # unexpected error, retry
            
            errors = self.REGEXPS['fleetSendError'].findall(page.text)
            if len(errors) > 0 or 'class="success"' not in page.text:
                errors = str(errors)
                if self.translations['fleetLimitReached'] in errors:
                    raise NoFreeSlotsError()
                elif self.translations['noShipSelected'] in errors:
                    raise NotEnoughShipsError(availableFleet, mission.fleet)
                else: 
                    raise FleetSendError(errors)

            resultPage = {}
            for resultType, value in self.REGEXPS['fleetSendResult'].findall(page.text):
                resultPage[resultType] = value

            mission.launched(self.serverData.currentTime, flightTime)
            


            # check the requested fleet was sent intact:
            # sentFleet = {}
            # for fullName, value in resultPage.items():
            #         name = self.translationsByLocalText.get(fullName)
            #         if name is None:
            #             continue
            #         if name in INGAME_TYPES_BY_NAME.keys():
            #             sentFleet[name] = int(value.replace('.', ''))

            # if mission.fleet != sentFleet:
            #         warnings.warn("Not all requested fleet was sent. Requested: %s. Sent: %s" % (mission.fleet, sentFleet))
            #         mission.fleet = sentFleet

            break

                
##########################################################################################
    def deleteMessages(self, messages):
        return
        page = self._fetchPhp('index.php', page='messages')
        form = ParseFile(page.stringio, page.url, backwards_compat=False)[0]
        for message in messages:
            checkBoxName = "delmes" + message.code
            try:
                form[checkBoxName]     = [None] # actually this marks the checbox as checked (!!)
                form["deletemessages"] = ["deletemarked"]
            except ControlNotFoundError:
                if __debug__:
                    print >> sys.stderr, "Could not delete message " + str(message)
            
        self._fetchValidResponse(form.click())

        
        
##########################################################################################
# TODO : not working        
    # def getStats(self, player, statsType, alreadyFetchedPage = None): # type can be: pts for points, flt for fleets or res for research
    #     if statsType != "pts" :
    #         page = self._fetchPhp('index.php', page='statistics')
    #         form = ParseFile(page.stringio, page.url, backwards_compat=False)[-1]
    #         form['type'] = [statsType]
    #         form['start'] = ['[Own position]']
    #         page = self._fetchValidResponse(form.click())
    #         stats = self.REGEXPS['stats'].search(page.text)
    #     else:   
    #         page = alreadyFetchedPage
    #         if not page:
    #             page = self._fetchPhp('index.php', page='overview')
    #         stats = self.REGEXPS['statsOverview'].search(page.text)

    #     player.rank = int(stats.group(1).replace('.',''))
    #     player.points = int(stats.group(2).replace('.',''))     


########################################################################################## 
    def getSolarSystems(self, solarSystems, deuteriumSourcePlanet = None): # solarsytems is an iterable of tuples
        if deuteriumSourcePlanet:
            self.goToPlanet(deuteriumSourcePlanet)
        threads = []
        inputQueue = Queue()
        outputQueue = Queue()
        for galaxy, solarSystem in solarSystems:
            params = {'session':self.session, 'galaxy':galaxy, 'system':solarSystem }
            url = "http://%s/game/index.php?page=galaxyContent&ajax=1&%s" % (self.config.webpage, urllib.urlencode(params))
            inputQueue.put((galaxy,solarSystem,url))
       
        for dummy in range(1):
            thread = ScanThread(inputQueue, outputQueue, self.opener)
            thread.start()
            threads.append(thread)
 

        found = []
        while True:
            try:
                output = outputQueue.get(True,1)
                if output not in found:
                    found.append(output)
                    yield output
            except Empty:
                if not filter(threading.Thread.isAlive, threads):
                    break
                
        for thread in threads:
            if thread.exception:
                raise thread.exception  

      
########################################################################################## 
class ScanThread(threading.Thread):
    ''' Scans solar systems from inputQueue'''
    
    # only one thread should be able to write htmls to disk at once:
    saveToDiskLock = threading.Lock()

    
    def __init__(self, inputQueue, outputQueue, opener):
        threading.Thread.__init__(self, name="GalaxyScanThread")
        self._inputQueue = inputQueue
        self._outputQueue = outputQueue
        self.opener = opener
        self.exception = None
        
    def run(self):
        socket.setdefaulttimeout(20)   
        playersByName = {}
        error = False
        
        while True:
            try:
                if not error:
                    galaxy, solarSystem, solarSystemUrl = self._inputQueue.get_nowait()

                page = WebPage(self.opener.open(solarSystemUrl))
                with ScanThread.saveToDiskLock:
                    page.saveToDisk()
                
                if __debug__: 
                    print >>sys.stderr, "\t" + datetime.now().strftime("%m-%d, %H:%M:%S") + " Fetched " + page.url
                    print >>sys.stderr, "\t\t Page length : " + str(len(page.text))
                
                if 'span class="error"' in page.text:
                    print >>sys.stderr, page.text
                    raise BotError("Probably there is not enough deuterium on planet.")
                
                if 'error' in  page.url:
                    error = True
                    continue
                
                foundPlanets = []
                for row in page.etree.xpath("//*[@id='galaxytable']//*[@class='row']"):
                    # Absolutely ALL EnemyPlanet and EnemyPlayer objects of the bot are created here
                    
                    ownerName = row.xpath("string(*//*[@class='TTgalaxy'])").strip()
                    if not ownerName: # empty position
                        continue
                    
                    ownerAlliance = row.xpath("string(*[@class='allytag']/*//text())")
                    # we want player objects to be unique:
                    owner = playersByName.get(ownerName)
                    if not owner:
                        owner = EnemyPlayer(ownerName, ownerAlliance)
                        playersByName[ownerName] = owner
                    owner.isInactive = row.xpath("string(*//*[@class='status'])").strip().lower() == "(i)"
                    
                    planetNumber = int(row.xpath("string(*[@class='position'])").strip())
                    planet = EnemyPlanet(Coords(galaxy, solarSystem, planetNumber), owner)
                    planet.name =      row.xpath("string(*[@class='planetname'])").replace ("(*)","").strip()
                    planet.hasMoon =   row.xpath("string(*[@class='moon'])").strip() != ""
                    planet.hasDebris = row.xpath("string(*[@class='debris'])").strip() != ""
                    
                    owner.colonies.append(planet)                    
                    foundPlanets.append(planet)

                    
                self._outputQueue.put((galaxy, solarSystem, foundPlanets, page))
                error = False
                
            except Empty:
                break
            except BotError, e:
                self.exception = e
                break
            except Exception, e:
                error = True
                if __debug__: 
                    print >>sys.stderr, repr(e)
                    traceback.print_exc()
                    


########################################################################################## 
def parseTime(strTime, format = "%d.%m.%Y %H:%M:%S"):
    ''' parses a time string formatted in OGame most usual format and 
    converts it to a datetime object'''
    
    return datetime.strptime(strTime, format) 
