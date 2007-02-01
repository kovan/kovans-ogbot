import sys
sys.path.append('lib')
sys.path.append('src')
sys.path.append('src/ui')
from distutils.core import setup
import py2exe

#opts = dict(py2exe= dict(excludes=["elementtree.ElementTree","PyQt4.elementtree.ElementTree"]))
uis = "src/ui",["src/ui/About.ui","src/ui/Options.ui","src/ui/MainWindow.ui"]
images = "src/ui/resources",["src/ui/resources/about.jpeg","src/ui/resources/qtlogo.JPG","src/ui/resources/icon.png","src/ui/resources/pythonlogo.png"]
rest = ".",["instructions.txt","license.txt"]
setup( windows=['src/OGBot.py'] ,data_files = [uis,rest,images])#, options=opts)
