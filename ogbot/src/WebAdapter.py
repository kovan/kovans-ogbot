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
from Queue import *
from datetime import datetime, time
from time import strptime
from cStringIO import *
from ClientForm import HTMLForm, ParseFile, ControlNotFoundError;
import keepalive

from CommonClasses import *
from Constants import *
from GameEntities import *



class WebAdapter(object):
    """Encapsulates the details of the communication with the ogame servers. This involves
        HTTP protocol encapsulation and HTML parsing.
    """
    
        
    class EventManager(BaseEventManager):
        def __init__(self, gui = None):
            self.gui = gui

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
        
    def __init__(self, config, allTranslations, checkThreadMsgsMethod, gui = None):
        self.server = ''
        self.lastFetchedUrl = ''
        self.serverCharset = ''        
        self.config = config
        self.checkThreadMsgsMethod = checkThreadMsgsMethod
        self._eventMgr = WebAdapter.EventManager(gui)
        self.serverTimeDelta = None
        
        self.webpage = "http://"+ config.webpage + "/home.php"

        if not self.loadState():
            self.session = '000000000000'

        #setup urllib2:
        socket.setdefaulttimeout(10.0)
        param1 = keepalive.HTTPHandler()
        param2 = urllib2.HTTPCookieProcessor()

        if self.config.proxy:
            param3 = urllib2.ProxyHandler({"http":"http://"+self.config.proxy})
            opener = urllib2.build_opener(param1,param2,param3)
        else:
            opener = urllib2.build_opener(param1,param2)
        
        opener.addheaders = [('User-agent', self.config.userAgent),('Keep-Alive', "300")]            
                    
        urllib2.install_opener(opener)

        
        cachedResponse = StringIO(self._fetchValidResponse(self.webpage, True).read())
        # check configured language equals ogame server language
        regexpLanguage = re.compile(r'<meta name="language" content="(\w+)"', re.I) # outide the regexp definition block because we need it to get the language in which the rest of the regexps will be generated
        self.serverLanguage =  regexpLanguage.findall(cachedResponse.getvalue())[0]
        try: self.translations = allTranslations[self.serverLanguage]
        except KeyError:
            raise BotFatalError("Server language (%s) not supported by bot" % self.serverLanguage)
        self.translationsByLocalText = dict([ (value, key) for key, value in self.translations.items() ])
        self.generateRegexps(self.translations)        
        # retrieve server based on universe number        
        cachedResponse.seek(0)                        
        form = ParseFile(cachedResponse, self.lastFetchedUrl, backwards_compat=False)[0]        
        select = form.find_control(name = "universe")
        translation = self.translations['universe']
        if self.serverLanguage == "tw":
            translation = translation.decode('gb2312').encode('utf-8')
        elif  self.serverLanguage == "kr":
            translation = translation.decode('Euc-kr').encode('utf-8')
        self.server = select.get(label = self.config.universe +'. '+  translation, nr=0).name
        

    def generateRegexps(self, translations):

        reportTmp  = r'%s (?P<planetName>[^<]*?) .*?(?P<coords>\[[0-9:]+\]).*? (?P<date>[0-9].*?)</td></tr>\n' %  translations['resourcesOn']
        reportTmp += r'<tr><td>.*?</td><td>(?P<metal>[-0-9.]+)</td>\n'
        reportTmp += r'<td>.*?</td><td>(?P<crystal>[-0-9.]+)</td></tr>\n'
        reportTmp += r'<tr><td>.*?</td><td>(?P<deuterium>[-0-9.]+)</td>\n'
        reportTmp += r'<td>.*?</td><td>(?P<energy>[-0-9.]+)</td></tr>'  
        reportTmp2 = r'<table width=[0-9]+><tr><td class=c colspan=4>%s(.*?)</table>'

        
        self.REGEXP_COORDS_STR  = r"([1-9]{1,3}):([0-9]{1,3}):([0-9]{1,2})"
        self.REGEXP_SESSION_STR = r"[0-9A-Fa-f]{12}"

        self.REGEXPS = \
        {
            'messages.php': re.compile(r'<input type="checkbox" name="delmes(?P<code>[0-9]+)".*?(?=<input type="checkbox")', re.DOTALL |re.I), 
            'fleetSendError':re.compile(r'<span class="error">(?P<error>.*?)</span>', re.I), 
            'myPlanets':re.compile('<option value="/game/overview\.php\?session='+self.REGEXP_SESSION_STR+'&cp=([0-9]+)&mode=&gid=&messageziel=&re=0" (?:selected)?>(.*?)<.*?\['+self.REGEXP_COORDS_STR+'].*?</option>', re.I), 
            'report': 
            {
                'all'  :    re.compile(reportTmp, re.LOCALE|re.I), 
                'fleet':    re.compile(reportTmp2 % translations['fleets'], re.DOTALL|re.I), 
                'defense':  re.compile(reportTmp2 % translations['defense'], re.DOTALL|re.I), 
                'buildings':re.compile(reportTmp2 % translations['buildings'], re.DOTALL|re.I), 
                'research': re.compile(reportTmp2 % translations['research'], re.DOTALL|re.I), 
                'details':  re.compile(r"<td>(?P<type>.*?)</td><td>(?P<cuantity>[-0-9.]+)</td>", re.DOTALL|re.I)
            }, 
            'serverTime':re.compile(r"<th>.*?%s.*?</th>.*?<th.*?>(?P<date>.*?)</th>" %  translations['serverTime'], re.DOTALL|re.I), 
            'availableFleet':re.compile(r'name="max(?P<type>ship[0-9]{3})" value="(?P<cuantity>[-0-9.]+)"', re.I), 
            'maxSlots':re.compile(r"%s([0-9]+)" %  translations['maxFleets'].replace('.', '\. '), re.I), 
            'researchLevels':re.compile(r">(?P<techName>[^<]+)</a></a>\s*?\(.*?(?P<level>\d+)\s*?\)", re.I|re.LOCALE),            
            'fleetSendResult':re.compile(r"<tr.*?>\s*<th.*?>(?P<name>.*?)</th>\s*<th.*?>(?P<value>.*?)</th>", re.I), 
            'charset':re.compile(r'content="text/html; charset=(.*?)"', re.I), 
            'solarSystem':re.compile(r'<tr>.*?<a href="#"  tabindex="\d+" >(\d+)</a>.*?<th width="130".*?>([^&<]+).*?<th width="150">.*?<span class="(\w+?)">([\w .]+?)</span>.*?<th width="80">.*?> *([\w .]*?) *<.*?</tr>')
        }
        
        
        
    def setSession(self, value):
        self._session = value
        self.saveState()
    def getSession(self): 
        return self._session
    session = property(getSession, setSession)    
    
    
    def serverTime(self):
        return self.serverTimeDelta + datetime.now()
            
    def _fetchPhp(self, php, **params):
        params['session'] = self.session
        url = "http://%s/game/%s?%s" % (self.server, php, urllib.urlencode(params))
        return self._fetchValidResponse(url)
    
    def _fetchForm(self, form):
        return self._fetchValidResponse(form.click())
    
    def _fetchValidResponse(self, request, skipValidityCheck = False):

        
        valid = False

        while not valid:
            self.checkThreadMsgsMethod()

            valid = True
            try:
                response = urllib2.urlopen(request)
                self.lastFetchedUrl = response.geturl()
                if __debug__: 
                    print >>sys.stderr, "         Fetched " + self.lastFetchedUrl
                cachedResponse = StringIO(response.read())
                p = cachedResponse.getvalue()
                cachedResponse.seek(0)
                # store last 20 pages fetched in the debug directory:
                files = os.listdir('debug')
                if len(files) >= 20: #never allow more than 20 files
                    files.sort()
                    os.remove('debug/'+files[0])
                try: php = '_'+re.findall("/(\w+\.php)", self.lastFetchedUrl)[0]
                except IndexError: php = ''
                date = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
                file = open("debug/%s%s.html" %(date, php), 'w')
                file.write(p.replace('<script', '<noscript').replace('</script>', '</noscript>').replace('http-equiv="refresh"', 'http-equiv="kovan-rulez"'))
                file.close()
                
                if skipValidityCheck:
                    return cachedResponse                
                elif self.translations['youAttemptedToLogIn'] in p:         
                    raise BotFatalError("Invalid username and/or password.")
                elif not p or 'errorcode=8' in self.lastFetchedUrl:
                    valid = False
                elif self.translations['dbProblem'] in p or self.translations['untilNextTime'] in p or "Grund 5" in p:
                    oldSession = self.session
                    self.doLogin()
                    if   isinstance(request, str):
                        request = request.replace(oldSession, self.session)
                    elif isinstance(request, HTMLForm):
                        request.action = request.action.replace(self.REGEXP_SESSION_STR, self.session)
                        request['session'] = self.session
                    elif isinstance(request, urllib2.Request) or isinstance(request, types.InstanceType): # check for new style object and old style too, 
                        for attrName in dir(request):
                            attr = getattr(request, attrName)
                            if isinstance(attr, str):
                                newValue = re.sub(oldSession, self.session, attr)  
                                setattr(request, attr, newValue)
                    else: raise BotError(request)
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
                mySleep(5)
        return cachedResponse
    
    def doLogin(self):
        if self.serverTimeDelta and self.serverTime().hour == 3 and self.serverTime().minute == 0: # don't connect immediately after 3am server reset
            mySleep(60)                
        page = self._fetchValidResponse(self.webpage)
        form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[0]
        form["universe"] = [self.server]
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
        mySleep(12)        
        page = self._fetchPhp('overview.php', lgn=1)               
        self.saveState()



    def getMyPlanets(self):
        self._fetchPhp('index.php', lgn=1)                
        page = self._fetchPhp('overview.php',lgn=1).read()
        
        myPlanets = []
        for code, name, galaxy, ss, pos in self.REGEXPS['myPlanets'].findall(page):
            coords = Coords(galaxy, ss, pos)
            for planet in myPlanets:
                if planet.coords == coords: # we found a moon for this planet
                    coords.coordsType = Coords.Types.moon
            planet = OwnPlanet(coords, name.strip(), code)
            myPlanets.append(planet)
        
        strTime = self.REGEXPS['serverTime'].findall(page)[0]
        serverTime = parseTime(strTime)
        self.serverTimeDelta = serverTime - datetime.now()
        self.serverCharset = self.REGEXPS['charset'].findall(page)[0]
        self.myPlanets = myPlanets
        return myPlanets
    
        
    def getEspionageReports(self):
        page = self._fetchPhp('messages.php').read()
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
                    for fullName, cuantity in self.REGEXPS['report']['details'].findall(text):
                        dict[self.translationsByLocalText[fullName.strip()]] = int(cuantity.replace('.', ''))
                        
                setattr(report, i, dict)
                
            report.rawHtml = rawMessage
            reports.append(report)
            
        return reports
        
