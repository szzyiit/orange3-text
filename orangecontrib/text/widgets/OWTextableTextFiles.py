"""
Class OWTextableTextFiles
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

__version__ = '0.17.10'


import codecs
import os
import re
from unicodedata import normalize

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QFileDialog

from chardet.universaldetector import UniversalDetector

from LTTL.Segmentation import Segmentation
from LTTL.Input import Input
import LTTL.Segmenter as Segmenter

from .TextableUtils import (
    OWTextableBaseWidget, VersionedSettingsHandler, ProgressBar,
    InfoBox, SendButton, AdvancedSettings,
    addSeparatorAfterDefaultEncodings, addAutoDetectEncoding,
    getPredefinedEncodings, pluralize
)

from Orange.widgets import gui, settings
from Orange.widgets.utils.signals import Output

CHUNK_LENGTH = 1000000
CHUNK_NUM = 100


class OWTextableTextFiles(OWTextableBaseWidget):
    """Orange widget for loading text files"""

    name = "XML 文件导入(XML Import)"
    description = "导入一个或者多个 XML 文件"
    icon = "icons/xml.png"
    priority = 2

    # Input and output channels...
    # inputs = [
    #     ('Message', JSONMessage, "inputMessage", widget.Single)
    # ]
    # outputs = [('Text data', Segmentation)]

    class Outputs:
        data = Output('文本数据(Text data)', Segmentation, replaces=['Text data'])

    settingsHandler = VersionedSettingsHandler(
        version=__version__.rsplit(".", 1)[0]
    )

    # Settings...
    files = settings.Setting([])
    encoding = settings.Setting('(auto-detect)')
    autoNumber = settings.Setting(False)
    # autoNumberKey = settings.Setting(u'num')
    importFilenames = settings.Setting(True)
    # importFilenamesKey = settings.Setting(u'filename')
    lastLocation = settings.Setting('.')
    displayAdvancedSettings = settings.Setting(False)
    file = settings.Setting(u'')

    want_main_area = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Other attributes...
        self.segmentation = None
        self.createdInputs = list()
        self.fileLabels = list()
        self.selectedFileLabels = list()
        self.newFiles = u''
        self.newAnnotationKey = u''
        self.newAnnotationValue = u''
        self.infoBox = InfoBox(widget=self.controlArea)
        self.sendButton = SendButton(
            widget=self.controlArea,
            master=self,
            callback=self.sendData,
            infoBoxAttribute='infoBox',
            sendIfPreCallback=self.updateGUI,
        )
        self.advancedSettings = AdvancedSettings(
            widget=self.controlArea,
            master=self,
            callback=self.sendButton.settingsChanged,
        )

        # GUI...

        # Advanced settings checkbox...
        self.advancedSettings.draw()

        # BASIC GUI...

        # Basic file box
        basicFileBox = gui.widgetBox(
            widget=self.controlArea,
            box=u'文件',
            orientation='vertical',
            addSpace=False,
        )
        basicFileBoxLine1 = gui.widgetBox(
            widget=basicFileBox,
            box=False,
            orientation='horizontal',
        )
        gui.lineEdit(
            widget=basicFileBoxLine1,
            master=self,
            value='file',
            orientation='horizontal',
            label=u'文件路径:',
            labelWidth=101,
            callback=self.sendButton.settingsChanged,
            tooltip=(
                u"文件路径."
            ),
        )
        gui.separator(widget=basicFileBoxLine1, width=5)
        gui.button(
            widget=basicFileBoxLine1,
            master=self,
            label=u'浏览',
            callback=self.browse,
            tooltip=(
                u"浏览以打开文件."
            ),
        )
        gui.separator(widget=basicFileBox, width=3)
        advancedEncodingsCombobox = gui.comboBox(
            widget=basicFileBox,
            master=self,
            value='encoding',
            items=getPredefinedEncodings(),
            sendSelectedValue=True,
            orientation='horizontal',
            label=u'编码:',
            labelWidth=101,
            callback=self.sendButton.settingsChanged,
            tooltip=(
                u"选择文件编码."
            ),
        )
        addSeparatorAfterDefaultEncodings(advancedEncodingsCombobox)
        addAutoDetectEncoding(advancedEncodingsCombobox)
        gui.separator(widget=basicFileBox, width=3)
        self.advancedSettings.basicWidgets.append(basicFileBox)
        self.advancedSettings.basicWidgetsAppendSeparator()

        # ADVANCED GUI...

        # File box
        fileBox = gui.widgetBox(
            widget=self.controlArea,
            box=u'文件',
            orientation='vertical',
            addSpace=False,
        )
        fileBoxLine1 = gui.widgetBox(
            widget=fileBox,
            box=False,
            orientation='horizontal',
            addSpace=True,
        )
        self.fileListbox = gui.listBox(
            widget=fileBoxLine1,
            master=self,
            value='selectedFileLabels',
            labels='fileLabels',
            callback=self.updateFileBoxButtons,
            tooltip=(
                u"The list of files whose content will be imported.\n"
                u"\nIn the output segmentation, the content of each\n"
                u"file appears in the same position as in the list.\n"
                u"\nColumn 1 shows the file's name.\n"
                u"Column 2 shows the file's annotation (if any).\n"
                u"Column 3 shows the file's encoding."
            ),
        )
        font = QFont()
        font.setFamily('Courier')
        font.setStyleHint(QFont.Courier)
        font.setPixelSize(12)
        self.fileListbox.setFont(font)
        fileBoxCol2 = gui.widgetBox(
            widget=fileBoxLine1,
            orientation='vertical',
        )
        self.moveUpButton = gui.button(
            widget=fileBoxCol2,
            master=self,
            label=u'上移',
            callback=self.moveUp,
            tooltip=(
                u"Move the selected file upward in the list."
            ),
        )
        self.moveDownButton = gui.button(
            widget=fileBoxCol2,
            master=self,
            label=u'下移',
            callback=self.moveDown,
            tooltip=(
                u"Move the selected file downward in the list."
            ),
        )
        self.removeButton = gui.button(
            widget=fileBoxCol2,
            master=self,
            label=u'移除',
            callback=self.remove,
            tooltip=(
                u"Remove the selected file from the list."
            ),
        )
        self.clearAllButton = gui.button(
            widget=fileBoxCol2,
            master=self,
            label=u'清除所有',
            callback=self.clearAll,
            tooltip=(
                u"Remove all files from the list."
            ),
        )
        fileBoxLine2 = gui.widgetBox(
            widget=fileBox,
            box=False,
            orientation='vertical',
        )
        # Add file box
        addFileBox = gui.widgetBox(
            widget=fileBoxLine2,
            box=True,
            orientation='vertical',
        )
        addFileBoxLine1 = gui.widgetBox(
            widget=addFileBox,
            orientation='horizontal',
        )
        gui.lineEdit(
            widget=addFileBoxLine1,
            master=self,
            value='newFiles',
            orientation='horizontal',
            label=u'文件路径',
            labelWidth=101,
            callback=self.updateGUI,
            tooltip=(
                u"The paths of the files that will be added to the\n"
                u"list when button 'Add' is clicked.\n\n"
                u"Successive paths must be separated with ' / ' \n"
                u"(whitespace + slash + whitespace). Their order in\n"
                u"the list will be the same as in this field."
            ),
        )
        gui.separator(widget=addFileBoxLine1, width=5)
        gui.button(
            widget=addFileBoxLine1,
            master=self,
            label=u'浏览',
            callback=self.browse,
            tooltip=(
                u"Open a dialog for selecting files.\n\n"
                u"To select multiple files at once, either draw a\n"
                u"selection box around them, or use shift and/or\n"
                u"ctrl + click.\n\n"
                u"Selected file paths will appear in the field to\n"
                u"the left of this button afterwards, ready to be\n"
                u"added to the list when button 'Add' is clicked."
            ),
        )
        gui.separator(widget=addFileBox, width=3)
        basicEncodingsCombobox = gui.comboBox(
            widget=addFileBox,
            master=self,
            value='encoding',
            items=getPredefinedEncodings(),
            sendSelectedValue=True,
            orientation='horizontal',
            label=u'编码:',
            labelWidth=101,
            callback=self.updateGUI,
            tooltip=(
                u"Select input file(s) encoding."
            ),
        )
        addSeparatorAfterDefaultEncodings(basicEncodingsCombobox)
        addAutoDetectEncoding(basicEncodingsCombobox)
        self.encoding = self.encoding
        gui.separator(widget=addFileBox, width=3)
        gui.lineEdit(
            widget=addFileBox,
            master=self,
            value='newAnnotationKey',
            orientation='horizontal',
            label=u'注释 key:',
            labelWidth=101,
            callback=self.updateGUI,
            tooltip=(
                u"This field lets you specify a custom annotation\n"
                u"key associated with each file that is about to be\n"
                u"added to the list."
            ),
        )
        gui.separator(widget=addFileBox, width=3)
        gui.lineEdit(
            widget=addFileBox,
            master=self,
            value='newAnnotationValue',
            orientation='horizontal',
            label=u'注释 value:',
            labelWidth=101,
            callback=self.updateGUI,
            tooltip=(
                u"This field lets you specify the annotation value\n"
                u"associated with the above annotation key."
            ),
        )
        gui.separator(widget=addFileBox, width=3)
        self.addButton = gui.button(
            widget=addFileBox,
            master=self,
            label=u'添加',
            callback=self.add,
            tooltip=(
                u"Add the file(s) currently displayed in the\n"
                u"'Files' text field to the list.\n\n"
                u"Each of these files will be associated with the\n"
                u"specified encoding and annotation (if any).\n\n"
                u"Other files may be selected afterwards and\n"
                u"assigned a different encoding and annotation."
            ),
        )
        self.advancedSettings.advancedWidgets.append(fileBox)
        self.advancedSettings.advancedWidgetsAppendSeparator()


        gui.rubber(self.controlArea)

        # Send button...
        self.sendButton.draw()

        # Info box...
        self.infoBox.draw()

        self.adjustSizeWithTimer()
        QTimer.singleShot(0, self.sendButton.sendIf)


    def sendData(self):

        """Load files, create and send segmentation"""

        # Check that there's something on input...
        if (
            (self.displayAdvancedSettings and not self.files) or
            not (self.file or self.displayAdvancedSettings)
        ):
            self.infoBox.setText(u'请选择输入文件.', 'warning')
            self.Outputs.data.send(self.segmentation)
            return


        # Clear created Inputs...
        self.clearCreatedInputs()

        fileContents = list()
        annotations = list()
        counter = 1

        if self.displayAdvancedSettings:
            myFiles = self.files
        else:
            myFiles = [[self.file, self.encoding, u'', u'']]

        self.infoBox.setText(u"正在处理, 请稍等...", "warning")
        self.controlArea.setDisabled(True)
        progressBar = ProgressBar(
            self,
            iterations=len(myFiles)
        )

        # Open and process each file successively...
        for myFile in myFiles:
            filePath = myFile[0]
            encoding = myFile[1]
            encoding = re.sub(r"[ ]\(.+", "", encoding)
            annotation_key = myFile[2]
            annotation_value = myFile[3]

            # Try to open the file...
            self.error()
            try:
                if encoding == "(auto-detect)":
                    detector = UniversalDetector()
                    fh = open(filePath, 'rb')
                    for line in fh:
                        detector.feed(line)
                        if detector.done: break
                    detector.close()
                    fh.close()
                    encoding = detector.result['encoding']
                fh = open(
                    filePath,
                    mode='rU',
                    encoding=encoding,
                )
                try:
                    fileContent = ""
                    i = 0
                    chunks = list()
                    for chunk in iter(lambda: fh.read(CHUNK_LENGTH), ""):
                        chunks.append('\n'.join(chunk.splitlines()))
                        i += CHUNK_LENGTH
                        if i % (CHUNK_NUM * CHUNK_LENGTH) == 0:
                            fileContent += "".join(chunks)
                            chunks = list()
                    if len(chunks):
                        fileContent += "".join(chunks)
                    del chunks
                except UnicodeError:
                    progressBar.finish()
                    if len(myFiles) > 1:
                        message = f"请为文件 '{filePath}' 请选择其他编码."
                    else:
                        message = u"请选择其他编码."
                    self.infoBox.setText(message, 'error')
                    # self.send('Text data', None, self)
                    self.Outputs.data.send(None)
                    self.controlArea.setDisabled(False)
                    return
                finally:
                    fh.close()
            except IOError:
                progressBar.finish()
                if len(myFiles) > 1:
                    message = u"无法打开文件: '%s'." % filePath
                else:
                    message = u"无法打开文件."
                self.infoBox.setText(message, 'error')
                # self.send('Text data', None, self)
                self.Outputs.data.send(self.segmentation)
                self.controlArea.setDisabled(False)
                return

            # Remove utf-8 BOM if necessary...
            if encoding == u'utf-8':
                fileContent = fileContent.lstrip(
                    codecs.BOM_UTF8.decode('utf-8')
                )

            # Normalize text (canonical decomposition then composition)...
            fileContent = normalize('NFC', fileContent)

            fileContents.append(fileContent)

            # Annotations...
            annotation = dict()
            if self.displayAdvancedSettings:
                if annotation_key and annotation_value:
                    annotation[annotation_key] = annotation_value
            annotations.append(annotation)
            progressBar.advance()

        # Create an LTTL.Input for each file...
        if len(fileContents) == 1:
            label = self.captionTitle
        else:
            label = None
        for index in range(len(fileContents)):
            myInput = Input(fileContents[index], label)
            segment = myInput[0]
            segment.annotations.update(annotations[index])
            myInput[0] = segment
            self.createdInputs.append(myInput)

        # If there's only one file, the widget's output is the created Input.
        if len(fileContents) == 1:
            self.segmentation = self.createdInputs[0]
        # Otherwise the widget's output is a concatenation...
        else:
            self.segmentation = Segmenter.concatenate(
                segmentations=self.createdInputs,
                label=self.captionTitle,
                copy_annotations=True,
                import_labels_as=None,
                sort=False,
                auto_number_as=None,
                merge_duplicates=False,
                progress_callback=None,
            )

        message = u'%i 个segment 发送到输出 ' % len(self.segmentation)
        message = pluralize(message, len(self.segmentation))
        numChars = 0
        for segment in self.segmentation:
            segmentLength = len(Segmentation.get_data(segment.str_index))
            numChars += segmentLength
        message += u'(%i character@p).' % numChars
        message = pluralize(message, numChars)
        self.infoBox.setText(message)
        progressBar.finish()
        self.controlArea.setDisabled(False)

        # self.send('Text data', self.segmentation, self)
        self.Outputs.data.send(self.segmentation)
        self.sendButton.resetSettingsChangedFlag()

    def clearCreatedInputs(self):
        for i in self.createdInputs:
            Segmentation.set_data(i[0].str_index, None)
        del self.createdInputs[:]


    def browse(self):
        """Display a FileDialog and select files"""
        if self.displayAdvancedSettings:
            filePathList, _ = QFileDialog.getOpenFileNames(
                self,
                u'选择文件',
                self.lastLocation,
                u'XML 文件(*.xml)'
            )
            if not filePathList:
                return
            filePathList = [os.path.normpath(f) for f in filePathList]
            self.newFiles = u' / '.join(filePathList)
            self.lastLocation = os.path.dirname(filePathList[-1])
            self.updateGUI()
        else:
            filePath, _ = QFileDialog.getOpenFileName(
                self,
                u'打开文件',
                self.lastLocation,
                u'XML 文件(*.xml)'
            )
            if not filePath:
                return
            self.file = os.path.normpath(filePath)
            self.lastLocation = os.path.dirname(filePath)
            self.updateGUI()
            self.sendButton.settingsChanged()

    def moveUp(self):
        """Move file upward in Files listbox"""
        if self.selectedFileLabels:
            index = self.selectedFileLabels[0]
            if index > 0:
                temp = self.files[index-1]
                self.files[index-1] = self.files[index]
                self.files[index] = temp
                self.selectedFileLabels = [index-1]
                self.sendButton.settingsChanged()

    def moveDown(self):
        """Move file downward in Files listbox"""
        if self.selectedFileLabels:
            index = self.selectedFileLabels[0]
            if index < len(self.files) - 1:
                temp = self.files[index+1]
                self.files[index+1] = self.files[index]
                self.files[index] = temp
                self.selectedFileLabels = [index+1]
                self.sendButton.settingsChanged()

    def clearAll(self):
        """Remove all files from files attr"""
        del self.files[:]
        del self.selectedFileLabels[:]
        self.sendButton.settingsChanged()

    def remove(self):
        """Remove file from files attr"""
        if self.selectedFileLabels:
            index = self.selectedFileLabels[0]
            self.files.pop(index)
            del self.selectedFileLabels[:]
            self.sendButton.settingsChanged()

    def add(self):
        """Add files to files attr"""
        filePathList = re.split(r' +/ +', self.newFiles)
        for filePath in filePathList:
            encoding = re.sub(r"[ ]\(.+", "", self.encoding)
            self.files.append((
                filePath,
                encoding,
                self.newAnnotationKey,
                self.newAnnotationValue,
            ))
        self.sendButton.settingsChanged()

    def updateGUI(self):
        """Update GUI state"""
        if self.displayAdvancedSettings:
            if self.selectedFileLabels:
                cachedLabel = self.selectedFileLabels[0]
            else:
                cachedLabel = None
            del self.fileLabels[:]
            if self.files:
                filePaths = [f[0] for f in self.files]
                filenames = [os.path.basename(p) for p in filePaths]
                encodings = [f[1] for f in self.files]
                annotations = ['{%s: %s}' % (f[2], f[3]) for f in self.files]
                maxFilenameLen = max([len(n) for n in filenames])
                maxAnnoLen = max([len(a) for a in annotations])
                for index in range(len(self.files)):
                    format = u'%-' + str(maxFilenameLen + 2) + u's'
                    fileLabel = format % filenames[index]
                    if maxAnnoLen > 4:
                        if len(annotations[index]) > 4:
                            format = u'%-' + str(maxAnnoLen + 2) + u's'
                            fileLabel += format % annotations[index]
                        else:
                            fileLabel += u' ' * (maxAnnoLen + 2)
                    fileLabel += encodings[index]
                    self.fileLabels.append(fileLabel)
            self.fileLabels = self.fileLabels
            if cachedLabel is not None:
                self.sendButton.sendIfPreCallback = None
                self.selectedFileLabels = [cachedLabel]
                self.sendButton.sendIfPreCallback = self.updateGUI
            if self.newFiles:
                if (
                    (self.newAnnotationKey and self.newAnnotationValue) or
                    (not self.newAnnotationKey and not self.newAnnotationValue)
                ):
                    self.addButton.setDisabled(False)
                else:
                    self.addButton.setDisabled(True)
            else:
                self.addButton.setDisabled(True)
            self.updateFileBoxButtons()
            self.advancedSettings.setVisible(True)
        else:
            self.advancedSettings.setVisible(False)

    def updateFileBoxButtons(self):
        """Update state of File box buttons"""
        if self.selectedFileLabels:
            self.removeButton.setDisabled(False)
            if self.selectedFileLabels[0] > 0:
                self.moveUpButton.setDisabled(False)
            else:
                self.moveUpButton.setDisabled(True)
            if self.selectedFileLabels[0] < len(self.files) - 1:
                self.moveDownButton.setDisabled(False)
            else:
                self.moveDownButton.setDisabled(True)
        else:
            self.moveUpButton.setDisabled(True)
            self.moveDownButton.setDisabled(True)
            self.removeButton.setDisabled(True)
        if len(self.files):
            self.clearAllButton.setDisabled(False)
            # self.exportButton.setDisabled(False)
        else:
            self.clearAllButton.setDisabled(True)
            # self.exportButton.setDisabled(True)

    def setCaption(self, title):
        if 'captionTitle' in dir(self):
            changed = title != self.captionTitle
            super().setCaption(title)
            if changed:
                self.sendButton.settingsChanged()
        else:
            super().setCaption(title)

    def onDeleteWidget(self):
        self.clearCreatedInputs()


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    appl = QApplication(sys.argv)
    ow = OWTextableTextFiles()
    ow.show()
    appl.exec_()
    ow.saveSettings()
