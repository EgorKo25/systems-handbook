"""Compile mission contracts and original commentary into maintained chapters."""
from pathlib import Path
from html import escape
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
RECIPE_STATUS = {
    'vm-lifecycle-prepared-guest-not-boot-tested': 'Подготовлен контроллер жизненного цикла VM; ОС ещё предстоит установить и проверить.',
    'manual-recipe-prepared-ssh-not-tested': 'Подготовлен рецепт SSH; вход на настоящем госте ещё не проверен.',
    'linux-netns-recipe-prepared-not-executed': 'Подготовлены скрипт и рецепт сети Linux; запуск внутри гостя ещё не проверен.',
    'packet-tracer-configs-prepared-not-cli-tested': 'Подготовлены конфигурации устройств; схема ещё не собрана и не проверена в Packet Tracer.',
    'http-linux-recipe-prepared-not-executed': 'Подготовлен рецепт HTTP в Linux; полный сценарий внутри гостя ещё не выполнен.',
    'dhcp-dns-pt-recipe-prepared-tls-planned': 'Есть рецепт DHCP/DNS для модели Cisco; отдельную службу TLS ещё предстоит собрать и проверить.',
    'pt-linux-recipes-prepared-other-tools-not-installed': 'Есть рецепты Packet Tracer и Linux; остальные среды предстоит получить, установить и проверить.',
}


def chapter_label(href):
    match = re.fullmatch(r'\.\./([a-z-]+)/index\.html#(.+)', href)
    if not match:
        raise ValueError(f'Unexpected chapter link: {href}')
    slug, anchor = match.groups()
    page = (ROOT/slug/'index.html').read_text()
    data = json.loads(re.search(r'<script[^>]*id="book-data"[^>]*>(.*?)</script>',page,re.S)[1])
    chapter = next((row for row in data if row['id']==anchor), None)
    if chapter is None:
        raise ValueError(f'Unknown chapter: {href}')
    labels = {'networks':'Сети','linux':'Linux','bash':'Bash','postgres':'PostgreSQL','cache':'Кэш','git':'Git','go':'Go','jenkins':'Jenkins','gitlab':'GitLab'}
    return labels[slug]+' · '+chapter['title']


def text(value):
    return escape(str(value))


def prepare():
    from .technology_starts import technology_start
    curriculum = json.loads((ROOT/'labs-personal/chapter-map.json').read_text())
    for mission in curriculum['stages']:
        identifier = mission['id']
        source = SRC/'missions'/f'{identifier}.html'
        fragment = source.read_text()
        sections = {}
        for part in ('analysis','hints','debrief'):
            match = re.search(r'<section data-mission-'+part+r'>(.*?)</section>',fragment,re.S)
            if not match:
                raise ValueError(f'{identifier}: missing {part}')
            sections[part] = match[1]
        contract = mission['mission']
        resources = mission['resources']
        before = mission['checkpoints']['before']
        after = mission['checkpoints']['after']
        body = '<header><h1>'+text(mission['title'])+'</h1><p>'+text(contract['context'])+'</p></header>'
        body += '<h2>Заявка и исходные условия</h2><p><strong>'+text(contract['ticket'])+'</strong></p>'
        body += '<p><strong>Доступ:</strong> '+text(contract['access_constraints'])+'</p>'
        body += '<p><strong>Наблюдаемый симптом:</strong> '+text(contract['symptoms'])+'</p>'
        body += '<p><strong>Доказательства результата:</strong> '+text(contract['success_evidence'])+'</p>'
        body += '<p><strong>Возврат:</strong> '+text(contract['rollback'])+'</p>'
        dependencies = mission['depends_on']
        if dependencies:
            body += '<p>Исходное состояние подготовлено в заданиях: '+', '.join('<a href="#'+text(i)+'">'+text(i)+'</a>' for i in dependencies)+'.</p>'
        if identifier == 'P00-rescue-bootstrap':
            body += '<p>До появления установленного гостя сохраняются ISO, его проверка и описание создаваемой машины. Точку <code>'+text(before)+'</code> можно сделать после первой установки, перед изменением доступа. После приёмки создаётся <code>'+text(after)+'</code>. Холодные точки сохраняют диск выключенного гостя, без открытых сеансов и памяти процессов.</p>'
        else:
            body += '<p>Контрольные точки выключенного мира: <code>'+text(before)+'</code> перед работой и <code>'+text(after)+'</code> после проверок. Это сохранение дискового состояния, без открытых сеансов и памяти процессов.</p>'
        memory = resources['guest_memory_mib_estimate']
        if memory is None:
            body += '<p>Ресурсы этого этапа оцениваются для выбранного симулятора или эмулятора на компьютере. Дополнительный фиксированный бюджет памяти Linux-гостя здесь не назначен.</p>'
        else:
            body += '<p>Начальная оценка памяти гостя: '+text(memory)+' МиБ. Это бюджет для проверки состава ролей, а не измеренное требование и не гарантия достаточности для всех служб вместе.</p>'
        status = mission['implementation_status']
        if status not in RECIPE_STATUS:
            body += '<aside class="callout"><strong>Этап развития стенда.</strong> Условие и разбор подготовлены; нужные роли и ограничения доступа ещё предстоит развернуть и проверить. Их работоспособность этим текстом не подтверждается.</aside>'
        else:
            body += '<aside class="callout"><strong>Подготовлен рецепт.</strong> '+text(RECIPE_STATUS[status])+' Полный запуск этого сценария на QEMU и Windows пока не подтверждён.</aside>'
        links = mission.get('chapters',[])
        if links:
            body += '<p><strong>Перед первой попыткой.</strong> Если механизм ещё не знаком, сначала прочитайте связанные главы: '+', '.join('<a href="'+text(link['href'])+'">'+text(link.get('title') or chapter_label(link['href']))+'</a>' for link in links)+'. Ниже упражнение использует эти основы; открытие подсказок не заменяет первоначального знакомства с инструментом.</p>'
        body += technology_start(identifier)
        body += '<h2>Как подойти к работе</h2>'+sections['analysis']
        assets = mission.get('assets',[])
        if assets:
            body += '<p>Файлы задания: '+', '.join('<a href="../labs-personal/'+text(name)+'">'+text(name)+'</a>' for name in assets)+'.</p>'
        body += '<details><summary>Подсказки · открыть после своей попытки</summary>'+sections['hints']+'</details>'
        body += '<details><summary>Разбор и проверка результата</summary>'+sections['debrief']+'</details>'
        body += '<h2>Что передать следующему этапу</h2><p>Сохрани отчёт по рабочему методу: исходные наблюдения, проверенную причину, изменения, положительные и отрицательные проверки и способ возврата. Затем выключи гость и создай точку <code>'+text(after)+'</code>. Новая глава использует этот результат; её открытие ничего не сбрасывает.</p>'
        path=SRC/f'{identifier}.html'
        if not path.exists() or path.read_text()!=body+'\n':path.write_text(body+'\n')
