"""Public-key fingerprints and real launcher PID/port lifecycle regression tests."""
from hashlib import sha256
import builtins
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import pytest

import delivery_signature as signing
import start
from error_messages import language_scope
from test_delivery_signature_0240 import archive

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def keys(tmp_path):
    private, public = tmp_path / 'private.pem', tmp_path / 'public.pem'
    created = signing.generate_keypair(private, public)
    yield private, public, created
    private.unlink(missing_ok=True)


@pytest.mark.parametrize('line_endings', ['lf', 'crlf'])
def test_public_fingerprint_matches_independent_raw_key_and_exact_delivery(keys, tmp_path, line_endings):
    from cryptography.hazmat.primitives import serialization
    private, public, created = keys
    public_bytes = public.read_bytes()
    expected = sha256(serialization.load_pem_public_key(public_bytes).public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).hexdigest()
    if line_endings == 'crlf':
        public.write_bytes(b' \r\n' + public_bytes.replace(b'\n', b'\r\n') + b'\r\n ')
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = signing.public_key_fingerprint(public)
    assert result == {'algorithm': 'Ed25519', 'key_sha256': expected, 'scope': 'raw_32_byte_public_key'}
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == original
    delivery = archive(tmp_path / 'delivery.zip')
    detached = tmp_path / 'delivery.sig.json'
    signed = signing.sign_delivery(delivery, private, detached)
    verified = signing.verify_delivery(delivery, detached, public)
    assert expected == created['key_sha256'] == signed['key_sha256'] == verified['key_sha256']
    assert expected != sha256(public.read_bytes()).hexdigest()


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_real_fingerprint_cli_is_local_read_only_json(keys, tmp_path, lang):
    _, public, created = keys
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    command = [sys.executable, '-m', 'delivery_signature', '--lang', lang,
               'fingerprint', '--public-key', str(public)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=15,
                            env=dict(os.environ, PYTHONPATH=str(ROOT)))
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    payload = json.loads(result.stdout)
    assert set(payload) == {'algorithm', 'key_sha256', 'scope', 'message', 'language'}
    assert payload['key_sha256'] == created['key_sha256'] and payload['language'] == lang
    assert ('Huella SHA-256' if lang == 'es' else 'SHA-256 fingerprint') in payload['message']
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('kind', ['double', 'private', 'trailing', 'empty', 'oversized', 'malformed',
                                  'rsa', 'ec', 'symlink', 'ancestor-symlink', 'directory', 'missing', 'fifo'])
