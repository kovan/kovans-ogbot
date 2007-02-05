import qobjectcreator
import logging

from PyQt4 import QtGui, QtCore

from PyQt4.uic import uiparser, properties

DEBUG = logging.debug

class DynamicUILoader(uiparser.UIParser):
    def __init__(self):
        uiparser.UIParser.__init__(self, QtCore, QtGui)
        self.wdb = qobjectcreator.QObjectCreator()
        self.wprops = properties.Properties(self.wdb, QtCore, QtGui)


    def createToplevelWidget(self, classname):
        if self.toplevelInst is not None:
            if not isinstance(self.toplevelInst, self.wdb[classname]):
                raise TypeError, ("Wrong base class of toplevel widget",
                                  (type(self.toplevelInst), self.wdb[classname]))
            return self.toplevelInst
        else:
            return self.wdb.createQObject(classname, self.uiname, ())


    def loadUi(self, filename, toplevelInst = None):
        self.toplevelInst = toplevelInst
        return self.parse(filename)
        
