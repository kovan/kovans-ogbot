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
import time
import re
import os
import urllib
import types
import pickle
import urllib2
import types
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

spyReportTmp  = r'%s (?P<planetName>.*?) (?P<coords>\[[0-9:]+\]) \w+ (?P<date>.*?)</td></tr>\n' %  _( "Recursos en" )
spyReportTmp += r'<tr><td>.*?</td><td>(?P<metal>[-0-9]+)</td>\n'
spyReportTmp += r'<td>.*?</td><td>(?P<crystal>[-0-9]+)</td></tr>\n'
spyReportTmp += r'<tr><td>.*?</td><td>(?P<deuterium>[-0-9]+)</td>\n'
spyReportTmp += r'<td>.*?</td><td>(?P<energy>[-0-9]+)</td></tr>'  
spyReportTmp2 = r'<table .*?>%s(.*?)</table>'

REGEXP_COORDS_STR  = r"([1-9]):([0-9]{1,3}):([0-9]{1,2})"
REGEXP_SESSION_STR = r"[0-9A-Fa-f]{12}"

REGEXPS = \
{
    'messages.php': re.compile( r'<input type="checkbox" name="delmes(?P<code>[0-9]+)".*?(?=<input type="checkbox")', re.DOTALL ), 
    'fleetSendError':re.compile( r'<span class="error">(?P<error>.*?)</span>' ), 
    'myPlanets':re.compile( '<option value="/game/overview\.php\?session='+REGEXP_SESSION_STR+'&cp=([0-9]+)&mode=&gid=&messageziel=&re=0" (?:selected)?>(.*?) +\['+REGEXP_COORDS_STR+']</option>' ), 
    'spyReport': 
    {
        'all'  :    re.compile( spyReportTmp, re.LOCALE ), 
        'fleet':    re.compile( spyReportTmp2 % _( "Flotas" )        , re.DOTALL ), 
        'defense':  re.compile( spyReportTmp2 % _( "Defensa" )       , re.DOTALL ), 
        'buildings':re.compile( spyReportTmp2 % _( "Edificios" )    , re.DOTALL ), 
        'research': re.compile( spyReportTmp2 % _( "Investigación" ), re.DOTALL ), 
        'details':  re.compile( r"<td>(?P<type>.*?)</td><td>(?P<cuantity>[-0-9]+)</td>" )
    }, 
    'serverTime':re.compile( r"<th>.*?%s.*?</th>.*?<th.*?>(?P<date>.*?)</th>" % _( "Hora del servidor" ), re.DOTALL ), 
    'availableFleet':re.compile( r'name="max(?P<type>ship[0-9]{3})" value="(?P<cuantity>[-0-9]+)"' ), 
    'maxSlots':re.compile( r"max\. ([0-9]+)" ), 
    'techLevels':re.compile( r">(?P<techName>\w+)</a></a> \(%s (?P<level>\d+)\)" % _( "Nivel" ), re.LOCALE ), 
    'fleetSendResult':re.compile( r"<tr.*?>\s*<th.*?>(?P<name>.*?)</th>\s*<th.*?>(?P<value>.*?)</th>" ), 
}

del( spyReportTmp )
del( spyReportTmp2 )


def parseTime( strTime ):
    strTime2 = "_%s %s_" % ( datetime.now().year, strTime )
    tuple = time.strptime(strTime2, "%Y %a %b %d %H:%M:%S" ) # example: 2006 Mon Aug 7 21:08:52                        
    return datetime( *tuple[0:6] )

