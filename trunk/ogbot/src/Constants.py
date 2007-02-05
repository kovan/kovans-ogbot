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
from GameEntities import Ship, Defense, Building, Research

FILE_PATHS = {
    'config' : 'config/config.ini', 
    'botstate' :  'botdata/bot.state.dat', 
    'webstate' : 'botdata/webadapter.state.dat', 
    'planetdb' :  'botdata/planets.db', 
    'gamedata' : 'botdata/gamedata.dat',     
    'log' : 'log/ogbot.log', 
}

INGAME_TYPES = [
    Ship('smallCargo', 'ship202', 5000, 20), 
    Ship('largeCargo', 'ship203', 25000, 50), 
    Ship('lightFighter', 'ship204', 50, 20), 
    Ship('heavyFighter', 'ship205', 100, 75), 
    Ship('cruiser', 'ship206', 800, 300), 
    Ship('battleShip', 'ship207', 1500, 500), 
    Ship('colonyShip', 'ship208', 7500, 1000), 
    Ship('recycler', 'ship209', 20000, 300), 
    Ship('espionageProbe', 'ship210', 5, 1), 
    Ship('bomber', 'ship211', 500, 1000), 
    Ship('solarSatellite', 'ship212', 0, 0), 
    Ship('destroyer', 'ship213', 2000, 1000), 
    Ship('deathStar', 'ship214', 1000000, 1), 
    Ship('battlecruiser', 'ship215',750,10000),
    
    Building('metalMine', 1), 
    Building('crystalMine', 2), 
    Building('deuteriumSynthesizer', 3), 
    Building('solarPlant', 4), 
    Building('fusionReactor', 12), 
    Building('roboticsFactory', 14), 
    Building('naniteFactory', 15), 
    Building('shipyard', 21), 
    Building('metalStorage', 22), 
    Building('crystalStorage', 23), 
    Building('deuteriumTank', 24), 
    Building('researchLab', 31), 
    Building('terraformer', 33), 
    Building('allianceDepot', 34), 
    Building('lunarBase', 41), 
    Building('sensorPhalanx', 42), 
    Building('jumpGate', 43), 
    Building('missileSilo', 44), 
    
    Defense('rocketLauncher', 401), 
    Defense('lightLaser', 402), 
    Defense('heavyLaser', 403), 
    Defense('gaussCannon', 404), 
    Defense('ionCannon', 405), 
    Defense('plasmaTurret', 406), 
    Defense('smallShieldDome', 407), 
    Defense('largeShieldDome', 408), 
    Defense('antiBallisticMissile', 502), 
    Defense('interplanetaryMissile', 503), 
    
    Research('espionageTechnology', 106), 
    Research('computerTechnology', 108), 
    Research('weaponsTechnology', 109), 
    Research('shieldingTechnology', 110), 
    Research('armourTechnology', 111), 
    Research('energyTechnology', 113), 
    Research('hyperspaceTechnology', 114), 
    Research('combustionDrive', 115), 
    Research('impulseDrive', 117), 
    Research('hyperspaceDrive', 118), 
    Research('laserTechnology', 120), 
    Research('ionTechnology', 121), 
    Research('plasmaTechnology', 122), 
    Research('intergalacticResearchNetwork', 123), 
    Research('gravitonTechnology', 199), 
]

INGAME_TYPES_BY_NAME = dict([ (type.name, type) for type in INGAME_TYPES  ])
INGAME_TYPES_BY_CODE = dict([ (type.code, type) for type in INGAME_TYPES  ])


