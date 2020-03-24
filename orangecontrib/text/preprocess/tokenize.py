from typing import List, Callable
import re
from nltk import tokenize
import jieba
import pkuseg

from Orange.util import wrap_callback, dummy_callback

from orangecontrib.text import Corpus
from orangecontrib.text.misc import wait_nltk_data
from orangecontrib.text.preprocess import Preprocessor

__all__ = ['BaseTokenizer', 'WordPunctTokenizer', 'PunktSentenceTokenizer',
           'RegexpTokenizer', 'WhitespaceTokenizer', 'TweetTokenizer',
           'BASE_TOKENIZER', 'Jieba']


class BaseTokenizer(Preprocessor):
    tokenizer = NotImplemented

    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        corpus = super().__call__(corpus)
        if callback is None:
            callback = dummy_callback
        callback(0, "Tokenizing...")
        return self._store_tokens_from_documents(corpus, callback)

    def _preprocess(self, string: str) -> List[str]:
        return list(filter(lambda x: x != '', self.tokenizer.tokenize(string)))


class WordPunctTokenizer(BaseTokenizer):
    """ 根据单词分词, 保留标点. This example. → (This), (example), (.)"""
    tokenizer = tokenize.WordPunctTokenizer()
    name = 'Word & Punctuation'


class PunktSentenceTokenizer(BaseTokenizer):
    """ 根据句子分词. This example. Another example. → (This example.), (Another example.) """
    tokenizer = tokenize.PunktSentenceTokenizer()
    name = 'Sentence'

    @wait_nltk_data
    def __init__(self):
        super().__init__()


class WhitespaceTokenizer(BaseTokenizer):
    """ 根据空白分词. This example. → (This), (example.)"""
    tokenizer = tokenize.WhitespaceTokenizer()
    name = 'Whitespace'


class RegexpTokenizer(BaseTokenizer):
    """ 按正则表达式分词，默认只保留单词。 """
    tokenizer_cls = tokenize.RegexpTokenizer
    name = 'Regexp'

    def __init__(self, pattern=r'\w+'):
        super().__init__()
        self.tokenizer = None
        self.__pattern = pattern

    def __call__(self, corpus: Corpus, callback: Callable = None) -> Corpus:
        # Compiled Regexes are NOT deepcopy-able and hence to make Corpus deepcopy-able
        # we cannot store then (due to Corpus also storing used_preprocessor for BoW compute values).
        # To bypass the problem regex is compiled before every __call__ and discarded right after.
        self.tokenizer = self.tokenizer_cls(self.__pattern)
        corpus = Preprocessor.__call__(self, corpus)
        if callback is None:
            callback = dummy_callback
        callback(0, "Tokenizing...")
        corpus = self._store_tokens_from_documents(corpus, callback)
        self.tokenizer = None
        return corpus

    def _preprocess(self, string: str) -> List[str]:
        assert self.tokenizer is not None
        return super()._preprocess(string)

    @staticmethod
    def validate_regexp(regexp: str) -> bool:
        try:
            re.compile(regexp)
            return True
        except re.error:
            return False


class TweetTokenizer(BaseTokenizer):
    """ 预训练的推特分词器.保留表情符号. This example. :-) #simple → (This), (example), (.), (:-)), (#simple) """
    tokenizer = tokenize.TweetTokenizer()
    name = 'Tweet'


BASE_TOKENIZER = WordPunctTokenizer()
class Jieba(BaseTokenizer):
    """ 结巴中文分词 """
    jieba.enable_paddle()  # 启动paddle模式
    name  = '结巴中文分词'
    tokenizer = jieba

    def __call__(self, sent):
        if isinstance(sent, str):
            return self.tokenize(sent)
        return self.tokenize_sents(sent)

    def tokenize(self, string):
        return list(filter(lambda x: x != '', self.tokenizer.cut(string, use_paddle=True)))

    def tokenize_sents(self, strings):
        return [self.tokenize(string) for string in strings]


class PKU(BaseTokenizer):
    """ 北大多领域中文分词工具 """
    name  = '北大中文分词'
    models = ['default', 'news', 'web', 'medicine', 'tourism']
    # tokenizer = pkuseg.pkuseg()

    def __init__(self, model_index=0):
        self._model_index = model_index
        self.tokenizer = pkuseg.pkuseg(model_name=self.models[self.model_index])

    @property
    def model_index(self):
        return self._model_index

    @model_index.setter
    def model_index(self, value):
        self._model_index = value
        self.tokenizer = pkuseg.pkuseg(model_name=self.models[self.model_index])

    def __call__(self, sent):
        if isinstance(sent, str):
            return self.tokenize(sent)
        return self.tokenize_sents(sent)

    def tokenize(self, string):
        return list(filter(lambda x: x != '', self.tokenizer.cut(string)))

    def tokenize_sents(self, strings):
        return [self.tokenize(string) for string in strings]
