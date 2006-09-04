import operator
from PyQt4.uic.exceptions import UnsupportedPropertyError

import logging

QtCore = None
QtGui = None

def int_list(prop):
    return [int(child.text) for child in iter(prop)]

bool_ = lambda v: v == "true"

def needsWidget(func):
    func.needsWidget = True
    return func

class Properties(object):
    def __init__(self, qobject_creator, QtCore_mod, QtGui_mod):
        self.reset()
        global QtGui, QtCore
        QtGui = QtGui_mod
        QtCore = QtCore_mod
        self.qobject_creator = qobject_creator

    def reset(self):
        self.buddies = []
        self.delayed_props = []

    def _pyEnumMember(self, cpp_name):
        try:
            prefix, membername = cpp_name.split("::")
            logging.debug(membername)
            if prefix == "Qt":
                return getattr(QtCore.Qt, membername)
            else:
                return getattr(getattr(QtGui, prefix), membername)
        except ValueError:
            return getattr(getattr(QtGui, self.wclass), cpp_name)

    def _set(self, prop):
        return reduce(operator.or_, [self._pyEnumMember(value)
                                     for value in prop.text.split('|')])

    def _enum(self, prop):
        return self._pyEnumMember(prop.text)

    def _number(self, prop):
        return int(prop.text)

    def _double(self, prop):
        return float(prop.text)

    def _bool(self, prop):
        return prop.text == 'true'

    def _string(self, prop):
        if isinstance(prop.text, unicode):
            text = prop.text.encode("UTF-8")
        else:
            text = prop.text
        return QtGui.QApplication.translate(self.uiname, text,
                                            None, QtGui.QApplication.UnicodeUTF8)

    def _cstring(self, prop):
        return str(prop.text)

    def _color(self, prop):
        return QtGui.QColor(*int_list(prop))

    def _rect(self, prop):
        return QtCore.QRect(*int_list(prop))

    def _size(self, prop):
        return QtCore.QSize(*int_list(prop))

    def _pixmap(self, prop):
        return QtGui.QPixmap(prop.text)

    def _iconset(self, prop):
        return QtGui.QIcon(prop.text)

    def _cursor(self, prop):
        return QtGui.QCursor(QtCore.Qt.CursorShape(int(prop.text)))

    def _date(self, prop):
        return QtCore.QDate(*int_list(prop))

    def _datetime(self, prop):
        args = int_list(prop)
        return QtCore.QDateTime(QtCore.QDate(*args[-3:]), QtCore.QTime(*args[:-3]))

    def _time(self, prop):
        return QtCore.QTime(*int_list(prop))

    # font needs special handling/conversion of all child elements
    _font_attributes = (("Family",    str),
                        ("PointSize", int),
                        ("Weight",    int),
                        ("Italic",    bool_),
                        ("Underline", bool_),
                        ("StrikeOut", bool_),
                        ("Bold",      bool_))

    #@needsWidget
    def _font(self, prop, widget):
        newfont = self.qobject_creator.createQObject("QFont", "font",
                                                     (widget.font(), ),
                                                     is_attribute = False)
        for attr, converter in self._font_attributes:
            v = prop.findtext("./%s" % (attr.lower(),))
            if v is None:
                continue

            getattr(newfont, "set%s" % (attr,))(converter(v))
        return newfont
    _font = needsWidget(_font)

    def convert(self, prop, widget = None):
        try:
            func = getattr(self, "_" + prop[0].tag)
        except AttributeError:
            raise UnsupportedPropertyError, prop[0].tag
        else:
            args = {}
            if getattr(func, "needsWidget", False):
                assert widget is not None
                args["widget"] = widget

            return func(prop[0], **args)


    def _getChild(self, elem_tag, elem, name, default = None):
        for prop in elem.findall(elem_tag):
            if prop.attrib["name"] == name:
                if prop[0].tag == "enum":
                    return prop[0].text
                else:
                    return self.convert(prop)
        else:
            return default

    def getProperty(self, elem, name, default = None):
        return self._getChild("property", elem, name, default)

    def getAttribute(self, elem, name, default = None):
        return self._getChild("attribute", elem, name, default)

    def setProperties(self, widget, elem):
        try:
            self.wclass = elem.attrib["class"]
        except KeyError:
            pass
        for prop in elem.findall("property"):
            if prop[0].text is None:
                continue
            propname = prop.attrib["name"]
            if hasattr(self, propname):
                getattr(self, propname)(widget, prop)
            else:
                getattr(widget, "set%s%s" % (propname[0].upper(), propname[1:]))(
                    self.convert(prop, widget))

    # delayed properties will be set after the whole widget tree has been populated
    def _delay(self, widget, prop):
        propname = prop.attrib["name"]
        self.delayed_props.append(
            (getattr(widget, "set%s%s" % (propname[0].upper(), propname[1:])),
                                  self.convert(prop)))

    # this properties will be set with a widget.setProperty call rather than
    # calling the set<property> function
    def _setViaSetProperty(self, widget, prop):
        widget.setProperty(prop.attrib["name"], QtCore.QVariant(self.convert(prop)))

    # all properties that need special handling
    currentIndex = currentRow = _delay
    showDropIndicator = intValue = value = _setViaSetProperty # QLCDValue needs this

    # buddy setting has to be done after the whole widget tree has been populated
    # we can't use delay here because we cannot get the actual buddy yet
    def buddy(self, widget, prop):
        self.buddies.append((widget, prop[0].text))

    # geometry has to be handled specially if set on the toplevel widget
    def geometry(self, widget, prop):
        rect = self._rect(prop[0])
        if widget.objectName() == self.uiname:
            widget.resize(QtCore.QSize(rect.size()).expandedTo(widget.minimumSizeHint()))
        else:
            widget.setGeometry(rect)

    def orientation(self, widget, prop):
        # if the class is a QFrame, it's a line
        if widget.metaObject().className() == "QFrame":
            widget.setFrameShape(
                {"Qt::Horizontal": QtGui.QFrame.HLine,
                 "Qt::Vertical"  : QtGui.QFrame.VLine}[prop[0].text])
            # in Qt Designer, lines appear to be sunken, QFormBuilder loads
            # them as such, uic generates plain lines. We stick to the look
            # in Qt Designer
            widget.setFrameShadow(QtGui.QFrame.Sunken)
        else:
            widget.setOrientation(self._enum(prop[0]))

    # sizePolicy is just plain weird
    def sizePolicy(self, widget, prop):
        values = [int(child.text) for child in prop[0]]
        sizePolicy = self.qobject_creator.createQObject(
            "QSizePolicy", "sizePolicy",
            (QtGui.QSizePolicy.Policy(values[0]), QtGui.QSizePolicy.Policy(values[1])),
            is_attribute = False)
        sizePolicy.setHorizontalStretch(values[2])
        sizePolicy.setVerticalStretch(values[3])
        sizePolicy.setHeightForWidth(widget.sizePolicy().hasHeightForWidth())
        widget.setSizePolicy(sizePolicy)

    # palette needs a lot of function calls
    def palette(self, widget, prop):
        palette = self.qobject_creator.createQObject("QPalette", "palette", (),
                                                   is_attribute = False)
        for palette_elem in prop[0]:
            sub_palette = getattr(QtGui.QPalette, palette_elem.tag.title())
            for idx, color in enumerate(palette_elem):
                palette.setColor(sub_palette, QtGui.QPalette.ColorRole(idx),
                                 self._color(color))
        widget.setPalette(palette)


    # attribute isWrapping of QListView is named inconsistently,
    # should be wrapping
    def isWrapping(self, widget, prop):
        widget.setWrapping(self.convert(prop))
