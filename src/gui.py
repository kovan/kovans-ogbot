#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#      Kovan's OGBot
#      Copyright (c) 2007 by kovan 
#
#      *************************************************************************
#      *                                                                       *
#      * This program is free software; you can redistribute it and/or modify  *
#      * it under the terms of the GNU General Public License as published by  *
#      * the Free Software Foundation; either version 2 of the License, or     *
#      * (at your option) any later version.                                   *
#      *                                                                       *
#      *************************************************************************
#

import sys
import locale
import os
import os.path
import shelve
import cPickle
import webbrowser, urllib
from datetime import datetime,timedelta
from Queue import *

import PyQt4
from PyQt4 import uic
from PyQt4.QtCore import QTimer,QObject, SIGNAL, SLOT, QProcess, Qt,QDir,QUrl,QVariant
from PyQt4.QtGui import *
import sip
sys.path.append('src/ui')

from OGBot import *
from CommonClasses import *
from GameEntities import *
from Constants import *

class MyColors:
    lightGreen,lightRed,lightYellow,lightGrey,veryLightGrey = (QColor(191,255,191),QColor(255,191,191),QColor(255,255,191),QColor(191,191,191),QColor(223,223,223))


formclass, baseclass = uic.loadUiType("src/ui/About.ui")
class AboutDialog(baseclass,formclass): 
    def __init__(self):
        baseclass.__init__(self)        
        self.setupUi(self)
        self.versionLabel.setText("Version: " + open("src/version.txt").read())



