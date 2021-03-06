#!/usr/bin/env python
# -*- coding: utf-8 -*-
import collections
import imp
import random
import string
import shutil
import tempfile
import time
import codecs
import uuid
import jinja2
import requests
import requests.packages.urllib3
from six import text_type, binary_type

try:
    imp.find_module('lxml')
    lxml_module_exists = True
    import lxml.etree
    import lxml.html
    import lxml.html.builder
except ImportError:
    lxml_module_exists = False

from .constants import *
from . import chapter

requests.packages.urllib3.disable_warnings()

class _Mimetype(object):

    def __init__(self, parent_directory):
        mimetype_template = os.path.join(EPUB_TEMPLATES_DIR, 'mimetype')
        shutil.copy(mimetype_template,
                    os.path.join(parent_directory, 'mimetype'))

class _ContainerFile(object):

    def __init__(self, parent_directory):
        container_template = os.path.join(EPUB_TEMPLATES_DIR, 'container.xml')
        shutil.copy(container_template,
                    os.path.join(parent_directory, 'container.xml'))


class _EpubFile(object):

    def __init__(self, template_file, **non_chapter_parameters):
        self.content = u''
        self.file_name = ''
        self.template_file = template_file
        self.non_chapter_parameters = non_chapter_parameters or {}

    def write(self, file_name):
        self.file_name = file_name
        with codecs.open(file_name, 'w', 'utf-8') as f:
            f.write(self.content)

    def add_image_items(self, image_list):
        self.non_chapter_parameters['image_items'] = image_list

    def _render_template(self, **variable_value_pairs):
        def read_template():
            with codecs.open(self.template_file, 'r', 'utf-8') as f:
                template = f.read()
            return jinja2.Template(template)
        template = read_template()
        rendered_template = template.render(variable_value_pairs)
        self.content = rendered_template

    def add_chapters(self, **parameter_lists):
        def check_list_lengths(lists):
            list_length = None
            for value in lists.values():
                assert isinstance(value, list)
                if list_length is None:
                    list_length = len(value)
                else:
                    assert len(value) == list_length
        check_list_lengths(parameter_lists)
        template_chapter = collections.namedtuple('template_chapter',
                                                  parameter_lists.keys())
        chapters = [template_chapter(*items) for items in zip(*parameter_lists.values())]
        self._render_template(chapters=chapters, **self.non_chapter_parameters)

    def get_content(self):
        return self.content


class TocHtml(_EpubFile):

    def __init__(self, template_file=os.path.join(EPUB_TEMPLATES_DIR, 'toc.html'), **non_chapter_parameters):
        super(TocHtml, self).__init__(template_file, **non_chapter_parameters)

    def add_chapters(self, chapter_list):
        chapter_numbers = range(1, len(chapter_list)+1)
        link_list = ['chapter_%04d.xhtml' % n for n in chapter_numbers]
        try:
            for c in chapter_list:
                assert type(c) == chapter.Chapter
        except AssertionError:
            raise TypeError('chapter_list items must be Chapter not %s',
                            str(t))
        chapter_titles = [c.html_title for c in chapter_list]
        super(TocHtml, self).add_chapters(title=chapter_titles,
                                          link=link_list)

    def get_content_as_element(self):
        if lxml_module_exists:
            root = lxml.html.fromstring(self.content.encode('utf-8'))
            return root
        else:
            raise NotImplementedError()


class TocNcx(_EpubFile):

    def __init__(self,
                 template_file=os.path.join(EPUB_TEMPLATES_DIR, 'toc_ncx.xml'),
                 **non_chapter_parameters):
        super(TocNcx, self).__init__(template_file, **non_chapter_parameters)

    def add_chapters(self, chapter_list):
        chapter_numbers = range(1,len(chapter_list)+1)
        id_list = ['chapter_%04d' % n for n in chapter_numbers]
        play_order_list = [n for n in chapter_numbers]
        title_list = [c.html_title for c in chapter_list]
        link_list = ['chapter_%04d.xhtml' % n for n in chapter_numbers]
        super(TocNcx, self).add_chapters(**{'id': id_list,
                                            'play_order': play_order_list,
                                            'title': title_list,
                                            'link': link_list})

    def get_content_as_element(self):
        if lxml_module_exists:
            root = lxml.etree.fromstring(self.content.encode('utf-8'))
            return root
        else:
            raise NotImplementedError()


class ContentOpf(_EpubFile):

    def __init__(self, title, creator='', language='', rights='', publisher='', uid='', date=time.strftime("%Y-%m-%d")):
        super(ContentOpf, self).__init__(os.path.join(EPUB_TEMPLATES_DIR, 'opf.xml'),
                                         title=title,
                                         creator=creator,
                                         language=language,
                                         rights=rights,
                                         publisher=publisher,
                                         uid=uid,
                                         date=date)

    def add_chapters(self, chapter_list):
        chapter_numbers = range(1,len(chapter_list)+1)
        id_list = ['chapter_%04d' % n for n in chapter_numbers]
        link_list = ['chapter_%04d.xhtml' % n for n in chapter_numbers]
        super(ContentOpf, self).add_chapters(**{'id': id_list, 'link': link_list})

    def get_content_as_element(self):
        if lxml_module_exists:
            root = lxml.etree.fromstring(self.content.encode('utf-8'))
            return root
        else:
            raise NotImplementedError()


