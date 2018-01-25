#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import os
import sys
import codecs
import re
import bs4
from bs4 import BeautifulSoup
from lxml import etree

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

def validate_xhtml(text):
    parser = etree.XMLParser()
    root = etree.fromstring(text, parser)

def _valid_xml_char_ordinal(c):
    codepoint = ord(c)
    # conditions ordered by presumed frequency
    return (
        0x20 <= codepoint <= 0xD7FF or
        codepoint in (0x9, 0xA, 0xD) or
        0xE000 <= codepoint <= 0xFFFD or
        0x10000 <= codepoint <= 0x10FFFF
        )

def remove_invalid_xml_chars2(html_string):
    soup = BeautifulSoup(html_string, 'html5lib')
    text = soup.get_text()
    soup.decompose()
    return re.sub(r'[^0\x20-\xD7FF\x9\xA\xD\xE000-\xFFFD\x10000-\x10FFFF]+','', text)

def remove_invalid_xml_chars(html_string):
    soup = BeautifulSoup(html_string, 'html5lib')
    text = soup.get_text()
    soup.decompose()
    # return re.sub(r'[\xE4C6\x00-\x1F\x7F-\x9F%&<>]+','', text)
    # https://stackoverflow.com/questions/8733233/filtering-out-certain-bytes-in-python
    return ''.join(c for c in text if _valid_xml_char_ordinal(c))
