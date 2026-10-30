#!/usr/bin/env python3
"""Local, unprivileged TCP experiment. Binds only 127.0.0.1, ephemeral port."""
import queue
import socket
import threading


def receive_exact(sock, size):
    result = bytearray()
    while len(result) < size:
        part = sock.recv(size-len(result))
        if not part:
            raise EOFError(f"Ранний конец: ожидалось {size}, получено {len(result)}")
        result.extend(part)
    return bytes(result)


def receive_message(sock):
    size = int.from_bytes(receive_exact(sock, 4), "big")
    if size > 1024:
        raise ValueError("Размер больше учебного лимита 1024 байта")
    return receive_exact(sock, size)


def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    address = listener.getsockname()
    results = queue.Queue()

    def server():
        try:
            with listener:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(5)
                    messages = [receive_message(conn), receive_message(conn)]
                    eof = conn.recv(1)
                    if eof != b"":
                        raise AssertionError("Ожидался конец клиентского потока")
                    conn.sendall(b"\x00\x00\x00\x02OK")
                    results.put((messages, eof, None))
        except BaseException as error:
            results.put((None, None, error))

    worker = threading.Thread(target=server)
    worker.start()
    with socket.create_connection(address, timeout=5) as client:
        data = b"\x00\x00\x00\x05HELLO\x00\x00\x00\x06WORLD!"
        # Deliberately split inside a length field and inside message bodies.
        cuts = [1, 3, 7, 10, 15, len(data)]
        begin = 0
        for end in cuts:
            client.sendall(data[begin:end])
            begin = end
        client.shutdown(socket.SHUT_WR)
        answer = receive_message(client)
        assert client.recv(1) == b""
    worker.join(timeout=6)
    if worker.is_alive():
        raise RuntimeError("Сервер не завершился вовремя")
    messages, eof, error = results.get(timeout=1)
    if error is not None:
        raise error
    assert messages == [b"HELLO", b"WORLD!"] and answer == b"OK"
    print("Путь: клиент 127.0.0.1 -> TCP ядра -> сервер 127.0.0.1")
    print("Клиент: 6 вызовов sendall; в потоке 19 байт")
    print("Сервер: сообщение 1 = b'HELLO'; сообщение 2 = b'WORLD!'")
    print("Сервер: recv после двух сообщений = b'' (конец клиентского потока)")
    print("Клиент: после shutdown(SHUT_WR) всё ещё получил b'OK'")
    print("Проверено: длины, содержимое, два направления и завершение")


if __name__ == "__main__":
    main()
