"""Common Bangla and English function words, ignored when looking for the terms a text is about.

Matching is exact (NFC, case-folded) on whole words, so inflected forms such as
``করার`` need their own entry. The lists are deliberately short and conservative;
extend :data:`STOPWORDS` for your own niche.
"""

from __future__ import annotations

import unicodedata
from typing import FrozenSet, Iterable, List

_BANGLA = """
অথবা অনেক অন্য আজ আবার আমরা আমার আমি আর আরও আরো আছে আছেন আপনার আপনি ইত্যাদি উপর এখন এই এক একটা একটি একে এখানে এবং এমন এর এরপর এস এসব এটা এটি এতে এবার ও ওই ওর
কখন কত করছে করা করে করেন করতে করবেন করার করি করুন কারণ কি কিন্তু কী কে কেউ কেন কেবল কোথায় কোন কোনো কোনও কিংবা
খুব গিয়ে গেছে গেলে
চান চায় চেয়ে ছিল ছিলেন ছিলাম জন্য জানা জানান জানি
টা টি তখন তবে তবু তা তাই তাকে তাতে তাদের তার তারা তাহলে তিনি তুমি তুলে তো তোমার থাকা থাকে থাকবে থেকে
দিকে দিন দিয়ে দিয়েছে দুই দেওয়া দেয় দেখা
নয় না নাকি নিয়ে নিজের নেই পর পরে পারে পারেন পারা পারি পুরো প্রতি প্রায়
বলে বলা বলেন বলল বরং বা বার বিভিন্ন বেশি ব্যবহার
মত মতো মধ্যে মাঝে যখন যদি যা যাওয়া যাবে যায় যার যারা যে যেন যেমন যেখানে যাতে
রয়েছে লাগে শুধু শুধুমাত্র সকল সব সঙ্গে সাথে সে সেই সেটা সেটি সেখানে সময় সহ সম্পর্কে
হওয়া হওয়ার হচ্ছে হতে হন হবে হয় হয়ে হয়েছে হয়েছিল হলে হলো হল হোক হই
"""

_ENGLISH = """
a about after all also am an and any are as at be been being but by can could did do does for from
had has have he her his how i if in into is it its just may more most my no not of on one only or
our out over she should so some such than that the their them then there these they this those to
too up us was we were what when where which who why will with would you your
"""


def _normalise(word: str) -> str:
    return unicodedata.normalize("NFC", word).casefold().strip()


STOPWORDS: FrozenSet[str] = frozenset(_normalise(w) for w in (_BANGLA + _ENGLISH).split())


def is_stopword(word: str, extra: Iterable[str] = ()) -> bool:
    """True when ``word`` (any case) is a stopword or listed in ``extra``."""
    folded = _normalise(word)
    return folded in STOPWORDS or folded in {_normalise(e) for e in extra}


def content_words(words: Iterable[str], keep: Iterable[str] = ()) -> List[str]:
    """``words`` without stopwords and bare numbers.

    Words in ``keep`` (for example the target keyword) are never dropped, even if they
    are in the stopword list.
    """
    kept = {_normalise(k) for k in keep}
    result = []
    for word in words:
        folded = _normalise(word)
        if folded in kept or (folded not in STOPWORDS and not folded.isdigit()):
            result.append(word)
    return result
