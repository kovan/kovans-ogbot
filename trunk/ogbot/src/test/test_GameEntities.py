#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2006 by kovan 
#
#      *************************************************************************
#      *                                                                         *
#      * This program is free software; you can redistribute it and/or modify  *
#      * it under the terms of the GNU General Public License as published by  *
#      * the Free Software Foundation; either version 2 of the License, or      *
#      * (at your option) any later version.                                      *
#      *                                                                         *
#      *************************************************************************
#

import unittest
from GameEntities import *
from  datetime import datetime, timedelta


class CoordsTest(unittest.TestCase):
    def setUp(self):
         self.coords = Coords('1:2:3',planetType=Coords.Types.moon)
    def testParsing(self):
         self.coords.parse('  4:5:6]  ')
         self.assertEqual(self.coords.tuple(),Coords(4,5,6).tuple())
    def testEquality(self):
         self.assertEqual(self.coords,Coords(1,2,3,Coords.Types.moon))
         self.assertNotEqual(self.coords,Coords(4,5,6,Coords.Types.moon))
    def testDistance(self):
         self.assertEqual(1040,Coords(2,250,6).distanceTo(Coords(2,250,14))) # same solar system, different planet
         self.assertEqual(2890,Coords(2,250,6).distanceTo(Coords(2,248,14))) # same galaxy, different solar system
         self.assertEqual(40000,Coords(2,250,6).distanceTo(Coords(4,1,1))) # different galaxy
         
class ResourcesTest(unittest.TestCase):    
    def setUp(self):
         self.resources = Resources(1000,1000,1000)
    def testEquality(self):
         self.assertEqual(self.resources,Resources(1000,1000,1000))
         self.assertNotEqual(self.resources,Resources(10,20,30))
    def testMEU(self):
         self.assertEqual(self.resources.metalEquivalent(),5500)
    def testAddAndSub(self):
         self.assertEqual(self.resources,Resources(300,400,500) + Resources(700,600,500))
         self.assertEqual(self.resources,Resources(1500,1400,1300) - Resources(500,400,300))
         
class SpyReportTest(unittest.TestCase):    
    def setUp(self):
         self.report = SpyReport(Coords(1,1,1), 'planet', datetime.now(), Resources(), 0)
    
    def testHasSomething(self):
         self.report.fleet = None
         self.assertEqual(self.report.hasFleet(),True)
         self.report.fleet = {}
         self.assertEqual(self.report.hasFleet(),False)       
         self.report.fleet = {'cruiser':1}
         self.assertEqual(self.report.hasFleet(),True)  
         
         self.report.defense = None
         self.assertEqual(self.report.hasDefense(),True)
         self.report.defense = {}
         self.assertEqual(self.report.hasDefense(),False)       
         self.report.defense = {'lightLaser':1}
         self.assertEqual(self.report.hasDefense(),True)  
         
         self.report.defense = None
         self.assertEqual(self.report.hasNonMissileDefense(),True)
         self.report.defense = {}
         self.assertEqual(self.report.hasNonMissileDefense(),False)       
         self.report.defense = {'lightLaser':1}
         self.assertEqual(self.report.hasNonMissileDefense(),True)  
         self.report.defense = {'interplanetaryMissile':1}
         self.assertEqual(self.report.hasNonMissileDefense(),False)
         self.report.defense = {'antiBallisticMissile':1}
         self.assertEqual(self.report.hasNonMissileDefense(),False)
         
    def testResourcesByNow(self):
         now = datetime.now()
         self.report.date = now
         self.report.buildings = {'metalMine':23,'crystalMine':21,'deuteriumSynthesizer':18}
         self.assertEqual(self.report.resourcesByNow(now + timedelta(hours=1)),Resources(6178,3108,1160))

    def testUpdateRentability(self):
         pass
    
if __name__ == '__main__':
    unittest.main()