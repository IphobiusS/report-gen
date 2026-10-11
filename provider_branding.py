"""Bundled provider marks, selected independently from client-owned images.

Only fixed local assets are read. User text is never interpreted as SVG or as
an asset path. The logo identifies a template family, not an earned credential.
"""
from pathlib import Path

ASSETS = Path(__file__).parent / 'exporters' / 'branding'


def provider_mark(design):
    from design_library import validate_design, profile
    from design_render import palette, ink_on
    d = validate_design(design)
    provider = profile(d['guidance_id'])['provider']
    if provider not in ('HTB', 'OffSec'):
        # A writing profile does not grant permission to invent a provider logo.
        # The cover still identifies its family and profile using ordinary text.
        return {'provider': provider, 'name': provider, 'svg': '', 'png': None, 'key': None}
    pal = palette(d)
    background = pal['--profile-dark'] if d['layout'] == 'split' else pal['--cover-bg']
    variant = 'on-dark' if ink_on(background) == '#FFFFFF' else 'on-light'
    if provider == 'HTB' and d['variant'] == 'quiet':
        variant = 'mono'
    key = {'HTB': 'htb', 'OffSec': 'offsec'}[provider] + '-' + variant
    return {'provider': provider, 'name': 'Hack The Box' if provider == 'HTB' else 'OffSec',
            'svg': (ASSETS / (key + '.svg')).read_text(encoding='utf-8'),
            'png': ASSETS / (key + '.png'), 'key': key}
