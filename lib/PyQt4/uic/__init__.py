import time
from cStringIO import StringIO

from PyQt4.QtCore import PYQT_VERSION_STR
from Compiler import indenter, compiler


_header = """# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '%s'
#
# Created: %s
#      by: PyQt4 UI code generator %s
#
# WARNING! All changes made in this file will be lost!

import sys
"""


_display_code = """

if __name__ == "__main__":
\tapp = QtGui.QApplication(sys.argv)
\t%(uiname)s = QtGui.%(baseclass)s()
\tui = %(uiclass)s()
\tui.setupUi(%(uiname)s)
\t%(uiname)s.show()
\tsys.exit(app.exec_())
"""


def compileUi(uifile, pyfile, execute=False, indent=4):
    """compileUi(uifile, pyfile, execute=False, indent=4)

    Creates a Python module from a Qt Designer .ui file.
    
    uifile is a file name or file-like object containing the .ui file.
    pyfile is the file-like object to which the Python code will be written to.
    execute is optionally set to add extra Python code that allows the code to
    be run as a standalone application.  The default is False.
    indent is the optional indentation width using spaces.  If it is 0 then a
    tab is used.  The default is 4.
    """
    try:
        uifname = uifile.name
    except AttributeError:
        uifname = uifile

    indenter.indentwidth = indent

    pyfile.write(_header % (uifname, time.ctime(), PYQT_VERSION_STR))

    winfo = compiler.UICompiler().compileUi(uifile, pyfile)

    if execute:
        indenter.write_code(_display_code % winfo)


def loadUiType(uifile):
    """loadUiType(uifile) -> (form class, base class)

    Load a Qt Designer .ui file and return the generated form class and the Qt
    base class.

    uifile is a file name or file-like object containing the .ui file.
    """
    from PyQt4 import QtGui

    code_string = StringIO()
    winfo = compiler.UICompiler().compileUi(uifile, code_string)

    ui_globals = {}
    exec code_string.getvalue() in ui_globals

    return (ui_globals[winfo["uiclass"]], getattr(QtGui, winfo["baseclass"]))


def loadUi(uifile, baseinstance=None):
    """loadUi(uifile, baseinstance=None) -> widget

    Load a Qt Designer .ui file and return an instance of the user interface.

    uifile is a file name or file-like object containing the .ui file.
    baseinstance is an optional instance of the Qt base class.  If specified
    then the user interface is created in it.  Otherwise a new instance of the
    base class is automatically created.
    """
    from Loader import loader

    return loader.DynamicUILoader().loadUi(uifile, baseinstance)
