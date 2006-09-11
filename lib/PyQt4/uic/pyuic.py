#!/usr/bin/env python

import sys
import optparse
import logging

from PyQt4 import QtCore, uic


Version = "Python User Interface Compiler %s for Qt version %s" % (QtCore.PYQT_VERSION_STR, QtCore.QT_VERSION_STR)


def previewUi(uifname):
    from PyQt4 import QtGui

    app = QtGui.QApplication([uifname])
    widget = uic.loadUi(uifname)
    widget.show()
    return app.exec_()


def generateUi(uifname, pyfname, execute, indent):
    if pyfname == "-":
        pyfile = sys.stdout
    else:
        pyfile = file(pyfname, "w")

    uic.compileUi(uifname, pyfile, execute, indent)
    return 0


optparser = optparse.OptionParser(usage="pyuic4 [options] <ui-file>",
                                  version=Version)
optparser.add_option("-p", "--preview", dest="preview",
                     action="store_true", default=False,
                     help="show a preview of the UI instead of generating code")
optparser.add_option("-o", "--output", dest="output",
                     default="-", metavar="FILE",
                     help="write generated code to FILE instead of stdout")
optparser.add_option("-x", "--execute", dest="execute",
                     action="store_true", default=False,
                     help="generate extra code to test and display the class")
optparser.add_option("-d", "--debug", dest="debug",
                     action="store_true", default=False,
                     help="show debug output")
optparser.add_option("-i", "--indent", dest="indent",
                     action="store", type="int", default=4, metavar="N",
                     help="set indent width to N spaces, tab if N is 0 (default: 4)")

options, args = optparser.parse_args(sys.argv)

if len(args) != 2:
    print "Error: one input ui-file must be specified"
    sys.exit(1)


if options.debug:
    logging.getLogger().setLevel(logging.DEBUG)

error = 1
try:
    if options.preview:
        error = previewUi(args[1])
    else:
        error = generateUi(args[1], options.output, options.execute, options.indent)
except IOError, e:
    sys.stderr.write("Error: %s: \"%s\"\n" % (e.strerror, e.filename))

except SyntaxError, e:
    sys.stderr.write("Error in input file: %s\n" % (e,))

except uic.exceptions.NoSuchWidgetError, e:
    if e.args[0].startswith("Q3"):
        sys.stderr.write("Error: Q3Support widgets are not supported by PyQt4.\n")
    else:
        sys.stderr.write(e)

except Exception, e:
    if logging.getLogger().level == logging.DEBUG:
        import traceback
        traceback.print_exception(*sys.exc_info())
    else:
        sys.stderr.write("""An unexpected error occurred.
Please send an error report to support@riverbankcomputing.co.uk and include the following data:
  * your version of PyQt4 (%s)
  * the UI file that caused this error
  * the debug output of pyuic4 (use the -d flag when calling pyuic4)
""" % QtCore.PYQT_VERSION_STR)

sys.exit(error)
