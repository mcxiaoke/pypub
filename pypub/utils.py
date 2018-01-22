#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
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
    return " ".join(text)
