"""Explicit text-export markers; ordinary SVG and prose keep existing semantics."""
from pathlib import Path
import re
import unittest

from cache.build import plain


class PlainProjectionTests(unittest.TestCase):
    def test_nested_rendering_omitted_without_losing_neighbors(self):
        value = ('<p>Before</p><figure><h3>Figure</h3><p>Intro</p>'
                 '<div data-plain-skip="true"><span>HIDDEN</span>'
                 '<div data-plain-skip="true">DEEP</div></div>'
                 '<table><tr><td>Visible row</td></tr></table>'
                 '<figcaption><p>Caption</p></figcaption></figure><p>After</p>')
        result = plain(value)
        self.assertNotIn('HIDDEN', result)
        self.assertNotIn('DEEP', result)
        self.assertEqual(result, 'Before\n\nFigure\n\nIntro\n\n | Visible row\n\nCaption\n\nAfter')

    def test_void_and_self_closing_nodes_do_not_extend_ignored_subtree(self):
        for void in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                     'link', 'meta', 'param', 'source', 'track', 'wbr'):
            with self.subTest(void=void):
                value = ('<p>A</p><div data-plain-skip="true"><'+void+'>'
                         '<svg><g><path d="M0 0"/></g></svg><'+void+'/>'
                         'HIDDEN</div><p>B</p>')
                self.assertEqual(plain(value), 'A\n\nB')
        self.assertEqual(plain('<p>A</p><svg data-plain-skip="true"/><p>B</p>'), 'A\n\nB')
        self.assertEqual(plain('<p>A</p><img data-plain-skip="true"><p>B</p>'), 'A\n\nB')

    def test_script_style_inside_skip_does_not_poison_following_text(self):
        value = ('<div data-plain-skip="true"><script>if(x<2) fake();</script>'
                 '<style>.x{color:red}</style><p>HIDDEN</p></div>'
                 '<p>Visible</p><script>ordinaryHidden()</script><p>After</p>')
        self.assertEqual(plain(value), 'Visible\n\nAfter')

    def test_character_references_and_quoted_angle_bracket(self):
        value = ('<p>A&amp;B &#x41; &lt;ok&gt; &nbsp;C</p>'
                 '<div title="a>b" data-plain-skip="tr&#117;e">HIDDEN</div>'
                 '<p>Привет&#33;</p>')
        self.assertEqual(plain(value), 'A&B A <ok> \xa0C\n\nПривет!')

    def test_unmarked_svg_and_matching_class_are_not_globally_skipped(self):
        value = ('<svg><text>SVG stays</text></svg>'
                 '<div class="cow-screen">Class stays</div>'
                 '<div class="cow-print">Print class stays</div>')
        self.assertEqual(plain(value), 'SVG staysClass staysPrint class stays')

    def test_marker_requires_explicit_true_value(self):
        for attr in ('data-plain-skip="false"', 'data-plain-skip="TRUE"',
                     'data-plain-skip', 'data-plain-skip=""'):
            with self.subTest(attr=attr):
                self.assertEqual(plain('<p '+attr+'>kept</p><p>after</p>'), 'kept\n\nafter')

    def test_literal_marker_text_does_not_hide_content(self):
        self.assertEqual(plain('<p>data-plain-skip is a word &amp; stays</p>'),
                         'data-plain-skip is a word & stays')

    def test_html_attribute_name_case_does_not_depend_on_comment_or_raw_literal(self):
        fragment = '<p>A</p><DIV DATA-PLAIN-SKIP="true"><b>HIDDEN</b></DIV><p>B</p>'
        self.assertEqual(plain(fragment), 'A\n\nB')
        self.assertEqual(plain('<!-- data-plain-skip -->' + fragment), 'A\n\nB')
        self.assertEqual(plain('<p title="data-plain-skip">A</p><p>B</p>'), 'A\n\nB')
        self.assertEqual(plain('<p>A</p><!-- DATA-PLAIN-SKIP="true" --><p>B</p>'), 'A\n\nB')
        self.assertEqual(plain('<div DATA-PLAIN-SKIP="TRUE">kept</div>'), 'kept')
        self.assertEqual(plain('<p>data-plain-skip</p><svg><text>SVG stays</text></svg>'),
                         'data-plain-skipSVG stays')

    def test_malformed_marked_nesting_fails_instead_of_swallowing_remainder(self):
        for value in ('<div data-plain-skip="true"><span>x</div><p>outside</p>',
                      '<div data-plain-skip="true">x',
                      '<div data-plain-skip="true"><script>unfinished'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plain(value)

    def test_cow_source_has_one_complete_transcript_and_caption(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'operating-systems/sources/os-10-page-tables-faults.html').read_text()
        figure = re.search(r'<figure class="cow-cutaway" id="os-cow-page"[^>]*>[\s\S]*?</figure>', source)[0]
        result = plain(figure)
        self.assertEqual(result.count('6. Повторилась запись'), 1)
        self.assertEqual(result.count('Ядро удерживает G: 4096 байт'), 1)
        self.assertNotIn('Q ещё не создан', result)
        self.assertNotIn('Нового кадра ещё нет', result)
        self.assertNotIn('Шаг 6 из 6', result)
        self.assertNotIn('function states', result)
        self.assertIn('Строки сверху', result)
        self.assertIn('PA вычисляется как PFN×4096+0x124', result)
        self.assertEqual(figure.count('id="os-cow-page-title"'), 1)
        self.assertEqual(figure.count('data-plain-skip="true"'), 2)


if __name__ == '__main__':
    unittest.main()
