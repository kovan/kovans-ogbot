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
import time
import re
import os
import urllib
import types
import cPickle

import urllib2
import copy
import sys
import httplib
import warnings
from datetime import datetime
from mechanize import *
from ClientForm import HTMLForm, ParseResponse, ControlNotFoundError;
from BeautifulSoup import *
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
            self.dispatch("activityMsg",msg)            
        def activityMsg(self,msg):
            self.logAndPrint(msg)
            msg = datetime.now().strftime("%X %x ") + msg
            self.dispatch("activityMsg",msg)
        
    def __init__(self, config, allTranslations,checkThreadMethod,gui = None):
        self.server = ''
        self.lastFetch = ''
        self.browser = Browser()
        self.config = config
        self._checkThreadMethod = checkThreadMethod
        self._eventMgr = WebAdapter.EventManager(gui)
        self.serverTimeDelta = None
        
        self.browser.set_handle_refresh(True, 0, False) # HTTPRefreshProcessor(0,False)         
        self.browser.set_handle_robots(False) # do not obey website's anti-bot indications
        self.browser.addheaders = [('User-agent', self.config.userAgent)]
        if self.config.proxy:
            self.browser.set_proxies({"http":"http://"+self.config.proxy})
        if config.webpage.endswith('.ba') or config.webpage.endswith('.com.hr'):
            self.webpage = "http://"+ config.webpage +"/portal/?lang=yu&frameset=1"
        else:
            self.webpage = "http://"+ config.webpage +"/portal/?frameset=1"
        
        if not self.loadState():
            self.session = '000000000000'
        

        page = self._fetchValidResponse(self.webpage,True)
        # check configured language equals wb language
        regexpLanguage = re.compile(r'<meta name="language" content="(\w+)"',re.I) # outide the regexp definition block because we need it to get the language in which the rest of the regexps will be generated
        self.serverLanguage =  regexpLanguage.findall(page.read())[0]
        try: self.translations = allTranslations[self.serverLanguage]
        except KeyError:
            raise BotFatalError("Server language (%s) not supported by bot" % self.serverLanguage )
        self.translationsByLocalText = dict([ (value,key) for key,value in self.translations.items() ])
        self.generateRegexps(self.translations)        
        # retrieve server based on universe number        
        page.seek(0)                        
        form = ParseResponse(page, backwards_compat=False)[0]        
        select = form.find_control(name = "Uni")
        translation = self.translations['universe']
        if self.serverLanguage == "tw":
            translation = translation.decode('gb2312').encode('utf-8')
        elif  self.serverLanguage == "kr":
            translation = translation.decode('Euc-kr').encode('utf-8')
        self.server = select.get(label = self.config.universe +'. '+  translation, nr=0).name
 

    def generateRegexps(self,translations):
        reportTmp  = r'%s (?P<planetName>.*?) .*?(?P<coords>\[[0-9:]+\]).*? (?P<date>[0-9].*?)</td></tr>\n' %  translations['resourcesOn']
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
            'fleetSendError':re.compile(r'<span class="error">(?P<error>.*?)</span>',re.I), 
            'myPlanets':re.compile('<option value="/game/overview\.php\?session='+self.REGEXP_SESSION_STR+'&cp=([0-9]+)&mode=&gid=&messageziel=&re=0" (?:selected)?>(.*?) +.*?\['+self.REGEXP_COORDS_STR+'].*?</option>',re.I), 
            'report': 
            {
                'all'  :    re.compile(reportTmp, re.LOCALE|re.I), 
                'fleet':    re.compile(reportTmp2 % translations['fleets'], re.DOTALL|re.I), 
                'defense':  re.compile(reportTmp2 % translations['defense'], re.DOTALL|re.I), 
                'buildings':re.compile(reportTmp2 % translations['buildings'], re.DOTALL|re.I), 
                'research': re.compile(reportTmp2 % translations['research'], re.DOTALL|re.I), 
                'details':  re.compile(r"<td>(?P<type>.*?)</td><td>(?P<cuantity>[-0-9.]+)</td>",re.DOTALL|re.I)
            }, 
            'serverTime':re.compile(r"<th>.*?%s.*?</th>.*?<th.*?>(?P<date>.*?)</th>" %  translations['serverTime'], re.DOTALL|re.I), 
            'availableFleet':re.compile(r'name="max(?P<type>ship[0-9]{3})" value="(?P<cuantity>[-0-9.]+)"',re.I), 
            'maxSlots':re.compile(r"%s([0-9]+)" %  translations['maxFleets'].replace('.','\. '),re.I), 
            'techLevels':re.compile(r">(?P<techName>\w+)</a></a> \(%s (?P<level>\d+)\)" %  translations['level'], re.LOCALE|re.I), 
            'fleetSendResult':re.compile(r"<tr.*?>\s*<th.*?>(?P<name>.*?)</th>\s*<th.*?>(?P<value>.*?)</th>",re.I), 
            
        }
        
        
        
    def setSession(self, value):
        self._session = value
        self.saveState()
    def getSession(self): 
        return self._session
    session = property(getSession, setSession)    
    
    def getControlUrl(self):
        return "http://%s/game/index.php?session=%s" % (self.server, self.session)
    
    def serverTime(self):
        return self.serverTimeDelta + datetime.now()
            
    def _fetchPhp(self, php, **params):
        params['session'] = self.session
        url = "http://%s/game/%s?%s" % (self.server, php, urllib.urlencode(params))
        self.lastFetch = url
        return self._fetchValidResponse(url)
    
    def _fetchForm(self, form):
        self.lastFetch = str(form)
        return self._fetchValidResponse(form.click())
    
    def _fetchValidResponse(self, request, skipValidityCheck = False):
        if __debug__: 
            print >>sys.stderr, "         Fetching " + self.lastFetch

        valid = False
        while not valid:
            valid = True
            try:
                # MAIN PLACE TO CHECK CHECK FOR INTER-THREAD QUEUE MESSAGES:
                #-----------------------------------------------------------
                self._checkThreadMethod()
                #-----------------------------------------------------------
                response = self.browser.open(request)
                p = response.read()

                
                files = os.listdir('debug')
                if len(files) >= 20: #never allow more than 20 files
                    files.sort()
                    os.remove('debug/'+files[0])
                try: php = '_'+re.findall("/(\w+\.php)",self.lastFetch)[0]
                except IndexError: php = ''
                date = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
                file = open("debug/%s%s.html" %(date,php), 'w')
                
                file.write(p.replace('<script','<noscript').replace('</script>','</noscript>').replace('http-equiv="refresh"','http-equiv="kovan-rulez"'))
                file.close()
                response.seek(0)
                if skipValidityCheck:
                    return response                
                elif self.translations['youAttemptedToLogIn'] in p:         
                    raise BotFatalError("Invalid username and/or password.")
                elif not p or self.translations['concurrentPetitionsError'] in p:
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
            except (urllib2.URLError, httplib.IncompleteRead, httplib.BadStatusLine), e:
                self._eventMgr.connectionError(e)
                valid = False
            if not valid: 
                sleep(5)
        return response
    
    def doLogin(self):
        if self.serverTimeDelta and self.serverTime().hour == 3 and self.serverTime().minute == 0: # don't connect immediately after 3am server reset
            sleep(40)                
        
        page = self._fetchValidResponse(self.webpage)
        form = ParseResponse(page, backwards_compat=False)[0]
        form["Uni"]   = [self.server]
        form["login"] = self.config.username
        form["pass"]  = self.config.password
        form.action = "http://"+self.server+"/game/reg/login2.php"
        page = self._fetchForm(form).read()
        try:
            self.session = re.findall(self.REGEXP_SESSION_STR, page)[0]
        except IndexError:
            raise BotFatalError(page)
        self._eventMgr.loggedIn(self.config.username, self.session)
        self.saveState()

    def getMyPlanets(self):
        page = self._fetchPhp('overview.php').read()
        
        myPlanets = []
        for code, name, galaxy, ss, pos in self.REGEXPS['myPlanets'].findall(page):
            coords = Coords(galaxy, ss, pos)
            for planet in myPlanets:
                if planet.coords == coords: # we found a moon for this planet
                    coords.coordsType = Coords.Types.moon
            planet = OwnPlanet(coords, name, code)
            myPlanets.append(planet)
        
        strTime = self.REGEXPS['serverTime'].findall(page)[0]
        serverTime = parseTime(strTime)
        self.serverTimeDelta = serverTime - datetime.now()
        return myPlanets

    def getSolarSystem(self, galaxy, solarSystem, deuteriumSourcePlanet = None):
        try:
            planets = {}         

            if deuteriumSourcePlanet:
                self._fetchPhp('overview.php', cp=self.deuteriumSourcePlanet.code)
            page = self._fetchPhp('galaxy.php',galaxy=galaxy,system=solarSystem).read()
            html = BeautifulSoup(page)              
            galaxyTable = html.findAll('table', width="569")[0]
            rowCount = 0
            for row in galaxyTable.findAll('tr', recursive=False)[2:16]:
                try:
                    rowCount += 1
                    columns = row.findAll('th')
                    name = str(columns[2].string).strip()
                    name = re.sub(r'&nbsp;.*', '', name) # remove planet idle time from name
                    owner = str(columns[5].a.span.string).strip()
                    ownerStatus = str(columns[5].a.span['class'])
                    if columns[6].a != None: # player has alliance
                        alliance = str(columns[6].a.string).strip()
                    else: alliance = ''
                    # Absolutely ALL EnemyPlanet objects of the bot are created here
                    planet = EnemyPlanet(Coords(galaxy, solarSystem, rowCount), owner, ownerStatus, name, alliance)
                    planets[str(planet.coords)] = planet
                except AttributeError: # no planet in that position
                    continue 
            return planets
        except IndexError:
            raise BotFatalError("Probably there is not enough deuterium.")
        
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
            resources = Resources(m.group('metal').replace('.',''), m.group('crystal').replace('.',''), m.group('deuterium').replace('.',''))

            report = EspionageReport(coords, planetName, date, resources, code)
            
            for i in "fleet", "defense", "buildings", "research":
                dict = None
                match = self.REGEXPS['report'][i].search(rawMessage)
                if match:
                    dict, text = {}, match.group(1)
                    for fullName, cuantity in self.REGEXPS['report']['details'].findall(text):
                        dict[self.translationsByLocalText[fullName.strip()]] = int(cuantity.replace('.',''))
                        
                setattr(report, i, dict)
                
            reports.append(report)
            
        return reports
        