formclass, baseclass = uic.loadUiType("src/ui/Options.ui")
class OptionsDialog(baseclass,formclass): 
    
    def __init__(self):
        baseclass.__init__(self)        
        self.setupUi(self)
        
        self.attackingShipButtonGroup = QButtonGroup()
        self.attackingShipButtonGroup.addButton(self.smallCargoRadioButton)
        self.attackingShipButtonGroup.addButton(self.largeCargoRadioButton)        
        
        self.lineEdits = ['webpage','username','password','proxy','rentabilityFormula','userAgent','deuteriumSourcePlanet']
        self.spinBoxes = ['universe','attackRadius','probesToSend','slotsToReserve','systemsPerGalaxy','maxProbes']
        self.textEdits = ['playersToAvoid','alliancesToAvoid']
        self.formulas = {
                    'defaultFormula': BotConfiguration('').rentabilityFormula,
                    'bestRelation'  : '(metal + crystal + deuterium) / flightTime',
                    'mostTotal'     : 'metal + crystal + deuterium',
                    'mostMetal'     : 'metal',
                    'mostCrystal'   : 'crystal',
                    'mostDeuterium' : 'deuterium'
                    }        
                
        for name in self.formulas.keys():
            control = getattr(self,name + "RadioButton")
            QObject.connect(control,SIGNAL("clicked()"),self.updateRentabilityFormula)
        QObject.connect(self.okButton,SIGNAL("clicked()"),self.saveOptions)
        QObject.connect(self.mainPlanetRadio,SIGNAL("clicked()"),self.disablePlanetList)
        QObject.connect(self.rotatePlanetsRadio,SIGNAL("clicked()"),self.enablePlanetList)
        QObject.connect(self.addPlanetButton,SIGNAL("clicked()"),self.addPlanetToList)        
        QObject.connect(self.removePlanetButton,SIGNAL("clicked()"),self.removePlanetFromList)                
        QObject.connect(self.resetUserAgentButton,SIGNAL("clicked()"),self.resetUserAgent) 

        
        self.enableOrDisablePlanetList(False)
        self.loadOptions()
        
    def loadOptions(self):
        
        self.config = BotConfiguration(FILE_PATHS['config'])
        if os.path.isfile(FILE_PATHS['config']):
            try: self.config.load()
            except BotError, e: 
                QMessageBox.critical(self,"Error in configuration",str(e))


        radioButton = getattr(self, self.config.attackingShip + "RadioButton")
        radioButton.setChecked(True)
        
        for i in self.lineEdits:
            control = getattr(self,i + "LineEdit")
            control.setText(str(self.config[i]))
        for i in self.spinBoxes:            
            control = getattr(self,i + "SpinBox")
            control.setValue(int(self.config[i]))
        for i in self.textEdits:            
            control = getattr(self,i + "TextEdit")
            control.setPlainText('\n'.join(self.config[i]))

        if self.config.get('sourcePlanets'):
            self.rotatePlanetsRadio.setChecked(True)
            self.enablePlanetList()
            self.sourcePlanetsList.addItems( [repr(p) for p in self.config['sourcePlanets']] )

        deuteriumSourcePlanet = self.config['deuteriumSourcePlanet']
        if deuteriumSourcePlanet and deuteriumSourcePlanet.isMoon():
            self.isMoonCheckBox2.setChecked(True)
        

        formulasReversed = dict([(formula,name) for name,formula in self.formulas.items() ])
        if self.config.rentabilityFormula in formulasReversed:
            control = formulasReversed[self.config.rentabilityFormula] + "RadioButton"
            getattr(self,control).setChecked(True)
        else:
            self.customFormulaRadioButton.setChecked(True)
            
        
    def saveOptions(self):
        try: 
            for i in self.lineEdits:
                control = getattr(self,i + "LineEdit")
                self.config[i] = str(control.text())
            for i in self.spinBoxes:            
                control = getattr(self,i + "SpinBox")
                self.config[i] = str(control.value())        
            for i in self.textEdits:
                control = getattr(self,i + "TextEdit")
                self.config[i] = str(control.toPlainText()).split('\n')
    
                
            if self.rotatePlanetsRadio.isChecked():
                sourcePlanets = [ Coords(str(self.sourcePlanetsList.item(i).text())) for i in range(self.sourcePlanetsList.count()) ]
                if not sourcePlanets:
                    QMessageBox.critical(self,"Error","No source of attacks planets selected")
                    return
            else: sourcePlanets = []
    
            self.config['sourcePlanets'] = sourcePlanets
            self.config['attackingShip'] = str(self.attackingShipButtonGroup.checkedButton().text())
        
            coordsStr = str(self.deuteriumSourcePlanetLineEdit.text())
            if '[::]' in coordsStr:
                deuteriumSourcePlanet = ''
            else:
                if self.isMoonCheckBox2.isChecked():
                    coordsType = Coords.Types.moon
                else:coordsType = Coords.Types.planet
                deuteriumSourcePlanet= Coords(coordsStr,coordsType = coordsType)
            self.config['deuteriumSourcePlanet'] = deuteriumSourcePlanet
            
            self.config.save()
            self.config.load()                 
        except Exception,e:
            QMessageBox.critical(self,"Error in configuration",str(e))
        else:
            self.accept()

    def enablePlanetList(self):
        self.enableOrDisablePlanetList(True)
    def disablePlanetList(self):
        self.enableOrDisablePlanetList(False)
        
    def enableOrDisablePlanetList(self,enable):
        self.addPlanetLineEdit.setEnabled(enable)
        self.addPlanetButton.setEnabled(enable)
        self.removePlanetButton.setEnabled(enable)
        self.sourcePlanetsList.setEnabled(enable)            
        self.isMoonCheckBox.setEnabled(enable)  
    
    def addPlanetToList(self):
        if self.isMoonCheckBox.isChecked():
            coordsType = Coords.Types.moon
        else : coordsType = Coords.Types.planet
        coords = Coords(str(self.addPlanetLineEdit.text()),coordsType = coordsType)
        self.sourcePlanetsList.addItem(repr(coords))
        
    def removePlanetFromList(self):
        selectedPlanet = self.sourcePlanetsList.currentItem()
        if not selectedPlanet:
            return
        index = self.sourcePlanetsList.row(selectedPlanet)
        self.sourcePlanetsList.takeItem(index)
        
    def resetUserAgent(self):
        tmpConfig = Configuration('')
        self.userAgentLineEdit.setText(tmpConfig.userAgent)

    def updateRentabilityFormula(self):
        for name,formula in self.formulas.items():
            control = getattr(self,name + "RadioButton")
            if control.isChecked():
                self.rentabilityFormulaLineEdit.setText(formula)

