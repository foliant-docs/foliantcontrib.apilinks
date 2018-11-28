'''apilinks preprocessor for Foliant.'''
import re
from io import BytesIO
from collections import OrderedDict
from urllib import request, error
from lxml import etree

from foliant.preprocessors.base import BasePreprocessor
from foliant.utils import output

DEFAULT_HEADER_TEMPLATE = '{verb} {command}'
REQUIRED_REF_REGEX_GROUPS = ['source', 'command']


class GenURLError(Exception):
    pass


class API:
    def __init__(self, name: str, url: str, htempl: str, offline: bool):
        self.name = name
        self.url = url.rstrip('/')
        self.offline = offline
        self.headers = self._fill_headers()
        self.header_template = htempl

    def format_header(self, format_dict):
        return self.header_template.format(**format_dict)

    def format_anchor(self, format_dict):
        return convert_to_anchor(self.format_header(format_dict))

    def gen_full_url(self, format_dict):
        return f'{self.url}/#{self.format_anchor(format_dict)}'

    def _fill_headers(self) -> dict:
        if self.offline:
            return {}
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
    header = reference.strip()
    for char in header:
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
    def __init__(self, source=None, prefix=None, verb=None, command=None):
        self.source = source
        self.prefix = prefix
        self.verb = verb
        self.command = command

    def init_from_match(self, match):
        groups = match.groupdict().keys()
        if 'source' in groups:
            self.source = match.group('source')
        if 'prefix' in groups:
            self.prefix = match.group('prefix')
        if 'verb' in groups:
            self.verb = match.group('verb')
        if 'command' in groups:
            self.command = match.group('command')


class Preprocessor(BasePreprocessor):
    defaults = {
        'ref-regex': r'(?P<source>`((?P<prefix>[\w-]+):\s*)?'
                     r'(?P<verb>POST|GET|PUT|UPDATE|DELETE)\s+'
                     r'(?P<command>\S+)`)',
        'output-template': '[{verb} {command}]({url})',
        'targets': [],
        'API': {},
        'offline': False
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.logger.getChild('apilinks')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

        self.link_pattern = self._compile_link_pattern(self.options['ref-regex'])
        self.offline = bool(self.options['offline'])
        self.apis = OrderedDict()
        self.default_api = None
        self.set_apis()

    def _warning(self, msg: str):
        '''log warning and print to user'''

        output(f'WARNING: {msg}', self.quiet)
        self.logger.warning(msg)

    def set_apis(self):
        for api in self.options.get('API', {}):
            try:
                api_dict = self.options['API'][api]
                api_obj = API(api,
                              api_dict['url'],
                              api_dict.get('header-template',
                                           DEFAULT_HEADER_TEMPLATE),
                              self.offline)
                self.apis[api] = api_obj
                if api_dict.get('default', False) and self.default_api is None:
                    self.default_api = api_obj
            except error.HTTPError:
                self._warning(f'Could not open url {self.url} for API {api}. '
                              'Skipping.')
        if not self.apis:
            raise RuntimeError('No APIs are set up. Try using offline mode')
        if self.default_api is None:
            first_api_name = list(self.apis.keys())[0]
            self.default_api = self.apis[first_api_name]

    def _compile_link_pattern(self, expr: str) -> bool:
        '''
        Check whether the expression expr is valid and has all required
        groups. Return compiled pattern.
        '''
        try:
            pattern = re.compile(expr)
        except re.error:
            self.logger.error(f'Incorrect regex: {expr}')
            raise RuntimeError(f'Incorrect regex: {expr}')
        for group in REQUIRED_REF_REGEX_GROUPS:
            if group not in pattern.groupindex:
                self._warning(f'regex is missing required group: '
                              f'{group}. Preprocessor may not work right')
        return pattern

    def find_url(self, verb: str, command: str):
        found = []
        for api_name in self.apis:
            api = self.apis[api_name]
            anchor = api.format_anchor(dict(verb=verb, command=command))
            if anchor in api.headers:
                found.append(api)
        if len(found) == 1:
            anchor = found[0].format_anchor(dict(verb=verb, command=command))
            return f'{found[0].url}/#{anchor}'
        elif len(found) > 1:
            found_list = ', '.join([api.name for api in found])
            raise GenURLError(f'{verb} {command} is present in several APIs'
                              f' ({found_list}). Please, use prefix.')
        raise GenURLError(f'Cannot find method {verb} {command}.')

    def get_url(self, prefix: str, verb: str, command: str):
        if prefix in self.apis:
            api = self.apis[prefix]
            anchor = api.format_anchor(dict(verb=verb, command=command))
            if anchor in api.headers:
                return api.gen_full_url(dict(verb=verb, command=command))
        else:
            raise GenURLError(f'"{prefix}" is a wrong prefix. Should be one of: '
                              f'{", ".join(self.apis.keys())}.')
        raise GenURLError(f'Cannot find method {verb} {command} in {prefix}.')

    def gen_url_offline(self, ref: Reference) -> str:
        if ref.prefix:
            if ref.prefix not in self.apis:
                raise GenURLError(f'"{ref.prefix}" is a wrong prefix. Should be one of: '
                                  f'{", ".join(self.apis.keys())}.')
            api = self.apis[ref.prefix]
        else:
            if self.default_api is None:
                raise GenURLError(f'Default API is not set.')
            api = self.default_api
        return api.gen_full_url(ref.__dict__)

    def gen_url(self, ref: Reference) -> str:
        if ref.prefix:
            return self.get_url(ref.prefix, ref.verb, ref.command)
        else:
            return self.find_url(ref.verb, ref.command)

    def process_links(self, content: str) -> str:
        def _sub(block) -> str:
            ref = Reference()
            ref.init_from_match(block)
            url = None

            try:
                if self.offline:
                    url = self.gen_url_offline(ref)
                else:
                    url = self.gen_url(ref)
            except GenURLError as e:
                self._warning(f'{e} Skipping')
                return ref.source

            if url:
                return self.options['output-template'].format(url=url,
                                                              **ref.__dict__)
            else:
                self._warning(f'Could not find method {ref.source} skipping')
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
