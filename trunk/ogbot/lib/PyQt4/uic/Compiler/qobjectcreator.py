from PyQt4.uic.exceptions import NoSuchWidgetError
import qtproxies

from indenter import write_code

class QObjectProxyCreator(object):
    cwidgets = {}
    def createQObject(self, classname, objectname, ctor_args,
                      is_attribute = True, no_instantiation = False):
        return self[classname](objectname, is_attribute,
                               ctor_args, no_instantiation)
        

    def addCustomWidget(self, classname, baseclass, module):
        write_code("from %s import %s" % (module, classname))
        self.cwidgets[classname] = type(classname, (getattr(qtproxies.QtGui, baseclass),),
                                        {"module":""})

    def getSlot(self, object, slotname):
        return qtproxies.Literal("%s.%s" % (object, slotname))
    
    def __getitem__(self, cls):
        try:
            return self.cwidgets[cls]
        except KeyError:
            try:
                w = getattr(qtproxies.QtGui, cls)
                if issubclass(w, qtproxies.LiteralProxyClass):
                    raise NoSuchWidgetError, cls
                return w
            except AttributeError:
                raise NoSuchWidgetError, cls