#    def buildShips(self, ships, planet):
#        return 
        #
        # with python 2.4. sgmlib doesnt parse well indexed controls, all of them get the root name, no index. the fix that corrected it in python 2.5 introduced the bug below
        
#        if not ships:
#            return
#        page = self._fetchPhp( 'buildings.php', mode='Flotte', cp=sourceplanet.code )
#        form = ParseFile( page,self.lastFetchedUrl, backwards_compat=False )[-1]
#        for shipType, cuantity in ships.items():
#            try:
#                controlName = "fmenge[%s]" % INGAME_TYPES_BY_NAME[shipType].code[-3:]
#                form[controlName] = str( cuantity )
#            except ControlNotFoundError:
#                raise BotError( shipType )
#        self._fetchForm( form )
        
    def buildBuildings(self, building, planet):
        self._fetchPhp('b_building.php', bau=building.code, cp=planet.code)
        
    def launchMission(self, mission, abortIfNotEnough = True, slotsToReserve = 0):

        while True:
            # assure cuantities are integers
            for shipType, cuantity in mission.fleet.items(): 
                mission.fleet[shipType] = int(cuantity)
                        
            # 1st step: select fleet
            page = self._fetchPhp('flotten1.php', mode='Flotte', cp=mission.sourcePlanet.code)
            pageText = page.read()
            page.seek(0)            
            
            
            availableFleet = self.getAvailableFleet(None, pageText)
            form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[-1]        
            
            for shipType, requested in mission.fleet.items():
                available = availableFleet.get(shipType, 0)
                if available == 0 or (abortIfNotEnough and available  < requested):
                    raise NotEnoughShipsError(availableFleet, {shipType:requested}, available)
                
                shipCode = INGAME_TYPES_BY_NAME[shipType].code            
                form[shipCode] = str(requested)
                
            if self.getFreeSlots(pageText) <= int(slotsToReserve):
                raise NoFreeSlotsError()
    
            # 2nd step: select destination and speed
            
            page = self._fetchForm(form)
            
            forms = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)
            if not forms or 'flotten3.php' not in forms[0].action:
                raise NoFreeSlotsError()
            form = forms[0]
            destCoords = mission.targetPlanet.coords         
            form['galaxy']    = str(destCoords.galaxy)
            form['system']    = str(destCoords.solarSystem)
            form['planet']    = str(destCoords.planet)
            form['planettype']= [str(destCoords.coordsType)]
            form['speed']      = [str(mission.speedPercentage / 10)]
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
            # 4th and final step: check result
            page = self._fetchForm(form).read()
            
            if self.translations['fleetCouldNotBeSent'] in page:
                continue
            
            errors = self.REGEXPS['fleetSendError'].findall(page)
            if len(errors) > 0 or 'class="success"' not in page:
                errors = str(errors)
                if   self.translations['fleetLimitReached'] in errors:
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
            mission.flightTime = returnTime - arrivalTime
            mission.launchTime = arrivalTime - mission.flightTime
            mission.distance =  int(resultPage[self.translations['distance']].replace('.', ''))
            mission.consumption = int(resultPage[self.translations['consumption']].replace('.', ''))
                
    #        # check simulation formulas are working correctly:
    #        assert mission.distance == mission.sourcePlanet.coords.distanceTo(mission.targetPlanet.coords)
    #        flightTime = mission.sourcePlanet.coords.flightTimeTo(mission.targetPlanet.coords, int(resultPage[self.translations['speed']].replace('.','')))
    #        margin = timedelta(seconds = 3)
    #        assert mission.flightTime > flightTime - margin and mission.flightTime < flightTime + margin
    #        # check mission was sent as expected:
    #        assert str(mission.sourcePlanet.coords) in resultPage[self.translations['start']]
    #        assert str(mission.targetPlanet.coords) in resultPage[self.translations['target']] 
            
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
                
    def getFreeSlots(self, alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('flotten1.php', mode='Flotte').read()
        usedSlotsNums = re.findall(r"<th>([0-9]+)</th>", page)

        if len(usedSlotsNums) == 0:
            usedSlots = 0
        else: 
            usedSlots = int(usedSlotsNums[-1])
        maxFleets = int(self.REGEXPS['maxSlots'].search(page).group(1))
        if "admiral_ikon.gif" in page:
            maxFleets += 2
        return maxFleets - usedSlots
    
    def getAvailableFleet(self, planet, alreadyFetchedPage = None):    
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('flotten1.php', mode='Flotte', cp=planet.code).read()
        fleet = {}
        for code, cuantity in self.REGEXPS['availableFleet'].findall(page):
            fleet[INGAME_TYPES_BY_CODE[code].name] = int(cuantity.replace('.', ''))
        return fleet
    
    def deleteMessages(self, messages):
        page = self._fetchPhp('messages.php')
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
        
    def getResearchLevels(self):


        for planet in self.myPlanets:
            page = self._fetchPhp('buildings.php', mode='Forschung',cp=planet.code).read()
            levels = {}            
            for fullName, level in self.REGEXPS['researchLevels'].findall(page):
                levels[self.translationsByLocalText[fullName]] = int(level)
            if 'impulseDrive' in levels and 'combustionDrive' in levels:
                return levels
               
        raise BotFatalError("Not enough technologies researched to run the bot")
                
    def goToPlanet(self, planet):
        self._fetchPhp('overview.php', cp=planet.code)
        
    def getSolarSystems(self, solarSystems, deuteriumSourcePlanet = None): # solarsytems is an iterable of tuples

        if deuteriumSourcePlanet:
            self.goToPlanet(deuteriumSourcePlanet)
        threads = []
        inputQueue = Queue()
        outputQueue = Queue()
        for galaxy, solarSystem in solarSystems:
            params = {'session':self.session, 'galaxy':galaxy, 'system':solarSystem }
            url = "http://%s/game/galaxy.php?%s" % (self.server, urllib.urlencode(params))        
            inputQueue.put(url)
            
        for dummy in range(20):
            thread = ScanThread(inputQueue, outputQueue, self.REGEXPS)
            threads.append(thread)            
            thread.start()

        found = []
        while filter(threading.Thread.isAlive, threads):
            try:
                output = outputQueue.get_nowait()
                if output not in found:
                    found.append(output)
                    yield output
            except Empty: 
                sleep(1)
        
        for thread in threads:
            if thread.exception:
                raise thread.exception
        
    def getStats(self, type): # type can be: pts for points, flt for fleets or res for research
        page = self._fetchPhp('stat.php', start=1)
        form = ParseFile(page, self.lastFetchedUrl, backwards_compat=False)[-1]
        
        for i in range(1, 1401, 100):
            form['type'] = [type]
            form['start'] = [str(i)]
            page = self._fetchForm(form).read()
            regexp = r"<th>(?:<font color='87CEEB'>)?([^<]+)(?:</font>)?</th>.*?<th>([0-9.]+)</th>"
            for player, points in re.findall(regexp, page, re.DOTALL):
                yield player, int(points.replace('.', ''))
        

    
    def saveState(self):
        file = open(FILE_PATHS['webstate'], 'wb')
        pickler = cPickle.Pickler(file, 2)        
        pickler.dump(self.server)         
        pickler.dump(self.session)
        file.close()
        
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
    
class ScanThread(threading.Thread):
    ''' Scans solar systems from inputQueue'''
    def __init__(self, inputQueue, outputQueue, regexps):
        threading.Thread.__init__(self, name="GalaxyScanThread")
        self._inputQueue = inputQueue
        self._outputQueue = outputQueue
        self.REGEXPS = regexps
        self.exception = None
        
    def run(self):
        socket.setdefaulttimeout(20)   

        error = False
        while True:
            try:
                if not error:
                    url = self._inputQueue.get_nowait()
                
                response = urllib2.urlopen(url)
                page = response.read()
                
                if 'span class="error"' in page:
                    raise BotError("Probably there is not enough deuterium in current planet.")
                elif 'error' in  response.geturl():
                    error = True
                    continue
                
                if __debug__: 
                    print >>sys.stderr, "         Fetched " + url                
                
                htmlSource = page
                page = page.replace("\n", "")
                galaxy      = re.findall('input type="text" name="galaxy" value="(\d+)"', page)[0]
                solarSystem = re.findall('input type="text" name="system" value="(\d+)"', page)[0]
                        
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
        
        
                



def parseTime(strTime, format = "%a %b %d %H:%M:%S"):# example: Mon Aug 7 21:08:52                        
    ''' parses a time string formatted in OGame's most usual format and 
    converts it to a datetime object'''
    
    format = "%Y " + format
    strTime = str(datetime.now().year) + " " +strTime
    tuple = strptime(strTime, format) 
    return datetime(*tuple[0:6])