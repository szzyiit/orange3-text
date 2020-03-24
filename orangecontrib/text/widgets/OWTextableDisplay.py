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

from PyQt5.QtWidgets import QTextBrowser, QApplication
from PyQt5.QtCore import QUrl

from LTTL.Segmentation import Segmentation
from LTTL.Input import Input as LInput
import LTTL.Segmenter as Segmenter

from .TextableUtils import (
    OWTextableBaseWidget, VersionedSettingsHandler, ProgressBar,
    getPredefinedEncodings
)

from Orange.widgets import gui 
from Orange.widgets.utils.signals import Input


class OWTextableDisplay(OWTextableBaseWidget):
    """A widget for displaying segmentations"""
    name = "查看(Display)"
    description = "查看文本分段数据"
    icon = "icons/Display.png"

    priority = 6001

    class Inputs:
        data = Input("分段(Segmentation)", Segmentation, replaces=["Segmentation"])


    settingsHandler = VersionedSettingsHandler(
        version=__version__.rsplit(".", 1)[0]
    )
    # Settings...

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
        self.goto = 0
        self.browser = QTextBrowser()
        # self.infoBox = InfoBox(widget=self.mainArea)
        

        # GUI...

        self.navigationBox = gui.widgetBox(
            widget=self.mainArea,
            orientation='vertical',
            box=u'导航',
            addSpace=True,
        )
        self.gotoSpin = gui.spin(
            widget=self.navigationBox,
            master=self,
            value='goto',
            minv=1,
            maxv=1,
            orientation='horizontal',
            label=u'到第几部分:',
            labelWidth=180,
            callback=self.gotoSegment,
        )
        self.mainArea.layout().addWidget(self.browser)


    @Inputs.data
    def inputData(self, newInput):
        """Process incoming data."""
        self.segmentation = newInput
        self.updateGUI()

    def updateGUI(self):
        """Update GUI state"""
        if self.segmentation:
            self.controlArea.setDisabled(True)
            self.mainArea.setDisabled(True)

            self.navigationBox.setVisible(True)
            self.warning()
            self.error()
            progressBar = ProgressBar(
                self,
                iterations=len(self.segmentation)
            )
            displayedString, summarized = self.segmentation.to_html(
                True,
                progressBar.advance,
            )
            self.navigationBox.setEnabled(
                len(self.segmentation) > 1 and not summarized
            )
            self.browser.append(displayedString)
            self.displayedSegmentation.update(
                displayedString,
                label=self.captionTitle,
            )
            self.gotoSpin.setRange(1, len(self.segmentation))
            if self.goto:
                self.browser.setSource(QUrl("#%i" % self.goto))
            else:
                self.browser.setSource(QUrl("#top"))
            progressBar.finish()

            self.controlArea.setDisabled(False)
            self.mainArea.setDisabled(False)

        else:
            self.goto = 0
            self.gotoSpin.setRange(0, 1)
            self.navigationBox.setVisible(True)
            self.navigationBox.setEnabled(False)

    def gotoSegment(self):
        if self.goto:
            self.browser.setSource(QUrl("#%i" % self.goto))
        else:
            self.browser.setSource(QUrl("#top"))



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
    ow = OWTextableDisplay()
    ow.show()
    seg1 = LInput(u'hello world', label=u'text1')
    seg2 = LInput(u'cruel world', label=u'text2')
    seg3 = Segmenter.concatenate([seg1, seg2], label=u'corpus')
    seg4 = Segmenter.tokenize(seg3, [(r'\w+(?u)', u'tokenize')], label=u'words')
    ow.inputData(seg4)
    appl.exec_()
