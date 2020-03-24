"""
Class OWTextableExtractXML
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

__version__ = '0.15.7'

import LTTL.Segmenter as Segmenter
from LTTL.Segmentation import Segmentation

from .TextableUtils import (
    OWTextableBaseWidget, VersionedSettingsHandler, ProgressBar,
    pluralize,SendButton, InfoBox
)

from Orange.widgets import gui, settings
from Orange.widgets.utils.signals import Output, Input


class OWTextableExtractXML(OWTextableBaseWidget):
    """Orange widget for xml markup extraction"""

    name = "提取 XML (Extract XML)"
    description = "提取 XML 标签"
    icon = "icons/ExtractXML.png"
    priority = 4005

    # Input and output channels...
    class Inputs:
        data = Input("分段(Segmentation)", Segmentation, replaces=["Segmentation"])

    class Outputs:
        data = Output('提取的数据(Extracted data)', Segmentation, replaces=['Extracted data'])

    settingsHandler = VersionedSettingsHandler(
        version=__version__.rsplit(".", 1)[0]
    )
    # Settings...
    conditions = settings.Setting([])
    importAnnotations = settings.Setting(True)
    autoNumber = settings.Setting(False)
    element = settings.Setting(u'')
    mergeDuplicates = settings.Setting(False)
    preserveLeaves = settings.Setting(False)
    deleteMarkup = settings.Setting(False)

    want_main_area = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.label = u'extracted_xml'
        self.importElement = False

        # Other attributes...
        self.inputSegmentation = None
        self.conditionsLabels = list()
        self.selectedConditionsLabels = list()
        self.newConditionAttribute = u''
        self.newConditionRegex = r''
        self.ignoreCase = False
        self.unicodeDependent = True
        self.multiline = False
        self.dotAll = False
        self.infoBox = InfoBox(widget=self.controlArea)
        self.sendButton = SendButton(
            widget=self.controlArea,
            master=self,
            callback=self.sendData,
            infoBoxAttribute='infoBox',
        )

        # (Basic) XML extraction box
        basicXmlExtractionBox = gui.widgetBox(
            widget=self.controlArea,
            box=u'XML 提取',
            orientation='vertical',
            addSpace=False,
        )
        gui.lineEdit(
            widget=basicXmlExtractionBox,
            master=self,
            value='element',
            orientation='horizontal',
            label=u'XML 元素:',
            labelWidth=180,
            callback=self.sendButton.settingsChanged,
            tooltip=(
                u"将提取 XML 元素"
            ),
        )
        # Send button...
        self.sendButton.draw()

        # Info box...
        self.infoBox.draw()

        self.sendButton.sendIf()
        self.adjustSizeWithTimer()

    def sendData(self):

        """(Have LTTL.Segmenter) perform the actual tokenization"""

        # Check that there's something on input...
        if not self.inputSegmentation:
            self.infoBox.setText(u'无输入.', 'warning')
            self.Outputs.data.send(None)
            return

        # Check that element field is not empty...
        if not self.element:
            self.infoBox.setText(u'请输入 XML 元素', 'warning')
            self.Outputs.data.send(None)
            return

        # TODO: update docs to indicate that angle brackets are optional
        # TODO: remove message 'No label was provided.' from docs

        num_iterations = len(self.inputSegmentation)

        # Prepare conditions...
        conditions = dict()
        importAnnotations = True
        mergeDuplicates = False
        preserveLeaves = False

        # Perform tokenization...
        self.controlArea.setDisabled(True)
        self.infoBox.setText(u"正在处理, 请稍等...", "warning")
        progressBar = ProgressBar(
            self,
            iterations=num_iterations
        )
        try:
            xml_extracted_data = Segmenter.import_xml(
                segmentation=self.inputSegmentation,
                element=self.element,
                conditions=conditions,
                label=self.captionTitle,
                import_annotations=importAnnotations,
                remove_markup=self.deleteMarkup,
                merge_duplicates=mergeDuplicates,
                preserve_leaves=preserveLeaves,
                progress_callback=progressBar.advance,
            )
            message = u'发送 %i 个片段.' % len(xml_extracted_data)
            message = pluralize(message, len(xml_extracted_data))
            self.infoBox.setText(message)
            self.Outputs.data.send(xml_extracted_data)
        except ValueError:
            self.infoBox.setText(
                message=u'请确认输入 XML 格式正确.',
                state='error',
            )
            self.Outputs.data.send(None)
        self.sendButton.resetSettingsChangedFlag()
        progressBar.finish()
        self.controlArea.setDisabled(False)

    @Inputs.data
    def set_inputData(self, segmentation):
        """Process incoming segmentation"""
        self.inputSegmentation = segmentation
        self.infoBox.inputChanged()
        self.sendButton.sendIf()


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    appl = QApplication(sys.argv)
    ow = OWTextableExtractXML()
    ow.show()
    appl.exec_()
    ow.saveSettings()
