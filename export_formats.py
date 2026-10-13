"""Single registry for the public formats, their writers and verification routes."""
from error_messages import message as backend_message
from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    key: str
    extension: str
    mime: str
    filename: str
    label_es: str
    label_en: str
    label_pt: str
    renderer: str
    inspector: str
    container: str

    def render(self, yaml_path, output):
        import export
        return getattr(export, self.renderer)(yaml_path, output)

    def inspect(self, path, captured):
        import delivery
        fn = getattr(delivery, self.inspector)
        if self.container == 'zip':
            return fn(path, self.key, captured['images'], captured.get('image_placements'))
        return fn(path, captured['image_placements'])


REGISTRY = {
    spec.key: spec for spec in (
        Format('pdf', 'pdf', 'application/pdf', 'informe.pdf', 'PDF', 'PDF', 'PDF', '_write_pdf', 'inspect_pdf', 'pdf'),
        Format('docx', 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
               'informe.docx', 'Word', 'Word', 'Word', '_write_docx', 'inspect_archive', 'zip'),
        Format('md', 'zip', 'application/zip', 'markdown.zip', 'Markdown + imágenes', 'Markdown + images', 'Markdown + imagens',
               '_write_markdown', 'inspect_archive', 'zip'),
        Format('html', 'html', 'text/html', 'informe.html', 'HTML portátil', 'Portable HTML', 'HTML portátil',
               '_write_html', 'inspect_html', 'html'),
    )
}


def get(key):
    key = 'md' if key == 'mdzip' else key
    if not isinstance(key, str) or key not in REGISTRY:
        raise ValueError(backend_message('Formato no soportado / Unsupported format'))
    return REGISTRY[key]


def catalog():
    return [dict(key=s.key, extension=s.extension, mime=s.mime, filename=s.filename,
                 label_es=s.label_es, label_en=s.label_en, label_pt=s.label_pt, checks=s.inspector) for s in REGISTRY.values()]
