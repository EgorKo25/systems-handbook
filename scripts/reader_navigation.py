"""Keep authored section numbers without a second browser-generated number.

Only navigation lists are changed. Chapter headings, link labels/anchors,
ordinary ordered examples and the chapter-number column remain untouched.
"""
from html.parser import HTMLParser
import re

CLASS = 'reader-authored-numbers'
STYLE_ID = 'reader-navigation-style'
STYLE = ('<style id="'+STYLE_ID+'">'
         '.local-toc ol.'+CLASS+',.volume-toc ol.'+CLASS+'{'
         'list-style:none;padding-left:0;padding-inline-start:0}'
         '</style>')
NUMBER = re.compile(r'^\s*(?:\d+(?:\.\d+)*[.)]|[IVXLCDM]+\.)\s+')
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class NavigationLists(HTMLParser):
    def __init__(self, page):
        super().__init__(convert_charrefs=True)
        self.offsets = [0]
        self.offsets.extend(match.end() for match in re.finditer('\n', page))
        self.stack = []
        self.lists = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get('class') or '').split())
        scope = bool(classes & {'local-toc','volume-toc'}) or bool(self.stack and self.stack[-1]['scope'])
        entry = dict(tag=tag, scope=scope, ordered=None, item=None)
        if tag == 'ol' and scope:
            line, column = self.getpos()
            entry['ordered'] = dict(start=self.offsets[line-1]+column,
                                    opening=self.get_starttag_text(), labels=[])
            self.lists.append(entry['ordered'])
        if tag == 'li' and self.stack and self.stack[-1]['ordered'] is not None:
            entry['item'] = []
            self.stack[-1]['ordered']['labels'].append(entry['item'])
        if tag not in VOID:
            self.stack.append(entry)

    def handle_endtag(self, tag):
        # Navigation markup is explicitly closed. Recover gracefully around an
        # unrelated optional HTML end tag without carrying its scope onward.
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for entry in reversed(self.stack):
            if entry['item'] is not None:
                entry['item'].append(data)
                return
            if entry['tag'] in {'ol','ul'}:
                return


def numbered_class(opening, enabled):
    attribute = re.search(r'\sclass\s*=\s*(["\'])(.*?)\1', opening, re.S|re.I)
    old = attribute[2].split() if attribute else []
    new = [name for name in old if name != CLASS]
    if enabled:
        new.append(CLASS)
    if new == old:
        return opening
    if attribute:
        replacement = ' class='+attribute[1]+' '.join(new)+attribute[1] if new else ''
        return opening[:attribute.start()]+replacement+opening[attribute.end():]
    return opening[:-1]+' class="'+CLASS+'">' if enabled else opening


def normalize_reader_navigation(page):
    parser = NavigationLists(page)
    parser.feed(page)
    authored = False
    for record in reversed(parser.lists):
        # Mixed lists also lose automatic markers: preserve the explicit 1.1
        # hierarchy and unnumbered subheadings, rather than duplicate only some.
        enabled = any(NUMBER.match(''.join(label)) for label in record['labels'])
        authored = authored or enabled
        opening = numbered_class(record['opening'], enabled)
        start = record['start']
        page = page[:start]+opening+page[start+len(record['opening']):]
    page = re.sub(r'<style\b[^>]*id=["\']'+STYLE_ID+r'["\'][^>]*>.*?</style>', '', page, flags=re.S|re.I)
    if authored:
        if '</head>' in page:
            page = page.replace('</head>', STYLE+'</head>', 1)
        else:
            page = STYLE+page
    return page
