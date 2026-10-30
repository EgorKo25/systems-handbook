#!/usr/bin/env python3
"""Generate an artificial, deterministic teaching capture. No network access."""
from pathlib import Path
import argparse
import json
import socket
import struct
import tempfile

REQUEST = (b"GET /api/session HTTP/1.1\r\n"
           b"Host: app.lab.test:7000\r\n"
           b"Connection: close\r\n\r\n")
BODY = b'{"user":"alice"}'
RESPONSE = (b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(BODY)).encode() + b"\r\n"
            b"Connection: close\r\n\r\n" + BODY)
CLIENT_IP, SERVER_IP = "192.0.2.10", "198.51.100.20"
CLIENT_MAC = bytes.fromhex("020000000010")
GATEWAY_MAC = bytes.fromhex("020000000001")


def checksum(data):
    """Internet checksum; checksum(valid protected bytes) equals zero."""
    if len(data) % 2:
        data += b"\0"
    value = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    while value >> 16:
        value = (value & 0xffff) + (value >> 16)
    return (~value) & 0xffff


def packet(from_client, seq, ack, flags, payload=b"", ident=0x1234):
    src, dst = ((CLIENT_IP, SERVER_IP) if from_client
                else (SERVER_IP, CLIENT_IP))
    sport, dport = (49152, 7000) if from_client else (7000, 49152)
    src_b, dst_b = socket.inet_aton(src), socket.inet_aton(dst)
    tcp = struct.pack("!HHIIBBHHH", sport, dport, seq, ack,
                      0x50, flags, 64240, 0, 0)
    pseudo = src_b + dst_b + struct.pack("!BBH", 0, 6, len(tcp) + len(payload))
    tcp_sum = checksum(pseudo + tcp + payload)
    tcp = tcp[:16] + struct.pack("!H", tcp_sum) + tcp[18:]
    # On the client's LAN: outgoing TTL 64, incoming TTL 63, one router.
    ttl = 64 if from_client else 63
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40 + len(payload), ident,
                     0x4000, ttl, 6, 0, src_b, dst_b)
    ip_sum = checksum(ip)
    ip = ip[:10] + struct.pack("!H", ip_sum) + ip[12:]
    eth = ((GATEWAY_MAC + CLIENT_MAC) if from_client
           else (CLIENT_MAC + GATEWAY_MAC)) + b"\x08\x00"
    frame = eth + ip + tcp + payload
    # Ethernet minimum length without its 4-byte FCS is 60 bytes.
    frame += b"\0" * max(0, 60 - len(frame))
    assert checksum(ip) == 0
    assert checksum(pseudo + tcp + payload) == 0
    return frame, {"source": src, "destination": dst, "seq": seq, "ack": ack,
                   "flags": flags, "payload_length": len(payload),
                   "ipv4_length": 40 + len(payload), "frame_length": len(frame),
                   "ipv4_checksum": f"0x{ip_sum:04x}",
                   "tcp_checksum": f"0x{tcp_sum:04x}", "ttl": ttl}


def hexdump(data):
    return "\n".join(f"{i:04x}  " + " ".join(f"{b:02x}" for b in data[i:i+16]).ljust(47)
                     + "  " + "".join(chr(b) if 32 <= b <= 126 else "."
                                     for b in data[i:i+16])
                     for i in range(0, len(data), 16))


