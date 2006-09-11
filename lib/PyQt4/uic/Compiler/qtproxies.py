# Hic sunt leones!
import re
import sys

from indenter import write_code


i18n_strings = []
i18n_context = ""

def i18n_print(string):
    i18n_strings.append(string)
    
def moduleMember(module, name):
    if module == "":
        return name
    else:
        return "%s.%s" % (module, name)

def obj_to_argument(obj):
    if isinstance(obj, str):
        return "\"%s\"" % (obj,)
    else:
        return str(obj)
    
def i18n_func(name):
    def _printer(self, *args):
        i18n_print("%s.%s(%s)" % (self, name, ",".join(map(obj_to_argument, args))))
    return _printer

class Literal(object):
    """Literal(string) -> new literal

    string will not be quoted when put into an argument list"""
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return self.string

class i18n_string(object):
    """i18n_string(string)

    string will be UTF-8-encoded, escaped, quoted and translated when included
    into a function call argument list."""
    _esc_regex = re.compile(r"(\"|\'|\\)")
    def __init__(self, string):
        if isinstance(string, unicode):
            self.string = string.encode("UTF-8")
        else:
            self.string = string

    def escape(self, text):
        x = self._esc_regex.sub(r"\\\1", text)
        return re.sub(r"\n", r'\\n"\n"', x)

    def __str__(self):
        return "QtGui.QApplication.translate(\"%s\", \"%s\", None, QtGui.QApplication.UnicodeUTF8)" % (i18n_context, self.escape(self.string))


# classes with this flag will occur in retranslateUi completely
# (construction, function calls, all calls to other functions with this
#  class as an argument)
I18N_ONLY = 1
# classes with this flag will be handled as literal values. If functions are
# called on these classes, the literal value changes.
# Example:
# the code
# >>> QSize(9,10).expandedTo(...)
# will print just that code.
AS_ARGUMENT = 2

# ATTENTION: currently, classes can either be literal or normal. If a class
# should need both kinds of behaviour, the code has to be changed.

class ProxyClassMember(object):
    def __init__(self, proxy, function_name, flags):
        self.proxy = proxy
        self.function_name = function_name
        self.flags = flags
        
    def __str__(self):
        return "%s.%s" % (self.proxy, self.function_name)
    
    def __call__(self, *args):
        func_call = "%s.%s(%s)" % (self.proxy,
                                   self.function_name,
                                   ",".join(map(obj_to_argument, args)))
        if self.flags & AS_ARGUMENT:
            self.proxy._name = func_call
            return self.proxy
        else:
            needs_translation = self.flags & I18N_ONLY
            for arg in args:
                if isinstance(arg, i18n_string) or getattr(arg, "flags", 0) & I18N_ONLY:
                    needs_translation = True
            if needs_translation:
                i18n_print(func_call)
            else:
                write_code(func_call)


class ProxyType(type):
    def __getattribute__(cls, name):
        try:
            attr = type.__getattribute__(cls, name)
            if isinstance(attr, ProxyType):
                type.__setattr__(attr, "module",
                                 moduleMember(type.__getattribute__(cls, "module"),
                                              type.__getattribute__(cls, "__name__")))
            return attr
        except AttributeError:
            return type(name, (LiteralProxyClass,),
                        {"module": moduleMember(type.__getattribute__(cls, "module"),
                                                type.__getattribute__(cls, "__name__"))})

    def __str__(cls):
        return moduleMember(type.__getattribute__(cls, "module"),
                            type.__getattribute__(cls, "__name__"))


class ProxyClass(object):
    __metaclass__ = ProxyType
    flags = 0
    module = ""
    def __init__(self, objectname, is_attribute,
                 args = (), noInstantiation = False):
        if is_attribute:
            self._name = "self.%s" % (objectname, )
        else:
            self._name = objectname
        if not noInstantiation:
            funcall = "\n%s = %s(%s)" % \
                      (self._name,
                       moduleMember(self.module, self.__class__.__name__),
                       ",".join(map(str, args)))
            if self.flags & I18N_ONLY:
                i18n_print(funcall)
            else:
                write_code(funcall)
    
    def __str__(self):
        return self._name

    def __getattribute__(self, attribute):
        try:
            return object.__getattribute__(self, attribute)
        except AttributeError:
            return ProxyClassMember(self, attribute, self.flags)

class I18NProxyClass(ProxyClass):
    flags = I18N_ONLY
    
class LiteralProxyClass(ProxyClass):
    """LiteralObject(*args) -> new literal class

    a literal class can be used as argument in a function call

    >>> class Foo(LiteralProxyClass): pass
    >>> str(Foo(1,2,3)) == "Foo(1,2,3)"
    """
    flags = AS_ARGUMENT
    def __init__(self, *args):
        self._name = "%s(%s)" % \
                     (moduleMember(self.module, self.__class__.__name__),
                      ",".join(map(obj_to_argument, args)))

