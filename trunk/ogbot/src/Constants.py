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
    'planets' : 'botdata/simulations.dat', 
    'log' : 'log/ogbot.log', 
}

INGAME_TYPES = [
    Ship('smallCargo', _('Nave pequeña de carga'), 'ship202', 5000, 20), 
    Ship('largeCargo', _('Nave grande de carga'), 'ship203', 25000, 50), 
    Ship('lightFighter', _('Cazador ligero'), 'ship204', 50, 20), 
    Ship('heavyFighter', _('Cazador pesado'), 'ship205', 100, 75), 
    Ship('cruiser', _('Crucero'), 'ship206', 800, 300), 
    Ship('battleShip', _('Nave de batalla'), 'ship207', 1500, 500), 
    Ship('colonyShip', _('Colonizador'), 'ship208', 7500, 1000), 
    Ship('recycler', _('Reciclador'), 'ship209', 20000, 300), 
    Ship('espionageProbe', _('Sonda de espionaje'), 'ship210', 5, 1), 
    Ship('bomber', _('Bombardero'), 'ship211', 500, 1000), 
    Ship('solarSatellite', _('Satélite solar'), 'ship212', 0, 0), 
    Ship('destroyer', _('Destructor'), 'ship213', 2000, 1000), 
    Ship('deathStar', _('Estrella de la muerte'), 'ship214', 1000000, 1), 
    
    Building('metalMine', _("Mina de metal"), 1), 
    Building('crystalMine', _("Mina de cristal"), 2), 
    Building('deuteriumSynthesizer', _("Sintetizador de deuterio"), 3), 
    Building('solarPlant', _("Planta de energía solar"), 4), 
    Building('fusionReactor', _("Planta de fusión"), 12), 
    Building('roboticsFactory', _("Fábrica de Robots"), 14), 
    Building('naniteFactory', _("Fábrica de Nanobots"), 15), 
    Building('shipyard', _("Hangar"), 21), 
    Building('metalStorage', _("Almacén de metal"), 22), 
    Building('crystalStorage', _("Almacén de cristal"), 23), 
    Building('deuteriumTank', _("Contenedor de deuterio"), 24), 
    Building('researchLab', _("Laboratorio de investigación"), 31), 
    Building('terraformer', _("Terraformer"), 33), 
    Building('allianceDepot', _("Depósito de la Alianza"), 34), 
    Building('lunarBase', _("Base lunar"), 41), 
    Building('sensorPhalanx', _("Sensor Phalanx"), 42), 
    Building('jumpGate', _("Salto cuántico"), 43), 
    Building('missileSilo', _("Silo"), 44), 
    
    Defense('rocketLauncher', _('Lanzamisiles'), 401), 
    Defense('lightLaser', _('Láser pequeño'), 402), 
    Defense('heavyLaser', _('Láser grande'), 403), 
    Defense('gaussCannon', _('Cañón Gauss'), 404), 
    Defense('ionCannon', _('Cañón iónico'), 405), 
    Defense('plasmaTurret', _('Cañón de plasma'), 406), 
    Defense('smallShieldDome', _('Cúpula pequeña de protección'), 407), 
    Defense('largeShieldDome', _('Cúpula grande de protección'), 408), 
    Defense('antiBallisticMissile', _('Misil de intercepción'), 502), 
    Defense('interplanetaryMissile', _('Misil interplanetario'), 503), 
    
    Research('espionageTechnology', _('Tecnología de espionaje'), 106), 
    Research('computerTechnology', _('Tecnología de computación'), 108), 
    Research('weaponsTechnology', _('Tecnología militar'), 109), 
    Research('shieldingTechnology', _('Tecnología de defensa'), 110), 
    Research('armourTechnology', _('Tecnología de blindaje'), 111), 
    Research('energyTechnology', _('Tecnología de energía'), 113), 
    Research('hyperspaceTechnology', _('Tecnología de hiperespacio'), 114), 
    Research('combustionDrive', _('Motor de combustión'), 115), 
    Research('impulseDrive', _('Motor de impulso'), 117), 
    Research('hyperspaceDrive', _('Propulsor hiperespacial'), 118), 
    Research('laserTechnology', _('Tecnología láser'), 120), 
    Research('ionTechnology', _('Tecnología iónica'), 121), 
    Research('plasmaTechnology', _('Tecnología de plasma'), 122), 
    Research('intergalacticResearchNetwork', _('Red de investigación intergaláctica'), 123), 
    Research('gravitonTechnology', _('Tecnología de gravitón'), 199), 
]

INGAME_TYPES_BY_NAME = dict([ (type.name, type) for type in INGAME_TYPES  ])
INGAME_TYPES_BY_CODE = dict([ (type.code, type) for type in INGAME_TYPES  ])
INGAME_TYPES_BY_FULLNAME = dict([ (type.fullName, type) for type in INGAME_TYPES  ])