def main():
    parser = argparse.ArgumentParser(
        description="Создать искусственный учебный PCAP без обращения к сети. "
                    "По умолчанию создаётся новый временный каталог; эталоны не меняются.")
    parser.add_argument("--output-dir", type=Path,
                        help="Новый, ещё не существующий каталог для результата")
    args = parser.parse_args()
    if args.output_dir is None:
        out = Path(tempfile.mkdtemp(prefix="dfbook-generated-"))
    else:
        out = args.output_dir.expanduser().resolve()
        if out.exists():
            parser.error("Каталог уже существует. Укажите новый каталог: "
                         "скрипт не перезаписывает существующие результаты и эталоны.")
        out.mkdir(parents=True, exist_ok=False)
    ce, se = 1001 + len(REQUEST), 9001 + len(RESPONSE)
    plan = [
        ("SYN", True, 1000, 0, 0x02, b"", 0x1231),
        ("SYN, ACK", False, 9000, 1001, 0x12, b"", 0x2231),
        ("ACK", True, 1001, 9001, 0x10, b"", 0x1232),
        ("HTTP request", True, 1001, 9001, 0x18, REQUEST, 0x1234),
        ("ACK request", False, 9001, ce, 0x10, b"", 0x2232),
        ("HTTP response", False, 9001, ce, 0x18, RESPONSE, 0x2233),
        ("server FIN, ACK", False, se, ce, 0x11, b"", 0x2234),
        ("ACK server FIN", True, ce, se + 1, 0x10, b"", 0x1235),
        ("client FIN, ACK", True, ce, se + 1, 0x11, b"", 0x1236),
        ("ACK client FIN", False, se + 1, ce + 1, 0x10, b"", 0x2235),
    ]
    frames, records = [], []
    pcap = bytearray(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
    for n, (name, direction, seq, ack, flags, payload, ident) in enumerate(plan, 1):
        frame, meta = packet(direction, seq, ack, flags, payload, ident)
        frames.append(frame)
        records.append({"number": n, "name": name, **meta})
        pcap += struct.pack("<IIII", 1700000000, (n-1)*10000,
                            len(frame), len(frame)) + frame
    (out / "document-flow-http.pcap").write_bytes(pcap)
    fields = [
        (0, 6, "Ethernet: MAC назначения", "02:00:00:00:00:01"),
        (6, 6, "Ethernet: MAC источника", "02:00:00:00:00:10"),
        (12, 2, "EtherType", "0x0800 — IPv4"),
        (14, 1, "IPv4: версия / IHL", "0x45 — IPv4, 20 байт"),
        (15, 1, "IPv4: DSCP / ECN", "0x00"),
        (16, 2, "IPv4: полная длина", str(40+len(REQUEST))),
        (18, 2, "IPv4: Identification", "0x1234"),
        (20, 2, "IPv4: флаги / смещение", "0x4000 — DF=1, offset=0"),
        (22, 1, "IPv4: TTL", "64"),
        (23, 1, "IPv4: протокол", "6 — TCP"),
        (24, 2, "IPv4: checksum", records[3]["ipv4_checksum"]),
        (26, 4, "IPv4: источник", CLIENT_IP),
        (30, 4, "IPv4: назначение", SERVER_IP),
        (34, 2, "TCP: порт источника", "49152"),
        (36, 2, "TCP: порт назначения", "7000"),
        (38, 4, "TCP: Sequence Number", "1001"),
        (42, 4, "TCP: Acknowledgment Number", "9001"),
        (46, 1, "TCP: Data Offset / reserved", "0x50 — 20 байт"),
        (47, 1, "TCP: флаги", "0x18 — PSH, ACK"),
        (48, 2, "TCP: окно", "64240; масштабирование не согласовано"),
        (50, 2, "TCP: checksum", records[3]["tcp_checksum"]),
        (52, 2, "TCP: Urgent Pointer", "0"),
        (54, len(REQUEST), "HTTP/1.1: запрос", REQUEST.decode("ascii")),
    ]
    explanations = [
        ("Кому передать кадр на ближайшем Ethernet-участке.", "Ядро клиента после выбора маршрута и разрешения адреса шлюза.", "Сетевая карта и коммутатор; затем интерфейс маршрутизатора.", "Это MAC шлюза, потому что адрес сервера находится в другой подсети. MAC сервера здесь не нужен."),
        ("От какого интерфейса пришёл кадр на этом участке.", "Ядро/драйвер клиента берёт MAC выбранного интерфейса.", "Коммутатор обучается расположению этого MAC, маршрутизатор принимает кадр.", "При маршрутизации MAC источника изменится на MAC выходного интерфейса маршрутизатора."),
        ("Какому разборщику передать содержимое Ethernet.", "Отправитель кадра при инкапсуляции.", "Принимающий сетевой стек.", "0x0800 означает IPv4; 0x0806 означал бы ARP. Нельзя сразу считать следующие байты TCP."),
        ("Версия IP и граница между его заголовком и данными.", "Отправляющий IP-стек.", "Маршрутизаторы и IP-стек получателя.", "Старшая половина 4: IPv4. Младшая 5: 5×4=20 байт; TCP начинается на 14+20=34."),
        ("Пометки обслуживания и явного сообщения о перегрузке.", "Отправляющий стек/политика; некоторые биты могут менять узлы пути.", "Узлы, поддерживающие соответствующую политику или ECN.", "Ноль здесь означает DSCP=0, ECN=Not-ECT. Это не число приоритета процесса."),
        ("Сколько байтов относится к IPv4, включая его заголовок.", "Отправляющий IP-стек из фактических размеров.", "Принимающий IP-стек и маршрутизатор.", "113=20+20+73. Ethernet-заголовок и Ethernet-дополнение в это число не входят."),
        ("Идентификатор, используемый при сборке фрагментов IPv4 в условиях, где он значим.", "Отправляющий IP-стек; в искусственном примере задан явно.", "Механизм сборки фрагментов у получателя.", "Это не TCP SEQ и не универсальный счётчик запросов. В нашем нефрагментируемом пакете не нужен для сборки."),
        ("Можно ли фрагментировать пакет и где лежит данный фрагмент.", "Отправляющий IP-стек; при допустимой фрагментации поля формируют и маршрутизаторы.", "Маршрутизатор и сборщик фрагментов получателя.", "0x4000: DF=1, MF=0, смещение0. При слишком малом MTU маршрутизатор не вправе дробить этот пакет."),
        ("Ограничитель числа дальнейших пересылок.", "Источник задаёт начальное значение; каждый маршрутизатор уменьшает его.", "Маршрутизаторы.", "64 в исходящем кадре станет63 после одного маршрутизатора. Это не число секунд с момента отправки."),
        ("Какой протокол находится внутри IPv4.", "Отправляющий IP-стек.", "IP-стек адресата и промежуточные фильтры.", "6 выбирает TCP; 17 выбирал бы UDP. Это не номер порта."),
        ("Проверка целостности только IPv4-заголовка.", "Источник; маршрутизатор обновляет при изменении TTL.", "Узлы, проверяющие IPv4-заголовок.", "0x3c01 верно для TTL64. После TTL63 без других изменений сумма становится0x3d01."),
        ("Адрес отправителя на уровне IP.", "Маршрутизация и IP-стек источника.", "Узлы пути и адресат; адресат использует для обратного направления.", "192.0.2.10 сохраняется через обычный маршрутизатор; при NAT правило было бы другим."),
        ("Конечный адресат IPv4-пакета.", "Приложение задаёт адрес назначения сокета; стек записывает его.", "Маршрутизаторы выбирают путь; конечный стек принимает локально.", "198.51.100.20 остаётся тем же при замене MAC на каждом Ethernet-участке."),
        ("Номер локального конца TCP-соединения у клиента.", "Обычно ядро выбирает временный свободный порт при connect; приложение может привязать явно.", "TCP сервера и TCP клиента при сопоставлении соединения.", "49152=0xc000. Порт не идентификатор процесса и не обязателен для всех запросов этого приложения."),
        ("Номер службы на конечном хосте.", "Клиент задаёт7000 при соединении.", "TCP сервера ищет соответствующий слушающий/установленный сокет.", "7000=0x1b58. Разные IP могут иметь независимые службы с тем же портом."),
        ("Номер первого байта данных в потоке этого направления.", "TCP отправителя ведёт своё пространство номеров.", "TCP получателя упорядочивает данные и распознаёт повторы.", "Данные занимают1001…1073; следующее ожидаемое число1074. Один TCP сегмент не равен одному HTTP сообщению."),
        ("Первый ещё не полученный непрерывно номер встречного потока.", "TCP отправителя на основании уже принятых байтов.", "TCP другой стороны подтверждает доставку в принимающий стек.", "9001 подтверждает серверный SYN9000; ответа HTTP ещё нет. ACK не доказывает чтение приложением."),
        ("Длина TCP-заголовка и зарезервированные биты.", "TCP отправителя по фактическому набору параметров.", "TCP получателя.", "Старшая половина5:20 байт. HTTP начинается на34+20=54; при TCP options граница сдвинулась бы."),
        ("Управляющие признаки, меняющие смысл полей и состояние соединения.", "TCP отправителя.", "TCP получателя.", "0x18=ACK0x10+PSH0x08. PSH не сообщает длину HTTP и не сохраняет границы sendall."),
        ("Объявленная способность принять байты встречного потока.", "TCP отправителя по состоянию принимающей стороны и её буферов.", "TCP другой стороны ограничивает отправку.", "64240=0xfaf0. Здесь множитель1: в SYN не согласована опция масштабирования."),
        ("Проверка TCP-заголовка, данных и служебной привязки к IP.", "TCP отправителя либо аппаратура при передаче.", "TCP получателя.", "0xdf89 рассчитана с псевдозаголовком. Ошибка в локальном захвате иногда связана с аппаратным вычислением после точки захвата."),
        ("Указатель срочных данных при установленном URG.", "TCP отправителя при использовании соответствующего механизма.", "TCP получателя, когда URG установлен.", "Ноль и URG=0: поле не обозначает полезные данные и не является длиной запроса."),
        ("Текст прикладного запроса, передаваемый как последовательность байтов.", "HTTP-клиент в приложении; TCP сохраняет значения и порядок байтов.", "HTTP-разборщик сервера после чтения сокета.", "73 ASCII-байта, завершение заголовков0d0a0d0a; сервер должен сам найти границу сообщения."),
    ]
    enriched_fields = []
    for (o, l, n, v), (role, writer, reader, diagnostic) in zip(fields, explanations):
        enriched_fields.append({"offset": o, "length": l, "name": n, "value": v,
                                "role": role, "writer": writer, "reader": reader,
                                "diagnostic": diagnostic})
    assert len(explanations) == len(fields)
    view = {"capture": "document-flow-http.pcap", "packet_number": 4,
            "hex": frames[3].hex(), "bytes": list(frames[3]),
            "request_ascii": REQUEST.decode("ascii"),
            "request_length": len(REQUEST), "response_length": len(RESPONSE),
            "fields": enriched_fields, "packets": records}
    (out / "packet-map.json").write_text(json.dumps(view, ensure_ascii=False, indent=2)+"\n")
    lines = ["Синтетический учебный PCAP; реальная сеть не использована.",
             "Захват на Ethernet-сегменте клиента. Linktype=1, classic pcap, little-endian.",
             "Преамбула, SFD, FCS, межкадровый интервал отсутствуют. Padding присутствует.",
             "Один маршрутизатор, без NAT. TCP options отсутствуют, window scaling не согласован.",
             "Абсолютные SEQ/ACK. SYN и FIN занимают по одному номеру последовательности.",
             f"Request={len(REQUEST)} bytes; response={len(RESPONSE)} bytes; body={len(BODY)} bytes.",
             "", json.dumps(records, ensure_ascii=False, indent=2), "",
             "Пакет 4, смещения от начала Ethernet:", hexdump(frames[3]), "",
             "HTTP request repr:", repr(REQUEST), "", "HTTP response repr:", repr(RESPONSE)]
    (out / "document-flow-http.txt").write_text("\n".join(lines)+"\n")
    print(f"Результаты записаны в новый каталог: {out}")
    print(f"Создано кадров: {len(frames)}; запрос: {len(REQUEST)} байтов; ответ: {len(RESPONSE)} байтов")
    print(json.dumps(records[3], ensure_ascii=False))
    print(hexdump(frames[3]))


if __name__ == "__main__":
    main()
