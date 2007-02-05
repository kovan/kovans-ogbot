import sys,os
sys.path.append('lib')
sys.path.append('src')
sys.path.append('src/ui')
from distutils.core import setup
import py2exe

languages = []
for file in os.listdir('languages'):
	fileName, extension = os.path.splitext(file)
	if not fileName or fileName.startswith('.') or extension != '.ini':
		continue
	languages.append("languages/"+file)
languages = "languages",languages
#opts = dict(py2exe= dict(excludes=["elementtree.ElementTree","PyQt4.elementtree.ElementTree"]))
opts = dict(py2exe= dict(optimize=1))
uis = "src/ui",["src/ui/About.ui","src/ui/Options.ui","src/ui/MainWindow.ui"]
images = "src/ui/resources",["src/ui/resources/about.jpeg","src/ui/resources/qtlogo.JPG","src/ui/resources/icon.png","src/ui/resources/pythonlogo.png"]

rest = ".",["changelog.txt","license.txt"]
setup( windows=['src/OGBot.py'] ,data_files = [uis,languages,images,rest],options=opts)
