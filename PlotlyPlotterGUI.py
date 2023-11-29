from PyQt6 import QtWidgets, QtWebEngineWidgets
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import (QApplication, QLabel, QPushButton, QComboBox, QGridLayout, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QComboBox,
                             QGroupBox, QStyledItemDelegate)
from PyQt6.QtGui import QStandardItem
import pandas as pd
import plotly.express as px
import plotly, sys, os

class CheckableComboBox(QComboBox):
    # Yoann Quenach de Quivillic on https://gis.stackexchange.com/questions/350148/qcombobox-multiple-selection-pyqt5
    # Subclass Delegate to increase item height
    class Delegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            size.setHeight(20)
            return size

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make the combo editable to set a custom text, but readonly
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        # Make the lineedit the same color as QPushButton
        palette = QtWidgets.QApplication.instance().palette()
        # palette.setBrush(QPalette.Base, palette.button())
        self.lineEdit().setPalette(palette)

        # Use custom delegate
        self.setItemDelegate(CheckableComboBox.Delegate())

        # Update the text when an item is toggled
        self.model().dataChanged.connect(self.updateText)

        # Hide and show popup when clicking the line edit
        self.lineEdit().installEventFilter(self)
        self.closeOnLineEditClick = False

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

    def resizeEvent(self, event):
        # Recompute text to elide as needed
        self.updateText()
        super().resizeEvent(event)

    def eventFilter(self, object, event):

        if object == self.lineEdit():
            if event.type() == QEvent.Type.MouseButtonRelease:
                if self.closeOnLineEditClick:
                    self.hidePopup()
                else:
                    self.showPopup()
                return True
            return False

        if object == self.view().viewport():
            if event.type() == QEvent.Type.MouseButtonRelease:
                index = self.view().indexAt(event.pos())
                item = self.model().item(index.row())

                if item.checkState() == Qt.CheckState.Checked:
                    item.setCheckState(Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(Qt.CheckState.Checked)
                return True
        return False

    def showPopup(self):
        super().showPopup()
        # When the popup is displayed, a click on the lineedit should close it
        self.closeOnLineEditClick = True

    def hidePopup(self):
        super().hidePopup()
        # Used to prevent immediate reopening when clicking on the lineEdit
        self.startTimer(100)
        # Refresh the display text when closing
        self.updateText()

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable click on line edit
        self.killTimer(event.timerId())
        self.closeOnLineEditClick = False

    def updateText(self):
        texts = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.CheckState.Checked:
                texts.append(self.model().item(i).text())
        text = ", ".join(texts)

        # Compute elided text (with "...")
        # metrics = QFontMetrics(self.lineEdit().font())
        # elidedText = metrics.elidedText(text, Qt.ElideRight, self.lineEdit().width())
        # self.lineEdit().setText(elidedText)
        self.lineEdit().setText(text)

    def addItem(self, text, data=None):
        item = QStandardItem()
        item.setText(text)
        if data is None:
            item.setData(text)
        else:
            item.setData(data)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        self.model().appendRow(item)

    def addItems(self, texts, datalist=None):
        for i, text in enumerate(sorted(texts)):
            try:
                data = datalist[i]
            except (TypeError, IndexError):
                data = None
            self.addItem(text, data)

    def currentData(self):
        # Return the list of selected items data
        res = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.CheckState.Checked:
                res.append(self.model().item(i).data())
        return res

    def checkAll(self):
        # Check all items in the list
        for i in range(self.model().rowCount()):
            self.model().item(i).setCheckState(Qt.CheckState.Checked)

    def uncheckAll(self):
        # Check all items in the list
        for i in range(self.model().rowCount()):
            self.model().item(i).setCheckState(Qt.CheckState.Unchecked)

class appWindow(QWidget):
    def __init__(self, parent=None):
        super(appWindow, self).__init__(parent)
        self.setWindowTitle("Plotly Plotter GUI")
        self.setAcceptDrops(True)
        mainLayout = QGridLayout()

        self.plotPanel = QGroupBox("Plot Settings")
        plotPanelLayout = QVBoxLayout()
        xLabel = QLabel("Column for x-Axis:")
        self.xList = CheckableComboBox(self)
        yLabel = QLabel("Column for y-Axis:")
        self.yList = CheckableComboBox(self)
        groupLabel = QLabel("Column for Grouping:")
        self.groupList = CheckableComboBox(self)
        self.figureTypes = QComboBox()
        figureTypeLabel = QLabel("Type of Figure:")
        self.figureTypes.addItems(["Lines", "Scatter", "Bar"])
        self.exportSVG = QPushButton("Export SVG")
        plotPanelLayout.addWidget(xLabel)
        plotPanelLayout.addWidget(self.xList)
        plotPanelLayout.addWidget(yLabel)
        plotPanelLayout.addWidget(self.yList)
        plotPanelLayout.addWidget(groupLabel)
        plotPanelLayout.addWidget(self.groupList)
        plotPanelLayout.addWidget(figureTypeLabel)
        plotPanelLayout.addWidget(self.figureTypes)
        plotPanelLayout.addWidget(self.exportSVG)
        self.plotPanel.setLayout(plotPanelLayout)
        
        self.table = QTableWidget(self)
        self.table.setMaximumHeight(600)
        self.figure = QtWebEngineWidgets.QWebEngineView(self)
        self.figure.setMinimumHeight(200)
        mainLayout.addWidget(self.plotPanel, 0, 0, 2, 1)
        mainLayout.addWidget(self.table, 0, 1, 1, 1)
        mainLayout.addWidget(self.figure, 1, 1, 1, 1)
        self.setLayout(mainLayout)
        self.buttonResponse()

    def buttonResponse(self):
        self.xList.model().dataChanged.connect(self.plotUpdate)
        self.yList.model().dataChanged.connect(self.plotUpdate)
        self.groupList.model().dataChanged.connect(self.plotUpdate)
        self.figureTypes.currentTextChanged.connect(self.plotUpdate)
        self.figure.page().profile().downloadRequested.connect(self.saveFigure)
        self.exportSVG.clicked.connect(self.saveVector)
    
    def plotUpdate(self):
        xSelection = self.xList.currentData()
        ySelection = self.yList.currentData()
        gSelection = self.groupList.currentData()
        try:
            if gSelection == []:
                if self.figureTypes.currentText() == "Lines":
                    self.figureData = px.line(self.data, x = xSelection[0], y = ySelection[0])
                elif self.figureTypes.currentText() == "Scatter":
                    self.figureData = px.scatter(self.data, x = xSelection[0], y = ySelection[0])
                elif self.figureTypes.currentText() == "Bar":
                    self.figureData = px.bar(self.data, x = xSelection[0], y = ySelection[0])
            else:
                if self.figureTypes.currentText() == "Lines":
                    self.figureData = px.line(self.data, x = xSelection[0], y = ySelection[0], color = gSelection[0])
                elif self.figureTypes.currentText() == "Scatter":
                    self.figureData = px.scatter(self.data, x = xSelection[0], y = ySelection[0], color = gSelection[0])
                elif self.figureTypes.currentText() == "Bar":
                    self.figureData = px.bar(self.data, x = xSelection[0], y = ySelection[0], color = gSelection[0])
            self.figure.setHtml(self.figureData.to_html(include_plotlyjs='cdn'))
        except:
            pass
    
    def saveFigure(self, download):
        download.setDownloadDirectory("Images")
        download.setDownloadFileName("Figure.png")
        download.accept()
        return

    def saveVector(self):
        plotly.io.write_image(self.figureData, "Images/VectorFigure.svg")
        return
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ingore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                print(path)
                fileExt = os.path.splitext(path)[1]
                if fileExt == ".csv":
                    self.data = pd.read_csv(path)
                elif fileExt == ".xlsx":
                    self.data = pd.read_excel(path)
                else:
                    raise Exception("Unsupported file format.")
                self.table.setRowCount(self.data.shape[0])
                self.table.setColumnCount(self.data.shape[1])
                self.table.setHorizontalHeaderLabels([str(col) for col in self.data.columns])
                for row in range(self.data.shape[0]):
                    for col in range(self.data.shape[1]):
                        self.table.setItem(col, row, QTableWidgetItem(str(self.data.iloc[row, col])))
                self.xList.addItems([str(col) for col in self.data.columns])
                self.yList.addItems([str(col) for col in self.data.columns])
                self.groupList.addItems([str(col) for col in self.data.columns])
            event.accept()
        else:
            event.ignore()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    appInterface = appWindow()
    appInterface.show()
    sys.exit(app.exec())