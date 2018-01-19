import bs4
from bs4 import BeautifulSoup
from bs4.dammit import EntitySubstitution
import jinja2

def clean_baike_html(soup):
    # baike fix begin
    for s in soup('span'):
        for c in s.children:
            if isinstance(c, bs4.element.Tag):
                if c.name == 'p':
                    s.replace_with_children()
                    break
    for s in soup(['ul', 'ol']):
        for c in s.children:
            if isinstance(c, bs4.element.Tag):
                if c.name != 'li':
                    s.decompose()
                    break
    # baike fix end

def process_node(node):
    if isinstance(node, bs4.element.NavigableString):
        return node.text
    else:
        if len(node.contents) == 1:
            return process_node(node.contents[0])
        elif len(node.contents) > 1:
            return map(process_node, node.children)

def clean_some_fixes(soup):
    for s in soup('blockquote'):
        s.wrap(soup.new_tag('p', **{'class':'_bq_fix'}))
        s.replace_with_children()
    for s in soup('p', class_='_bq_fix'):
        del s['class']
        s.wrap(soup.new_tag('blockquote'))

def deep_clean(soup):
    for s in soup(['script', 'style', 'a', 'dd', 'svg', 'ul', 'ol', 'meta', 'noscript']):
        s.decompose()
    for s in soup(['li', 'p', 'span']):
        if not s.text.strip():
            s.decompose()
    for s in soup(['ul','ol']):
        if not s.text.strip():
            s.decompose()
    for s in soup('div'):
        if not s.children:
            s.decompose()
    for s in soup(True):
        del s['id']
    for s in soup('img'):
        src = s.get('src')
        if not src or src.startswith('data:image/'):
            s.decompose()
        else:
            s['alt'] = '[IMG]'
    clean_baike_html(soup)
    clean_some_fixes(soup)
    return soup