class WebAdapter( object ):
    """Encapsulates the details of the communication with the ogame servers. This involves
        HTTP protocol encapsulation and HTML parsing.
    """
    
    class EventManager( BaseEventManager ):
        def __init__( self, gui = None ):
            self.gui = gui

        def connectionError( self, reason ):
            self.logAndPrint( "** CONNECTION ERROR: %s" % reason )
            self.dispatch( "connectionError", reason )              
        def loggedIn( self, username, session ):
            self.logAndPrint( 'Logged in with user %s. Session identifier: %s' % ( username, session ) )
            self.dispatch( "loggedIn", username, session )
            
    def __init__( self, config, onQueueCheckCallback, gui = None ):
        self.server = ''
        self.browser = Browser()
        self.config = config
        self._onQueueCheckCallback = onQueueCheckCallback
        self._eventMgr = WebAdapter.EventManager( gui )
                
        self.browser.set_handle_refresh( True, 0, False ) # HTTPRefreshProcessor(0,False)         
        self.browser.set_handle_robots( False ) # do not obey website's anti-bot indications
        self.browser.addheaders = [( 'User-agent', 'Mozilla/5.0' )] # self-identify as Mozilla
        self.webpage = "http://"+ config.webpage +"/portal/?frameset=1"
        
        if not self.loadState():
            self.session = '000000000000'
        
        # retrieve server based on universe number
        page = self._fetchValidResponse( self.webpage )
        form = ParseResponse( page, backwards_compat=False )[0]
        select = form.find_control( name = "Uni" )
        self.server = select.get( label = self.config.universe +'. '+ _( "Universo" ), nr=0 ).name
        
        # retrieve and store galaxy fetching form
        page = self._fetchPhp( 'galaxy.php' )
        form = ParseResponse( page, backwards_compat=False )[0]
        self.galaxyForm = form         
        
    def setSession( self, value ):
        self._session = value
        self.saveState()
    def getSession( self ): 
        return self._session
    session = property( getSession, setSession )    
    
    def getControlUrl( self ):
        return "http://%s/game/index.php?session=%s" % ( self.server, self.session )

            
    def _fetchPhp( self, php, **params ):
        params['session'] = self.session
        url = "http://%s/game/%s?%s" % ( self.server, php, urllib.urlencode( params ) )
        print >>sys.stderr , "         Fetching %s" % url
        return self._fetchValidResponse( url )
    
    def _fetchForm( self, form ):
        print >>sys.stderr, "         Fetching %s" % form
        return self._fetchValidResponse( form.click() )
    
    def _fetchValidResponse( self, request ):
        

        valid = False
        while not valid:
            valid = True
            try:
                # MAIN PLACE TO CHECK CHECK FOR INTER-THREAD QUEUE MESSAGES:
                #-----------------------------------------------------------
                # self._onQueueCheckCallback()
                #-----------------------------------------------------------
                                
                response = self.browser.open( request )
                p = response.read()
                response.seek( 0 )
                if "<title>%s</title>" % _( "Página de errores OGame" ) in p:
                    if "Esta cuenta no existe" in p:                 
                        raise BotFatalError( "Invalid username and/or password." )
                    valid = False
                if _( "Problema de base de datos" ) in p or _( "Hasta la  próxima!" ) in p or "Grund 5" in p:
                    oldSession = self.session
                    self.doLogin()
                    if   isinstance( request, str ):
                        request = request.replace( oldSession, self.session )
                    elif isinstance( request, HTMLForm ):
                        request.action = request.action.replace( REGEXP_SESSION_STR, self.session )
                        request['session'] = self.session
                    elif isinstance( request, urllib2.Request ) or isinstance( request, types.InstanceType ): # check for new style object and old style too, 
                        for attrName in dir( request ):
                            attr = getattr( request, attrName )
                            if isinstance( attr, str ):
                                newValue = re.sub( oldSession, self.session, attr )  
                                setattr( request, attr, newValue )
                    else: raise BotError( request )
                    valid = False
            except ( urllib2.URLError, httplib.IncompleteRead ), e:
                self._eventMgr.connectionError( e )
                valid = False
            if not valid: 
                sleep( 5 )
        return response
    
    def doLogin( self ):
        
        page = self._fetchValidResponse( self.webpage )
        form = ParseResponse( page, backwards_compat=False )[0]
        form["Uni"]   = [self.server]
        form["login"] = self.config.username
        form["pass"]  = self.config.password
        form.action = "http://"+self.server+"/game/reg/login2.php"
        page = self._fetchForm( form ).read()
        self.session = re.findall( REGEXP_SESSION_STR, page )[0]
        self._eventMgr.loggedIn( self.config.username, self.session )

    def getMyPlanetsAndServerTime( self ):
        page = self._fetchPhp( 'overview.php' ).read()
        
        myPlanets = []
        for code, name, galaxy, ss, pos in REGEXPS['myPlanets'].findall( page ):
            planet = OwnPlanet( Coords( galaxy, ss, pos ), name, code )
            myPlanets.append( planet )
        myPlanets[0].isMainPlanet = True
        
        strTime = REGEXPS['serverTime'].findall( page )[0]
        serverTime = parseTime( strTime )
        return myPlanets, serverTime

    def getSolarSystem( self, galaxy, solarSystem, deuteriumSourcePlanet = None ):
        try:
            planets = {}         
            self.galaxyForm['galaxy'] = str( galaxy )
            self.galaxyForm['system'] = str( solarSystem )
            if deuteriumSourcePlanet:
                self._fetchPhp( 'overview.php', cp=self.deuteriumSourcePlanet.code )
            page = self._fetchForm( self.galaxyForm ).read()
            html = BeautifulSoup( page )              
            galaxyTable = html.findAll( 'table', width="569" )[0]
            rowCount = 0
            for row in galaxyTable.findAll( 'tr', recursive=False )[2:16]:
                try:
                    rowCount += 1
                    columns = row.findAll( 'th' )
                    name = str( columns[2].string ).strip()
                    name = re.sub( r'&nbsp;.*', '', name ) # remove planet idle time from name
                    owner = str( columns[5].a.span.string ).strip()
                    ownerStatus = str( columns[5].a.span['class'] )
                    if columns[6].a != None: # player has alliance
                        alliance = str( columns[6].a.string ).strip()
                    else: alliance = ''
                    # Absolutely ALL EnemyPlanet objects of the bot are created here
                    planet = EnemyPlanet( Coords( galaxy, solarSystem, rowCount ), owner, ownerStatus, name, alliance )
                    planets[str( planet.coords )] = planet
                except AttributeError: # no planet in that position
                    continue 
            return planets
        except IndexError:
            raise BotFatalError( "Probably there is not enough deuterium to navigate through galaxies" )
        
    def getSpyReports( self ):
        page = self._fetchPhp( 'messages.php' ).read()
        rawMessages = {}
        for match in REGEXPS['messages.php'].finditer( page ):
            rawMessages[match.group( 'code' )] = match.group( 0 ) 
            
        reports = []              
        for code, rawMessage in rawMessages.items():
            if 'class="espionagereport"' not in rawMessage:
                continue
            
            m = REGEXPS['spyReport']['all'].search( rawMessage )
            if m == None: #theorically should never happen
                continue
            planetName = m.group( 'planetName' )
            coords = Coords( m.group( 'coords' ) )
            datestring = "%s-%s" % ( datetime.now().year, m.group( 'date' ) )
            date = datetime( *time.strptime( datestring, "%Y-%m-%d %H:%M:%S" )[0:6] )
            resources = Resources( m.group( 'metal' ), m.group( 'crystal' ), m.group( 'deuterium' ) )

            spyReport = SpyReport( coords, planetName, date, resources, code )
            
            for i in "fleet", "defense", "buildings", "research":
                dict = None
                match = REGEXPS['spyReport'][i].search( rawMessage )
                if match:
                    dict = {}
                    for fullName, cuantity in REGEXPS['spyReport']['details'].findall( match.group( 1 ) ):
                        dict[INGAME_TYPES_BY_FULLNAME[fullName].name] = int( cuantity )
                        
                setattr( spyReport, i, dict )
                
            reports.append( spyReport )
            
        return reports
        
    def buildShips( self, ships, planet):
        return 
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
        
    def buildBuildings( self, building, planet ):
        self._fetchPhp( 'b_building.php', bau=building.code, cp=planet.code )
        
    def launchMission( self, mission ):
        
        # assure cuantities are integers
        for shipType, cuantity in mission.fleet.items(): 
            mission.fleet[shipType] = int( cuantity )
                    
        # 1st step: select fleet
        page = self._fetchPhp( 'flotten1.php', mode='Flotte', cp=mission.sourcePlanet.code )
        if _( "Se ha alcanzado el máximo de flotas" ) in page.read():
            raise NoFreeSlotsError()
        page.seek( 0 )
        form = ParseResponse( page, backwards_compat=False )[-1]
        for shipType, cuantity in mission.fleet.items():
            shipCode = INGAME_TYPES_BY_NAME[shipType].code
            try:
                form[shipCode] = str( cuantity )
            except ControlNotFoundError:
                raise NotEnoughShipsError( shipType )

        # 2nd step: select destination and speed
        page = self._fetchForm( form )
        
        forms = ParseResponse( page, backwards_compat=False )
        if len( forms ) == 0 or 'flotten3.php' not in forms[0].action:
            raise NoFreeSlotsError()
        form = forms[0]
        destCoords = mission.targetPlanet.coords         
        form['galaxy']    = str( destCoords.galaxy )
        form['system']    = str( destCoords.solarSystem )
        form['planet']    = str( destCoords.planet )
        form['planettype']= [str( destCoords.planetType )]
        form['speed']      = [str( mission.speedPercentage / 10 )]
        # 3rd step:  select mission and resources to carry
        page = self._fetchForm( form )
        form = ParseResponse( page, backwards_compat=False )[0]
        form['order']      = [str( mission.missionType )]
        resources = mission.resources
        form['resource1'] = str( resources.metal )
        form['resource2'] = str( resources.crystal )
        form['resource3'] = str( resources.deuterium )                   
        # 4th and final step: check result
        page = self._fetchForm( form ).read()
            
        errors = REGEXPS['fleetSendError'].findall( page )
        if len( errors ) > 0 or 'class="success"' not in page:
            if   _( "Se ha alcanzado el número máximo de flotas" ) in errors:
                raise NoFreeSlotsError()
            elif _( "No seleccionaste ninguna nave" ) in errors:
                raise NotEnoughShipsError()
            else: 
                raise FleetSendError( errors )

        resultPage = {}
        for type, value in REGEXPS['fleetSendResult'].findall( page ):
            resultPage[type] = value
        if __debug__ and not resultPage:
            open( 'debug.txt', 'a' ).write( page )              
            assert False
        # fill remaining mission fields
        arrivalTime = parseTime( resultPage[_( "Hora de llegada" )] )
        returnTime = parseTime( resultPage[_( "Hora de vuelta" )] )
        mission.flightTime = returnTime - arrivalTime
        mission.launchTime = arrivalTime - mission.flightTime
        mission.distance =  int( resultPage[_( "Distancia" )] )
        mission.consumption = int( resultPage[_( "Consumo" )] )
            
        # check simulation formulas are working correctly:
        assert mission.distance == mission.sourcePlanet.coords.distanceTo( mission.targetPlanet.coords )
        flightTime = mission.sourcePlanet.coords.flightTimeTo( mission.targetPlanet.coords, int( resultPage[_( "Velocidad" )] ) )
        margin = timedelta( seconds = 3 )
        assert mission.flightTime > flightTime - margin and mission.flightTime < flightTime + margin
        # check mission was sent as expected:
        assert resultPage[_( "Comienzo" )] == str( mission.sourcePlanet.coords )
        assert resultPage[_( "Objetivo" )] == str( mission.targetPlanet.coords )            
        
        # check the requested fleet was sent intact:
        sentFleet = {}
        for name, value in resultPage.items():
            if name in INGAME_TYPES_BY_FULLNAME.keys():
                sentFleet[INGAME_TYPES_BY_FULLNAME[name].name] = int( value )

        if mission.fleet != sentFleet:
            warnings.warn( "Not all requested fleet was sent. Requested: %s. Sent: %s", mission.fleet, sentFleet )
            mission.fleet = sentFleet
        
    
    def getFreeSlots( self ):
        page = self._fetchPhp( 'flotten1.php', mode='Flotte' ).read()
        usedSlotsNums = re.findall( r"<th>([0-9]+)</th>", page )

        if len( usedSlotsNums ) == 0:
            usedSlots = 0
        else: usedSlots = int( usedSlotsNums[-1] )
        maxFleets = int( REGEXPS['maxSlots'].search( page ).group( 1 ) )
        return maxFleets - usedSlots
    
    def getAvailableFleet( self, planet):    
        page = self._fetchPhp( 'flotten1.php', mode='Flotte', cp=planet.code ).read()
        fleet = {}
        for code, cuantity in REGEXPS['availableFleet'].findall( page ):
            fleet[INGAME_TYPES_BY_CODE[code].name] = int( cuantity )
        return fleet
    
    def deleteMessage( self, message ):
        page = self._fetchPhp( 'messages.php' )
        form = ParseResponse( page, backwards_compat=False )[0]
        checkBoxName = "delmes" + message.code
        try:
            form[checkBoxName]      = [None] # actually this marks the checbox as checked (!!)
            form["deletemessages"] = ["deletemarked"]
        except ControlNotFoundError:
            pass
        self._fetchForm( form )
        
    def getInvestigationLevels( self ):
        page = self._fetchPhp( 'buildings.php', mode='Forschung' ).read()
        levels = {}
        for fullName, level in REGEXPS['techLevels'].findall( page ):
            levels[INGAME_TYPES_BY_FULLNAME[fullName].name] = level
        return levels

    def saveState( self ):
        file = open( FILE_PATHS['webstate'], 'w' )
        pickle.dump( self.server, file )         
        pickle.dump( self.session, file )
        file.close()
        
    def loadState( self ):
        try:
            file = open( FILE_PATHS['webstate'], 'r' )
            self.server = pickle.load( file )            
            self.session = pickle.load( file )
            file.close()
        except ( EOFError, IOError ):
            try:
                os.remove( FILE_PATHS['webstate'] )              
            except Exception : pass
            return False
        return True   
    
