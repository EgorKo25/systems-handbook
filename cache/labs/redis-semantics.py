"""Verify transaction, WATCH, list, stream and ACL examples on one owned Redis.

Linux + Redis required. No existing server is used. No load or durability claim.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from live import Redis, port, wait_ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--redis-server', default='redis-server')
    args = parser.parse_args()
    if not shutil.which(args.redis_server):
        parser.error('Missing Redis binary: ' + args.redis_server)
    output = Path(__file__).with_name('redis-semantics-results.json')
    report = {
        'status': 'RUNNING',
        'kind': 'actual owned loopback Redis process',
        'cases': [],
        'limits': ['No load test', 'No persistence or power-loss test',
                   'No network partition or cluster in this script'],
    }

    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def check(name, actual, expected):
        if actual != expected:
            raise AssertionError(f'{name}: {actual!r} != {expected!r}')
        report['cases'].append({'name': name, 'status': 'PASS', 'actual': actual})

    save()
    with tempfile.TemporaryDirectory(prefix='redis-book-semantics-') as folder:
        number = port()
        clients = []
        log_path = Path(folder) / 'redis.log'
        with log_path.open('wb') as log:
            process = subprocess.Popen([
                args.redis_server, '--bind', '127.0.0.1', '--port', str(number),
                '--save', '', '--appendonly', 'no', '--dir', folder,
            ], stdout=log, stderr=log)
            try:
                wait_ready(process, number)
                first, second = Redis(number), Redis(number)
                clients.extend([first, second])
                report['redis_version'] = next(line.split(':', 1)[1]
                    for line in first.send('INFO', 'server').splitlines()
                    if line.startswith('redis_version:'))
                check('set non-integer', first.send('SET', 'book:tx-number', 'text'), 'OK')
                check('begin transaction', first.send('MULTI'), 'OK')
                for command in [('SET', 'book:tx-first', 'done'),
                                ('INCR', 'book:tx-number'),
                                ('SET', 'book:tx-last', 'done')]:
                    first.send(*command)
                result = first.send('EXEC')
                check('first EXEC result', result[0], 'OK')
                check('middle EXEC runtime error', bool(result[1].get('error')), True)
                check('last EXEC result', result[2], 'OK')
                check('successful effects survive neighboring runtime error',
                      first.send('MGET', 'book:tx-first', 'book:tx-number', 'book:tx-last'),
                      ['done', 'text', 'done'])

                first.send('SET', 'book:balance', 10)
                first.send('WATCH', 'book:balance')
                check('watched read', first.send('GET', 'book:balance'), '10')
                second.send('INCR', 'book:balance')
                first.send('MULTI')
                first.send('SET', 'book:balance', 11)
                check('WATCH conflict aborts EXEC', first.send('EXEC'), None)

                check('list count', first.send('LPUSH', 'book:list-demo', 'job-A', 'job-B'), 2)
                check('list left-to-right order', first.send('LRANGE', 'book:list-demo', 0, 9), ['job-B', 'job-A'])
                check('opposite ends implement FIFO', first.send('RPOP', 'book:list-demo'), 'job-A')

                check('stream group created', first.send('XGROUP', 'CREATE', 'book:events-demo', 'workers', 0, 'MKSTREAM'), 'OK')
                identifier = first.send('XADD', 'book:events-demo', '*', 'type', 'price-changed', 'product', '42')
                first.send('XREADGROUP', 'GROUP', 'workers', 'consumer-1', 'COUNT', 1, 'STREAMS', 'book:events-demo', '>')
                check('pending before acknowledgement', first.send('XPENDING', 'book:events-demo', 'workers')[0], 1)
                check('XACK acknowledges one entry', first.send('XACK', 'book:events-demo', 'workers', identifier), 1)
                check('pending after acknowledgement', first.send('XPENDING', 'book:events-demo', 'workers')[0], 0)
                check('XACK retains stream data', first.send('XLEN', 'book:events-demo'), 1)

                first.send('ACL', 'SETUSER', 'book-reader', 'reset', 'on', '>old',
                           '~book:product:*', '+get', '+mget', '+ttl', '+ping')
                check('initial ACL authentication', second.send('AUTH', 'book-reader', 'old'), 'OK')
                first.send('ACL', 'SETUSER', 'book-reader', '>new')
                first.send('ACL', 'SETUSER', 'book-reader', '<old')
                third = Redis(number)
                clients.append(third)
                check('old password rejected for new authentication',
                      'WRONGPASS' in third.send('AUTH', 'book-reader', 'old')['error'], True)
                check('new password accepted', third.send('AUTH', 'book-reader', 'new'), 'OK')
                check('previously authenticated connection remains usable', second.send('PING'), 'PONG')
                report['status'] = 'PASS'
                report['cases_count'] = len(report['cases'])
                save()
                print(json.dumps({'status': report['status'], 'cases': report['cases_count'],
                                  'redis_version': report['redis_version']}))
            except Exception as error:
                report['status'] = 'FAIL'
                report['error'] = str(error)
                save()
                raise
            finally:
                for client in clients:
                    try:
                        client.close()
                    except OSError:
                        pass
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    main()
