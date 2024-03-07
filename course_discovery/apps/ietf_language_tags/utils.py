def serialize_language(language):
    """
    Given a language object, it returns the language name if the language code starts with 'zh' else returns the
    macrolanguage.
    """
    if language.code.startswith('zh'):
        return language.name

    return language.macrolanguage
