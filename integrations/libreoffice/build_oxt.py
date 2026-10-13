"""Build a deterministic, optional LibreOffice extension without installing it."""
import argparse
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LANGUAGE_TAG = "zxx-ZZ-x-rgwrap"
SERVICE = "com.sun.star.i18n.BreakIterator_qlt_ZZ_zxx-ZZ-x-rgwrap"
IMPLEMENTATION = "org.reportgen.TechnicalLiteralBreakIterator"
PAYLOAD_PATHS = {
    "technical_literals.py": "integrations/libreoffice/extension/technical_literals.py",
    "description.xml": "integrations/libreoffice/extension/description.xml",
    "META-INF/manifest.xml": "integrations/libreoffice/extension/META-INF/manifest.xml",
    "SCOPE.txt": "integrations/libreoffice/extension/SCOPE.txt",
    "LICENSE": "LICENSE",
}


def build_oxt(output, files_mapping=None):
    """Write the explicit extension payload; never discover or add residual files."""
    payload = ({name: (ROOT / relative).read_bytes() for name, relative in PAYLOAD_PATHS.items()}
               if files_mapping is None else dict(files_mapping))
    if set(payload) != set(PAYLOAD_PATHS):
        raise ValueError("OXT payload must contain exactly the approved five files")
    if not all(isinstance(data, bytes) for data in payload.values()):
        raise TypeError("OXT payload values must be bytes from the selected source")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Destination .oxt file (not installed)")
    args = parser.parse_args()
    print(build_oxt(args.output).resolve())


if __name__ == "__main__":
    main()