class ProxyNamespace(ProxyClass):
    pass

# These are all the Qt classes used by pyuic4 in their namespaces. 
# If a class is missing, the compiler will fail, normally with an
# AttributeError.
# For adding new classes:
#     - utility classes used as literal values do not need to be listed
#       because they are created on the fly as subclasses of LiteralProxyClass
#     - classes which are *not* QWidgets inherit from ProxyClass and they
#       have to be listed explicitly in the correct namespace. These classes
#       are created via a the ProxyQObjectCreator
#     - new QWidget-derived classes have to inherit from qtproxies.QWidget
#       If the widget does not need any special methods, it can be listed
#       in _qwidgets

class QtCore(ProxyNamespace):
    class Qt(ProxyNamespace):
        pass

    ## connectSlotsByName and connect have to be handled as class methods,
    ## otherwise they would be created as LiteralProxyClasses and never be
    ## printed
    class QMetaObject(ProxyClass):
        def connectSlotsByName(cls, *args):
            ProxyClassMember(cls, "connectSlotsByName", 0)(*args)
        connectSlotsByName = classmethod(connectSlotsByName)


    class QObject(ProxyClass):
        def metaObject(self):
            class _FakeMetaObject(object):
                def className(*args):
                    return self.__class__.__name__
            return _FakeMetaObject()

        def objectName(self):
            return self._name.split(".")[-1]

        def connect(cls, *args):
            ProxyClassMember(cls, "connect", 0)(*args)
        connect = classmethod(connect)

_qwidgets = (
    "QCheckBox", "QComboBox", "QDateEdit", "QDateTimeEdit", "QDial", "QDialog",
    "QDockWidget", "QDoubleSpinBox", "QFrame", "QGroupBox", "QLabel",
    "QLCDNumber", "QLineEdit", "QListView", "QListWidget", "QMainWindow",
    "QMenu", "QMenuBar", "QProgressBar", "QPushButton", "QRadioButton", 
    "QScrollBar", "QSlider", "QSpinBox", "QSplitter", "QStackedWidget", 
    "QStatusBar", "QTableView", "QTableWidget", "QTabWidget", "QTextBrowser",
    "QTextEdit", "QTimeEdit", "QToolBar", "QToolBox", "QToolButton", "QTreeView",
    "QTreeWidget", "QAbstractItemView",)

class QtGui(ProxyNamespace):
    class QListWidgetItem(I18NProxyClass):
        pass

    class QTreeWidgetItem(I18NProxyClass):
        pass

    class QTableWidgetItem(I18NProxyClass):
        pass

    class QPalette(ProxyClass): pass
    class QFont(ProxyClass): pass
    class QSpacerItem(ProxyClass): pass
    class QSizePolicy(ProxyClass): pass
    ## QActions inherit from QObject for the metaobject stuff
    ## and the hierarchy has to be correct since we have a
    ## isinstance(x, QtGui.QLayout) call in the ui parser
    class QAction(QtCore.QObject): pass
    class QLayout(QtCore.QObject): pass
    class QGridLayout(QLayout): pass
    class QHBoxLayout(QLayout): pass
    class QVBoxLayout(QLayout): pass

    class QWidget(QtCore.QObject):
        def font(self):
            return Literal("%s.font()" % (self,))

        def minimumSizeHint(self):
            return Literal("%s.minimumSizeHint()" % (self,))

        def sizePolicy(self):
            sp = LiteralProxyClass()
            sp._name = "%s.sizePolicy()" % (self,)
            return sp

    class QListWidget(QWidget):
        clear = i18n_func("clear")
    
    class QTableWidget(QWidget):
        clear = i18n_func("clear")
        setRowCount = i18n_func("setRowCount")
        setColumnCount = i18n_func("setColumnCount")
        
    class QTreeWidget(QWidget):
        clear = i18n_func("clear")

        def headerItem(self):
            return QtGui.QWidget("%s.headerItem()" % (self,), False, (), noInstantiation = True)

    class QMenu(QWidget):
        def menuAction(self):
            return Literal("%s.menuAction()" % (self,))

    class QTabWidget(QWidget):
        def addTab(self, *args):
            write_code("%s.addTab(%s, \"\")" % (self._name, args[0]))
            i18n_print("%s.setTabText(%s.indexOf(%s), %s)" % \
                       (self._name, self._name, args[0], args[1]))

    class QToolBox(QWidget):
        def addItem(self, *args):
            write_code("%s.addItem(%s, \"\")" % (self._name, args[0]))
            i18n_print("%s.setItemText(%s.indexOf(%s), %s)" % \
                       (self._name, self._name, args[0], args[1]))

    # add all remaining classes
    for _class in _qwidgets:
        if not locals().has_key(_class):
            locals()[_class] = type(_class, (QWidget, ), {})
