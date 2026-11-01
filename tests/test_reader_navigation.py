"""Navigation numbers have one source; ordinary numbered prose is unaffected."""
from html.parser import HTMLParser
from pathlib import Path
import importlib.util
import unittest

SPEC=importlib.util.spec_from_file_location('reader_navigation',Path(__file__).resolve().parents[1]/'scripts/reader_navigation.py')
NAV=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NAV)


def document(body):
    return '<!doctype html><html><head><title>Reader</title></head><body>'+body+'</body></html>'


class Links(HTMLParser):
    def __init__(self,page):
        super().__init__(); self.links=[];self.active=None;self.feed(page)
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            self.active=[dict(attrs).get('href'),[]]
    def handle_data(self,data):
        if self.active is not None:self.active[1].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.active is not None:
            self.links.append((self.active[0],''.join(self.active[1])))
            self.active=None


class ReaderNavigationTests(unittest.TestCase):
    def test_authored_hierarchical_numbers_keep_their_labels_and_order(self):
        page=document('<details class="local-toc"><summary>Contents</summary><ol>'
                      '<li><a href="#purpose">1. Purpose</a></li>'
                      '<li><a href="#versions">1.1. Versions</a></li>'
                      '<li><a href="#state">1.2. State &amp; data</a></li></ol></details>'
                      '<h2 id="versions">1.1. Versions</h2>')
        result=NAV.normalize_reader_navigation(page)
        self.assertIn('<ol class="reader-authored-numbers">',result)
        self.assertEqual(Links(result).links,Links(page).links)
        self.assertIn('<h2 id="versions">1.1. Versions</h2>',result)
        self.assertIn('list-style:none;padding-left:0;padding-inline-start:0',result)

    def test_mixed_toc_disables_only_its_automatic_markers(self):
        page=document('<details class="local-toc"><ol>'
                      '<li><a href="#intro">Introduction</a></li>'
                      '<li><a href="#one">01. One</a></li>'
                      '<li class="toc-sub"><a href="#detail">Detail</a></li>'
                      '</ol></details><ol id="recipe"><li>1. Literal example</li></ol>')
        result=NAV.normalize_reader_navigation(page)
        self.assertIn('<ol class="reader-authored-numbers">',result)
        self.assertIn('<ol id="recipe"><li>1. Literal example</li></ol>',result)
        self.assertEqual(Links(result).links,Links(page).links)

    def test_plain_toc_keeps_browser_numbering_and_protocol_title_is_not_a_prefix(self):
        page=document('<details class="local-toc"><ol>'
                      '<li><a href="#wifi">802.11 radio</a></li>'
                      '<li><a href="#go">Go 1.27</a></li></ol></details>')
        self.assertEqual(NAV.normalize_reader_navigation(page),page)

    def test_volume_contents_and_nested_lists_are_independent(self):
        page=document('<div class="volume-toc"><ol class="chapters">'
                      '<li><a href="#one">1) First</a><ol>'
                      '<li><a href="#sub">Unnumbered child</a></li></ol></li>'
                      '<li><a href="#two">2) Second</a></li></ol></div>')
        result=NAV.normalize_reader_navigation(page)
        self.assertIn('<ol class="chapters reader-authored-numbers">',result)
        self.assertIn('<ol><li><a href="#sub">Unnumbered child</a>',result)
        self.assertEqual(Links(result).links,Links(page).links)

    def test_no_changes_to_sidebar_numbers_or_ordinary_lists(self):
        page=document('<nav class="chapter-nav"><a href="#one">'
                      '<span class="chapter-num">01</span><span>Chapter title</span></a></nav>'
                      '<ol><li>1. An ordinary example</li></ol>')
        self.assertEqual(NAV.normalize_reader_navigation(page),page)

    def test_idempotent_and_stale_owned_class_is_removed(self):
        page=document('<details class="local-toc"><ol><li><a href="#x">1. X</a></li></ol></details>')
        result=NAV.normalize_reader_navigation(page)
        self.assertEqual(NAV.normalize_reader_navigation(result),result)
        changed=result.replace('>1. X<','>X<')
        fixed=NAV.normalize_reader_navigation(changed)
        self.assertNotIn('reader-authored-numbers',fixed)
        self.assertNotIn('reader-navigation-style',fixed)
        self.assertIn('<ol>',fixed)
        self.assertEqual(NAV.normalize_reader_navigation(fixed),fixed)


if __name__=='__main__':unittest.main()
