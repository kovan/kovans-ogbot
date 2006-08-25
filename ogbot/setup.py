import sys
sys.path.append('lib')
sys.path.append('src')
sys.path.append('src/ui')
from distutils.core import setup
import py2exe

uis = "src/ui",["src/ui/About.ui","src/ui/Options.ui","src/ui/MainWindow.ui"]
rest = ".",["instructions.txt","license.txt"]
setup( windows=['src/OGBot.py'] ,data_files = [uis,rest])
