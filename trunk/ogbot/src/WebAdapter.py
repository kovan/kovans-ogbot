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
import httplib
import warnings
import cookielib
import StringIO
import random


from Queue import *
import datetime, time
from time import strptime
from ClientForm import HTMLForm, ParseFile, ControlNotFoundError;
import keepalive
from CommonClasses import *
from Constants import *
from GameEntities import *


"""Ability to 
tested? description                     |name

        updatePlayer                    |updatePlayerData
        updatePlanet                    |updatePlanetData
x       check for attacks               |checkForAttack
X       check resources                 |checkResourcesOnPlanet
        check building fields           |checkBuildingFields
X       get building levels             |getBuildingLevels
X         find upgrade end time         |_checkEndTimeOfBuildingUpgrade
X         build building                |upgradeBuilding
X       check research levels           |getResearchLevels
X         find upgrade end time         |_checkEndTimeOfResearchUpgrade
X         upgrade research              |upgradeResearch
X       check defense on planet         |getDefense
X         check defense queue           |checkDefenseQueue
X         upgrade defense on planet     |buildDefense
X       check fleet on planet           |getAvailableFleet
X         check fleet queue             |checkFleetQueue
X         check total fleetslots        |getTotalFleetSlots
X         check fleetslots available    |getFreeFleetSlots
X         build ships                   |buildShips
        scan galaxy                     |getSolarSystems
X       parse espionage reports         |getEspionageReports
X       send missions                   |launchMission
        


        
X       login                           |doLogin
X       determine server time           |getServerTime
X       switch planet                   |goToPlanet
X       get planet list                 |getMyPlanets
        get stats                       |getStats
X       delete Messages                 |deleteMessages
"""

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
            msg = datetime.datetime.now().strftime("%X %x ") + msg
            self.dispatch("activityMsg", msg)            
        def activityMsg(self, msg):
            self.logAndPrint(msg)
            msg = datetime.datetime.now().strftime("%X %x ") + msg
            self.dispatch("activityMsg", msg)

            
##########################################################################################        
    def __init__(self, config, allTranslations, checkThreadMsgsMethod, gui = None):
        self.server = ''
        self.lastFetchedUrl = ''
        self.serverCharset = ''        
        self.config = config
        self.checkThreadMsgsMethod = checkThreadMsgsMethod
        self._eventMgr = WebAdapter.EventManager(gui)
        self.serverTimeDelta = None
        self._mutex = threading.RLock()
        self.webpage = "http://"+ config.webpage + "/index.php"     

        if not self.loadState():
            self.session = '000000000000'  

        # setup urllib2:
        socket.setdefaulttimeout(10.0)
        #httplib.HTTPConnection.debuglevel = 1

        # set up a class to handle http cookies, passes that to http processor
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        # set us a class to keep connections open, passas that to the http processor
        self.keepAliveOpener = urllib2.build_opener(keepalive.HTTPHandler())        
        
        if self.config.proxy:
            proxyHandler = urllib2.ProxyHandler({"http":"http://"+self.config.proxy})
            self.opener.add_handler(proxyHandler)
            self.keepAliveOpener.add_handler(proxyHandler)
        

        #defines what broswer your "using" and how long to keep http connections alive
        headers = [('User-agent', self.config.userAgent),('Keep-Alive', "300")]            
        self.opener.addheaders = headers
        self.keepAliveOpener.addheaders = headers
                    
        cachedResponse = StringIO.StringIO(self._fetchValidResponse(self.webpage, True).read())

        # check configured language equals ogame server language
        regexpLanguage = re.compile(r'<meta name="language" content="(\w+)"', re.I) # outide the regexp definition block because we need it to get the language in which the rest of the regexps will be generated

        try: self.translations = allTranslations[self.serverLanguage]
        except KeyError:
            raise BotFatalError("Server language (%s) not supported by bot" % self.serverLanguage)
        if int(self.translations['fileVersion']) < 0.1:
            raise BotFatalError("Server language (%s) needs to updated follow instructions in language/howtofix.fix" % self.serverLanguage)
        self.translationsByLocalText = dict([ (value, key) for key, value in self.translations.items() ])
        self.generateRegexps(self.translations)        
        # retrieve server based on universe number        
        cachedResponse.seek(0)     
        form = ParseFile(cachedResponse, self.lastFetchedUrl, backwards_compat=False)[0]   
        select = form.find_control(name = "uni_url")
        translation = self.translations['universe']
        
        if self.serverLanguage == "tw":
            translation = translation.decode('gb2312').encode('utf-8')

        self.server = select.get(label = self.config.universe +'. '+  translation, nr=0).name


