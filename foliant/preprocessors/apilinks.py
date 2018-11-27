'''apilinks preprocessor for Foliant.'''
import re
from io import BytesIO
from urllib import request, error
from lxml import etree

from foliant.preprocessors.base import BasePreprocessor
from foliant.utils import output

DEFAULT_HEADER_TEMPLATE = '{verb} {link}'


class API:
    def __init__(self, name: str, url: str, htempl: str):
        self.name = name
        self.url = url.rstrip('/')
        self.headers = self._fill_headers()
        self.header_template = htempl

    def format_header(self, format_dict):
        return self.header_template.format(**format_dict)

    def format_anchor(self, format_dict):
        return convert_to_anchor(self.format_header(format_dict))

    def _fill_headers(self) -> dict:
        page = request.urlopen(self.url).read()  # may throw HTTPError
        headers = {}
        for event, elem in etree.iterparse(BytesIO(page), html=True):
            if elem.tag == 'h2':
                anchor = elem.attrib.get('id', None)
                if anchor:
                    headers[anchor] = elem.text
        return headers

    def __str__(self):
        return f'API({self.name})'


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


class Reference:
    def __init__(self, source=None, prefix=None, verb=None, link=None):
        self.source = source
        self.prefix = prefix
        self.verb = verb
        self.link = link

    def init_from_match(self, match):
        groups = match.groupdict().keys()
        if 'source' in groups:
            self.source = match.group('source')
        if 'prefix' in groups:
            self.prefix = match.group('prefix')
        if 'verb' in groups:
            self.verb = match.group('verb')
        if 'link' in groups:
            self.link = match.group('link')


class Preprocessor(BasePreprocessor):
    defaults = {
        'ref-regex': r'(?P<source>`((?P<prefix>[\w-]+):\s*)?'
                     r'(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+'
                     r'(?P<link>\S+)`)',
        'output-template': '[{verb} {link}]({url})',
        'targets': []
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.logger.getChild('apilinks')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

        self.link_pattern = self._compile_link_pattern(self.options['ref-regex'])
        self.apis = {}
        self.set_apis()

    def set_apis(self):
        for api in self.options.get('API', {}):
            try:
                api_obj = API(api,
                              self.options['API'][api]['url'],
                              self.options['API'][api].get('header-template',
                                                      DEFAULT_HEADER_TEMPLATE))
            except error.HTTPError:
                output(f'Could not open url {self.url} for API {api}. '
                       'Skipping.')
                continue
            self.apis[api] = api_obj

    def _compile_link_pattern(self, expr: str) -> bool:
        '''
        TODO!
        Check whether the expression expr is valid and has all required
        groups. Return compiled pattern.
        '''
        return re.compile(expr)

    def find_url(self, verb: str, link: str):
        found = []
        for api_name in self.apis:
            api = self.apis[api_name]
            anchor = api.format_anchor(dict(verb=verb, link=link))
            if anchor in api.headers:
                found.append(api)
        if len(found) == 1:
            anchor = api.format_anchor(dict(verb=verb, link=link))
            return f'{found[0].url}/#{anchor}'
        elif len(found) > 1:
            found_list = ', '.join([api.name for api in found])
            raise RuntimeError(f'WARNING: {verb} {link} is present in '
                               f'several APIs ({found_list}).'
                               'Please, use prefix. Skipping')
        return None

    def get_url(self, prefix: str, verb: str, link: str):
        if prefix in self.apis:
            api = self.apis[prefix]
            anchor = api.format_anchor(dict(verb=verb, link=link))
            if anchor in api.headers:
                return f'{api.url}/#{anchor}'
        else:
            output(f'"{prefix}" is a wrong prefix. Should be one of: ' +
                   ", ".join(self.apis.keys()), self.quiet)
            return None
        return None

    def process_links(self, content: str) -> str:
        def _sub(block) -> str:
            ref = Reference()
            ref.init_from_match(block)
            url = None
            if ref.prefix:
                url = self.get_url(ref.prefix, ref.verb, ref.link)
            else:
                try:
                    url = self.find_url(ref.verb, ref.link)
                except RuntimeError as e:
                    output(e, self.quiet)
                    return ref.source

            if url:
                return self.options['output-template'].format(url=url,
                                                              **ref.__dict__)
            else:
                output(f'WARNING: Could not find method {ref.source} skipping',
                       self.quiet)
                return ref.source

        return self.link_pattern.sub(_sub, content)

    def apply(self):
        if not self.options['targets'] or\
                self.context['target'] in self.options['targets']:
            self.logger.info('Applying preprocessor')

            for markdown_file_path in self.working_dir.rglob('*.md'):
                with open(markdown_file_path,
                          encoding='utf8') as markdown_file:
                    content = markdown_file.read()

                processed_content = self.process_links(content)

                if processed_content:
                    with open(markdown_file_path,
                              'w',
                              encoding='utf8') as markdown_file:
                        markdown_file.write(processed_content)

            self.logger.info('Preprocessor applied')
