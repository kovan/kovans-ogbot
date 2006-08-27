#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
#
#     Kovan's OGBot
#     Copyright (c) 2006 by kovan 
#
#     *************************************************************************
#     *                                                                       *
#     * This program is free software; you can redistribute it and/or modify  *
#     * it under the terms of the GNU General Public License as published by  *
#     * the Free Software Foundation; either version 2 of the License, or     *
#     * (at your option) any later version.                                   *
#     *                                                                       *
#     *************************************************************************
#

from OGBot import CONFIG_FILE

import sys
import os
import os.path
import shelve
import pickle
from Queue import *

import PyQt4
from PyQt4 import uic
from PyQt4.QtCore import QTimer,QObject, SIGNAL, SLOT, QProcess, Qt,QDir
from PyQt4.QtGui import *
import sip
sys.path.append('src/ui')

import OGBot
from HelperClasses import *
import BotResources

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
        QObject.connect(self.okButton,SIGNAL("clicked()"),self.saveOptions)
        self.attackingShipComboBox.addItems([shiptype for shiptype in SHIP_TYPES.keys()])
        self.config = Configuration(OGBot.CONFIG_FILE)
        try: self.config.load()
        except BotError: pass

        index = self.attackingShipComboBox.findText(self.config['attackingShip'])
        self.attackingShipComboBox.setCurrentIndex(index)
        
        for i in ['webpage','username','password']:
            control = getattr(self,i + "LineEdit")
            control.setText(self.config[i])
        for i in ['universe','attackRadio','probesToSend','minTheft']:            
            control = getattr(self,i + "SpinBox")
            control.setValue(int(self.config[i]))
        
    def saveOptions(self):
        
        if not self.usernameLineEdit.text() or not self.passwordLineEdit.text() or not self.webpageLineEdit.text():
            QMessageBox.critical(self,"Error","Required data missing")
            return
        
        self.config['attackingShip'] = self.attackingShipComboBox.currentText()
        for i in ['webpage','username','password']:
            control = getattr(self,i + "LineEdit")
            self.config[i] = control.text()
        for i in ['universe','attackRadio','probesToSend','minTheft']:            
            control = getattr(self,i + "SpinBox")
            self.config[i] = str(control.value())        
            
        self.config.save()
        self.accept()


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
        self.botActivityLabel.setBackgroundRole(QPalette.AlternateBase) # background of a ligh color
        self.setStatusBar(None)
        self.spyReportsTree.header().setResizeMode(QHeaderView.Stretch)
        
        self.planetsTree.header().setResizeMode(QHeaderView.Stretch)                 
        self.botActivityTree.header().setResizeMode(QHeaderView.Interactive)
        self.botActivityTree.header().setStretchLastSection(False)
        self.botActivityTree.header().resizeSection(1,60)                
        self.botActivityTree.header().resizeSection(4,65)        
        self.progressBar.setVisible(False)
                
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


        import WebAdapter
        try:
            file = open(WebAdapter.STATE_FILE,'r')
            self.server = pickle.load(file)        
            self.session = pickle.load(file)
            file.close()
        except IOError:
            self.server, self.session = '',''
            self.launchBrowserButton.setEnabled(False)
            
        config = Configuration(CONFIG_FILE)
        try: config.load()
        except BotError: self.showOptions()
        
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
                
                if msg.methodName is not "connectionError":
                    self.setConnectionOK()
                method = getattr(self,msg.methodName)
                method(*msg.args)
            except Empty:
                break
 
    def startClicked(self):
        if self.startButton.text() == "Start":
            if self.bot and self.bot.isAlive():
                self.bot.join()
            self.bot = OGBot.Bot(self)
            self.bot.start()
            self.botActivityLabel.setText("Starting bot...")
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
        self.startButton.setText("Start")
        self.botStatusLabel.setPalette(QPalette(MyColors.lightRed))
        self.botStatusLabel.setText("Stopped")        
        self.botActivityLabel.setText("Stopped")
        self.connectionStatusLabel.setText("")      
        self.connectionStatusLabel.setPalette(self.palette())
        
    def launchBrowser(self):
        command = "cmd /c start http://%s/game/index.php?session=%s" % (self.server,self.session)
        QProcess(self).start(command)
        
    def viewLog(self):
        command = 'cmd /c start "%s"' % OGBot.LOG_FILE
        QProcess(self).start(command)

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
        filterText     = str(self.planetFilterLineEdit.text())
        columnToFilter = str(self.planetFilterComboBox.currentText())
        self.planetsTree.clear()
        self._planetDb = PlanetDb(OGBot.PLANETDB_FILE)
                
        for planet in self._planetDb.readAll():
            attrName = re.sub(r" (\w)",lambda m: m.group(0).upper().strip(),columnToFilter.lower()) # convert names from style "Player status" to style "playerStatus"
            columnValue = str(getattr(planet,attrName))
            spyReportCount = str(len(planet.spyReports))
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
        self._planetDb_fillReportsTree(planet.spyReports)
        
    def _planetDb_fillReportsTree(self,spyReports):
        if len(spyReports) == 0:
            return
        
        for spyReport in spyReports:
            res = spyReport.resources
            onlyHasMissiles = not spyReport.hasNonMissileDefense() and spyReport.hasDefense()
            if onlyHasMissiles: defense = "Only missiles"
            else: defense = spyReport.hasInfoAbout("defense")
            
            itemData = [spyReport.code,spyReport.date.strftime("%X %x"),str(spyReport.coords),str(res.metal),str(res.crystal),str(res.deuterium)]
            itemData += [spyReport.hasInfoAbout("fleet"),defense,spyReport.actionTook]            
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
        spyReport = [report for report in planet.spyReports if str(report.code) == codeStr][0]
        
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
        allPlanets = self._planetDb.readAll()
        allReports = [planet.spyReports[-1] for planet in allPlanets if len(planet.spyReports) > 0]
        self._planetDb_fillReportsTree(allReports)
        
    def initProgressBar(self, range):
        self.progressBar.setVisible(True)        
        self.progressBar.setMaximum(range)
        self.progressBar.reset()
    def increaseProgressBar(self):
        value = self.progressBar.value()
        self.progressBar.setValue(value + 1)    
        
    def addActivityTreeItem(self,coordsStr,texts,backColor):
        item = QTreeWidgetItem()
        self.botActivityTree.addTopLevelItem(item)        
        for i in range(len(texts)):
            item.setText(i,texts[i])
            item.setBackgroundColor(i,backColor)            
        self.botActivityTree.scrollToItem(item)        

            
    def setActivityTreeItem(self,coordsStr,texts,backColor):    
        item = self.botActivityTree.findItems(coordsStr,Qt.MatchContains,1)[-1]
        for i in range(len(texts)):
            item.setText(i,texts[i])
            item.setBackgroundColor(i,backColor)            
        self.botActivityTree.scrollToItem(item)        
        
    # bot events handler methods:
    # ------------------------------------------------------------------------
    
    def targetsSearchBegin(self,howMany): 
        self.botActivityLabel.setText("Searching %s target planets to attack..." % howMany)
        self.initProgressBar(howMany)
        
    def solarSystemAnalyzed(self,galaxy,solarSystem): pass          
    
    def targetPlanetFound(self,planet):
        self.increaseProgressBar()                
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["Queued for espionage"]
        self.addActivityTreeItem(str(planet.coords), texts, MyColors.lightYellow)

    def planetSkippedByPrecalculation(self,planet,reason):
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["Skipped because %s" % reason]
        self.addActivityTreeItem(str(planet.coords), texts, MyColors.veryLightGrey)
        
    def targetsSearchEnd(self):
        self.progressBar.setVisible(False)   
        self.botActivityLabel.setText("")
        
    def espionagesBegin(self,howMany):
        self.botActivityLabel.setText("Sending %s espionages" % howMany)
        self.initProgressBar(howMany)
        
    def probesSent(self,planet,howMany):
        self.increaseProgressBar()                
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["%s probes sent" % howMany]
        self.setActivityTreeItem(str(planet.coords), texts, MyColors.lightYellow)            
            
    def errorSendingProbes(self, planet, probesCount,reason): 
        self.increaseProgressBar()                
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["Error while sending probes: %s" % reason]
        self.setActivityTreeItem(str(planet.coords), texts, MyColors.lightRed)            
        
    def espionagesEnd(self):
        self.progressBar.setVisible(False)
        self.botActivityLabel.setText("")
    def waitForReportsBegin(self,howMany):
        self.botActivityLabel.setText("Waiting for all %s reports to arrive..." % howMany)
        self.progressBar.setVisible(False)        
    def waitForReportsEnd(self):
        self.botActivityLabel.setText("")
    def reportsAnalysisBegin(self,howMany):
        self.botActivityLabel.setText("Analyzing all %s reports..." % howMany)        
    def planetSkipped(self,planet,cause):
        self.increaseProgressBar()                
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["Skipped because it has %s" % cause]
        self.setActivityTreeItem(str(planet.coords), texts, MyColors.lightGrey)                            
        
    def reportsAnalysisEnd(self): 
        self.botActivityLabel.setText("")   
        items = self.botActivityTree.findItems("probes sent",Qt.MatchContains,5)
        if len(items) > 0:
            items[0].setText(5,"Queued for attack")
    def attacksBegin(self,howMany): 
        self.botActivityLabel.setText("Attacking %s planets" % howMany)
    def planetAttacked(self,planet,fleet,resources):
        self.increaseProgressBar()                
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["Attacked with %s for %s " % (fleet,resources)]
        self.setActivityTreeItem(str(planet.coords), texts, MyColors.lightGreen)            
                            
    def errorAttackingPlanet(self, planet, reason): 
        self.increaseProgressBar()                
        texts = [datetime.now().strftime("%X %x")] + planet.toStringList() + ["Errror while attacking: %s" % reason]
        self.setActivityTreeItem(str(planet.coords), texts, MyColors.lightRed)
                
    def attacksEnd(self): 
        self.progressBar.setVisible(False)        
        self.botActivityLabel.setText("")
    def waitForSlotBegin(self):
        self.botStatusLabel.setText("Fleet limit reached.\nWaiting...")
        self.botStatusLabel.setPalette(QPalette(MyColors.lightYellow))        
    def waitForSlotEnd(self):
        self.setBotStatusRunning()          
    def waitForShipsBegin(self, shipType):
        self.botStatusLabel.setText("No %ss \navailable. Waiting..." % shipType)        
        self.botStatusLabel.setPalette(QPalette(MyColors.lightYellow))             
    def waitForShipsEnd(self):
        self.setBotStatusRunning()                       
    def connectionError(self,reason):
        self.connectionStatusLabel.setText("Connection error")        
        self.connectionStatusLabel.setPalette(QPalette(MyColors.lightRed))
    def loggedIn(self,username,session):
        self.launchBrowserButton.setEnabled(True)
        self.session = session
    def fatalException(self,exception):
        self.stopClicked()
        QMessageBox.critical(self,"Fatal error","Critical error: %s" % exception)

def guiMain():
    app = QApplication(sys.argv)
    QApplication.setStyle(QStyleFactory.create("plastique"))
    window = MainWindow()
    window.show()
    app.exec_()
    