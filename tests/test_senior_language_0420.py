"""New explicit-language prose obeys request scope without formatting opaque data."""
import pytest

import finding_instances
import http_evidence
import test_plans
import ticket_connectors
from error_messages import current_language, language_scope


@pytest.mark.parametrize('language,slot', [('es', 0), ('en', 1), ('pt', 2), ('pt-BR', 2), ('unsupported', 0)])
def test_senior_validation_uses_normalized_request_language(language, slot):
    cases = [
        (lambda: test_plans.create(None), ('Campos de caso de prueba inválidos', 'Invalid test case fields', 'Campos de caso de teste inválidos')),
        (lambda: finding_instances.new_instance(None), ('Campos de instancia inválidos', 'Invalid instance fields', 'Campos de instância inválidos')),
        (lambda: http_evidence.add({}, []), ('HTTP: selecciona entre 1 y 100 mensajes', 'HTTP: select between 1 and 100 messages', 'HTTP: selecione entre 1 e 100 mensagens')),
        (lambda: ticket_connectors.base_url(None), ('Servidor inválido', 'Invalid server', 'Servidor inválido')),
    ]
    previous = current_language()
    with language_scope(language):
        for operation, expected in cases:
            with pytest.raises(ValueError) as caught:
                operation()
            assert str(caught.value) == expected[slot]
    assert current_language() == previous


@pytest.mark.parametrize('language,prefix', [('es', 'HTTP: texto inválido en '), ('en', 'HTTP: invalid text in '), ('pt-BR', 'HTTP: texto inválido em ')])
def test_http_error_preserves_opaque_braces_in_field_name(language, prefix):
    field = 'header.{author_value} {{literal}}'
    with language_scope(language), pytest.raises(ValueError) as caught:
        http_evidence.text(None, 100, field)
    assert str(caught.value) == prefix + field
