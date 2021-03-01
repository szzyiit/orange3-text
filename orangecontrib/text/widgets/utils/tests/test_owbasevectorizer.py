from orangecontrib.text import Corpus
from orangecontrib.text.vectorization import BowVectorizer
from orangecontrib.text.widgets.utils.owbasevectorizer import OWBaseVectorizer
try:
    from orangewidget.tests.base import WidgetTest
except:
    from Orange.widgets.tests.base import WidgetTest


class TestableBaseVectWidget(OWBaseVectorizer):
    name = "TBV"
    Method = BowVectorizer


class TestOWBaseVectorizer(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(TestableBaseVectWidget)
        self.corpus = Corpus.from_file('deerwester')

    def test_hide_attributes(self):
        self.send_signal("语料库(Corpus)", self.corpus)
        self.assertTrue(all(f.attributes['hidden'] for f in
                            self.get_output("语料库(Corpus)").domain.attributes))
        self.widget.controls.hidden_cb.setChecked(False)
        self.assertFalse(any(f.attributes['hidden'] for f in
                            self.get_output("语料库(Corpus)").domain.attributes))
        new_corpus = Corpus.from_file('book-excerpts')[:10]
        self.send_signal("语料库(Corpus)", new_corpus)
        self.assertFalse(any(f.attributes['hidden'] for f in
                            self.get_output("语料库(Corpus)").domain.attributes))