##########################################################################################         
    def _fetchForm(self, form):
        return self._fetchValidResponse(form.click())


########################################################################################## 
    def _fetchPhp(self, php, **params):
        params['session'] = self.session
        url = "http://%s/game/%s?%s" % (self.server, php, urllib.urlencode(params))
        return self._fetchValidResponse(url)


##########################################################################################     
    def _fetchValidResponse(self, request, skipValidityCheck = False):
        self._mutex.acquire()

        if isinstance(request, str):
            request = urllib2.Request(request)
        if self.lastFetchedUrl:
            request.add_header('Referer',self.lastFetchedUrl)
            
        valid = False            
        while not valid:
            self.checkThreadMsgsMethod()

            valid = True
            try:
                response = self.opener.open(request)
                self.lastFetchedUrl = response.geturl()
                if __debug__: 
                    print >>sys.stderr, "\t " + datetime.datetime.now().strftime("%m-%d, %H:%M:%S") + " Fetched " + self.lastFetchedUrl
                cachedResponse = StringIO.StringIO(response.read())
                p = cachedResponse.getvalue()
                cachedResponse.seek(0)
                # store last 30 pages fetched in the debug directory:
                files = os.listdir('debug')
                if len(files) >= 30: #never allow more than 30 files
                    files.sort()
                    os.remove('debug/'+files[0])
                try: php = '_'+re.findall("/(\w+\.php)", self.lastFetchedUrl)[0]
                except IndexError: php = ''
                date = datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
                file = open("debug/%s%s.html" %(date, php), 'w')
                file.write(p.replace('<script', '<noscript').replace('</script>', '</noscript>').replace('http-equiv="refresh"', 'http-equiv="kovan-rulez"'))
                file.close()
                if skipValidityCheck:
                    return cachedResponse           
                elif self.translations['youAttemptedToLogIn'] in p:         
                    raise BotFatalError("Invalid username and/or password.")
                elif not p or 'errorcode=8' in self.lastFetchedUrl:
                    valid = False
                #TODO \ FIX THIS if this fails then just comment it ???
                elif self.translations['dbProblem'] in p or self.translations['untilNextTime'] in p or "Grund 5" in p:
                    oldSession = self.session
                    self.doLogin()
                    url =  request.get_full_url().replace(oldSession, self.session)
                    data = request.get_data()
                    if data: data = data.replace(oldSession, self.session)                    
                    request = urllib2.Request(url,data)
                    valid = False
            except urllib2.HTTPError, e:
                if e.code == 302: # happens once in a while when user and bot are playing simultaneusly.
                    raise BotError()
                else: raise e
            except (urllib2.URLError, httplib.IncompleteRead, httplib.BadStatusLine), e:
                self._eventMgr.connectionError(e)
                valid = False
            except Exception, e:
                if "timed out" in str(e):
                    self._eventMgr.connectionError("timed out")
                    valid = False
                else: raise e
            if not valid: 
                mySleep(10)                
        self._mutex.release()
        return cachedResponse
    
########################################################################################## 
    def doLogin(self):
        if self.serverTimeDelta and self.getServerTime().hour == 3 and self.getServerTime().minute == 0: # don't connect immediately after 3am server reset
            mySleep(30)                
        page = self._fetchValidResponse(self.webpage)
        form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[-1]
        form["uni_url"] = [self.server]
        form["login"] = self.config.username
        form["pass"]  = self.config.password
        form.action = "http://"+self.server+"/game/reg/login2.php"
        page = self._fetchForm(form).read()
        try:
            self.session = re.findall(self.REGEXP_SESSION_STR, page)[0]
        except IndexError:
            raise BotFatalError(page)
        self._eventMgr.loggedIn(self.config.username, self.session)
        page = self._fetchPhp('index.php', lgn=1)                
        mySleep(10)        
        page = self._fetchPhp('index.php', page='overview', lgn=1)               
        self.saveState()


