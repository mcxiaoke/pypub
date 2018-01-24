#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import os
import sys
import codecs
import bs4
from bs4 import BeautifulSoup

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

def is_html_file(content):
    soup = BeautifulSoup(content, "html.parser")
    return bool(soup.body)

def read_list(filename):
    if not os.path.isfile(filename):
        return []
    with codecs.open(filename, 'r', 'utf-8') as f:
        return filter(bool, [line.strip() for line in f])

def get_html_title(html_string):
    try:
        root = BeautifulSoup(html_string, 'html.parser')
        title_node = root.title
        if title_node is not None:
            title = unicode(title_node.string)
        else:
            raise ValueError
    except (IndexError, ValueError):
        title = '[TITLE]'
    return title.strip()

def strip_html_tags(html_string):
    soup = BeautifulSoup(html_string, 'html5lib')
    text = soup.find_all(text=lambda text:isinstance(text, bs4.element.NavigableString))
    text = " ".join(text)
    text = text.replace('&','')
    text = text.replace('<','')
    text = text.replace('>','')
    text = text.replace('\uE4C6','')
    return strip_invalid_xml_chars(text)

def _valid_xml_char_ordinal(c):
    codepoint = ord(c)
    # conditions ordered by presumed frequency
    return (
        0x20 <= codepoint <= 0xD7FF or
        codepoint in (0x9, 0xA, 0xD) or
        0xE000 <= codepoint <= 0xFFFD or
        0x10000 <= codepoint <= 0x10FFFF
        )

def strip_invalid_xml_chars(html_string):
    # https://stackoverflow.com/questions/8733233/filtering-out-certain-bytes-in-python
    return ''.join(c for c in html_string if _valid_xml_char_ordinal(c))
