"""Standalone markup for the dependency-free RESP stream teaching model."""
from html import escape


def render_resp() -> str:
    states = [
        ("0 · До чтения", "0 из 26 байт", "Нет готовых аргументов. Число элементов пока неизвестно. Ждём начало массива."),
        ("1 · Получены первые 8 байт", r"*2\r\n$3\r\n", "Заголовок объявил два аргумента. Первый должен содержать три байта. Само имя GET ещё не получено; готовых аргументов 0."),
        ("2 · Добавлены 13 байт, суммарно 21", r"GET\r\n$7\r\nbook", "Первый аргумент GET завершён. У ключа получены только 4 из 7 байт: book. Готовых аргументов 1 из 2; выполнять команду рано."),
        ("3 · Добавлены последние 5 байт, суммарно 26", r":42\r\n", "Ключ book:42 и его CRLF завершены. Готовы оба аргумента. Парсер может передать целую команду следующему этапу."),
    ]
    transcript = "".join(
        f"<li><strong>{escape(title)}</strong><br><code>{escape(wire)}</code><p>{escape(note)}</p></li>"
        for title, wire, note in states
    )
    return r'''<section class="resp-lab" id="cache-resp-stream" aria-labelledby="cache-resp-stream-title" data-resp-lab>
<h3 id="cache-resp-stream-title">Один запрос, три чтения: где заканчивается команда</h3>
<p>26 байт RESP2 приходят приложению искусственными порциями 8, 13 и 5 байт. Это границы чтений, а не TCP-пакетов или сегментов. Показано суммарное поступление; размер текущего входного буфера Redis может быть другим.</p>
<div data-resp-live hidden>
  <div class="resp-controls"><button type="button" data-resp-prev>← Назад</button><span data-resp-step></span><button type="button" data-resp-next>Принять 8 байт →</button></div>
  <div class="resp-bytes" data-resp-bytes aria-label="Байты запроса; нажмите байт для шестнадцатеричного вида"></div>
  <p class="resp-byte-note" data-resp-byte-note>Под символом указан номер байта, нумерация с нуля. Нажмите байт, чтобы увидеть hex — шестнадцатеричное значение.</p>
  <div class="resp-progress"><span data-resp-received></span><span data-resp-args></span></div>
  <div class="resp-explanation" role="status" aria-live="polite" aria-atomic="true"><strong data-resp-state></strong><p data-resp-explanation></p></div>
  <div class="resp-reply" data-resp-reply hidden>
    <label>Состояние ключа <select data-resp-response><option value="missing">Отсутствует</option><option value="empty">Пустая строка</option><option value="hello">Строка hello</option><option value="wrongtype">Другой тип данных</option></select></label>
    <pre><code data-resp-reply-wire></code></pre><p data-resp-reply-note aria-live="polite"></p>
  </div>
</div>
<details class="resp-transcript"><summary>Все шаги и ответы текстом</summary><ol>''' + transcript + r'''</ol>
<p>Отсутствие: <code>$-1\r\n</code> — корректный ответ с отсутствующим значением. Пустая строка: <code>$0\r\n\r\n</code> — найденное значение из нуля байт. Строка hello: <code>$5\r\nhello\r\n</code> — найденные пять байт.</p>
<p><code>-WRONGTYPE Operation against a key holding the wrong kind of value\r\n</code> — корректно закодированный ответ об ошибке команды GET для другого типа. Это не промах и не повреждённый RESP.</p></details>
<p class="resp-scope">Граница модели: массив RESP2 из строк с объявленной байтовой длиной — bulk strings. В ответах различаются такая строка, null — отсутствие значения — и простая ошибка. Вложенные массивы, остальные типы RESP2/RESP3 и исполнение Redis здесь не эмулируются. Учебные пределы: 0–128 аргументов, 1 MiB на строку, 4 MiB на вход; это ограничения модели.</p>
<p class="sources"><a href="https://redis.io/docs/latest/develop/reference/protocol-spec/">Официальная спецификация RESP</a>. Длины относятся к байтам после кодирования; CR и LF — отдельные байты 0D и 0A.</p>
</section>'''
