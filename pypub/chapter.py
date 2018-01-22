#!/usr/bin/env python
# -*- coding: utf-8 -*-
import cgi
import codecs
import imghdr
import os
import shutil
import tempfile
import urllib
import urlparse
import uuid
import mimetypes
import traceback

from six import text_type, binary_type
import bs4
from bs4 import BeautifulSoup
from bs4.dammit import EntitySubstitution
import jinja2
import requests
from constants import CHAPTER_TEMPLATE, CONTENT_TEMPLATE
import clean
import utils

_DEFAULT_USER_AGENT = r'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
_DEFAULT_HEADERS = {'User-Agent': _DEFAULT_USER_AGENT}

SUPPORTTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif']

class NoUrlError(Exception):
    def __str__(self):
        return 'Chapter instance URL attribute is None'


class ImageErrorException(Exception):
    def __init__(self, image_url):
        self.image_url = image_url

    def __str__(self):
        return 'Error downloading image from ' + self.image_url

class CSSErrorException(Exception):
    def __init__(self, css_url):
        self.css_url = css_url

    def __str__(self):
        return 'Error downloading css from ' + self.css_url

def is_web_url(url):
    us = urlparse.urlparse(url)
    return us.scheme and len(us.scheme) > 2

def get_image_type(url):
    if not os.path.splitext(url)[1]:
        return None
    mimetype =  mimetypes.guess_type(url)[0]
    if mimetype in SUPPORTTED_MIME_TYPES:
        return mimetype

def fix_file_name(filename):
    valid_chars = ' _().#[]'
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c in valid_chars]).rstrip()

def save_image(image_url, image_directory, image_name):
    """
    Saves an online image from image_url to image_directory with the name image_name.
    Returns the extension of the image saved, which is determined dynamically.

    Args:
        image_url (str): The url of the image.
        image_directory (str): The directory to save the image in.
        image_name (str): The file name to save the image as.

    Raises:
        ImageErrorException: Raised if unable to save the image at image_url
    """
    if not get_image_type(image_url):
        raise ImageErrorException(image_url)
    full_image_file_name = os.path.join(image_directory, image_name)

    if is_web_url(image_url):
        try:
            with open(full_image_file_name, 'wb') as f:
                headers = {}
                headers.update(_DEFAULT_HEADERS)
                headers['Referer'] = image_url
                requests_object = requests.get(image_url, headers=headers)
                try:
                    content = requests_object.content
                    # Check for empty response
                    f.write(content)
                except AttributeError:
                    raise ImageErrorException(image_url)
        except IOError:
            raise ImageErrorException(image_url)
        return full_image_file_name
    else:
        # If the image is present on the local filesystem just copy it
        if os.path.exists(image_url):
            shutil.copy(image_url, full_image_file_name)
            return full_image_file_name


def _replace_image(image_url, image_tag, ebook_folder,
                   image_name=None):
    """
    Replaces the src of an image to link to the local copy in the images folder of the ebook. Tightly coupled with bs4
        package.

    Args:
        image_url (str): The url of the image.
        image_tag (bs4.element.Tag): The bs4 tag containing the image.
        ebook_folder (str): The directory where the ebook files are being saved. This must contain a subdirectory
            called "images".
        image_name (Option[str]): The short name to save the image as. Should not contain a directory or an extension.
    """
    # print('_replace_image %s in %s' % (image_url, ebook_folder))
    try:
        assert isinstance(image_tag, bs4.element.Tag)
    except AssertionError:
        raise TypeError("image_tag cannot be of type " + str(type(image_tag)))
    if image_name is None:
        if is_web_url(image_url):
            image_name = os.path.basename(urlparse.urlparse(image_url).path)
        else:
            image_name = os.path.basename(image_url)
    image_name = fix_file_name(image_name)
    # print('_replace_image %s with %s ' % (image_url, image_name))
    try:
        image_full_path = os.path.join(ebook_folder, 'images')
        assert os.path.exists(image_full_path)
        save_image(image_url, image_full_path,
                                     image_name)
        image_tag['src'] = 'images' + '/' + image_name
        return image_name
    except ImageErrorException:
        image_tag.decompose()
        # traceback.print_exc()
    except AssertionError:
        raise ValueError('%s doesn\'t exist or doesn\'t contain a subdirectory images' % ebook_folder)
    except TypeError:
        image_tag.decompose()
        # traceback.print_exc()



