#!/usr/bin/env python3
"""Учебный CGI: только stdin/env -> заголовки и тело stdout, без сервера и записи файлов."""
import os
import sys


def respond(status, text, *, allow=None):
    body = text.encode('utf-8')
    allow_header = '' if allow is None else 'Allow: ' + allow + '\r\n'
    headers = ('Status: ' + status + '\r\n' + allow_header +
               'Content-Type: text/plain; charset=utf-8\r\n\r\n').encode('ascii')
    sys.stdout.buffer.write(headers + body)
    sys.stdout.buffer.flush()


def main():
    if os.environ.get('REQUEST_METHOD') != 'POST':
        respond('405 Method Not Allowed', 'expected POST\n', allow='POST')
        return 2
    if os.environ.get('CONTENT_TYPE', '').split(';', 1)[0].strip().lower() != 'text/plain':
        respond('415 Unsupported Media Type', 'expected text/plain\n')
        return 2
    raw = os.environ.get('CONTENT_LENGTH', '')
    if not raw or not raw.isascii() or not raw.isdecimal() or len(raw) > 10:
        respond('400 Bad Request', 'invalid CONTENT_LENGTH\n')
        return 2
    length = int(raw)
    if length > 1024:
        respond('413 Content Too Large', 'maximum body is 1024 bytes\n')
        return 2
    mode = os.environ.get('DEMO_MODE')
    if mode not in ('before', 'after'):
        respond('500 Internal Server Error', 'missing demonstration mode\n')
        return 2
    body = bytearray()
    while len(body) < length:
        chunk = sys.stdin.buffer.read(length - len(body))
        if not chunk:
            respond('400 Bad Request', 'EOF before declared body length\n')
            return 2
        body.extend(chunk)
    respond('200 OK', f'mode={mode}; bytes={len(body)}; hex={body.hex()}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
