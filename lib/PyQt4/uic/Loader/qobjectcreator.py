from PyQt4.uic.exceptions import NoSuchWidgetError
from PyQt4 import QtGui

class QObjectCreator(object):
    def __init__(self):
        self.widgets = {}
        
    def createQObject(self, classname, objectname, ctor_args, is_attribute = True):
        return self[classname](*ctor_args)


    def addCustomWidget(self, classname, baseclass, module):
        import sys # for now!
        sys.path.append(".")
        self.widgets[classname] = getattr(__import__(module, {}, {}, (classname,)),
                                          classname)

    def getSlot(self, object, slotname):
        return getattr(object, slotname)
    
    def __getitem__(self, cls):
        try:
            return getattr(QtGui, cls)
        except AttributeError:
            try:
                return self.widgets[cls]
            except KeyError:
                raise NoSuchWidgetError, cls
