from typing import Callable
import re

from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import strip_accents_unicode

from Orange.util import wrap_callback, dummy_callback

from orangecontrib.text import Corpus
from orangecontrib.text.preprocess import Preprocessor

__all__ = ['BaseTransformer', 'HtmlTransformer', 'LowercaseTransformer',
           'StripAccentsTransformer', 'UrlRemover', 'BASE_TRANSFORMER']


class BaseTransformer(Preprocessor):
    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        corpus = super().__call__(corpus)
        if callback is None:
            callback = dummy_callback
        callback(0, "Transforming...")
        corpus = self._store_documents(corpus, wrap_callback(callback, end=0.5))
        return self._store_tokens(corpus, wrap_callback(callback, start=0.5)) \
            if corpus.has_tokens() else corpus


class LowercaseTransformer(BaseTransformer):
    """ 所有字母转为小写. """
    name = '转为小写'

    def _preprocess(self, string: str) -> str:
        return string.lower()


class StripAccentsTransformer(BaseTransformer):
    """ naïve → naive """
    name = "去除音调符号"

    def _preprocess(self, string: str) -> str:
        return strip_accents_unicode(string)


class HtmlTransformer(BaseTransformer):
    """ <a href…>Some text</a> → Some text """
    name = "去除 html 标签"

    def _preprocess(self, string: str) -> str:
        return BeautifulSoup(string, 'html.parser').getText()


class UrlRemover(BaseTransformer):
    """ 去除超链接. """
    name = "去除 urls"
    urlfinder = None

    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        self.urlfinder = re.compile(r"((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)")
        corpus = super().__call__(corpus, callback)
        self.urlfinder = None
        return corpus

    def _preprocess(self, string: str) -> str:
        assert self.urlfinder is not None
        return self.urlfinder.sub('', string)


BASE_TRANSFORMER = LowercaseTransformer()
