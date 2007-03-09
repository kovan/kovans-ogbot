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
import os
import os.path
import shelve
import cPickle
import webbrowser
from datetime import datetime,timedelta
from Queue import *

import PyQt4
from PyQt4 import uic
from PyQt4.QtCore import QTimer,QObject, SIGNAL, SLOT, QProcess, Qt,QDir
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


        
formclass, baseclass = uic.loadUiType("src/ui/Options.ui")
class OptionsDialog(baseclass,formclass): 
    
    def __init__(self):
        baseclass.__init__(self)        
        self.setupUi(self)
        

        self.lineEdits = ['webpage','username','password','proxy','rentabilityFormula','userAgent']
        self.spinBoxes = ['universe','attackRadius','probesToSend','slotsToReserve','systemsPerGalaxy']
        self.textEdits = ['playersToAvoid','alliancesToAvoid']
        self.formulas = {
                    'defaultFormula': Configuration('').rentabilityFormula,
                    'mostWithRatio' : 'metal + 1.5 * crystal + 3 * deuterium',
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
        self.attackingShipComboBox.addItems([str(shiptype) for shiptype in INGAME_TYPES if isinstance(shiptype,Ship)])
        self.loadOptions()
        
    def loadOptions(self):
        
        self.config = Configuration(FILE_PATHS['config'])
        try: self.config.load()
        except BotError, e: 
            QMessageBox.critical(self,"Error in config.ini",str(e))

        index = self.attackingShipComboBox.findText(self.config.attackingShip)
        self.attackingShipComboBox.setCurrentIndex(index)
        
               
        for i in self.lineEdits:
            control = getattr(self,i + "LineEdit")
            control.setText(self.config[i])
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
        

        formulasReversed = dict([(formula,name) for name,formula in self.formulas.items() ])
        if self.config.rentabilityFormula in formulasReversed:
            control = formulasReversed[self.config.rentabilityFormula] + "RadioButton"
            getattr(self,control).setChecked(True)
        else:
            self.customFormulaRadioButton.setChecked(True)
            
        
    def saveOptions(self):
        
        if self.rotatePlanetsRadio.isChecked():
            sourcePlanets = [ Coords(str(self.sourcePlanetsList.item(i).text())) for i in range(self.sourcePlanetsList.count()) ]
            if not sourcePlanets:
                QMessageBox.critical(self,"Error","No source of attacks planets selected")
                return
        else: sourcePlanets = []

        self.config['sourcePlanets'] = sourcePlanets
        self.config['attackingShip'] = str(self.attackingShipComboBox.currentText().toAscii())
        

        for i in self.lineEdits:
            control = getattr(self,i + "LineEdit")
            self.config[i] = str(control.text())
        for i in self.spinBoxes:            
            control = getattr(self,i + "SpinBox")
            self.config[i] = str(control.value())        
        for i in self.textEdits:
            control = getattr(self,i + "TextEdit")
            self.config[i] = str(control.toPlainText()).split('\n')
            
       
        
        self.config.save()
        try: self.config.load()                 
        except BotError,e:
            QMessageBox.critical(self,"Error in configuration",str(e))
            return
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
        self.bot = None
        
        QObject.connect(qApp,SIGNAL("lastWindowClosed ()"),self.stopClicked)
        QObject.connect(self.aboutButton,SIGNAL("clicked()"),self.showAbout)
        QObject.connect(self.optionsButton,SIGNAL("clicked()"),self.showOptions)
        QObject.connect(self.launchBrowserButton,SIGNAL("clicked()"),self.launchBrowser)
    #  QObject.connect(self.viewLogButton,SIGNAL("clicked()"),self.viewLog)
        QObject.connect(self.showAllReportsButton,SIGNAL("clicked()"),self.showAllReports)    
        QObject.connect(self.startButton,SIGNAL("clicked()"),self.startClicked)
        QObject.connect(self.stopButton,SIGNAL("clicked()"),self.stopClicked)                
        QObject.connect(self.searchButton,SIGNAL("clicked()"),self._planetDb_filter)                        
        QObject.connect(self.planetsTree,SIGNAL("currentItemChanged (QTreeWidgetItem*,QTreeWidgetItem*)"),self._planetDb_updateReportsTree)        
        QObject.connect(self.spyReportsTree,SIGNAL("currentItemChanged (QTreeWidgetItem*,QTreeWidgetItem*)"),self._planetDb_updateReportDetailsTrees)                
        QObject.connect(self.reloadDbButton,SIGNAL("clicked()"),self._planetDb_filter)                        
        QObject.connect(self.botActivityTree,SIGNAL(" itemDoubleClicked (QTreeWidgetItem *,int)"),self.botActivityTreePlanetClicked)
        
        self.splitter.setSizes([230,111,0])
        #self.botActivityLabel.setBackgroundRole(QPalette.AlternateBase) # background of a ligh color
        self.setStatusBar(None)
        self.spyReportsTree.header().setResizeMode(QHeaderView.Stretch)
        
        self.planetsTree.header().setResizeMode(QHeaderView.Stretch)                
        self.botActivityTree.header().setResizeMode(QHeaderView.Interactive)
        self.botActivityTree.header().setStretchLastSection(False)
        self.botActivityTree.header().resizeSection(0,70)                
        self.botActivityTree.header().resizeSection(1,80)                        
        self.botActivityTree.header().resizeSection(2,111)
        self.botActivityTree.header().resizeSection(3,111)        
        self.botActivityTree.header().resizeSection(4,111)        
        self.botActivityTree.header().resizeSection(5,300)         
        self.botActivityTree.header().resizeSection(6,60)                 
        self.botActivityTree.header().resizeSection(7,120)        
        #self.progressBar.setVisible(False)
                
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

        
        self._planetDb_filter()
    
    def _dispatchBotMessages(self):
        ''' An inter-thread message is an array whose first element is the event handler method and the rest
            are its arguments.
            This method checks the queue for new messages and converts them to method calls.
        '''
        while True:
            try:
                msg = self.msgQueue.get(False)
                if msg.methodName not in dir(self):
                    raise BotFatalError("Inter-queue message not found.")
                
                method = getattr(self,msg.methodName)
                method(*msg.args)
            except Empty:
                break
 
    def startClicked(self):
        if self.startButton.text() == "Start":
            if self.bot and self.bot.isAlive():
                self.bot.join()
            self.bot = Bot(self)
            self.bot.start()
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
        self.toolBox.setCurrentWidget(self.planetDbPage)
        
    def _planetDb_filter(self):    
        filterText    = str(self.planetFilterLineEdit.text())
        columnToFilter = str(self.planetFilterComboBox.currentText())
        self.planetsTree.clear()
        self._planetDb = PlanetDb(FILE_PATHS['planetdb'])
        self.spyReportsTree.clear()                
        
        for planet in self._planetDb.readAll():
            attrName = re.sub(r" (\w)",lambda m: m.group(0).upper().strip(),columnToFilter.lower()) # convert names from style "Player status" to style "playerStatus"
            columnValue = str(getattr(planet,attrName))
            spyReportCount = str(len(planet.spyReportHistory))
            if spyReportCount == '0' : spyReportCount = '-'
            if filterText.lower() in columnValue.lower():
                item = QTreeWidgetItem(planet.toStringList() + [planet.ownerStatus, spyReportCount])
                self.planetsTree.addTopLevelItem(item)
                
    def _planetDb_updateReportsTree(self,planetTreeSelectedItem):
        if not planetTreeSelectedItem:
            return
        coordsStr = str(planetTreeSelectedItem.text(0))
        self.spyReportsTree.clear()
        planet = self._planetDb.read(coordsStr)
        self._planetDb_fillReportsTree(planet.spyReportHistory)
        
    def _planetDb_fillReportsTree(self,spyReports):
        if len(spyReports) == 0:
            return
        self.spyReportsTree.clear()
        for spyReport in spyReports:
            res = spyReport.resources
            onlyHasMissiles = not spyReport.hasNonMissileDefense() and spyReport.hasDefense()
            if onlyHasMissiles: defense = "Only missiles"
            else: defense = spyReport.hasInfoAbout("defense")
            
            itemData = [spyReport.code,spyReport.date.strftime("%X %x"),str(spyReport.coords),str(res.metal),str(res.crystal),str(res.deuterium)]
            itemData += [spyReport.hasInfoAbout("fleet"),defense,str(spyReport.probesSent)]            
            item = QTreeWidgetItem(itemData)
            self.spyReportsTree.addTopLevelItem(item)
            
        self.splitter.setSizes([230,111,1])
        self.spyReportsTree.setCurrentItem(self.spyReportsTree.topLevelItem(0))            
        
    def _planetDb_updateReportDetailsTrees(self,spyReportsTreeSelectedItem):
        if spyReportsTreeSelectedItem is None:
            return
        codeStr = str(spyReportsTreeSelectedItem.text(0))        
        coordsStr = str(spyReportsTreeSelectedItem.text(2))
        
        planet =  self._planetDb.read(coordsStr)
        spyReport = [report for report in planet.spyReportHistory if str(report.code) == codeStr][0]
        
        for i in ["fleet","defense","buildings","research"]:
            tree = getattr(self,i + "Tree")
            tree.clear()
            var = spyReport.hasInfoAbout(i) +" "+ i # var results in, p.e: "Unknown fleet"
            if var == "Yes " + i:
                items = []
                for type, cuantity in  getattr(spyReport,i).items():
                    items.append(QTreeWidgetItem([type,str(cuantity)]))
            else: items = [QTreeWidgetItem([var])]
            tree.addTopLevelItems(items)

    def showAllReports(self):
        self.spyReportsTree.clear()
        allPlanets = self._planetDb.readAll()
        allReports = [planet.spyReportHistory[-1] for planet in allPlanets if len(planet.spyReportHistory) > 0]
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
    # new GUI messages
    def statusMsg(self,msg):
        self.setConnectionOK()        
        self.botStatusLabel.setPalette(QPalette(MyColors.lightYellow))
        self.botStatusLabel.setText(msg)       
    def connected(self):
        self.setConnectionOK()        
        self.launchBrowserButton.setEnabled(True)
    def simulationsUpdate(self,simulations,rentabilities):
        self.setConnectionOK()

        self.botActivityTree.clear() 
        maxRentability = 0
        for rentability in rentabilities:
            if isinstance(rentability,tuple) and rentability[1] > maxRentability:
                maxRentability = rentability[1] 
                
        for planet in rentabilities:
            if isinstance(planet,tuple):
                planet,rentability = planet
            else: rentability = 0

            if not planet.spyReportHistory: 
                simulatedResources = 'Not spied'
                defendedStr = 'Not spied'
                minesStr = 'Not spied'
            else:
                simulatedResources = simulations[repr(planet.coords)].simulatedResources
                report = planet.spyReportHistory[-1]
                if  report.defense == None:
                    defendedStr = '?'
                elif  report.isUndefended():
                    defendedStr = 'No'
                else:
                    defendedStr = 'Yes'
                
                if report.buildings == None:
                    minesStr = '?'
                else:
                    minesStr = "M: %s, C: %s D: %s" % (report.buildings.get('metalMine',0),report.buildings.get('crystalMine',0),report.buildings.get('deuteriumSynthesizer',0))
                     
            item = QTreeWidgetItem(["%.2f" % rentability,str(planet.coords),planet.name,planet.owner,planet.alliance,str(simulatedResources),defendedStr,minesStr])
            if rentability > 0:
                value = int (rentability *  255 / maxRentability)
                backColor = QColor(255-value,255,255-value)            
                item.setBackgroundColor(0,backColor)
            self.botActivityTree.addTopLevelItem(item)        
            
            
    def activityMsg(self,msg):            
        self.setConnectionOK()   
        self.setBotStatusRunning()     
        item = QListWidgetItem(str(msg))
        self.botActivityList.addItem(item)
        self.botActivityList.scrollToItem(item)

        

def guiMain(autostart = False):
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create("plastique"))
    window = MainWindow()
    window.show()
    if autostart:
        window.startClicked()
    app.exec_()
    