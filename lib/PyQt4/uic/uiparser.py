import sys
import logging
import re
from itertools import count

try:
    from cElementTree import parse
except ImportError:
    try:
        from elementtree.ElementTree import parse
    except ImportError:
        from PyQt4.elementtree.ElementTree import parse
        

from exceptions import NoSuchWidgetError

if sys.version_info < (2,4,0):
    def reversed(seq):
        for i in xrange(len(seq)-1, -1, -1):
            yield seq[i]

DEBUG = logging.debug

QtCore = None
QtGui = None


def gridPosition(elem):
    """gridPosition(elem) -> tuple

    Return the 4-tuple of (row, column, rowspan, colspan)
    for a widget element, or an empty tuple.
    """
    try:
        return (int(elem.attrib["row"]),
                int(elem.attrib["column"]),
                int(elem.attrib.get("rowspan", 1)),
                int(elem.attrib.get("colspan", 1)))
    except KeyError:
        return ()


class WidgetStack(list):
    topwidget = None
    def push(self, item):
        DEBUG("push %s %s" % (item.metaObject().className(),
                              item.objectName()))
        self.append(item)
        if isinstance(item, QtGui.QWidget):
            self.topwidget = item


    def popLayout(self):
        layout = list.pop(self)
        DEBUG("pop layout %s %s" % (layout.metaObject().className(),
                                    layout.objectName()))
        return layout


    def popWidget(self):
        widget = list.pop(self)
        DEBUG("pop widget %s %s" % (widget.metaObject().className(),
                                    widget.objectName()))
        for item in reversed(self):
            if isinstance(item, QtGui.QWidget):
                self.topwidget = item
                break
        else:
            self.topwidget = None
        DEBUG("new topwidget %s" % (self.topwidget,))
        return widget


    def peek(self):
        return self[-1]
    

    def topIsLayout(self):
        return isinstance(self[-1], QtGui.QLayout)


