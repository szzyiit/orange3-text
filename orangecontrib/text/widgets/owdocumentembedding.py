from typing import Any, Tuple
import numpy as np

from AnyQt.QtWidgets import QPushButton, QStyle, QLayout
from AnyQt.QtCore import Qt, QSize

from Orange.widgets.gui import widgetBox, comboBox, auto_commit, hBox
from Orange.widgets.settings import Setting
from Orange.widgets.widget import OWWidget, Msg, Input, Output
from Orange.widgets.utils.concurrent import ConcurrentWidgetMixin, TaskState

from Orange.misc.utils.embedder_utils import EmbeddingConnectionError

from orangecontrib.text.vectorization.document_embedder import DocumentEmbedder
from orangecontrib.text.vectorization.document_embedder import LANGS_TO_ISO, AGGREGATORS
from orangecontrib.text.corpus import Corpus


LANGUAGES = sorted(list(LANGS_TO_ISO.keys()))


def run_pretrained_embedder(corpus: Corpus,
                            language: str,
                            aggregator: str,
                            state: TaskState) -> Tuple[Corpus, Corpus]:
    """Runs DocumentEmbedder.

    Parameters
    ----------
    corpus : Corpus
        Corpus on which transform is performed.
    language : str
        ISO 639-1 (two-letter) code of desired language.
    aggregator : str
        Aggregator which creates document embedding (single
        vector) from word embeddings (multiple vectors).
        Allowed values are mean, sum, max, min.
    state : TaskState
        State object.

    Returns
    -------
    Corpus
        New corpus with additional features.
    """
    embedder = DocumentEmbedder(language=language,
                                aggregator=aggregator)

    ticks = iter(np.linspace(0., 100., len(corpus)))

    def advance(success=True):
        if state.is_interruption_requested():
            embedder.set_cancelled()
        if success:
            state.set_progress_value(next(ticks))

    new_corpus, skipped_corpus = embedder(corpus, processed_callback=advance)
    return new_corpus, skipped_corpus


class OWDocumentEmbedding(OWWidget, ConcurrentWidgetMixin):
    name = "文档嵌入(Document Embedding)"
    description = "使用预训练模型的文档嵌入."
    keywords = ['embedding', 'document embedding', 'wendangqianru', 'qianru']
    icon = 'icons/TextEmbedding.svg'
    priority = 300
    category = '文本挖掘(Text Mining)'


    want_main_area = False
    _auto_apply = Setting(default=True)

    class Inputs:
        corpus = Input("语料库(Corpus)", Corpus, replaces=['Corpus'])

    class Outputs:
        new_corpus = Output('嵌入(Embeddings)', Corpus, default=True, replaces=['Embeddings'])
        skipped = Output('略过的文档(Skipped documents)', Corpus, replaces=['Skipped documents'])

    class Error(OWWidget.Error):
        no_connection = Msg("No internet connection. " +
                            "Please establish a connection or " +
                            "use another vectorizer.")
        unexpected_error = Msg('Embedding error: {}')

    class Warning(OWWidget.Warning):
        unsuccessful_embeddings = Msg('Some embeddings were unsuccessful.')

    language = Setting(default=LANGUAGES.index("English"))
    aggregator = Setting(default=0)

    def __init__(self):
        OWWidget.__init__(self)
        ConcurrentWidgetMixin.__init__(self)

        self.aggregators = AGGREGATORS
        self.corpus = None
        self.new_corpus = None
        self._setup_layout()

    @staticmethod
    def sizeHint():
        return QSize(300, 300)

    def _setup_layout(self):
        self.controlArea.setMinimumWidth(self.sizeHint().width())
        self.layout().setSizeConstraint(QLayout.SetFixedSize)

        widget_box = widgetBox(self.controlArea, '设置')

        self.language_cb = comboBox(
            widget=widget_box,
            master=self,
            value='language',
            label='语言: ',
            orientation=Qt.Horizontal,
            items=LANGUAGES,
            callback=self._option_changed,
            searchable=True
         )

        self.aggregator_cb = comboBox(widget=widget_box,
                                      master=self,
                                      value='aggregator',
                                      label='聚合方法: ',
                                      orientation=Qt.Horizontal,
                                      items=self.aggregators,
                                      callback=self._option_changed)

        self.auto_commit_widget = auto_commit(widget=self.controlArea,
                                              master=self,
                                              value='_auto_apply',
                                              label='应用',
                                              commit=self.commit,
                                              box=False)

        self.cancel_button = QPushButton(
            '取消',
            icon=self.style()
            .standardIcon(QStyle.SP_DialogCancelButton))

        self.cancel_button.clicked.connect(self.cancel)

        hbox = hBox(self.controlArea)
        hbox.layout().addWidget(self.cancel_button)
        self.cancel_button.setDisabled(True)

    @Inputs.corpus
    def set_data(self, data):
        self.Warning.clear()
        self.cancel()

        if not data:
            self.corpus = None
            self.clear_outputs()
            return

        self.corpus = data
        self.unconditional_commit()

    def _option_changed(self):
        self.commit()

    def commit(self):
        if self.corpus is None:
            self.clear_outputs()
            return

        self.cancel_button.setDisabled(False)

        self.start(run_pretrained_embedder,
                   self.corpus,
                   LANGS_TO_ISO[LANGUAGES[self.language]],
                   self.aggregators[self.aggregator])

        self.Error.clear()

    def on_done(self, embeddings: Tuple[Corpus, Corpus]) -> None:
        self.cancel_button.setDisabled(True)
        self._send_output_signals(embeddings[0], embeddings[1])

    def on_partial_result(self, result: Any):
        self.cancel()
        self.Error.no_connection()

    def on_exception(self, ex: Exception):
        self.cancel_button.setDisabled(True)
        if isinstance(ex, EmbeddingConnectionError):
            self.Error.no_connection()
        else:
            self.Error.unexpected_error(type(ex).__name__)
        self.cancel()
        self.clear_outputs()

    def cancel(self):
        self.cancel_button.setDisabled(True)
        super().cancel()

    def _send_output_signals(self, embeddings, skipped):
        self.Outputs.new_corpus.send(embeddings)
        self.Outputs.skipped.send(skipped)
        unsuccessful = len(skipped) if skipped else 0
        if unsuccessful > 0:
            self.Warning.unsuccessful_embeddings()

    def clear_outputs(self):
        self._send_output_signals(None, None)

    def onDeleteWidget(self):
        self.cancel()
        super().onDeleteWidget()


if __name__ == '__main__':
    from orangewidget.utils.widgetpreview import WidgetPreview
    WidgetPreview(OWDocumentEmbedding).run(Corpus.from_file('book-excerpts'))
