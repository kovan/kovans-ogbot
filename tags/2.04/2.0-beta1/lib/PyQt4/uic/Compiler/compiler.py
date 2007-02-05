import sys

from proxyproperties import ProxyProperties
from qobjectcreator import QObjectProxyCreator
import qtproxies

from indenter import createCodeIndenter, getIndenter, write_code

from PyQt4.uic import uiparser


class UICompiler(uiparser.UIParser):
    def __init__(self):
        uiparser.UIParser.__init__(self, qtproxies.QtCore, qtproxies.QtGui)
        
        self.wdb = QObjectProxyCreator()
        self.wprops = ProxyProperties(self.wdb)


    def reset(self):
        qtproxies.i18n_strings = []
        uiparser.UIParser.reset(self)


    def setContext(self, context):
        qtproxies.i18n_context = context

        
    def createToplevelWidget(self, classname):
        indenter = getIndenter()
        indenter.level = 0
        indenter.write("from PyQt4 import QtCore, QtGui\n\n")
        indenter.write("class Ui_%s(object):\n" % self.uiname)
        indenter.indent()
        indenter.write("def setupUi(self, %s):" % self.uiname)
        indenter.indent()
        w = self.wdb.createQObject(classname, self.uiname, (),
                                   is_attribute = False,
                                   no_instantiation = True)
        w.uiname = self.uiname
        w.baseclass = classname
        w.uiclass = "Ui_%s" % self.uiname
        return w

            
    def setDelayedProps(self):
        write_code("\nself.retranslateUi(%s)\n" % self.uiname)
        uiparser.UIParser.setDelayedProps(self)


    def finalize(self):
        indenter = getIndenter()
        indenter.level = 1
        indenter.write("""
def retranslateUi(self, %s):
""" % self.uiname)
        indenter.indent()
        indenter.write("\n".join(qtproxies.i18n_strings))
        indenter.dedent()
        indenter.dedent()


    def compileUi(self, input_stream, output_stream):
        createCodeIndenter(output_stream)
        w = self.parse(input_stream)
        return {"uiname": w.uiname,
                "uiclass" : w.uiclass,
                "baseclass" : w.baseclass}
