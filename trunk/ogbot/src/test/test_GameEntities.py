#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#     Kovan's OGBot
#     Copyright (c) 2006 by kovan 
#
#     *************************************************************************
#     *                                                                       *
#     * This program is free software; you can redistribute it and/or modify  *
#     * it under the terms of the GNU General Public License as published by  *
#     * the Free Software Foundation; either version 2 of the License, or     *
#     * (at your option) any later version.                                   *
#     *                                                                       *
#     *************************************************************************
#

import unittest
from GameEntities import *

class CoordsTest(unittest.TestCase):
    def setUp(self):
        self.coords = Coords('1:2:3',planetType=Coords.Types.moon)
    def testParsing(self):
        self.coords.parse('  4:5:6]  ')
        self.assertEqual(self.coords.tuple(),Coords(4,5,6).tuple())
    def testEquality(self):
        self.assertEqual(self.coords,Coords(1,2,3,Coords.Types.moon))
        




if __name__ == '__main__':
    unittest.main()