formclass, baseclass = uic.loadUiType("src/ui/MainWindow.ui")
class MainWindow(baseclass,formclass): 
    
    def __init__(self):
        baseclass.__init__(self)
        self.setupUi(self) # parent ui setup
        self.msgQueue = Queue()
        self._planetDb = {}
        self.bot = None
        self.botThread = None
        
        QObject.connect(qApp,SIGNAL("lastWindowClosed ()"),self.stopClicked)
        QObject.connect(self.aboutButton,SIGNAL("clicked()"),self.showAbout)
        QObject.connect(self.optionsButton,SIGNAL("clicked()"),self.showOptions)
        QObject.connect(self.launchBrowserButton,SIGNAL("clicked()"),self.launchBrowser)
        QObject.connect(self.showAllReportsButton,SIGNAL("clicked()"),self.showAllReports)    
        QObject.connect(self.startButton,SIGNAL("clicked()"),self.startClicked)
        QObject.connect(self.stopButton,SIGNAL("clicked()"),self.stopClicked)                
        QObject.connect(self.searchButton,SIGNAL("clicked()"),self._planetDb_filter)                        
        QObject.connect(self.planetsTree,SIGNAL("currentItemChanged (QTreeWidgetItem*,QTreeWidgetItem*)"),self._planetDb_updateReportsTree)        
        QObject.connect(self.reportsTree,SIGNAL("currentItemChanged (QTreeWidgetItem*,QTreeWidgetItem*)"),self._planetDb_updateReportDetailsTrees)                
        QObject.connect(self.reloadDbButton,SIGNAL("clicked()"),self._planetDb_filter)                        
        QObject.connect(self.botActivityTree,SIGNAL(" itemDoubleClicked (QTreeWidgetItem *,int)"),self.botActivityTreePlanetClicked)
        QObject.connect(self.botActivityTree,SIGNAL("customContextMenuRequested (QPoint)"),self.botActivityTreeRightClicked)
        #QObject.connect(self.validateButton,SIGNAL("clicked()"),self.validateButtonClicked)                        
                
        self.splitter.setSizes([230,111,0])
        self.setStatusBar(None)
        self.reportsTree.header().setResizeMode(QHeaderView.Stretch)
        
        self.planetsTree.header().setResizeMode(QHeaderView.Stretch)                
        self.botActivityTree.header().setResizeMode(QHeaderView.Interactive)
        self.botActivityTree.header().setStretchLastSection(False)
        headerSizes = [70,70,90,80,55,280,60,111,162,135]
        for i in range(len(headerSizes)):
            self.botActivityTree.header().resizeSection(i,headerSizes[i])
                
        for i in ["fleet","defense","buildings","research"]:
            tree = getattr(self,i + "Tree")
            tree.header().setHidden(True)
            tree.header().setResizeMode(QHeaderView.Custom)
        
        # Using a python threading.Timer here would NOT be safe to use here because it'd launch
        # a third thread that would access GUI data, resulting in potential data corruption. 
        # A QTimer, on the other hand, thread-safely sends a signal to the GUI thread, so 
        # the scheduled method would run in the GUI thread, and that is safe.
        
        self.timer = QTimer()
        QObject.connect(self.timer,SIGNAL("timeout()"),self._dispatchBotMessages)
        self.timer.start(500)        


        config = Configuration(FILE_PATHS['config'])
        try: config.load()
        except (BotFatalError, BotError): 
            self.showOptions()

     
        #self.subscribeLabel.setText(urllib.unquote('<a href="https://www.paypal.com/cgi-bin/webscr?cmd=_xclick-subscriptions&business=jsceballos%40gmail%2ecom&item_name=Kovan%27s%20OGBot%20AUTO%20FLEETSAVE&item_number=1&no_shipping=1&no_note=1&currency_code=EUR&lc=ES&bn=PP%2dSubscriptionsBF&charset=UTF%2d8&a3=4%2e00&p3=1&t3=M&src=1&sra=1">Subscribe</a>'))
        self.setWindowTitle("%s uni%s %s" %(self.windowTitle(),config.universe,config.webpage))
        self.tabWidget.removeTab(2)
       
    
    def _dispatchBotMessages(self):
        ''' An inter-thread message is an array whose first element is the event handler method and the rest
            are its arguments.
            This method checks the queue for new messages and converts them to method calls.
        '''
        while True:
            try:
                msg = self.msgQueue.get(False)
                if msg.methodName not in dir(self):
                    raise BotFatalError("Inter-thread message not found (%s)." % msg.methodName)
                
                method = getattr(self,msg.methodName)
                method(*msg.args)
            except Empty:
                break
 
    def startClicked(self):
        if self.startButton.text() == "Start":
            self.bot = Bot(self)
            self.botThread = threading.Thread(None,self.bot.run,"BotThread")
            self.botThread.start()
            
            self.setBotStatusRunning()
            self.startButton.setText("Pause")
            self.stopButton.setEnabled(True)
        elif self.startButton.text() == "Pause":
            self.bot.msgQueue.put(GuiToBotMsg(GuiToBotMsg.pause))
            self.botStatusLabel.setPalette(QPalette(MyColors.lightYellow))
            self.botStatusLabel.setText("Paused")
            self.startButton.setText("Resume") 
        elif self.startButton.text() == "Resume":
            self.bot.msgQueue.put(GuiToBotMsg(GuiToBotMsg.resume))
            self.setBotStatusRunning()                
            self.startButton.setText("Pause") 
    
    def stopClicked(self):
        if self.bot:
            self.bot.msgQueue.put(GuiToBotMsg(GuiToBotMsg.stop))
        else: return
        self.stopButton.setEnabled(False)
        self.launchBrowserButton.setEnabled(False)        
        self.startButton.setText("Start")
        self.botStatusLabel.setPalette(QPalette(MyColors.lightRed))
        self.botStatusLabel.setText("Stopped")        
        self.connectionStatusLabel.setText("")    
        self.connectionStatusLabel.setPalette(self.palette())
        
    def launchBrowser(self):
        try:
            file = open(FILE_PATHS['webstate'],'r')
            server = cPickle.load(file)        
            session = cPickle.load(file)
            file.close()
            webbrowser.open("http://%s/game/index.php?session=%s" % (server,session))             
        except IOError:
            self.launchBrowserButton.setEnabled(False)
        
    def showAbout(self):
        window = AboutDialog()
        window.exec_()
        
    def showOptions(self):
        window = OptionsDialog()
        window.exec_()
            
    def setConnectionOK(self):
        self.connectionStatusLabel.setPalette(QPalette(MyColors.lightGreen))
        self.connectionStatusLabel.setText("OK")        
        
    def setBotStatusRunning(self):
        self.botStatusLabel.setPalette(QPalette(MyColors.lightGreen))
        self.botStatusLabel.setText("Running...")        

    def botActivityTreePlanetClicked(self,item):
        coordsStr = item.text(1)
        self.planetFilterLineEdit.setText(coordsStr)
        self._planetDb_filter()
        self.tabWidget.setCurrentWidget(self.planetDbPage)
        
    def botActivityTreeRightClicked (self,point):
         menu = QMenu(self.botActivityTree)
         action=menu.addAction("Copy last espionage report to clipboard")
         QObject.connect(action, SIGNAL("triggered()"), self.copyReportToClipboard)         
         action=menu.addAction("Attack now with small cargos")
         QObject.connect(action, SIGNAL("triggered()"), self.forceAttackPlanetSmallCargos)
         action=menu.addAction("Attack now with large cargos")
         QObject.connect(action, SIGNAL("triggered()"), self.forceAttackPlanetLargeCargos)         
         action=menu.addAction("Spy now")
         QObject.connect(action, SIGNAL("triggered()"), self.forceSpyPlanet)
         menu.exec_(QCursor.pos())

    def copyReportToClipboard(self):
        if self.bot:
            rawReport = self.botActivityTree.currentItem().data(0,Qt.UserRole).toString()
            QApplication.clipboard().setText(rawReport)
    
    def forceAttackPlanetSmallCargos(self):
        if self.bot:
            selectedCoordsStr = str(self.botActivityTree.currentItem().text(1))
            self.bot.msgQueue.put(GuiToBotMsg(GuiToBotMsg.attackSmallCargo,selectedCoordsStr))
            
    def forceAttackPlanetLargeCargos(self):
        if self.bot:
            selectedCoordsStr = str(self.botActivityTree.currentItem().text(1))
            self.bot.msgQueue.put(GuiToBotMsg(GuiToBotMsg.attackLargeCargo,selectedCoordsStr))
            
    def forceSpyPlanet(self):
        if self.bot:
            selectedCoordsStr = str(self.botActivityTree.currentItem().text(1))
            self.bot.msgQueue.put(GuiToBotMsg(GuiToBotMsg.spy,selectedCoordsStr))
            
            
    def validateButtonClicked(self):
        config = Configuration(FILE_PATHS['config'])
        config.load()   
        if config.proxy:     
            proxy = {"http":config.proxy}
        else: proxy = {}
        file = "fleetsave.pyc"
        #urllib.URLopener(proxy).retrieve("http://kovansogbot.info/paypal/k.php?txn_id=%s" % self.lineEdit.text() ,file)