class UIParser(object):    
    def __init__(self, QtCoreModule, QtGuiModule):
        self.reset()
        global QtCore, QtGui
        QtCore = QtCoreModule
        QtGui = QtGuiModule

    def uniqueName(self, name):
        """UIParser.uniqueName(string) -> string

        Create a unique name from a string.
        >>> p = UIParser(QtCore, QtGui)
        >>> p.uniqueName("foo")
        'foo'
        >>> p.uniqueName("foo")
        'foo1'
        """
        try:
            return "%s%i" % (name, self.name_suffixes[name].next(),)
        except KeyError:
            self.name_suffixes[name] = count(1)
            return name


    def reset(self):
        try: self.wprops.reset()
        except AttributeError: pass
        self.toplevelWidget = None
        self.stack = WidgetStack()
        self.name_suffixes = {}
        self.defaults = {"spacing": 6, "margin": 0}
        self.actions = []
        

    def setupObject(self, clsname, parent, branch, is_attribute = True):
        name = self.uniqueName(branch.attrib["name"] or clsname[1:].lower())
        if parent is None:
            args = ()
        else:
            args = (parent, )
        obj =  self.wdb.createQObject(clsname, name, args, is_attribute)
        self.wprops.setProperties(obj, branch)
        obj.setObjectName(name)
        if is_attribute:
            setattr(self.toplevelWidget, name, obj)
        return obj

    
    def createWidget(self, elem):
        def widgetClass(elem):
            cls = elem.attrib["class"]
            if cls == "Line":
                return "QFrame"
            else:
                return cls
            
        self.column_counter = 0
        self.row_counter = 0
        self.first_item = True
        
        parent = self.stack.topwidget
        if isinstance(parent, (QtGui.QToolBox, QtGui.QTabWidget,
                               QtGui.QStackedWidget)):
            parent = None
        
        
        self.stack.push(self.setupObject(widgetClass(elem), parent, elem))

        if isinstance(self.stack.topwidget, QtGui.QTableWidget):
            self.stack.topwidget.clear()
            self.stack.topwidget.setColumnCount(len(elem.findall("column")))
            self.stack.topwidget.setRowCount(len(elem.findall("row")))

        self.traverseWidgetTree(elem)
        widget = self.stack.popWidget()
        
        if self.stack.topIsLayout():
            self.stack.peek().addWidget(widget, *elem.attrib["grid-position"])

            
        if isinstance(self.stack.topwidget, QtGui.QToolBox):
            self.stack.topwidget.addItem(widget, self.wprops.getAttribute(elem, "label"))
        elif isinstance(self.stack.topwidget, QtGui.QTabWidget):
            self.stack.topwidget.addTab(widget, self.wprops.getAttribute(elem, "title"))
        elif isinstance(self.stack.topwidget, QtGui.QStackedWidget):
            self.stack.topwidget.addWidget(widget)
        elif isinstance(self.stack.topwidget, QtGui.QDockWidget):
            self.stack.topwidget.setWidget(widget)
        elif isinstance(self.stack.topwidget, QtGui.QMainWindow):
            if type(widget) == QtGui.QWidget:
                self.stack.topwidget.setCentralWidget(widget)
            elif isinstance(widget, QtGui.QToolBar):
                self.stack.topwidget.addToolBar(widget)
            elif isinstance(widget, QtGui.QMenuBar):
                self.stack.topwidget.setMenuBar(widget)
            elif isinstance(widget, QtGui.QStatusBar):
                self.stack.topwidget.setStatusBar(widget)
            elif isinstance(widget, QtGui.QDockWidget):
                dwArea = self.wprops.getAttribute(elem, "dockWidgetArea")
                self.stack.topwidget.addDockWidget(
                    QtCore.Qt.DockWidgetArea(dwArea), widget)


    def createSpacer(self, elem):
        width = int(elem.findtext("property/size/width"))
        height = int(elem.findtext("property/size/height"))
        sizeType = self.wprops.getProperty(elem, "sizeType")
        if sizeType is None:
            sizeType = "QSizePolicy::Expanding"
        policy = (QtGui.QSizePolicy.Minimum,
                  getattr(QtGui.QSizePolicy, sizeType.split("::")[-1]))
        if self.wprops.getProperty(elem, "orientation") == "Qt::Horizontal":
            policy = policy[1], policy[0]
        spacer = self.wdb.createQObject("QSpacerItem", self.uniqueName("spacerItem"),
                                       (width, height) + policy,
                                        is_attribute = False)
        if self.stack.topIsLayout():
            self.stack.peek().addItem(spacer, *elem.attrib["grid-position"])


    def createLayout(self, elem):
        classname = elem.attrib["class"]
        if self.stack.topIsLayout():
            parent = None
        else:
            parent = self.stack.topwidget
        elem.attrib["name"] = classname[1:].lower()
        self.stack.push(self.setupObject(classname, parent, elem))
        self.traverseWidgetTree(elem)
        layout = self.stack.popLayout()
        if self.stack.topIsLayout():
            self.stack.peek().addLayout(layout, *elem.attrib["grid-position"])


    def handleItem(self, elem):
        if self.stack.topIsLayout():
            elem[0].attrib["grid-position"] = gridPosition(elem)
            self.traverseWidgetTree(elem)
        else:
            w = self.stack.topwidget
            if isinstance(w, QtGui.QComboBox):
                icon = self.wprops.getProperty(elem, "icon")
                if icon:
                    w.addItem(icon, self.wprops.getProperty(elem, "text"))
                else:
                    w.addItem(self.wprops.getProperty(elem, "text"))
            elif isinstance(w, QtGui.QListWidget):
                if self.first_item:
                    w.clear()
                    self.first_item = False
                item = self.wdb.createQObject("QListWidgetItem",
                                              self.uniqueName("item"),
                                              (w,), False)
                self.wprops.setProperties(item, elem)
            elif isinstance(w, QtGui.QTreeWidget):
                if self.first_item:
                    w.clear()
                    self.first_item = False
                    self.itemstack = [w]
                item = self.wdb.createQObject("QTreeWidgetItem",
                                              self.uniqueName("item"),
                                              (self.itemstack[-1],), False)
                column = -1
                for prop in elem.findall("property"):
                    if prop.attrib["name"] == "text":
                        column += 1
                        item.setText(column, self.wprops.convert(prop))
                    else:
                        item.setIcon(column, self.wprops.convert(prop))
                self.itemstack.append(item)
                self.traverseWidgetTree(elem)
                self.itemstack.pop()
            elif isinstance(w, QtGui.QTableWidget):
                item = self.wdb.createQObject("QTableWidgetItem",
                                              self.uniqueName("item"),
                                              (), False)
                self.wprops.setProperties(item, elem)
                w.setItem(int(elem.attrib["row"]), int(elem.attrib["column"]), item)
                             

                
    def addAction(self, elem):
        self.actions.append((self.stack.topwidget, elem.attrib["name"]))


    def addHeader(self, elem):
        if isinstance(self.stack.topwidget, QtGui.QTreeWidget):
            self.stack.topwidget.headerItem().setText(
                self.column_counter,
                self.wprops.getProperty(elem, "text"))
            icon = self.wprops.getProperty(elem, "icon")
            if icon:
                self.stack.topwidget.headerItem().setIcon(self.column_counter, icon)
            self.column_counter += 1
        elif isinstance(self.stack.topwidget, QtGui.QTableWidget):
            if len(elem) == 0:
                return
            item = self.wdb.createQObject("QTableWidgetItem",
                                          self.uniqueName("headerItem"),
                                          (), False)
            self.wprops.setProperties(item, elem)
            if elem.tag == "column":
                self.stack.topwidget.setHorizontalHeaderItem(self.column_counter, item)
                self.column_counter += 1
            else:
                self.stack.topwidget.setVerticalHeaderItem(self.row_counter, item)
                self.row_counter += 1
            

    def createAction(self, elem):
        self.setupObject("QAction", self.toplevelWidget, elem)

        
    widgetTreeItemHandlers = {
        "widget"    : createWidget,
        "addaction" : addAction,
        "layout"    : createLayout,
        "spacer"    : createSpacer,
        "item"      : handleItem,
        "action"    : createAction,
        "column"    : addHeader,
        "row"       : addHeader,
        }
    def traverseWidgetTree(self, elem):
        for child in iter(elem):
            try:
                handler = self.widgetTreeItemHandlers[child.tag]
            except KeyError, e: 
                continue
            handler(self, child)
            

    def createUserInterface(self, elem):
        self.toplevelWidget = self.createToplevelWidget(elem.attrib["class"])
        self.toplevelWidget.setObjectName(self.uiname)
        DEBUG("toplevel widget is %s",
              self.toplevelWidget.metaObject().className())
        self.wprops.setProperties(self.toplevelWidget, elem)
        self.stack.push(self.toplevelWidget)
        self.traverseWidgetTree(elem)
        self.stack.popWidget()
        self.addActions()
        self.setBuddies()
        self.setDelayedProps()
        
    def addActions(self):
        for widget, action_name in self.actions:
            if action_name == "separator":
                widget.addSeparator()
            else:
                DEBUG("add action %s to %s", action_name, widget.objectName())
                action_obj = getattr(self.toplevelWidget, action_name)
                if isinstance(action_obj, QtGui.QMenu):
                    widget.addAction(action_obj.menuAction())
                else:
                    widget.addAction(action_obj)


    def setDelayedProps(self):
        for func, args in self.wprops.delayed_props:
            func(args)

            
    def setBuddies(self):
        for widget, buddy in self.wprops.buddies:
            DEBUG("%s is buddy of %s", buddy, widget.objectName())
            try:
                widget.setBuddy(getattr(self.toplevelWidget, buddy))
            except AttributeError:
                DEBUG("ERROR in ui spec: %s (buddy of %s) does not exist",
                      buddy, widget.objectName())


    def classname(self, elem):
        DEBUG("uiname is %s", elem.text)
        self.uiname = elem.text
        self.wprops.uiname = elem.text
        self.setContext(self.uiname)


    def setContext(self, context):
        """
        Reimplemented by a sub-class if it needs to know the translation
        context.
        """
        pass


    def readDefaults(self, elem):
        self.defaults["margin"] = int(elem.attrib["margin"])
        self.defaults["spacing"] = int(elem.attrib["spacing"])
        

    def setTaborder(self, elem):
        try:
            lastwidget = getattr(self.toplevelWidget, elem[0].text)
        except IndexError:
            return
        for widget in iter(elem[1:]):
            widget = getattr(self.toplevelWidget, widget.text)
            self.toplevelWidget.setTabOrder(lastwidget, widget)
            lastwidget = widget


    def createConnections(self, elem):
        def name2object(obj):
            if obj == self.uiname:
                return self.toplevelWidget
            else:
                return getattr(self.toplevelWidget, obj)
        for conn in iter(elem):
            QtCore.QObject.connect(name2object(conn.findtext("sender")),
                                   QtCore.SIGNAL(conn.findtext("signal")),
                                   self.wdb.getSlot(name2object(conn.findtext("receiver")),
                                                    conn.findtext("slot").split("(")[0]))
        QtCore.QMetaObject.connectSlotsByName(self.toplevelWidget)


    def customWidgets(self, elem):
        def header2module(header):
            """header2module(header) -> string

            Convert paths to C++ header files to according Python modules
            >>> header2module("foo/bar/baz.h")
            'foo.bar.baz'
            """
            if header.endswith(".h"):
                header = header[:-2]

            return header.replace("/", ".")
    
        for custom_widget in iter(elem):
            classname = custom_widget.findtext("class")
            if classname.startswith("Q3"):
                raise NoSuchWidgetError, classname
            self.wdb.addCustomWidget(classname,
                                     custom_widget.findtext("extends") or "QWidget",
                                     header2module(custom_widget.findtext("header")))
                                     

    def createToplevelWidget(*args):
        raise NotImplementedError, "must be overwritten"

    
    # finalize will be called after the whole tree has been parsed
    # and can be overwritten
    def finalize(self):
        pass

    def parse(self, filename):
        # the order in which the different branches are handled is important
        # the widget tree handler relies on all custom widgets being known,
        # and in order to create the connections, all widgets have to be populated
        branchHandlers = (
            ("layoutdefault", self.readDefaults),
            ("class",         self.classname),
            ("customwidgets", self.customWidgets),
            ("widget",        self.createUserInterface),
            ("connections",   self.createConnections),
            ("tabstops",      self.setTaborder),
        )
        document = parse(filename)
        version = document.getroot().attrib["version"]
        DEBUG("UI version is %s" % (version,))
        # right now, only version 4.0 is supported, which is used
        # by Qt 4.0 and 4.1 as of 1/2006
        assert version in ("4.0",)
        for tagname, actor in branchHandlers:
            elem = document.find(tagname)
            if elem is not None:
                actor(elem)
        self.finalize()
        w = self.toplevelWidget
        self.reset()
        return w
