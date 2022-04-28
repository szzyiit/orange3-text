from typing import List, Callable
import os
# import ufal.udpipe as udpipe
from lemmagen3 import Lemmatizer
import serverfiles
from nltk import stem
from requests.exceptions import ConnectionError

from Orange.misc.environ import data_dir
from Orange.util import wrap_callback, dummy_callback

from orangecontrib.text import Corpus
from orangecontrib.text.misc import wait_nltk_data
from orangecontrib.text.preprocess import Preprocessor, TokenizedPreprocessor

__all__ = ['BaseNormalizer', 'WordNetLemmatizer', 'PorterStemmer',
           'SnowballStemmer',  'LemmagenLemmatizer']


class BaseNormalizer(TokenizedPreprocessor):
    """ A generic normalizer class.
    You should either overwrite `normalize` method or provide a custom
    normalizer.
    """
    normalizer = NotImplemented

    def __init__(self):
        # cache already normalized string to speedup normalization
        self._normalization_cache = {}

    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        if callback is None:
            callback = dummy_callback
        corpus = super().__call__(corpus, wrap_callback(callback, end=0.2))
        callback(0.2, "Normalizing...")
        return self._store_tokens(corpus, wrap_callback(callback, start=0.2))

    def _preprocess(self, string: str) -> str:
        """ Normalizes token to canonical form. """
        if string in self._normalization_cache:
            return self._normalization_cache[string]
        self._normalization_cache[string] = norm_string = self.normalizer(string)
        return norm_string

    def __getstate__(self):
        d = self.__dict__.copy()
        # since cache can be quite big, empty cache before pickling
        d["_normalization_cache"] = {}
        return d


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
    supported_languages = [l.capitalize() for l in
                           stem.SnowballStemmer.languages]

    def __init__(self, language='English'):
        super().__init__()
        self.normalizer = stem.SnowballStemmer(language.lower()).stem


def language_to_name(language):
    return language.lower().replace(' ', '') + 'ud'


def file_to_name(file):
    return file.replace('-', '').replace('_', '')


def file_to_language(file):
    return file[:file.find('ud') - 1] \
        .replace('-', ' ').replace('_', ' ').capitalize()


class LemmagenLemmatizer(BaseNormalizer):
    name = 'Lemmagen Lemmatizer'
    lemmagen_languages = {
        "Bulgarian": "bg",
        "Croatian": "hr",
        "Czech": "cs",
        "English": "en",
        "Estonian": "et",
        "Farsi/Persian": "fa",
        "French": "fr",
        "German": "de",
        "Hungarian": "hu",
        "Italian": "it",
        "Macedonian": "mk",
        "Polish": "pl",
        "Romanian": "ro",
        "Russian": "ru",
        "Serbian": "sr",
        "Slovak": "sk",
        "Slovenian": "sl",
        "Spanish": "es",
        "Ukrainian": "uk"
    }

    def __init__(self, language='English'):
        super().__init__()
        self.language = language
        self.lemmatizer = None

    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        # lemmagen3 lemmatizer is not picklable, define it on call and discard it afterward
        self.lemmatizer = Lemmatizer(self.lemmagen_languages[self.language])
        output_corpus = super().__call__(corpus, callback)
        self.lemmatizer = None
        return output_corpus

    def normalizer(self, token):
        assert self.lemmatizer is not None
        t = self.lemmatizer.lemmatize(token)
        # sometimes Lemmagen returns an empty string, return original tokens
        # in this case
        return t if t else token
