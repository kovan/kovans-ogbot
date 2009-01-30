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
from GameEntities import Ship, Defense, Building, Research

FILE_PATHS = {
    'config' : 'config/config.ini', 
    'botstate' :  'botdata/bot.state.dat', 
    'webstate' : 'botdata/webadapter.state.dat', 
    'planetdb' :  'botdata/planets.db', 
    'gamedata' : 'botdata/gamedata.dat',     
    'newinactives': 'botdata/newinactives.dat',
    'log' : 'log/ogbot.log', 
}

INGAME_TYPES = [
    Ship('smallCargo', 'ship202', 2000, 2000, 0, 5000, 20), 
    Ship('largeCargo', 'ship203', 6000, 6000, 0, 25000, 50), 
    Ship('lightFighter', 'ship204', 3000, 1000, 0, 50, 20), 
    Ship('heavyFighter', 'ship205', 6000, 4000, 0, 100, 75), 
    Ship('cruiser', 'ship206', 20000, 7000, 2000, 800, 300), 
    Ship('battleShip', 'ship207', 45000, 15000, 0,1500, 500), 
    Ship('colonyShip', 'ship208', 10000, 20000, 10000, 7500, 1000), 
    Ship('recycler', 'ship209', 10000, 6000, 2000, 20000, 300), 
    Ship('espionageProbe', 'ship210', 0, 1000, 0, 1, 1), 
    Ship('bomber', 'ship211', 500, 50000, 25000, 15000, 1000), 
    Ship('solarSatellite', 'ship212', 0, 2000, 500, 0, 0), 
    Ship('destroyer', 'ship213', 60000, 50000, 15000, 2000, 1000), 
    Ship('deathStar', 'ship214', 5000000, 4000000, 1000000, 1000000, 1), 
    Ship('battlecruiser', 'ship215', 30000, 40000, 15000, 750, 250),
    
    Building('metalMine', 1, 60, 15, 0), 
    Building('crystalMine', 2, 48, 24, 0), 
    Building('deuteriumSynthesizer', 3, 225, 75, 0), 
    Building('solarPlant', 4, 75, 30, 0), 
    Building('fusionReactor', 12, 900, 360, 180), 
    Building('roboticsFactory', 14, 400, 120, 200), 
    Building('naniteFactory', 15, 1000000, 500000, 100000), 
    Building('shipyard', 21, 400, 200, 100), 
    Building('metalStorage', 22, 2000, 0, 0), 
    Building('crystalStorage', 23, 2000, 1000, 0), 
    Building('deuteriumTank', 24, 2000, 2000, 0), 
    Building('researchLab', 31, 200, 400, 200), 
    Building('terraformer', 33, 0, 50000, 100000), 
    Building('allianceDepot', 34, 20000, 40000, 0), 
    Building('lunarBase', 41, 20000, 40000, 20000), 
    Building('sensorPhalanx', 42, 20000, 40000, 20000), 
    Building('jumpGate', 43, 2000000, 4000000, 2000000), 
    Building('missileSilo', 44, 20000, 20000, 1000), 
    
    Defense('rocketLauncher', 401, 2000, 0, 0), 
    Defense('lightLaser', 402, 1500, 500, 0), 
    Defense('heavyLaser', 403, 6000, 2000, 0), 
    Defense('gaussCannon', 404, 20000, 15000, 2000), 
    Defense('ionCannon', 405, 2000, 6000, 0), 
    Defense('plasmaTurret', 406, 50000, 50000, 30000), 
    Defense('smallShieldDome', 407, 10000, 10000, 0), 
    Defense('largeShieldDome', 408, 50000, 50000, 0), 
    Defense('antiBallisticMissile', 502, 8000, 0, 2000), 
    Defense('interplanetaryMissile', 503, 12500, 2500, 10000), 
    
    Research('espionageTechnology', 106, 200, 1000, 200), 
    Research('computerTechnology', 108, 0, 400, 600), 
    Research('weaponsTechnology', 109, 800, 200, 0), 
    Research('shieldingTechnology', 110, 200, 600, 0), 
    Research('armourTechnology', 111, 1000, 0, 0), 
    Research('energyTechnology', 113, 0, 900, 400), 
    Research('hyperspaceTechnology', 114, 0, 4000, 2000), 
    Research('combustionDrive', 115, 400, 0, 600), 
    Research('impulseDrive', 117, 2000, 4000, 600), 
    Research('hyperspaceDrive', 118, 10000, 20000, 6000), 
    Research('laserTechnology', 120, 200, 100, 0), 
    Research('ionTechnology', 121, 1000, 300, 100), 
    Research('plasmaTechnology', 122, 2000, 4000, 100), 
    Research('intergalacticResearchNetwork', 123, 240000, 400000, 160000), 
    Research('gravitonTechnology', 199, 0, 0, 0),
    Research('expeditionTechnology', 124, 4000, 8000, 4000),
 
]

INGAME_TYPES_BY_NAME = dict([ (type.name, type) for type in INGAME_TYPES  ])
INGAME_TYPES_BY_CODE = dict([ (type.code, type) for type in INGAME_TYPES  ])