########################################################################################## 
    def setSession(self, value):
        self._session = value
        self.saveState()


########################################################################################## 
    def getSession(self): 
        return self._session
    session = property(getSession, setSession)    


########################################################################################## 
    def saveState(self):
        file = open(FILE_PATHS['webstate'], 'wb')
        pickler = cPickle.Pickler(file, 2)        
        pickler.dump(self.server)         
        pickler.dump(self.session)
        file.close()


##########################################################################################      
    def loadState(self):
        try:
            file = open(FILE_PATHS['webstate'], 'rb')
            u = cPickle.Unpickler(file)            
            self.server = u.load()            
            self.session = u.load()
            file.close()
        except (EOFError, IOError):
            try:
                os.remove(FILE_PATHS['webstate'])              
            except Exception : pass
            return False
        return True   


##########################################################################################     
    def generateRegexps(self, translations):

        reportTmp  = r'%s (?P<planetName>[^<]*?) .*?(?P<coords>\[[0-9:]+\]).*?<br[\s]*/>.*? (?P<date>[0-9].*?)</td></tr>\n' %  translations['resourcesOn']
        reportTmp += r'.*?<tr><td>.*?</td><td>(?P<metal>[-0-9.]+)</td>\n'
        reportTmp += r'<td>.*?</td><td>(?P<crystal>[-0-9.]+)</td></tr>\n'
        reportTmp += r'<tr><td>.*?</td><td>(?P<deuterium>[-0-9.]+)</td>\n'
        reportTmp += r'<td>.*?</td><td>(?P<energy>[-0-9.]+)</td></tr>'  
        reportTmp2 = r'<table width=[0-9]+><tr><td class=c colspan=4>%s(.*?)</table>'

        
        self.REGEXP_COORDS_STR  = r"([1-9]{1,3}):([0-9]{1,3}):([0-9]{1,2})"
        self.REGEXP_SESSION_STR = r"[0-9A-Fa-f]{12}"

        self.REGEXPS = \
        {
            'messages.php': re.compile(r'<input type="checkbox" name="delmes(?P<code>[0-9]+)".*?(?=<input type="checkbox")', re.DOTALL |re.I), 
            'charset':re.compile(r'content="text/html; charset=(.*?)"', re.I), 
            'serverTime':re.compile(r"<th>.*?%s.*?</th>.*?<th.*?>(?P<date>.*?)</th>" % (translations['serverTime']), re.DOTALL|re.I),
            'report': 
            {
                'all'  :    re.compile(reportTmp, re.LOCALE|re.I), 
                'fleet':    re.compile(reportTmp2 % translations['fleets'], re.DOTALL|re.I), 
                'defense':  re.compile(reportTmp2 % translations['defense'], re.DOTALL|re.I), 
                'buildings':re.compile(reportTmp2 % translations['buildings'], re.DOTALL|re.I), 
                'research': re.compile(reportTmp2 % translations['research'], re.DOTALL|re.I), 
                'details':  re.compile(r"<td>(?P<type>.*?)</td><td>(?P<quantity>[-0-9.]+)</td>", re.DOTALL|re.I)
            },
            'planet':
            {
                'availableFleet':re.compile(r'name="max(?P<type>ship[0-9]{3})" value="(?P<quantity>[-0-9.]+)"', re.I), 
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
            'fleetSlots':re.compile(r"%s[\s]*([0-9]+) \/ ([0-9]+)" %(translations['fleets']), re.I),
            'myPlanets':re.compile('<option value="/game/index\.php\?page=overview&session='+self.REGEXP_SESSION_STR+'&cp=([0-9]+)&mode=&gid=&messageziel=&re=0" (?:selected)?>(.*?)<.*?\['+self.REGEXP_COORDS_STR+'].*?</option>', re.I),    
            'researchLevels':re.compile(r">(?P<techName>[^<]+)</a></a>\s*?\(.*?(?P<level>[0-9]+)\s*?\)",re.I|re.LOCALE),            
            'solarSystem':re.compile(r'<tr>.*?<a href="#"  tabindex="[0-9]+" >([0-9]+)</a>.*?<th width="130".*?>([^&<]+).*?<th width="150">.*?<span class="(\w+?)">(.*?)</span>.*?<th width="80">.*?> *([\w .]*?) *<.*?</tr>'),
            'stats': re.compile(r"style='color:lime;'.*?<!-- points -->.*?([0-9.]+).*?<!-- rank -->.*?([0-9.]+)", re.I|re.DOTALL),
            'statsOverview': re.compile(r"([0-9.]+)[\s]*\(%s.*?>([0-9.]+)</a>" %(translations['rank']), re.I)
        }
        
        
##########################################################################################     
    def getServerTime(self):
        return self.serverTimeDelta + datetime.datetime.now()
     

########################################################################################## 
    def goToPlanet(self, planet):
        self._fetchPhp('index.php', page='overview', cp=planet.code)


########################################################################################## 
    def getMyPlanets(self, player, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='overview', mode='', gid='', messageziel='', re='0').read()
        myPlanets = []
        plan = self.REGEXPS['myPlanets'].findall(page)
        for code, name, galaxy, ss, pos in self.REGEXPS['myPlanets'].findall(page):
            coords = Coords(galaxy, ss, pos)
            for planet in myPlanets:
                if planet.coords == coords: # we found a moon for this planet
                    coords.coordsType = Coords.Types.moon
            planet = OwnPlanet(coords, name.strip(), code)
            player.colonies.append(planet)
        
        strTime = self.REGEXPS['serverTime'].findall(page)[0]
        serverTime = parseTime(strTime)
        self.serverTimeDelta = serverTime - datetime.datetime.now()
        self.serverCharset = self.REGEXPS['charset'].findall(page)[0]


########################################################################################## 
    def updateAllData(self, player):
        self.updatePlayerData(player)
        for planet in player.colonies:
            self.updatePlanetData(planet)

########################################################################################## 
    def updatePlayerData(self, player):
        overview = self._fetchPhp('index.php', page='overview', mode='', gid='', messageziel='', re='0').read()
        self.checkForAttack(player, overview)
        self.getMyPlanets(player, overview)
        self.getStats(player, "pts", overview)
        self.getFleetSlots(player)
        self.getResearchLevels(player, [player.colonies[0]])
########################################################################################## 
    def updatePlanetData(self, planet):
        overview = self._fetchPhp('index.php', page='overview', mode='', gid='', messageziel='', re='0').read()
        self.checkResourcesOnPlanet(planet, overview)
        self.checkBuildingFields(planet, overview)
        self.getBuildingLevels(planet)
        self.getDefense(planet)


########################################################################################## 
    def checkForAttack(self, player, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='overview', mode='', gid='', messageziel='', re='0').read()
        player.attacks = []
        for targetPlanet, missionType in self.REGEXPS['attack'].findall(page):
            if missionType == self.translations['attack']:   
                player.attacks.append(targetPlanet)


########################################################################################## 
    def checkResourcesOnPlanet(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='overview',cp=planet.code, mode='', gid='', messageziel='', re='0').read()
        resources       = self.REGEXPS['planet']['resources'].findall(text)
        planet.metal            = int(resources[0].replace('.', ''))
        planet.crystal          = int(resources[1].replace('.', ''))
        planet.deuterium        = int(resources[2].replace('.', ''))
        planet.availableEnergy  = int(self.REGEXPS['planet']['resourceEnergy'].search(text).group(1).replace('.', ''))


########################################################################################## 
    def checkBuildingFields(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='overview',cp=planet.code, mode='', gid='', messageziel='', re='0').read()
        BuildingFields  = self.REGEXPS['planet']['buildingFields'].findall(text)
        planet.totalBuildingFields = int(BuildingFields[1])
        planet.freeBuildingFields = int(BuildingFields[1])


########################################################################################## 
    def getBuildingLevels(self, planet):
        page = self._fetchPhp('index.php', page='b_building',cp=planet.code).read()
        self._checkEndTimeOfBuildingUpgrade(planet, page)
        planet.buildings, planet.allBuildings = {}, {}
        for fullName, level in self.REGEXPS['planet']['buildingLevels'].findall(page):
             planet.buildings[self.translationsByLocalText[fullName]] = int(level)
        for item in ['solarPlant', 'metalMine', 'crystalMine', 'deuteriumSynthesizer', 'fusionReactor', 'roboticsFactory', 'naniteFactory', 'shipyard', 'metalStorage', 'crystalStorage', 'deuteriumTank', 'researchLab', 'terraformer', 'allianceDepot', 'missileSilo']:
            if item in player.buildings:
                planet.allBuildings[item] = building[item]      
            else:
                planet.allBuildings[item] = 0


########################################################################################## 
    def _checkEndTimeOfBuildingUpgrade(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='b_building', cp=planet.code).read()
        upgradeTime = self.REGEXPS['planet']['currentlyUpgradingBuilding'].search(page)
        if upgradeTime:
            planet.endBuildTime = datetime.datetime.now() + timedelta(seconds=int(upgradeTime.group(1)))
        else:
            #guarentuees all time comparisons will work
            planet.endBuildTime = datetime.datetime.now() - timedelta(days=10000)
        

########################################################################################## 
    def upgradeBuilding(self, planet, building):
        page = self._fetchPhp('index.php', page='b_building', modus='add', techid=building.code, cp=planet.code).read()
        mySleep(10)
        self._checkEndTimeOfBuildingUpgrade(planet, page)
    

########################################################################################## 
    def getResearchLevels(self, player, planetList):
        player.research, player.allResearch = {}, {}
        for planet in planetList:
            page = self._fetchPhp('index.php', page='buildings', mode='Forschung',cp=planet.code).read()
            player.research['CompletionTime'] = self._checkEndTimeOfResearchUpgrade(planet, page)
            for fullName, level in self.REGEXPS['researchLevels'].findall(page):
                player.research[self.translationsByLocalText[fullName]] = int(level)
                
        for item in ['espionageTechnology', 'computerTechnology', 'weaponsTechnology', 'shieldingTechnology', 'armourTechnology', 'energyTechnology', 'hyperspaceTechnology', 'combustionDrive', 'impulseDrive', 'hyperspaceDrive', 'laserTechnology', 'ionTechnology',  'plasmaTechnology', 'intergalacticResearchNetwork', 'gravitonTechnology']:
            if item in player.research:
                player.allResearch[item] = player.research[item]
            else:
                player.allResearch[item] = 0


########################################################################################## 
    def _checkEndTimeOfResearchUpgrade(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
                page = self._fetchPhp('index.php', page='buildings', cp=planet.code).read()     
        upgradeTime = self.REGEXPS['currentlyUpgradingResearch'].search(page)
        labPresent  = self.REGEXPS['planet']['ResearchLabPresent'].search(page)
        if labPresent:
            if upgradeTime:
                return datetime.datetime.now() + timedelta(seconds=int(upgradeTime.group(1)))
            else:
                #guarentuees all time comparisons will work
                return datetime.datetime.now() - timedelta(days=10000)


########################################################################################## 
    def upgradeResearch(self, planet, research):
        reply = self._fetchPhp('index.php', page='buildings', mode='Forschung', cp=planet.code, bau=research.code).read()
        mySleep(10)
        return self._checkEndTimeOfResearchUpgrade(planet, reply)


########################################################################################## 
    def getDefense(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='buildings', mode='Verteidigung', cp=planet.code).read()
        planet.defense = {}
        for name, quantity in self.REGEXPS['planet']['defense'].findall(page):
            planet.defense[name] = int(quantity.replace('.', ''))
        self.checkDefenseQueue(planet, page)

########################################################################################## 
    def checkDefenseQueue(self, planet, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='buildings', mode='Verteidigung', cp=planet.code).read()
        time = self.REGEXPS['planet']['durationRemaining'].search(page)
        if time: 
            return True 
            planet.endDefenseWaitTime = datetime.datetime.now() + timedelta(days=time.group(2), hours=time.group(4), minutes=time.group(5), seconds=time.group(6))
        else: 
            return False    


########################################################################################## 
    def buildDefense(self, planet, defense):
        page = self._fetchPhp('index.php', page='buildings', mode='Verteidigung', cp=planet.code )
        form = ParseFile( page, self.lastFetchedUrl, backwards_compat=False )[-1]
        for defenseType, quantity in defense.iteritems():
            try:
                controlName = "fmenge[%s]" % INGAME_TYPES_BY_NAME[defenseType].code
                form[controlName] = str( quantity )
            except ControlNotFoundError:
                raise BotError( defenseType )
        reply = self._fetchForm( form )
        self.checkDefenseQueue(planet, reply)

########################################################################################## 
    def getAvailableFleet(self, planet, alreadyFetchedPage = None):    
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='flotten1', mode='Flotte', cp=planet.code).read()
        planet.fleet = {}
        for code, quantity in self.REGEXPS['planet']['availableFleet'].findall(page):
            planet.fleet[INGAME_TYPES_BY_CODE[code].name] = int(quantity.replace('.', ''))


########################################################################################## 
    def checkFleetQueue(self, planet, alreadyFetchedPage = None):
        time = self.REGEXPS['planet']['durationRemaining'].search(page.read())
        if time: 
            return True 
            planet.endFleetWaitTime = datetime.datetime.now() + timedelta(days=time.group(2), hours=time.group(4), minutes=time.group(5), seconds=time.group(6))
        else: 
            return False    


########################################################################################## 
    def buildShips(self, planet, ships):
        if not ships: return
        page = self._fetchPhp('index.php', page='buildings', mode='Flotte', cp=planet.code )
        form = ParseFile( page, self.lastFetchedUrl, backwards_compat=False )[-1]
        for shipType, quantity in ships.iteritems():
            try:
                controlName = "fmenge[%s]" % INGAME_TYPES_BY_NAME[shipType].code[-3:]
                form[controlName] = str( quantity )
            except ControlNotFoundError:
                raise BotError( shipType )
        reply = self._fetchForm( form )
        self.checkFleetQueue(planet, reply)

########################################################################################## 
    def getFleetSlots(self, player, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('index.php', page='flotten1', mode='Flotte').read()
        fleetSlots = self.REGEXPS['fleetSlots'].search(page)
        player.totalFleetSlots = int(fleetSlots.group(2))
        player.freeFleetSlots = player.totalFleetSlots - int(fleetSlots.group(1))


########################################################################################## 
    def getEspionageReports(self):
        page = self._fetchPhp('index.php', page='messages').read()
        rawMessages = {}
        for match in self.REGEXPS['messages.php'].finditer(page):
            rawMessages[match.group('code')] = match.group(0) 
            
        reports = []              
        for code, rawMessage in rawMessages.items():
#            if 'class="combatreport"' in rawMessage:
#                [2:444:6] (A:8.000)
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
                dict = None
                match = self.REGEXPS['report'][i].search(rawMessage)
                if match:
                    dict, text = {}, match.group(1)
                    for fullName, quantity in self.REGEXPS['report']['details'].findall(text):
                        dict[self.translationsByLocalText[fullName.strip()]] = int(quantity.replace('.', ''))
                        
                setattr(report, i, dict)
                
            report.rawHtml = rawMessage
            reports.append(report)
            
        return reports

   
##########################################################################################         
    def launchMission(self, player, mission, abortIfNotEnough = True, fleetSlotsToReserve = 0):

        while True:
            # assure cuantities are integers
            for shipType, quantity in mission.fleet.items(): 
                mission.fleet[shipType] = int(quantity)

            # 1st step: select fleet
            page = self._fetchPhp('index.php', page='flotten1', mode='Flotte', cp=mission.sourcePlanet.code)
            pageText = page.read()
            page.seek(0)            

            self.getFleetSlots(player, pageText)
            self.getAvailableFleet(mission.sourcePlanet, pageText)
            form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[-1]        

            for shipType, requested in mission.fleet.iteritems():
                available = mission.sourcePlanet.fleet.get(shipType, 0)
                if available == 0 or (abortIfNotEnough and available  < requested):
                    raise NotEnoughShipsError(mission.sourcePlanet.fleet, {shipType:requested}, available)
                shipCode = INGAME_TYPES_BY_NAME[shipType].code
                form[shipCode] = str(requested)

            if player.freeFleetSlots <= int(fleetSlotsToReserve):
                raise NoFreeSlotsError()

            mySleep(3)
            # 2nd step: select destination and speed  
            page = self._fetchForm(form)

            forms = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)
            if not forms or 'flotten3' not in forms[0].action:
                continue
            form = forms[0]
            destCoords = mission.targetPlanet.coords         
            form['galaxy']    = str(destCoords.galaxy)
            form['system']    = str(destCoords.solarSystem)
            form['planet']    = str(destCoords.planet)
            form['planettype']= [str(destCoords.coordsType)]
            form['speed']      = [str(mission.speedPercentage / 10)]

            mySleep(3)
            # 3rd step:  select mission and resources to carry
            page = self._fetchForm(form)
            form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[0]
            try:
                form['order']      = [str(mission.missionType)]
            except ControlNotFoundError:
                continue

            resources = mission.resources
            form['resource1'] = str(resources.metal)
            form['resource2'] = str(resources.crystal)
            form['resource3'] = str(resources.deuterium)                   

            mySleep(3)
            # 4th and final step: check result
            page = self._fetchForm(form).read()
            if self.translations['fleetCouldNotBeSent'] in page:
                continue
            
            errors = self.REGEXPS['fleetSendError'].findall(page)
            if len(errors) > 0 or 'class="success"' not in page:
                errors = str(errors)
                if self.translations['fleetLimitReached'] in errors:
                    raise NoFreeSlotsError()
                elif self.translations['noShipSelected'] in errors:
                    raise NotEnoughShipsError(availableFleet, mission.fleet)
                else: 
                    raise FleetSendError(errors)

            resultPage = {}
            for type, value in self.REGEXPS['fleetSendResult'].findall(page):
                resultPage[type] = value

            # fill remaining mission fields
            arrivalTime = parseTime(resultPage[self.translations['arrivalTime']])
            returnTime = parseTime(resultPage[self.translations['returnTime']])
            mission.setTimes(arrivalTime, returnTime)
            mission.distance =  int(resultPage[self.translations['distance']].replace('.', ''))
            mission.consumption = int(resultPage[self.translations['consumption']].replace('.', ''))

            #check simulation formulas are working correctly:
#               assert mission.distance == mission.sourcePlanet.coords.distanceTo(mission.targetPlanet.coords)
#               flightTime = mission.sourcePlanet.coords.flightTimeTo(mission.targetPlanet.coords, int(resultPage[self.translations['speed']].replace('.','')))
#               margin = timedelta(seconds = 3)
#               assert mission.flightTime > flightTime - margin and mission.flightTime < flightTime + margin
#               check mission was sent as expected:
#               assert str(mission.sourcePlanet.coords) in resultPage[self.translations['start']]
#               assert str(mission.targetPlanet.coords) in resultPage[self.translations['target']] 

            # check the requested fleet was sent intact:
            sentFleet = {}
            for fullName, value in resultPage.items():
                    name = self.translationsByLocalText.get(fullName)
                    if name is None:
                        continue
                    if name in INGAME_TYPES_BY_NAME.keys():
                        sentFleet[name] = int(value.replace('.', ''))

            if mission.fleet != sentFleet:
                    warnings.warn("Not all requested fleet was sent. Requested: %s. Sent: %s" % (mission.fleet, sentFleet))
                    mission.fleet = sentFleet

            break

                
##########################################################################################
    def deleteMessages(self, messages):
        page = self._fetchPhp('index.php', page='messages')
        form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[0]
        for message in messages:
            checkBoxName = "delmes" + message.code
            try:
                form[checkBoxName]      = [None] # actually this marks the checbox as checked (!!)
                form["deletemessages"] = ["deletemarked"]
            except ControlNotFoundError:
                if __debug__:
                    print >> sys.stderr, "Could not delete message " + str(message)
            
        self._fetchForm(form)


########################################################################################## 
    def getStats(self, player, type, alreadyFetchedPage = None): # type can be: pts for points, flt for fleets or res for research
        if type != "pts" :
            page = self._fetchPhp('index.php', page='statistics')
            form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[-1]
            form['type'] = [type]
            form['start'] = ['[Own position]']
            page = self._fetchForm(form)
            page = page.read()
            stats = self.REGEXPS['stats'].search(page)
        else:   
            page = alreadyFetchedPage
            if not page:
                page = self._fetchPhp('index.php', page='overview').read()
            stats = self.REGEXPS['statsOverview'].search(page)

        player.rank = int(stats.group(1).replace('.',''))
        player.points = int(stats.group(2).replace('.',''))     


########################################################################################## 
    def getSolarSystems(self, solarSystems, deuteriumSourcePlanet = None): # solarsytems is an iterable of tuples
        if deuteriumSourcePlanet:
            self.goToPlanet(deuteriumSourcePlanet)
        threads = []
        inputQueue = Queue()
        outputQueue = Queue()
        for galaxy, solarSystem in solarSystems:
            params = {'session':self.session, 'galaxy':galaxy, 'system':solarSystem }
            url = "http://%s/game/index.php?page=galaxy&%s" % (self.server, urllib.urlencode(params))        
            inputQueue.put(url)
       
        for dummy in range(1):
            thread = ScanThread(inputQueue, outputQueue, self.keepaliveopener, self.REGEXPS)
            thread.start() 
            threads.append(thread)            
 

        found = []
        while filter(threading.Thread.isAlive, threads):
            try:
                output = outputQueue.get_nowait()
                if output not in found:
                    found.append(output)
                    yield output
            except Empty: 
                mySleep(2)
        
        for thread in threads:
            if thread.exception:
                raise thread.exception  

      
########################################################################################## 
class ScanThread(threading.Thread):
    ''' Scans solar systems from inputQueue'''
    def __init__(self, inputQueue, outputQueue, opener, regexps):
        threading.Thread.__init__(self, name="GalaxyScanThread")
        self._inputQueue = inputQueue
        self._outputQueue = outputQueue
        self.opener = opener
        self.REGEXPS = regexps
        self.exception = None
        
    def run(self):
        socket.setdefaulttimeout(20)   

        error = False
        while True:
            try:
                if not error:
                    url = self._inputQueue.get_nowait()
                
                response = self.opener.open(url)
                page = response.read()
                
                if 'span class="error"' in page:
                    print >>sys.stderr, page
                    raise BotError("Probably there is not enough deuterium on planet.")
                elif 'error' in  response.geturl():
                    error = True
                    continue
                
                if __debug__: 
                    print >>sys.stderr, "\t " + datetime.datetime.now().strftime("%m-%d, %H:%M:%S") + " Fetched " + url                
                
                htmlSource = page
                page = page.replace("\n", "")

                if __debug__: 
                    print >>sys.stderr, "         Page length : %s" %(len(page))  
                    if len(page) < 1000: 
                        print >>sys.stderr, page

                galaxy      = re.findall('input type="text" name="galaxy" value="([0-9]+)"', page)[0]
                solarSystem = re.findall('input type="text" name="system" value="([0-9]+)"', page)[0]
                        
                foundPlanets = []
                for number, name, ownerStatus, owner, alliance in self.REGEXPS['solarSystem'].findall(page):
                # Absolutely ALL EnemyPlanet objects of the bot are created here
                    planet = EnemyPlanet(Coords(galaxy, solarSystem, number), owner, ownerStatus, name, alliance)
                    foundPlanets.append(planet)
                    self._outputQueue.put((galaxy, solarSystem, foundPlanets, htmlSource))
                    
                error = False
            except Empty:
                break
            except BotError, e:
                self.exception = e
                break
            except Exception, e:
                error = True
                if __debug__: 
                    print >>sys.stderr, e


########################################################################################## 
def parseTime(strTime, format = "%a %b %d %H:%M:%S"):# example: Mon Aug 7 21:08:52                        
    ''' parses a time string formatted in OGame most usual format and 
    converts it to a datetime object'''
    
    format = "%Y " + format
    strTime = str(datetime.datetime.now().year) + " " +strTime
    date = datetime.datetime.strptime(strTime, format) 
    return date
