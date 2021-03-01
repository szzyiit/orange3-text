import unittest

from Orange.widgets.tests.base import WidgetTest, WidgetOutputsTestMixin

from orangecontrib.text.corpus import Corpus
from orangecontrib.text.widgets.owbagofwords import OWTBagOfWords


class TestBagOfWords(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWTBagOfWords)
        self.corpus = Corpus.from_file('deerwester')

    def test_corpus(self):
        """
        Just basic test.
        GH-247
        """
        self.send_signal("语料库(Corpus)", self.corpus)
        self.send_signal("语料库(Corpus)", None)


if __name__ == "__main__":
    unittest.main()