class Epub(object):
    """
    Class representing an epub. Add chapters to this and then output your ebook
    as an epub file.

    Args:
        title (str): The title of the epub.
        creator (Option[str]): The creator of your epub. By default this is
            pypub.
        language (Option[str]): The language of your epub.
        rights (Option[str]): The rights of your epub.
        publisher (Option[str]): The publisher of your epub. By default this
            is pypub.
    """

    def __init__(self, title, creator='pypub', language='en', rights='', 
        publisher='pypub', cover_file=None, css_file=None,
        uid=None, epub_dir=None):
        self._create_directories(epub_dir)
        self.chapters = []
        self.title = title
        try:
            assert title
        except AssertionError:
            raise ValueError('title cannot be empty string')
        self.creator = creator
        self.language = language
        self.rights = rights
        self.publisher = publisher
        self.uid = uid or uuid.uuid4().hex
        self.current_chapter_number = None
        self._increase_current_chapter_number()
        self.cover = cover_file or DEFAULT_COVER
        self.css = css_file or DEFAULT_CSS
        self.toc_html = TocHtml()
        self.toc_ncx = TocNcx()
        self.opf = ContentOpf(self.title, self.creator, self.language, 
            self.rights, self.publisher, self.uid)
        self.mimetype = _Mimetype(self.EPUB_DIR)
        self.container = _ContainerFile(self.META_INF_DIR)

    def _create_directories(self, epub_dir=None):
        if epub_dir is None:
            self.EPUB_DIR = tempfile.mkdtemp()
        else:
            self.EPUB_DIR = epub_dir
        self.OEBPS_DIR = os.path.join(self.EPUB_DIR, 'OEBPS')
        self.META_INF_DIR = os.path.join(self.EPUB_DIR, 'META-INF')
        self.LOCAL_IMAGE_DIR = 'images'
        self.IMAGE_DIR = os.path.join(self.OEBPS_DIR, self.LOCAL_IMAGE_DIR)
        os.makedirs(self.OEBPS_DIR)
        os.makedirs(self.META_INF_DIR)
        os.makedirs(self.IMAGE_DIR)

    def _increase_current_chapter_number(self):
        if self.current_chapter_number is None:
            self.current_chapter_number = 1
        else:
            self.current_chapter_number += 1
        self.current_chapter_id = str(self.current_chapter_number)
        self.current_chapter_path = 'chapter_%04d.xhtml' % self.current_chapter_number

    def add_chapter(self, c):
        """
        Add a Chapter to your epub.

        Args:
            c (Chapter): A Chapter object representing your chapter.

        Raises:
            TypeError: Raised if a Chapter object isn't supplied to this
                method.
        """
        try:
            assert type(c) == chapter.Chapter
        except AssertionError:
            raise TypeError('chapter must be of type Chapter')
        chapter_file_output = os.path.join(self.OEBPS_DIR, self.current_chapter_path)
        c._replace_images_in_chapter(self.OEBPS_DIR)
        c.write(chapter_file_output)
        self._increase_current_chapter_number()
        self.chapters.append(c)

    def create_epub(self, output_directory, epub_name=None):
        """
        Create an epub file from this object.

        Args:
            output_directory (str): Directory to output the epub file to
            epub_name (Option[str]): The file name of your epub. This should not contain
                .epub at the end. If this argument is not provided, defaults to the title of the epub.
        """
        def createTOCs_and_ContentOPF():
            image_items = []
            for c in self.chapters:
                image_items.extend(c.images)
                
            self.opf.add_image_items(image_items)
            for epub_file, name in ((self.toc_html, 'toc.html'), (self.toc_ncx, 'toc.ncx'), (self.opf, 'content.opf'),):
                epub_file.add_chapters(self.chapters)
                epub_file.write(os.path.join(self.OEBPS_DIR, name))

        def copy_resources():
            cover_image_output = os.path.join(self.OEBPS_DIR, 'cover.jpg')
            shutil.copy(self.cover, cover_image_output)
            cover_html_input = os.path.join(EPUB_TEMPLATES_DIR, 'cover.xhtml')
            cover_html_output = os.path.join(self.OEBPS_DIR, 'cover.xhtml')
            shutil.copy(cover_html_input, cover_html_output)
            css_output = os.path.join(self.OEBPS_DIR, 'main.css')
            shutil.copy(self.css, css_output)

        def clean_emtpy_dirs():
            for name in os.listdir(self.OEBPS_DIR):
                f = os.path.join(self.OEBPS_DIR, name)
                if os.path.isdir(f):
                    if not os.listdir(f):
                        os.rmdir(f)

        def create_zip_archive(epub_name):
            try:
                assert isinstance(epub_name, text_type) or epub_name is None
            except AssertionError:
                raise TypeError('epub_name must be string or None')
            if epub_name is None:
                epub_name = self.title
            epub_name_with_path = os.path.join(output_directory, epub_name)
            epub_name_with_path_ext = os.path.join(output_directory, '%s.zip' % epub_name)
            if os.path.exists(epub_name_with_path_ext):
                os.remove(epub_name_with_path_ext)
            clean_emtpy_dirs()
            shutil.make_archive(epub_name_with_path, 'zip', self.EPUB_DIR)
            return epub_name_with_path_ext

        def turn_zip_into_epub(zip_archive_file):
            dir_name = os.path.dirname(zip_archive_file)
            file_name = os.path.basename(zip_archive_file)
            base, ext = os.path.splitext(file_name)
            epub_full_name = os.path.join(dir_name, '%s.epub' % base)
            if os.path.exists(epub_full_name):
                os.remove(epub_full_name)
            # shutil.copy(zip_archive_file, epub_full_name)
            os.rename(zip_archive_file, epub_full_name)
            print('ePub file saved to %s' % epub_full_name)
            return epub_full_name
        print('Collecting resources in %s' % self.EPUB_DIR)
        createTOCs_and_ContentOPF()
        copy_resources()
        return turn_zip_into_epub(create_zip_archive(epub_name))
