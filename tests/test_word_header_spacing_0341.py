"""Running headers need clearance above text and table continuation pages."""
import pytest
from docx import Document
from docx.shared import Cm, Pt

import engine
import export
from design_library import profile
from design_samples import sample_data


@pytest.mark.parametrize('ident', ['enterprise-assurance', 'centri-btl2', 'offsec-oscp'])
@pytest.mark.parametrize('density', ['comfortable', 'compact'])
def test_body_header_cannot_share_table_top_boundary(tmp_path, ident, density):
    data = sample_data(profile(ident), 'brand', 'en')
    data['meta']['report_density'] = density
    path = tmp_path / 'report.docx'
    export.to_docx(data, data['meta'], engine.load_lang('en'), tmp_path, path)
    document = Document(path)
    cover, body = document.sections
    # Moving the running header must not consume body space or alter the cover.
    assert cover.top_margin == 0
    assert body.top_margin.twips == Cm(1.6).twips
    assert body.bottom_margin.twips == Cm(1.6).twips
    assert body.left_margin.twips == body.right_margin.twips == Cm(1.8).twips
    assert body.header.is_linked_to_previous is False
    assert body.header_distance + Pt(18) < body.top_margin
    header = body.header.paragraphs[0]
    assert data['meta']['branding']['wordmark'] in header.text
    assert header._p.xpath('./w:pPr/w:pBdr/w:bottom')