class ImageItem(object):
    def __init__(self, link, id=None):
        self.link  = link
        self.name = os.path.basename(link)
        self.id = 'image_%s' % (id or self.name.rsplit('.')[0])
        self.type = get_image_type(link)
        # self.link = 'images' + '/' + self.name

    def __str__(self):
        return "ImageItem{%s, %s}" % (self.link, self.type)

class Chapter(object):
    """
    Class representing an ebook chapter. By and large this shouldn't be
    called directly but rather one should use the class ChapterFactor to
    instantiate a chapter.

    Args:
        content (str): The content of the chapter. Should be formatted as
            xhtml.
        title (str): The title of the chapter.
        url (Option[str]): The url of the webpage where the chapter is from if
            applicable. By default this is None.

    Attributes:
        content (str): The content of the ebook chapter.
        title (str): The title of the chapter.
        url (str): The url of the webpage where the chapter is from if
            applicable.
        html_title (str): Title string with special characters replaced with
            html-safe sequences
    """
    def __init__(self, content, title, url=None):
        self._validate_input_types(content, title)
        self.content = content
        self.title = title
        self.soup = BeautifulSoup(content, 'html.parser')
        self.url = url
        self.html_title = cgi.escape(self.title, quote=True)
        self.images = []
        self._insert_title()
        print('Chapter(title=%s, url=%s, type=%s)' % (title, url, type(content)))

    def _insert_title(self):
        title_tag = self.soup.new_tag('h1')
        title_tag.string = self.html_title
        hr_tag = self.soup.new_tag('hr')
        self.soup.body.insert(0, title_tag)
        self.soup.body.insert(1, hr_tag)

    def _get_body(self):
        return unicode(self.soup.body.prettify())

    def _render_template(self, **variable_value_pairs):
        def read_template():
            with codecs.open(CHAPTER_TEMPLATE, 'r', 'utf-8') as f:
                template = f.read()
            return jinja2.Template(template)
        template = read_template()
        return template.render(variable_value_pairs)

    def _parse_images(self):
        images = []
        for node in self.soup('img'):
            image = ImageItem(node['src'])
            images.append(image)
            node['id'] = image.id
        self.images = images

    def get_content(self):
        return self._render_template(title=self.title, body=self._get_body())

    def write(self, file_name):
        """
        Writes the chapter object to an xhtml file.

        Args:
            file_name (str): The full name of the xhtml file to save to.
        """
        try:
            assert file_name[-6:] == '.xhtml'
        except (AssertionError, IndexError):
            raise ValueError('filename must end with .xhtml')
        with codecs.open(file_name, 'w','utf-8') as f:
            f.write(self.get_content())

    def _validate_input_types(self, content, title):
        try:
            assert isinstance(content, basestring)
        except AssertionError:
            raise TypeError('content must be a string')
        try:
            assert isinstance(title, basestring)
        except AssertionError:
            raise TypeError('title must be a string')
        try:
            assert title != ''
        except AssertionError:
            raise ValueError('title cannot be empty string')
        try:
            assert content != ''
        except AssertionError:
            raise ValueError('content cannot be empty string')

    def get_url(self):
        if self.url is not None:
            return self.url
        else:
            raise NoUrlError()

    def _extract_urls(self, node_list):
        final_nodes = []
        final_urls = []
        in_web_page = is_web_url(self.url)
        if in_web_page:
            root_scheme = urlparse.urlparse(self.url).scheme
        else:
            root_scheme = None
        for node in node_list:
            url = node.get('src')
            if in_web_page:
                url = urlparse.urljoin(self.url, url)
            else:
                folder = os.path.dirname(self.url)
                url = os.path.abspath(os.path.join(folder, url))
            final_nodes.append(node)
            final_urls.append(url)
        return zip(final_nodes, final_urls)

    def _get_image_urls(self):
        node_list = self.soup('img')
        return self._extract_urls(node_list)

    def _replace_images_in_chapter(self, ebook_folder):
        image_url_list = self._get_image_urls()
        for image_tag, image_url in image_url_list:
            result = _replace_image(image_url, image_tag, ebook_folder)
            # print('_replace_images_in_chapter', image_tag)
        self._parse_images()

