"""Build with JDK 17+ and a separately obtained official Montoya API JAR.

Usage: python build.py /path/to/montoya-api-2025.2.jar
The API is compile-only; no Burp classes are bundled in the extension.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('montoya_api', type=Path)
    parser.add_argument('--javac', default='javac')
    parser.add_argument('--java', default='java')
    parser.add_argument('--ecj', type=Path, help='Optional Eclipse compiler JAR when a Java 17 runtime has no javac')
    parser.add_argument('--test', action='store_true', help='Run the interface/transport harness; this does not launch Burp')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if not args.montoya_api.is_file():
        parser.error('Provide the official Montoya API JAR.')
    classes = root / 'build' / 'classes'
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True)
    sources = [str(path) for path in (root / 'src').rglob('*.java')]
    compiler = [args.java, '-jar', str(args.ecj.resolve()), '-17'] if args.ecj else [args.javac, '--release', '17']
    subprocess.run([*compiler, '-encoding', 'UTF-8', '-cp', str(args.montoya_api.resolve()),
                    '-d', str(classes), *sources], check=True)
    if args.test:
        test_classes = root / 'build' / 'test-classes'
        test_classes.mkdir(parents=True, exist_ok=True)
        classpath = os.pathsep.join([str(args.montoya_api.resolve()), str(classes)])
        subprocess.run([*compiler, '-encoding', 'UTF-8', '-cp', classpath,
                        '-d', str(test_classes), str(root / 'tests' / 'BridgeSelfTest.java')], check=True)
        subprocess.run([args.java, '-cp', classpath + os.pathsep + str(test_classes), 'reportgen.BridgeSelfTest'], check=True)
    output = root / 'build' / 'report-gen-burp.jar'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('META-INF/MANIFEST.MF', 'Manifest-Version: 1.0\r\n\r\n')
        for path in sorted(classes.rglob('*.class')):
            archive.write(path, path.relative_to(classes).as_posix())
    print(output)


if __name__ == '__main__':
    main()
