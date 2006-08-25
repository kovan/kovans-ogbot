from PyQt4.uic import properties
from PyQt4.uic.Compiler import qtproxies

class ProxyProperties(properties.Properties):
    def __init__(self, qobject_creator):
        properties.Properties.__init__(self, qobject_creator,
                                       qtproxies.QtCore, qtproxies.QtGui)

    def _string(self, prop):
        return qtproxies.i18n_string(prop.text or "")

    def _set(self, prop):
        return qtproxies.Literal("|".join([str(self._pyEnumMember(value))
                                           for value in prop.text.split('|')]))
