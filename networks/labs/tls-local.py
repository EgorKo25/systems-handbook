#!/usr/bin/env python3
"""Offline TLS 1.3 experiment in an isolated Linux network namespace.

Needs Python 3, openssl, ip, unshare; changes no host network or trust store.
Creates an ephemeral CA and server certificate in a temporary directory.
No external address is contacted. All private keys disappear on completion.
"""
import argparse
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def command(args, cwd, data=None, ok=True):
    result = subprocess.run(args, cwd=cwd, input=data, text=True,
                            capture_output=True, timeout=20)
    if ok and result.returncode:
        raise RuntimeError("Command failed: " + " ".join(args) + "\n" + result.stderr)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    for tool in ("openssl", "ip", "unshare"):
        if not shutil.which(tool):
            raise SystemExit("Missing local tool: " + tool)
    if not args.inside:
        result = subprocess.run(["unshare", "-Urn", "--", sys.executable,
                                 str(Path(__file__).resolve()), "--inside"])
        if result.returncode:
            print("Experiment did not complete; check whether unprivileged namespaces are enabled.", file=sys.stderr)
        raise SystemExit(result.returncode)
    command(["ip", "link", "set", "lo", "up"], ".")
    with tempfile.TemporaryDirectory(prefix="network-book-tls-") as temp:
        root = Path(temp)
        command(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                 "ec_paramgen_curve:P-256", "-nodes", "-keyout", "ca.key",
                 "-out", "ca.pem", "-days", "2", "-subj", "/CN=Offline laboratory CA",
                 "-addext", "basicConstraints=critical,CA:TRUE",
                 "-addext", "keyUsage=critical,keyCertSign,cRLSign"], root)
        command(["openssl", "req", "-new", "-newkey", "ec", "-pkeyopt",
                 "ec_paramgen_curve:P-256", "-nodes", "-keyout", "server.key",
                 "-out", "server.csr", "-subj", "/CN=app.lab.test"], root)
        (root / "server.ext").write_text("basicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature\n"
                "extendedKeyUsage=serverAuth\nsubjectAltName=DNS:app.lab.test\n")
        command(["openssl", "x509", "-req", "-in", "server.csr", "-CA", "ca.pem",
                 "-CAkey", "ca.key", "-CAcreateserial", "-out", "server.pem",
                 "-days", "2", "-extfile", "server.ext"], root)
        with (root / "server.log").open("w") as log:
            server = subprocess.Popen(["openssl", "s_server", "-accept", "127.0.0.1:18443",
                    "-cert", "server.pem", "-key", "server.key", "-tls1_3", "-www"],
                    cwd=root, stdout=log, stderr=log)
            try:
                for _ in range(50):
                    if server.poll() is not None:
                        raise RuntimeError("TLS server failed: " + (root / "server.log").read_text())
                    try:
                        with socket.create_connection(("127.0.0.1", 18443), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.02)
                else:
                    raise RuntimeError("Local TLS server did not start")
                base = ["openssl", "s_client", "-connect", "127.0.0.1:18443", "-servername",
                        "app.lab.test", "-verify_return_error", "-CAfile", "ca.pem", "-tls1_3"]
                request = "GET / HTTP/1.0\r\nHost: app.lab.test\r\n\r\n"
                good = command(base + ["-verify_hostname", "app.lab.test"], root, request)
                combined = good.stdout + good.stderr
                assert "TLSv1.3" in combined and "Verification: OK" in combined
                print("PASS: TLS 1.3, trusted laboratory CA, matching DNS name")
                bad = command(base + ["-verify_hostname", "wrong.lab.test"], root, request, ok=False)
                assert bad.returncode and "hostname mismatch" in (bad.stderr + bad.stdout).lower()
                print("PASS: wrong.lab.test rejected with hostname mismatch")
                cert = command(["openssl", "x509", "-in", "server.pem", "-noout", "-ext",
                                "subjectAltName,extendedKeyUsage,keyUsage,basicConstraints"], root)
                print(cert.stdout.strip())
                if shutil.which("curl"):
                    good_curl = command(["curl", "--noproxy", "*", "--cacert", "ca.pem",
                            "--resolve", "app.lab.test:18443:127.0.0.1", "--silent", "--show-error",
                            "--max-time", "5", "https://app.lab.test:18443/"], root)
                    assert "HTTP" in good_curl.stdout or "s_server" in good_curl.stdout
                    print("PASS: curl --resolve preserves hostname and verifies certificate")
                else:
                    print("SKIP: curl not installed; openssl checks completed")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    print("Temporary keys removed; isolated network namespace closed.")


if __name__ == "__main__":
    main()
