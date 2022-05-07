import os
import numpy as np

from Orange.data import Table, StringVariable, Variable
from Orange.data.io import FileFormat
from Orange.widgets import gui
from Orange.widgets.utils.itemmodels import VariableListModel, DomainModel
from Orange.widgets.data.owselectcolumns import VariablesListItemView
from Orange.widgets.settings import Setting, ContextSetting,\
    DomainContextHandler
from Orange.widgets.widget import OWWidget, Msg, Input, Output
from Orange.widgets.utils.concurrent import TaskState, ConcurrentWidgetMixin
from orangecontrib.text.corpus import Corpus, get_sample_corpora_dir
from orangecontrib.text.widgets.utils import widgets, QSize


class OWCorpus(OWWidget, ConcurrentWidgetMixin):
    name = "语料库(Corpuls)"
    description = "载入文档语料库."
    icon = "icons/TextFile.svg"
    priority = 100
    keywords = ["yuliaoku"]
    replaces = ["orangecontrib.text.widgets.owloadcorpus.OWLoadCorpus"]
    category = '文本挖掘(Text Mining)'


    class Inputs:
        data = Input('数据(Data)', Table, replaces=['Data'])

    class Outputs:
        corpus = Output('语料库(Corpus)', Corpus, replaces=['Corpus'])

    want_main_area = False
    resizing_enabled = True

    dlgFormats = (
        "All readable files ({});;".format(
            '*' + ' *'.join(FileFormat.readers.keys())) +
        ";;".join("{} (*{})".format(f.DESCRIPTION, ' *'.join(f.EXTENSIONS))
                  for f in sorted(set(FileFormat.readers.values()),
                                  key=list(FileFormat.readers.values()).index)))

    settingsHandler = DomainContextHandler()

    recent_files = Setting([
        "book-excerpts.tab",
        "grimm-tales-selected.tab",
        "election-tweets-2016.tab",
        "friends-transcripts.tab",
        "andersen.tab",
    ])
    used_attrs = ContextSetting([])
    title_variable = ContextSetting("")

    class Error(OWWidget.Error):
        read_file = Msg("无法读取文件 {} ({})")
        no_text_features_used = Msg("至少需要使用一个文本特征.")
        corpus_without_text_features = Msg("语料库没有文本特征.")

    def __init__(self):
        OWWidget.__init__(self)
        ConcurrentWidgetMixin.__init__(self)

        self.corpus = None

        # Browse file box
        fbox = gui.widgetBox(self.controlArea, "语料库文件", orientation=0)
        self.file_widget = widgets.FileWidget(
            recent_files=self.recent_files, icon_size=(16, 16),
            on_open=self.open_file, dialog_format=self.dlgFormats,
            dialog_title='打开橙现智能文档语料库',
            reload_label='重载', browse_label='浏览',
            allow_empty=False, minimal_width=250,
        )
        fbox.layout().addWidget(self.file_widget)

        # dropdown to select title variable
        self.title_model = DomainModel(
            valid_types=(StringVariable,), placeholder="(无标题)")
        gui.comboBox(
            self.controlArea, self, "title_variable",
            box="标题变量", model=self.title_model,
            callback=self.update_feature_selection
        )

        # Used Text Features
        fbox = gui.widgetBox(self.controlArea, orientation=0)
        ubox = gui.widgetBox(fbox, "使用的文本特征")
        self.used_attrs_model = VariableListModel(enable_dnd=True)
        self.used_attrs_view = VariablesListItemView()
        self.used_attrs_view.setModel(self.used_attrs_model)
        ubox.layout().addWidget(self.used_attrs_view)

        aa = self.used_attrs_model
        aa.dataChanged.connect(self.update_feature_selection)
        aa.rowsInserted.connect(self.update_feature_selection)
        aa.rowsRemoved.connect(self.update_feature_selection)

        # Ignored Text Features
        ibox = gui.widgetBox(fbox, "忽略的文本特征")
        self.unused_attrs_model = VariableListModel(enable_dnd=True)
        self.unused_attrs_view = VariablesListItemView()
        self.unused_attrs_view.setModel(self.unused_attrs_model)
        ibox.layout().addWidget(self.unused_attrs_view)

        # Documentation Data Sets & Report
        box = gui.hBox(self.controlArea)
        self.browse_documentation = gui.button(
            box, self, "浏览文档语料库",
            callback=lambda: self.file_widget.browse(
                get_sample_corpora_dir()),
            autoDefault=False,
        )

        # load first file
        self.file_widget.select(0)

    def sizeHint(self):
        return QSize(400, 300)

    @Inputs.data
    def set_data(self, data):
        have_data = data is not None

        # Enable/Disable command when data from input
        self.file_widget.setEnabled(not have_data)
        self.browse_documentation.setEnabled(not have_data)

        if have_data:
            self.open_file(data=data)
        else:
            self.file_widget.reload()

    @staticmethod
    def _load_corpus(path: str, data: Table, state: TaskState) -> Corpus:
        state.set_status("Loading")
        corpus = None
        if data:
            corpus = Corpus.from_table(data.domain, data)
        elif path:
            corpus = Corpus.from_file(path)
            corpus.name = os.path.splitext(os.path.basename(path))[0]
        return corpus

    def open_file(self, path=None, data=None):
        self.closeContext()
        self.Error.clear()
        self.cancel()
        self.unused_attrs_model[:] = []
        self.used_attrs_model[:] = []
        self.start(self._load_corpus, path, data)

    def on_done(self, corpus: Corpus) -> None:
        self.corpus = corpus
        if corpus is None:
            return

        self._setup_title_dropdown()
        self.used_attrs = list(self.corpus.text_features)
        all_str_features = [f for f in self.corpus.domain.metas if f.is_string]
        if not all_str_features:
            self.Error.corpus_without_text_features()
            self.Outputs.corpus.send(None)
            return
        self.openContext(self.corpus)
        self.used_attrs_model.extend(self.used_attrs)
        self.unused_attrs_model.extend(
            [f for f in self.corpus.domain.metas
             if f.is_string and f not in self.used_attrs_model]
        )

    def on_exception(self, ex: Exception) -> None:
        if isinstance(ex, BaseException):
            self.Error.read_file(str(ex))
        else:
            raise ex

    def _setup_title_dropdown(self):
        self.title_model.set_domain(self.corpus.domain)

        # if title variable is already marked in a dataset set it as a title
        # variable
        title_var = list(filter(
            lambda x: x.attributes.get("title", False),
            self.corpus.domain.metas))
        if title_var:
            self.title_variable = title_var[0]
            return

        # if not title attribute use heuristic for selecting it
        v_len = np.vectorize(len)
        first_selection = (None, 0)  # value, uniqueness
        second_selection = (None, 100)  # value, avg text length

        variables = [v for v in self.title_model
                     if v is not None and isinstance(v, Variable)]

        for variable in sorted(
                variables, key=lambda var: var.name, reverse=True):
            # if there is title, heading, or filename attribute in corpus
            # heuristic should select them -
            # in order title > heading > filename - this is why we use sort
            if str(variable).lower() in ('title', 'heading', 'filename'):
                first_selection = (variable, 0)
                break

            # otherwise uniqueness and length counts
            column_values = self.corpus.get_column_view(variable)[0]
            average_text_length = v_len(column_values).mean()
            uniqueness = len(np.unique(column_values))

            # if the variable is short enough to be a title select one with
            # the highest number of unique values
            if uniqueness > first_selection[1] and average_text_length <= 30:
                first_selection = (variable, uniqueness)
            # else select the variable with shortest average text that is
            # shorter than 100 (if all longer than 100 leave empty)
            elif average_text_length < second_selection[1]:
                second_selection = (variable, average_text_length)

        if first_selection[0] is not None:
            self.title_variable = first_selection[0]
        elif second_selection[0] is not None:
            self.title_variable = second_selection[0]
        else:
            self.title_variable = None

    def update_feature_selection(self):
        self.Error.no_text_features_used.clear()
        # TODO fix VariablesListItemView so it does not emit
        # duplicated data when reordering inside a single window
        def remove_duplicates(l):
            unique = []
            for i in l:
                if i not in unique:
                    unique.append(i)
            return unique

        if self.corpus is not None:
            self.corpus.set_text_features(
                remove_duplicates(self.used_attrs_model))
            self.used_attrs = list(self.used_attrs_model)

            if len(self.unused_attrs_model) > 0 and not self.corpus.text_features:
                self.Error.no_text_features_used()

            self.corpus.set_title_variable(self.title_variable)
            # prevent sending "empty" corpora
            dom = self.corpus.domain
            empty = not (dom.variables or dom.metas) \
                or len(self.corpus) == 0 \
                or not self.corpus.text_features
            self.Outputs.corpus.send(self.corpus if not empty else None)

    def send_report(self):
        def describe(features):
            if len(features):
                return ', '.join([f.name for f in features])
            else:
                return '(none)'

        if self.corpus is not None:
            domain = self.corpus.domain
            self.report_items('Corpus', (
                ("File", self.file_widget.get_selected_filename()),
                ("Documents", len(self.corpus)),
                ("Used text features", describe(self.used_attrs_model)),
                ("Ignored text features", describe(self.unused_attrs_model)),
                ('Other features', describe(domain.attributes)),
                ('Target', describe(domain.class_vars)),
            ))


if __name__ == '__main__':
    from orangewidget.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWCorpus).run()
