"""Supported interface/report language keys and public language tags."""

LANGUAGES = ("es", "en", "pt")
LANGUAGE_TAGS = {"es": "es", "en": "en", "pt": "pt-BR"}


def normalize_language(value, default="es"):
    """Return a supported key; callers may pass None to reject invalid values."""
    if not isinstance(value, str):
        return default
    key = value.strip().lower()
    if key == "pt-br":
        key = "pt"
    return key if key in LANGUAGES else default


def language_tag(value, default="es"):
    """BCP 47 metadata for the supported language, without changing report text."""
    key = normalize_language(value, default)
    return LANGUAGE_TAGS.get(key, key)


def language_index(value, default="es"):
    """Index for explicit Spanish, English, Brazilian Portuguese string tuples."""
    return LANGUAGES.index(normalize_language(value, default))


def language_argument(value):
    """Argparse converter: normalize aliases while rejecting unsupported input."""
    key = normalize_language(value, None)
    if key is None:
        from error_messages import message
        raise ValueError(message("Idiomas admitidos: es, en, pt (pt-BR)",
                                 en="Supported languages: es, en, pt (pt-BR)",
                                 pt="Idiomas disponíveis: es, en, pt (pt-BR)"))
    return key


def console_language(argv=None):
    """Read the explicit language before composing an argparse help page."""
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--lang", type=language_argument, default="es")
    return parser.parse_known_args(argv)[0].lang
