from typing import List, Callable
import os
import json
import serverfiles
from nltk import stem
from requests.exceptions import ConnectionError

from Orange.misc.environ import data_dir
from Orange.util import wrap_callback, dummy_callback

from orangecontrib.text import Corpus
from orangecontrib.text.misc import wait_nltk_data
from orangecontrib.text.preprocess import Preprocessor, TokenizedPreprocessor

__all__ = ['BaseNormalizer', 'WordNetLemmatizer', 'PorterStemmer',
           'SnowballStemmer']


class BaseNormalizer(TokenizedPreprocessor):
    """ A generic normalizer class.
    You should either overwrite `normalize` method or provide a custom
    normalizer.
    """
    normalizer = NotImplemented

    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        if callback is None:
            callback = dummy_callback
        corpus = super().__call__(corpus, wrap_callback(callback, end=0.2))
        callback(0.2, "Normalizing...")
        return self._store_tokens(corpus, wrap_callback(callback, start=0.2))

    def _preprocess(self, string: str) -> str:
        """ Normalizes token to canonical form. """
        return self.normalizer(string)


class WordNetLemmatizer(BaseNormalizer):
    name = 'WordNet Lemmatizer'
    normalizer = stem.WordNetLemmatizer().lemmatize

    @wait_nltk_data
    def __init__(self):
        super().__init__()


class PorterStemmer(BaseNormalizer):
    name = 'Porter Stemmer'
    normalizer = stem.PorterStemmer().stem


class SnowballStemmer(BaseNormalizer):
    name = 'Snowball Stemmer'
    supported_languages = [l.capitalize() for l in stem.SnowballStemmer.languages]

    def __init__(self, language='English'):
        self.normalizer = stem.SnowballStemmer(language.lower())

    def _preprocess(self, token):
        return self.normalizer.stem(token)


def language_to_name(language):
    return language.lower().replace(' ', '') + 'ud'


def file_to_name(file):
    return file.replace('-', '').replace('_', '')


def file_to_language(file):
    return file[:file.find('ud')-1]\
        .replace('-', ' ').replace('_', ' ').capitalize()