#    def buildShips(self, ships, planet):
#        return 
        #
        # with python 2.4. sgmlib doesnt parse well indexed controls, all of them get the root name, no index. the bug that corrected it in python 2.5 introduced the bug below
        
#        if not ships:
#            return
#        page = self._fetchPhp( 'buildings.php', mode='Flotte', cp=sourceplanet.code )
#        form = ParseResponse( page, backwards_compat=False )[-1]
#        for shipType, cuantity in ships.items():
#            try:
#                controlName = "fmenge[%s]" % INGAME_TYPES_BY_NAME[shipType].code[-3:]
#                form[controlName] = str( cuantity )
#            except ControlNotFoundError:
#                raise BotError( shipType )
#        self._fetchForm( form )
        
    def buildBuildings(self, building, planet):
        self._fetchPhp('b_building.php', bau=building.code, cp=planet.code)
        
    def launchMission(self, mission,abortIfNotEnough = True,slotsToReserve = 0):
        
        # assure cuantities are integers
        for shipType, cuantity in mission.fleet.items(): 
            mission.fleet[shipType] = int(cuantity)
                    
        # 1st step: select fleet
        page = self._fetchPhp('flotten1.php', mode='Flotte', cp=mission.sourcePlanet.code)
        pageText = page.read()

        if self.translations['fleetLimitReached'] in pageText:
            raise NoFreeSlotsError()
        
        if self.getFreeSlots(pageText) <= int(slotsToReserve):
            raise NoFreeSlotsError()
        
        fleet = self.getAvailableFleet(None,pageText)
        
        page.seek(0)            
        form = ParseResponse(page, backwards_compat=False)[-1]        
        
        for shipType, requested in mission.fleet.items():
            available = fleet.get(shipType,0)
            if available == 0 or (abortIfNotEnough and available  < requested):
                raise NotEnoughShipsError('Requested: %s. Available: %s' %({shipType:requested},available))
            
            shipCode = INGAME_TYPES_BY_NAME[shipType].code            
            form[shipCode] = str(cuantity)
            

        # 2nd step: select destination and speed
        page = self._fetchForm(form)
        
        forms = ParseResponse(page, backwards_compat=False)
        if len(forms) == 0 or 'flotten3.php' not in forms[0].action:
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
        form = ParseResponse(page, backwards_compat=False)[0]
        form['order']      = [str(mission.missionType)]
        resources = mission.resources
        form['resource1'] = str(resources.metal)
        form['resource2'] = str(resources.crystal)
        form['resource3'] = str(resources.deuterium)                   
        # 4th and final step: check result
        page = self._fetchForm(form).read()
            
        errors = self.REGEXPS['fleetSendError'].findall(page)
        if len(errors) > 0 or 'class="success"' not in page:
            errors = str(errors)
            if   self.translations['fleetLimitReached2'] in errors:
                raise NoFreeSlotsError()
            elif self.translations['noShipSelected'] in errors:
                raise NotEnoughShipsError('Requested: %s. Available: ?' % mission.fleet)
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
        mission.distance =  int(resultPage[self.translations['distance']].replace('.',''))
        mission.consumption = int(resultPage[self.translations['consumption']].replace('.',''))
            
        # check simulation formulas are working correctly:
        assert mission.distance == mission.sourcePlanet.coords.distanceTo(mission.targetPlanet.coords)
        flightTime = mission.sourcePlanet.coords.flightTimeTo(mission.targetPlanet.coords, int(resultPage[self.translations['speed']].replace('.','')))
        margin = timedelta(seconds = 3)
        assert mission.flightTime > flightTime - margin and mission.flightTime < flightTime + margin
        # check mission was sent as expected:
        assert str(mission.sourcePlanet.coords) in resultPage[self.translations['start']]
        assert str(mission.targetPlanet.coords) in resultPage[self.translations['target']] 
        
        # check the requested fleet was sent intact:
        sentFleet = {}
        for fullName, value in resultPage.items():
            name = self.translationsByLocalText.get(fullName)
            if name is None:
                continue
            if name in INGAME_TYPES_BY_NAME.keys():
                sentFleet[name] = int(value.replace('.',''))

        if mission.fleet != sentFleet:
            warnings.warn("Not all requested fleet was sent. Requested: %s. Sent: %s" % ( mission.fleet, sentFleet))
            mission.fleet = sentFleet
        
    
    def getFreeSlots(self,alreadyFetchedPage = None):
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('flotten1.php', mode='Flotte').read()
        usedSlotsNums = re.findall(r"<th>([0-9]+)</th>", page)

        if len(usedSlotsNums) == 0:
            usedSlots = 0
        else: usedSlots = int(usedSlotsNums[-1])
        maxFleets = int(self.REGEXPS['maxSlots'].search(page).group(1))
        return maxFleets - usedSlots
    
    def getAvailableFleet(self, planet,alreadyFetchedPage = None):    
        page = alreadyFetchedPage
        if not page:
            page = self._fetchPhp('flotten1.php', mode='Flotte', cp=planet.code).read()
        fleet = {}
        for code, cuantity in self.REGEXPS['availableFleet'].findall(page):
            fleet[INGAME_TYPES_BY_CODE[code].name] = int(cuantity.replace('.',''))
        return fleet
    
    def deleteMessage(self, message):
        page = self._fetchPhp('messages.php')
        form = ParseResponse(page, backwards_compat=False)[0]
        checkBoxName = "delmes" + message.code
        try:
            form[checkBoxName]      = [None] # actually this marks the checbox as checked (!!)
            form["deletemessages"] = ["deletemarked"]
        except ControlNotFoundError:
            pass
        self._fetchForm(form)
        
    def getInvestigationLevels(self):
        page = self._fetchPhp('buildings.php', mode='Forschung').read()
        levels = {}
        for fullName, level in self.REGEXPS['techLevels'].findall(page):
            levels[self.translationsByLocalText[fullName]] = level
        return levels

    def saveState(self):
        file = open(FILE_PATHS['webstate'], 'wb')
        cPickle.dump(self.server, file,2)         
        cPickle.dump(self.session, file,2)
        file.close()
        
    def loadState(self):
        try:
            file = open(FILE_PATHS['webstate'], 'rb')
            self.server = cPickle.load(file)            
            self.session = cPickle.load(file)
            file.close()
        except (EOFError, IOError):
            try:
                os.remove(FILE_PATHS['webstate'])              
            except Exception : pass
            return False
        return True   
    



def parseTime(strTime, format = "%a %b %d %H:%M:%S"):# example: Mon Aug 7 21:08:52                        
    ''' parses a time string formatted in OGame's most usual format and 
    converts it to a datetime object'''
    strTime = "%s %s" % (datetime.now().year, strTime)
    format = "%Y " + format
            
    goodLocale = locale.getlocale() 
    locale.setlocale(locale.LC_ALL, 'C')   
    tuple = time.strptime(strTime, format) 
    locale.setlocale(locale.LC_ALL, goodLocale) 
    return datetime(*tuple[0:6])