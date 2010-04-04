#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2010 by kovan 
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
from GameEntities import Ship, Defense, Building, Research, Resources

SUPPORTED_OGAME_VERSION = 1.1

FILE_PATHS = {
    'config'       : 'files/config/config.ini', 
    'botstate'     : 'files/botdata/bot.state.dat', 
    'webstate'     : 'files/botdata/webadapter.state.dat', 
    'planetdb'     : 'files/botdata/planets.db', 
    'gamedata'     : 'files/botdata/gamedata.dat',     
    'newinactives' : 'files/botdata/newinactives.dat',
    'log'          : 'files/log/ogbot.log', 
}

INGAME_TYPES = [
    Building('metalMine'                    , 1   , Resources(60      , 15      , 0))       , 
    Building('crystalMine'                  , 2   , Resources(48      , 24      , 0))       , 
    Building('deuteriumSynthesizer'         , 3   , Resources(225     , 75      , 0))       , 
    Building('solarPlant'                   , 4   , Resources(75      , 30      , 0))       , 
    Building('fusionReactor'                , 12  , Resources(900     , 360     , 180))     , 
    Building('roboticsFactory'              , 14  , Resources(400     , 120     , 200))     , 
    Building('naniteFactory'                , 15  , Resources(1000000 , 500000  , 100000))  , 
    Building('shipyard'                     , 21  , Resources(400     , 200     , 100))     , 
    Building('metalStorage'                 , 22  , Resources(2000    , 0       , 0))       , 
    Building('crystalStorage'               , 23  , Resources(2000    , 1000    , 0))       , 
    Building('deuteriumTank'                , 24  , Resources(2000    , 2000    , 0))       , 
    Building('researchLab'                  , 31  , Resources(200     , 400     , 200))     , 
    Building('terraformer'                  , 33  , Resources(0       , 50000   , 100000))  , 
    Building('allianceDepot'                , 34  , Resources(20000   , 40000   , 0))       , 
    Building('lunarBase'                    , 41  , Resources(20000   , 40000   , 20000))   , 
    Building('sensorPhalanx'                , 42  , Resources(20000   , 40000   , 20000))   , 
    Building('jumpGate'                     , 43  , Resources(2000000 , 4000000 , 2000000)) , 
    Building('missileSilo'                  , 44  , Resources(20000   , 20000   , 1000))    , 
    
    Research('espionageTechnology'          , 106 , Resources(200     , 1000    , 200))     , 
    Research('computerTechnology'           , 108 , Resources(0       , 400     , 600))     , 
    Research('weaponsTechnology'            , 109 , Resources(800     , 200     , 0))       , 
    Research('shieldingTechnology'          , 110 , Resources(200     , 600     , 0))       , 
    Research('armourTechnology'             , 111 , Resources(1000    , 0       , 0))       , 
    Research('energyTechnology'             , 113 , Resources(0       , 900     , 400))     , 
    Research('hyperspaceTechnology'         , 114 , Resources(0       , 4000    , 2000))    , 
    Research('combustionDrive'              , 115 , Resources(400     , 0       , 600))     , 
    Research('impulseDrive'                 , 117 , Resources(2000    , 4000    , 600))     , 
    Research('hyperspaceDrive'              , 118 , Resources(10000   , 20000   , 6000))    , 
    Research('laserTechnology'              , 120 , Resources(200     , 100     , 0))       , 
    Research('ionTechnology'                , 121 , Resources(1000    , 300     , 100))     , 
    Research('plasmaTechnology'             , 122 , Resources(2000    , 4000    , 100))     , 
    Research('intergalacticResearchNetwork' , 123 , Resources(240000  , 400000  , 160000))  , 
    Research('expeditionTechnology'         , 124 , Resources(4000    , 8000    , 4000))    ,
    Research('gravitonTechnology'           , 199 , Resources(0       , 0       , 0))       ,
 
    Ship('smallCargo'                      , 202 , Resources(2000    , 2000    , 0)        , 5000    , 20)   , 
    Ship('largeCargo'                      , 203 , Resources(6000    , 6000    , 0)        , 25000   , 50)   , 
    Ship('lightFighter'                    , 204 , Resources(3000    , 1000    , 0)        , 50      , 20)   , 
    Ship('heavyFighter'                    , 205 , Resources(6000    , 4000    , 0)        , 100     , 75)   , 
    Ship('cruiser'                         , 206 , Resources(20000   , 7000    , 2000)     , 800     , 300)  , 
    Ship('battleShip'                      , 207 , Resources(45000   , 15000   , 0)        , 1500    , 500)  , 
    Ship('colonyShip'                      , 208 , Resources(10000   , 20000   , 10000)    , 7500    , 1000) , 
    Ship('recycler'                        , 209 , Resources(10000   , 6000    , 2000)     , 20000   , 300)  , 
    Ship('espionageProbe'                  , 210 , Resources(0       , 1000    , 0)        , 1       , 1)    , 
    Ship('bomber'                          , 211 , Resources(500     , 50000   , 25000)    , 15000   , 1000) , 
    Ship('solarSatellite'                  , 212 , Resources(0       , 2000    , 500)      , 0       , 0)    , 
    Ship('destroyer'                       , 213 , Resources(60000   , 50000   , 15000)    , 2000    , 1000) , 
    Ship('deathStar'                       , 214 , Resources(5000000 , 4000000 , 1000000)  , 1000000 , 1)    , 
    Ship('battlecruiser'                   , 215 , Resources(30000   , 40000   , 15000)    , 750     , 250)  ,

    Defense('rocketLauncher'                , 401 , Resources(2000    , 0       , 0))       , 
    Defense('lightLaser'                    , 402 , Resources(1500    , 500     , 0))       , 
    Defense('heavyLaser'                    , 403 , Resources(6000    , 2000    , 0))       , 
    Defense('gaussCannon'                   , 404 , Resources(20000   , 15000   , 2000))    , 
    Defense('ionCannon'                     , 405 , Resources(2000    , 6000    , 0))       , 
    Defense('plasmaTurret'                  , 406 , Resources(50000   , 50000   , 30000))   , 
    Defense('smallShieldDome'               , 407 , Resources(10000   , 10000   , 0))       , 
    Defense('largeShieldDome'               , 408 , Resources(50000   , 50000   , 0))       , 
    Defense('antiBallisticMissile'          , 502 , Resources(8000    , 0       , 2000))    , 
    Defense('interplanetaryMissile'         , 503 , Resources(12500   , 2500    , 10000))   , 
    
]

INGAME_TYPES_BY_NAME = dict([ (t.name, t) for t in INGAME_TYPES  ])
INGAME_TYPES_BY_CODE = dict([ (t.code, t) for t in INGAME_TYPES  ])


