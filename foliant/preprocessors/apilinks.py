'''apilinks preprocessor for Foliant.'''
import re
from io import BytesIO
from urllib import request, error
from lxml import etree

from foliant.preprocessors.base import BasePreprocessor
from foliant.utils import output


class API:
    def __init__(self, name, url, verb=True):
        self.name = name
        self.url = url.rstrip('/')
        self.headers = self._fill_headers()
        self.verb = verb

    def _fill_headers(self):
        try:
            page = request.urlopen(self.url).read()
        except error.HTTPError:
            output(f'Could not open url {self.url}')
            return
        # TODO: process exception
        headers = {}
        for event, elem in etree.iterparse(BytesIO(page), html=True):
            if elem.tag == 'h2':
                anchor = elem.attrib.get('id', None)
                if anchor:
                    headers[anchor] = elem.text
        return headers


def convert_to_anchor(reference):
    '''
    Convert reference string into correct anchor

    >>> convert_to_anchor('GET /endpoint/method{id}')
    'get-endpoint-method-id'
    '''
    result = ''
    accum = False
    for char in reference:
        if char == '_' or char.isalpha():
            if accum:
                accum = False
                result += f'-{char.lower()}'
            else:
                result += char.lower()
        else:
            accum = True
    return result


class Anchor:
    def __init__(self, verb, link):
        self.verb = verb
        self.link = link

    def with_verb(self):
        ref = f'{self.verb} {self.link}'
        return convert_to_anchor(ref)

    def without_verb(self):
        return convert_to_anchor(self.link)

    def anchor(self, verb=True):
        if verb:
            return self.with_verb()
        else:
            return self.without_verb()


class Preprocessor(BasePreprocessor):
    defaults = {
        'regex': r'(?P<source>`(?P<prefix>[\w-]+:\s*)?'
                 r'(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+'
                 r'(?P<link>\S+)`)'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.logger.getChild('apilinks')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

        self.link_pattern = self._compile_link_pattern(self.options['regex'])
        self.apis = {}
        if 'API' in self.options:
            apidict = self.options['API']
            self.apis = {api: API(api,
                                  apidict[api]['url'],
                                  apidict[api].get('verb', None))
                         for api in apidict}

    def _compile_link_pattern(self, expr: str) -> bool:
        '''
        TODO!
        Check whether the expression expr is valid and has all required
        groups. Return compiled pattern.
        '''
        return re.compile(expr)

    def find_url_by_anchor(self, anchor: Anchor):
        for api in self.apis:
            anchor_ = anchor.anchor(self.apis[api].verb)
            if anchor_ in self.apis[api].headers:
                    return f'{self.apis[api].url}/#{anchor_}'
        return None

    def get_url_by_prefix(self, prefix, anchor: Anchor):
        if prefix in self.apis:
            anchor_ = anchor.anchor(self.apis[prefix].verb)
            if anchor_ in self.apis[prefix].headers:
                return f'{self.apis[prefix].url}/#{anchor_}'
        return None

    def process_links(self, content: str) -> str:
        def _sub(block) -> str:
            source = block.group('source')
            anchor = Anchor(block.group('verb'), block.group('link'))
            url = None
            if block.group('prefix'):
                prefix = block.group('prefix').strip(': ')
                url = self.get_url_by_prefix(prefix, anchor)
            else:
                url = self.find_url_by_anchor(anchor)

            if url:
                return f"[{block.group('verb')} {block.group('link')}]({url})"
            else:
                output(f'Could not find method {source}')
                return source

        return self.link_pattern.sub(_sub, content)

    def apply(self):
        self.logger.info('Applying preprocessor')

        for markdown_file_path in self.working_dir.rglob('*.md'):
            with open(markdown_file_path, encoding='utf8') as markdown_file:
                content = markdown_file.read()

            processed_content = self.process_links(content)

            if processed_content:
                with open(markdown_file_path, 'w', encoding='utf8') as markdown_file:
                    markdown_file.write(processed_content)

        self.logger.info('Preprocessor applied')
