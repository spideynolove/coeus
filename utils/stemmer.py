import re


STEM_RULES = [
    (r'ies$', 'y'),
    (r'ied$', 'y'),
    (r'ying$', 'y'),
    (r'ied$', 'y'),
    (r'sses$', 'ss'),
    (r'hes$', 'h'),
    (r'([^s])s$', r'\1'),
    (r'ing$', ''),
    (r'ed$', ''),
    (r'er$', ''),
    (r'est$', ''),
    (r'ly$', ''),
    (r'ness$', ''),
    (r'ment$', ''),
    (r'tion$', 't'),
]

EXCEPTIONS = {
    'is', 'was', 'has', 'does', 'goes', 'this', 'thus',
    'analysis', 'basis', 'crisis', 'thesis'
}


def stem_word(word: str) -> str:
    word = word.lower().strip()

    if word in EXCEPTIONS or len(word) <= 3:
        return word

    for pattern, replacement in STEM_RULES:
        new_word = re.sub(pattern, replacement, word)
        if new_word != word:
            return new_word

    return word


def stem_text(text: str, mode: str = "aggressive") -> str:
    words = text.split()

    if mode == "aggressive":
        stemmed = [stem_word(w) for w in words]
    else:
        stemmed = [re.sub(r'([^s])s$', r'\1', w.lower()) for w in words]

    return ' '.join(stemmed)