#        import fleetsave, new
#        new.instancemethod(fleetsave.analyzeEnemyMissions,self.bot,Bot)
#        new.instancemethod(fleetsave.getEnemyMissions,self.bot.web,WebAdapter)

#        os.remove(file)

            
    def _planetDb_filter(self):    
        filterText    = str(self.planetFilterLineEdit.text())
        columnToFilter = str(self.planetFilterComboBox.currentText())
        self.planetsTree.clear()
        self._planetDb = PlanetDb(FILE_PATHS['planetdb'])
        self.reportsTree.clear()                
        
        try:
            allPlanets = self._planetDb.readAll()
        except AttributeError:
            os.remove(FILE_PATHS['planetdb'])     
        else:        
            for planet in allPlanets:
                attrName = re.sub(r" (\w)",lambda m: m.group(0).upper().strip(),columnToFilter.lower()) # convert names from style "Player status" to style "playerStatus"
                columnValue = str(getattr(planet,attrName))
                reportCount = str(len(planet.espionageHistory))
                if reportCount == '0' : reportCount = '-'
                if filterText.lower() in columnValue.lower():
                    item = MyTreeWidgetItem(planet.toStringList() + [planet.ownerStatus, reportCount])
                    self.planetsTree.addTopLevelItem(item)
           
    def _planetDb_updateReportsTree(self,planetTreeSelectedItem):
        if not planetTreeSelectedItem:
            return
        coordsStr = str(planetTreeSelectedItem.text(0))
        self.reportsTree.clear()
        planet = self._planetDb.read(coordsStr)
        self._planetDb_fillReportsTree(planet.espionageHistory)
        
    def _planetDb_fillReportsTree(self,reports):
        if len(reports) == 0:
            return
        self.reportsTree.clear()
        for report in reports:
            res = report.resources
            onlyHasMissiles = not report.hasNonMissileDefense() and report.hasDefense()
            if onlyHasMissiles: defense = "Only missiles"
            else: defense = report.hasInfoAbout("defense")
            
            itemData = [report.code,report.date.strftime("%X %x"),str(report.coords),str(res.metal),str(res.crystal),str(res.deuterium)]
            itemData += [report.hasInfoAbout("fleet"),defense,str(report.probesSent)]            
            item = MyTreeWidgetItem(itemData)
            self.reportsTree.addTopLevelItem(item)
            
        self.splitter.setSizes([230,111,1])
        self.reportsTree.setCurrentItem(self.reportsTree.topLevelItem(0))            
        
    def _planetDb_updateReportDetailsTrees(self,reportsTreeSelectedItem):
        if reportsTreeSelectedItem is None:
            return
        codeStr = str(reportsTreeSelectedItem.text(0))        
        coordsStr = str(reportsTreeSelectedItem.text(2))
        
        planet =  self._planetDb.read(coordsStr)
        report = [report for report in planet.espionageHistory if str(report.code) == codeStr][0]
        
        for i in ["fleet","defense","buildings","research"]:
            tree = getattr(self,i + "Tree")
            tree.clear()
            var = report.hasInfoAbout(i) +" "+ i # var results in, p.e: "Unknown fleet"
            if var == "Yes " + i:
                items = []
                for type, cuantity in  getattr(report,i).items():
                    items.append(MyTreeWidgetItem([type,str(cuantity)]))
            else: items = [MyTreeWidgetItem([var])]
            tree.addTopLevelItems(items)

    def showAllReports(self):
        self.reportsTree.clear()
        allPlanets = self._planetDb.readAll()
        allReports = [planet.espionageHistory[-1] for planet in allPlanets if len(planet.espionageHistory) > 0]
        self._planetDb_fillReportsTree(allReports)
        

    # bot events handler methods:
    # ------------------------------------------------------------------------
    
            


  
            
    def connectionError(self,reason):
        self.connectionStatusLabel.setText("Connection error")        
        self.connectionStatusLabel.setPalette(QPalette(MyColors.lightRed))
        self.botStatusLabel.setPalette(QPalette(MyColors.lightRed))
        self.botStatusLabel.setText("Stopped")        
        
    def loggedIn(self,username,session):
        self.launchBrowserButton.setEnabled(True)
        self.session = session
    def fatalException(self,exception):
        self.stopClicked()
        QMessageBox.critical(self,"Fatal error","Critical error: %s" % exception)

    def statusMsg(self,msg):
        self.setConnectionOK()        
        self.botStatusLabel.setPalette(QPalette(MyColors.lightYellow))
        self.botStatusLabel.setText(msg)       
    def connected(self):
        self.setConnectionOK()        
        self.launchBrowserButton.setEnabled(True)
    def simulationsUpdate(self,rentabilitiesTable):
        self.setConnectionOK()

        self.botActivityTree.clear() 
        maxRentability = 0
        for item in rentabilitiesTable:
            if item.rentability > maxRentability:
                maxRentability = item.rentability
                
        for item in rentabilitiesTable:

            if not item.targetPlanet.espionageHistory: 
                simulatedResources = 'Not spied'
                defendedStr = 'Not spied'
                minesStr = 'Not spied'
                lastSpiedStr = 'Not spied'
            else:
                simulatedResources = item.targetPlanet.simulation.simulatedResources

                report = item.targetPlanet.getBestEspionageReport()
                lastSpiedStr = str(report.date)                
                if  report.defense == None:
                    defendedStr = '?'
                elif not report.isDefended():
                    defendedStr = 'No'
                else:
                    defendedStr = 'Yes'
                
                if report.buildings == None:
                    minesStr = '?'
                else:
                    minesStr = "M: %s, C: %s D: %s" % (report.buildings.get('metalMine',0),report.buildings.get('crystalMine',0),report.buildings.get('deuteriumSynthesizer',0))
                     
                 
            treeItem = MyTreeWidgetItem(["%.2f" % item.rentability,str(item.targetPlanet.coords),item.targetPlanet.name,item.targetPlanet.owner,item.targetPlanet.alliance,str(simulatedResources),defendedStr,minesStr,str(item.sourcePlanet),lastSpiedStr])
            if item.targetPlanet.espionageHistory:
                treeItem.setToolTip(6,str(report.fleet) + str(report.defense))
                treeItem.setToolTip(7,str(report.buildings) + str(report.research))
                treeItem.setData(0,Qt.UserRole,QVariant(item.targetPlanet.espionageHistory[-1].rawHtml))
        
            if item.rentability > 0:
                value = int (item.rentability *  255 / maxRentability)
                backColor = QColor(255-value,255,255-value)            
                treeItem.setBackgroundColor(0,backColor)
            self.botActivityTree.addTopLevelItem(treeItem)        
            
            
    def activityMsg(self,msg):            
        self.setConnectionOK()   
        self.setBotStatusRunning()     
        item = QListWidgetItem(str(msg))
        self.botActivityList.addItem(item)
        self.botActivityList.scrollToItem(item)

class MyTreeWidgetItem(QTreeWidgetItem):
    # subclassed just to implement sorting by numbers instead of by strings
    def __lt__(self,other):
        sortCol = self.treeWidget().sortColumn()
        myNumber, ok1 = self.text(sortCol).toDouble()
        otherNumber, ok2 = other.text(sortCol).toDouble()
        if not ok1 or not ok2:
            return self.text(sortCol) < other.text(sortCol)
        else:
            return myNumber < otherNumber
        

        

def guiMain(options):
    app = QApplication(sys.argv)
    locale.setlocale(locale.LC_ALL,'C')
    QApplication.setStyle(QStyleFactory.create("plastique"))
    window = MainWindow()
    window.show()
    if options and options.autostart:
        window.startClicked()
    app.exec_()
    
    
    