def test_public_fingerprint_rejects_ambiguous_unsafe_or_non_ed25519_inputs(keys, tmp_path, kind):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    private, public, _ = keys
    target = tmp_path / 'input.pem'
    blob = public.read_bytes()
    mutations = {'double': blob + blob, 'private': private.read_bytes(), 'trailing': blob + b'untrusted',
                 'empty': b'', 'oversized': b'A' * (signing.MAX_KEY_BYTES + 1),
                 'malformed': b'-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n'}
    if kind in mutations:
        target.write_bytes(mutations[kind])
    elif kind in {'rsa', 'ec'}:
        key = (rsa.generate_private_key(public_exponent=65537, key_size=2048) if kind == 'rsa'
               else ec.generate_private_key(ec.SECP256R1()))
        target.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                        serialization.PublicFormat.SubjectPublicKeyInfo))
    elif kind == 'symlink':
        target.symlink_to(public)
    elif kind == 'ancestor-symlink':
        (tmp_path / 'alias').symlink_to(tmp_path, target_is_directory=True)
        target = tmp_path / 'alias' / 'public.pem'
    elif kind == 'directory':
        target.mkdir()
    elif kind == 'fifo':
        if not hasattr(os, 'mkfifo'):
            pytest.skip('POSIX FIFO input')
        os.mkfifo(target)
    with pytest.raises((ValueError, OSError)):
        signing.public_key_fingerprint(target)


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_fingerprint_missing_optional_dependency_is_clear_json(keys, monkeypatch, capsys, lang):
    _, public, _ = keys
    original = builtins.__import__

    def without_crypto(name, *args, **kwargs):
        if name == 'cryptography' or name.startswith('cryptography.'):
            raise ImportError('synthetic absent optional dependency')
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', without_crypto)
    assert signing.main(['--lang', lang, 'fingerprint', '--public-key', str(public)]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    payload = json.loads(captured.err)
    assert payload['language'] == lang
    assert ('Instala report-gen[signing]' if lang == 'es' else 'Install report-gen[signing]') in payload['error']


def test_public_fingerprint_does_not_inherit_private_posix_requirement(keys, monkeypatch):
    # The production reader's private flag controls POSIX/mode/link restrictions;
    # public verification/fingerprinting intentionally permits readable public files.
    _, public, _ = keys
    public.chmod(0o644)
    alias = public.with_name('public-hardlink.pem')
    os.link(public, alias)
    with language_scope('en'):
        assert signing.public_key_fingerprint(alias) == signing.public_key_fingerprint(public)


def _listening(port):
    with socket.socket() as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(('127.0.0.1', port)) == 0


@pytest.mark.skipif(os.name != 'posix', reason='POSIX same-PID exec and process signals')
@pytest.mark.parametrize('kind', ['SIGTERM', 'SIGINT', 'SIGKILL'])
def test_real_launcher_replacement_exits_with_server_port_on_signal(tmp_path, kind):
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        port = reserved.getsockname()[1]
    probe = tmp_path / 'probe'
    probe.mkdir()
    pid_log = tmp_path / 'startup-pids.jsonl'
    # Record actual interpreter startups even on Linux sandboxes without /proc.
    # The instrumented environment is confined to this disposable process group.
    (probe / 'sitecustomize.py').write_text(
        "import json, os, sys\n"
        "with open(os.environ['RG_LAUNCH_PID_LOG'], 'a') as target:\n"
        "    target.write(json.dumps({'pid': os.getpid(), 'argv': sys.argv}) + '\\n')\n"
    )
    with (tmp_path / 'launcher.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'start.py'), '--port', str(port)],
                                   cwd=tmp_path, stdout=log, stderr=log, start_new_session=True,
                                   env=dict(os.environ, PYTHONPATH=os.pathsep.join((str(probe), str(ROOT))),
                                            RG_LAUNCH_PID_LOG=str(pid_log)))
        try:
            deadline = time.monotonic() + 25
            while not _listening(port) and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            assert process.poll() is None and _listening(port), (tmp_path / 'launcher.log').read_text()
            startups = [json.loads(line) for line in pid_log.read_text().splitlines()]
            launcher = [row for row in startups if row['argv'][0] == str(ROOT / 'start.py')]
            server = [row for row in startups if row['argv'][0] == str(ROOT / 'webapp/app.py')]
            assert len(launcher) == len(server) == 1
            assert launcher[0]['pid'] == server[0]['pid'] == process.pid
            process.send_signal(getattr(signal, kind))
            process.wait(timeout=10)
            deadline = time.monotonic() + 3
            while _listening(port) and time.monotonic() < deadline:
                time.sleep(0.05)
            assert not _listening(port), 'The launcher exited but an orphan still holds the server port'
            if kind in {'SIGTERM', 'SIGKILL'}:
                assert process.returncode == -getattr(signal, kind)
            (tmp_path / 'launcher-result.json').write_text(json.dumps({
                'signal': kind, 'pid': process.pid, 'port': port, 'returncode': process.returncode,
                'same_pid_exec_verified': True, 'interpreter_startups': startups,
                'port_closed': True, 'launch_from_foreign_directory': True,
            }, indent=2) + '\n')
        finally:
            # Isolated process group also cleans up a regressed child-server implementation.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)


def test_windows_console_shutdown_terminates_child_and_restores_handlers(monkeypatch):
    original = {kind: signal.getsignal(kind) for kind in (signal.SIGINT, signal.SIGTERM)}
    events = []

    class Child:
        code = None

        def poll(self):
            return self.code

        def terminate(self):
            events.append('terminate')
            self.code = 1

        def wait(self, timeout=None):
            if self.code is None:
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return self.code

    monkeypatch.setattr(start.subprocess, 'Popen', lambda command, **kwargs: Child())
    assert start._run_windows_server(['synthetic-interpreter']) == 128 + signal.SIGTERM
    assert events == ['terminate']
    assert {kind: signal.getsignal(kind) for kind in original} == original


def test_windows_child_exception_uses_bounded_cleanup_and_restores_handlers(monkeypatch):
    original = {kind: signal.getsignal(kind) for kind in (signal.SIGINT, signal.SIGTERM)}
    events = []

    class Child:
        code = None

        def poll(self):
            return self.code

        def terminate(self):
            events.append('terminate')

        def kill(self):
            events.append('kill')
            self.code = 1

        def wait(self, timeout=None):
            events.append(('wait', timeout))
            if self.code is not None:
                return self.code
            if timeout is not None:
                raise subprocess.TimeoutExpired('synthetic-interpreter', timeout)
            raise RuntimeError('synthetic wait failure')

    monkeypatch.setattr(start.subprocess, 'Popen', lambda command, **kwargs: Child())
    with pytest.raises(RuntimeError, match='synthetic wait failure'):
        start._run_windows_server(['synthetic-interpreter'])
    assert events == [('wait', None), 'terminate', ('wait', 5), 'kill', ('wait', None)]
    assert {kind: signal.getsignal(kind) for kind in original} == original
