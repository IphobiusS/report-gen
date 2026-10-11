"""Spanish ordinary todo is not an editorial marker; explicit markers remain."""
from copy import deepcopy

import pytest

import workflows


def pending(text, directory, language='es', ui_language='es'):
    data = {'meta': {'lang': language}, 'findings': [],
            'report': {'sections': [{'key': 'notes', 'body': text}]}}
    original = deepcopy(data)
    result = [item for item in workflows.review(data, directory, lang=ui_language)
              if item['path'] == 'report.sections[0].body']
    assert data == original
    return result


@pytest.mark.parametrize('ui_language', ['es', 'en'])
@pytest.mark.parametrize('text', ['Todo acceso requiere autorización.',
                                  'Se comprobó todo el contenido.',
                                  'Todo: registros, eventos y resultados.'])
def test_spanish_ordinary_todo_is_not_a_placeholder(tmp_path, ui_language, text):
    assert pending(text, tmp_path, ui_language=ui_language) == []


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('marker', ['TODO', 'TODO: document evidence', 'tbd', 'TBD',
                                    'fixme', 'FIXME', 'Pendiente de completar',
                                    'LOREM IPSUM', '{{ 7 * 7 }}', '<completar>'])
def test_explicit_and_other_existing_markers_remain_warnings(tmp_path, language, marker):
    issues = pending(marker, tmp_path, language=language)
    assert len(issues) == 1 and issues[0]['level'] == 'warning'


@pytest.mark.parametrize('language', ['en', None])
@pytest.mark.parametrize('marker', ['todo', 'Todo', 'ToDo'])
def test_english_and_legacy_keep_case_insensitive_todo(tmp_path, language, marker):
    assert len(pending(marker, tmp_path, language=language)) == 1


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('text', ['methodology', 'TODOLOGY', 'subtotal', 'todopoderoso'])
def test_marker_word_boundaries_remain_intact(tmp_path, language, text):
    assert pending(text, tmp_path, language=language) == []