class ChapterFactory(object):
    """
    Used to create Chapter objects.Chapter objects can be created from urls,
    files, and strings.

    Args:
        clean_function (Option[function]): A function used to sanitize raw
            html to be used in an epub. By default, this is the pypub.clean
            function.
    """

    def __init__(self, clean_function=clean.clean):
        self.clean_function = clean_function
        self.request_headers = _DEFAULT_HEADERS

    def create_chapter_from_url(self, url, title=None):
        """
        Creates a Chapter object from a url. Pulls the webpage from the
        given url, sanitizes it using the clean_function method, and saves
        it as the content of the created chapter. Basic webpage loaded
        before any javascript executed.

        Args:
            url (string): The url to pull the content of the created Chapter
                from
            title (Option[string]): The title of the created Chapter. By
                default, this is None, in which case the title will try to be
                inferred from the webpage at the url.

        Returns:
            Chapter: A chapter object whose content is the webpage at the given
                url and whose title is that provided or inferred from the url

        Raises:
            ValueError: Raised if unable to connect to url supplied
        """
        try:
            request_object = requests.get(url, headers=self.request_headers, allow_redirects=True)
            request_object.encoding = 'utf-8'
        except (requests.exceptions.MissingSchema,
                requests.exceptions.ConnectionError):
            raise ValueError("%s is an invalid url or no network connection" % url)
        except requests.exceptions.SSLError:
            raise ValueError("Url %s doesn't have valid SSL certificate" % url)
        unicode_string = request_object.text
        return self.create_chapter_from_string(unicode_string, title, url, True)

    def create_chapter_from_file(self, file_path, title=None):
        """
        Creates a Chapter object from an html or xhtml file. Sanitizes the
        file's content using the clean_function method, and saves
        it as the content of the created chapter.

        Args:
            file_name (string): The file_name containing the html or xhtml
                content of the created Chapter
            url (Option[string]): A url to infer the title of the chapter from
            title (Option[string]): The title of the created Chapter. By
                default, this is None, in which case the title will try to be
                inferred from the webpage at the url.

        Returns:
            Chapter: A chapter object whose content is the given file
                and whose title is that provided or inferred from the url
        """
        file_path = os.path.abspath(file_path)
        if not title:
            title = os.path.splitext(os.path.basename(file_path))[0]
        with codecs.open(file_path, 'r', 'utf-8') as f:
            content_string = f.read()
        return self.create_chapter_from_string(content_string, title, file_path, False)

    def create_chapter_from_string(self, content, title=None, url=None, clean_html=False):
        """
        Creates a Chapter object from a html or text string. Sanitizes the
        string using the clean_function method, and saves
        it as the content of the created chapter.

        Args:
            content (string): The html or xhtml content of the created
                Chapter
            url (Option[string]): A url to infer the title of the chapter from
            title (Option[string]): The title of the created Chapter. By
                default, this is None, in which case the title will try to be
                inferred from the webpage at the url.

        Returns:
            Chapter: A chapter object whose content is the given string
                and whose title is that provided or inferred from the url
        """
        print('create_chapter_from_string source:[%s]' % url)
        if title:
            if isinstance(title, binary_type):
                title = title.decode('utf-8')
        else:
            title = utils.get_html_title(content)
        if utils.is_html_file(content):
            html_string = self.clean_function(content) if clean_html else content
        else:
            content = utils.strip_html_tags(content)
            content_tpl = codecs.open(CONTENT_TEMPLATE, 'r', 'utf-8').read()
            html_lines = ['<p>%s</p>' % line for line in content.split('\n')]
            html_string = content_tpl % (title, '\n'.join(html_lines))
        
        xhtml_string = clean.html_to_xhtml(html_string)

        return Chapter(xhtml_string, title, url)

create_chapter_from_url = ChapterFactory().create_chapter_from_url
create_chapter_from_file = ChapterFactory().create_chapter_from_file
create_chapter_from_string = ChapterFactory().create_chapter_from_string
