"""
Class OWTextableDisplay
Copyright 2012-2019 LangTech Sarl (info@langtech.ch)
-----------------------------------------------------------------------------
This file is part of the Orange3-Textable package.

Orange3-Textable is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Orange3-Textable is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Orange3-Textable. If not, see <http://www.gnu.org/licenses/>.
"""

__version__ = '0.16.11'

import sys
import os
import codecs
import re

from PyQt5.QtWidgets import QTextBrowser, QFileDialog, QMessageBox, QApplication

from LTTL.Segmentation import Segmentation
from LTTL.Input import Input as LInput
import LTTL.Segmenter as Segmenter

from .TextableUtils import (
    OWTextableBaseWidget, VersionedSettingsHandler, ProgressBar,
    SendButton, InfoBox, getPredefinedEncodings, pluralize,
    addSeparatorAfterDefaultEncodings
)

from Orange.widgets import gui, settings
from Orange.widgets.utils.signals import Output, Input


class OWTextableExporter(OWTextableBaseWidget):
    """A widget for converting and exporting"""
    name = "转换和导出(Converter & Exporter)"
    description = " 转换格式和导出文件"
    icon = "icons/Convert.png"

    priority = 6001

    class Inputs:
        data = Input("分段(Segmentation)", Segmentation, replaces=["Segmentation"])

    class Outputs:
        bypassed_data = Output('未处理数据(Bypassed segmentation)', 
                                Segmentation, 
                                replaces=['Bypassed segmentation'],
                                default=True)
        converted_data = Output('处理的数据(Converted segmentation)', 
                                Segmentation, 
                                replaces=['Displayed segmentation', 'Converted segmentation'])

    settingsHandler = VersionedSettingsHandler(
        version=__version__.rsplit(".", 1)[0]
    )
    # Settings...
    customFormat = settings.Setting(u'%(__content__)s')
    segmentDelimiter = settings.Setting(u'\\n')
    encoding = settings.Setting('utf8')
    lastLocation = settings.Setting('.')

    # Predefined list of available encodings...
    encodings = getPredefinedEncodings()

    want_main_area = True

    def __init__(self, *args, **kwargs):
        """Initialize a Display widget"""
        super().__init__(*args, **kwargs)
        # Current general warning and error messages (as submited
        # through self.error(text) and self.warning(text)
        self._currentErrorMessage = ""
        self._currentWarningMessage = ""

        self.segmentation = None
        self.displayedSegmentation = LInput(
            label=u'displayed_segmentation',
            text=u''
        )
        self.browser = QTextBrowser()
        self.infoBox = InfoBox(widget=self.mainArea)
        self.sendButton = SendButton(
            widget=self.controlArea,
            master=self,
            callback=self.sendData,
            sendIfPreCallback=self.updateGUI,
            infoBoxAttribute='infoBox',
        )

        # GUI...

        formattingBox = gui.widgetBox(
            widget=self.controlArea,
            box=u'格式',
            orientation='vertical',
            addSpace=True,
        )
        gui.separator(widget=formattingBox, height=3)
        self.formattingIndentedBox = gui.indentedBox(
            widget=formattingBox,
        )
        gui.lineEdit(
            widget=self.formattingIndentedBox,
            master=self,
            value='customFormat',
            label=u'格式:',
            labelWidth=131,
            orientation='horizontal',
            callback=self.sendButton.settingsChanged,
        )

        self.advancedExportBox = gui.widgetBox(
            widget=self.controlArea,
            box=u'输出',
            orientation='vertical',
            addSpace=True,
        )
        encodingCombo = gui.comboBox(
            widget=self.advancedExportBox,
            master=self,
            value='encoding',
            items=type(self).encodings,
            sendSelectedValue=True,
            orientation='horizontal',
            label=u'文件编码:',
            labelWidth=151,
        )
        addSeparatorAfterDefaultEncodings(encodingCombo)
        gui.separator(widget=self.advancedExportBox, height=3)
        exportBoxLine2 = gui.widgetBox(
            widget=self.advancedExportBox,
            orientation='horizontal',
        )
        gui.button(
            widget=exportBoxLine2,
            master=self,
            label=u'输出到文件',
            callback=self.exportFile,
        )

        gui.rubber(self.controlArea)

        # Send button and checkbox
        self.sendButton.draw()

        self.mainArea.layout().addWidget(self.browser)

        # Info box...
        self.infoBox.draw()

        self.sendButton.sendIf()

    @Inputs.data
    def inputData(self, newInput):
        """Process incoming data."""
        self.segmentation = newInput
        self.infoBox.inputChanged()
        self.sendButton.sendIf()

    def sendData(self):
        """Send segmentation to output"""
        if not self.segmentation:
            self.infoBox.setText(u'Widget needs input.', 'warning')
            self.Outputs.bypassed_data.send(None)
            self.Outputs.converted_data.send(None)
            return

        self.Outputs.bypassed_data.send(Segmenter.bypass(self.segmentation, self.captionTitle))
        # TODO: Check if this is correct replacement for textable v1.*, v2.*
        if 'format' in self._currentWarningMessage or \
                'format' in self._currentErrorMessage:
            # self.send('Displayed segmentation', None, self)
            self.Outputs.converted_data.send(None)
            return
        if len(self.displayedSegmentation[0].get_content()) > 0:
            self.Outputs.converted_data.send(self.displayedSegmentation)
            
        else:
            self.Outputs.converted_data.send(None)

        # TODO: Differes only in capitalization with a check before
        #       Is this intentional?
        if "Format" not in self._currentErrorMessage:
            message = u'%i segment@p sent to output.' % len(self.segmentation)
            message = pluralize(message, len(self.segmentation))
            self.infoBox.setText(message)
        self.sendButton.resetSettingsChangedFlag()

    def updateGUI(self):
        """Update GUI state"""
        self.controlArea.setVisible(True)
        self.browser.clear()
        if self.segmentation:

            self.controlArea.setDisabled(True)
            self.mainArea.setDisabled(True)
            self.infoBox.setText(u"Processing, please wait...", "warning")

            # self.navigationBox.setVisible(False)
            # self.navigationBox.setDisabled(True)
            self.advancedExportBox.setDisabled(True)
            self.formattingIndentedBox.setDisabled(False)
            displayedString = u''
            progressBar = ProgressBar(
                self,
                iterations=len(self.segmentation)
            )
            try:
                displayedString = self.segmentation.to_string(
                    codecs.decode(self.customFormat, 'unicode_escape'),
                    codecs.decode(self.segmentDelimiter, 'unicode_escape'),
                    codecs.decode('', 'unicode_escape'),
                    codecs.decode('', 'unicode_escape'),
                    True,
                    progress_callback=progressBar.advance,
                )
                self.infoBox.settingsChanged()
                self.advancedExportBox.setDisabled(False)
                self.warning()
                self.error()
            except TypeError as type_error:
                try:
                    self.infoBox.setText(type_error.message, 'error')
                except AttributeError:
                    message = "Please enter a valid format (type error)."
                    self.infoBox.setText(message, 'error')
            except KeyError:
                message = "Please enter a valid format (error: missing name)."
                self.infoBox.setText(message, 'error')
            except ValueError:
                message = "Please enter a valid format (error: missing "   \
                    + "variable type)."
                self.infoBox.setText(message, 'error')
            self.browser.append(displayedString)
            self.displayedSegmentation.update(
                displayedString,
                label=self.captionTitle,
            )
            progressBar.finish()

            self.controlArea.setDisabled(False)
            self.mainArea.setDisabled(False)


    def exportFile(self):
        """Display a FileDialog and export segmentation to file"""
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            u'Export segmentation to File',
            self.lastLocation,
        )
        if filePath:
            self.lastLocation = os.path.dirname(filePath)
            encoding = re.sub(r"[ ]\(.+", "", self.encoding)
            outputFile = codecs.open(
                filePath,
                encoding=encoding,
                mode='w',
                errors='xmlcharrefreplace',
            )
            outputFile.write(
                #normalizeCarriageReturns(
                    self.displayedSegmentation[0].get_content()
                #)
            )
            outputFile.close()
            QMessageBox.information(
                None,
                'Textable',
                'Segmentation correctly exported',
                QMessageBox.Ok
            )

    def onDeleteWidget(self):
        if self.displayedSegmentation is not None:
            self.displayedSegmentation.clear()

    def setCaption(self, title):
        if 'captionTitle' in dir(self):
            changed = title != self.captionTitle
            super().setCaption(title)
            if changed:
                self.sendButton.settingsChanged()
        else:
            super().setCaption(title)

    def error(self, *args, **kwargs):
        # Reimplemented to track the current active error message
        if args:
            text_or_id = args[0]
        else:
            text_or_id = kwargs.get("text_or_id", None)

        if isinstance(text_or_id, str) or text_or_id is None:
            self._currentErrorMessage = text_or_id or ""
        return super().error(*args, **kwargs)

    def warning(self, *args, **kwargs):
        # Reimplemented to track the current active warning message
        if args:
            text_or_id = args[0]
        else:
            text_or_id = kwargs.get("text_or_id", None)

        if isinstance(text_or_id, str) or text_or_id is None:
            self._currentWarningMessage = text_or_id or ""
        return super().warning(*args, **kwargs)


if __name__ == '__main__':
    appl = QApplication(sys.argv)
    ow = OWTextableExporter()
    ow.show()
    seg1 = LInput(u'hello world', label=u'text1')
    seg2 = LInput(u'cruel world', label=u'text2')
    seg3 = Segmenter.concatenate([seg1, seg2], label=u'corpus')
    seg4 = Segmenter.tokenize(seg3, [(r'\w+(?u)', u'tokenize')], label=u'words')
    ow.inputData(seg4)
    appl.exec_()
