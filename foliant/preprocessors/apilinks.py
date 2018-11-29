'''apilinks preprocessor for Foliant. Replaces API references with links to API
docs'''
import re
from io import BytesIO
from collections import OrderedDict
from urllib import request, error
from lxml import etree

from foliant.preprocessors.base import BasePreprocessor
from foliant.utils import output

HTTP_VERBS = ('OPTIONS', 'GET', 'HEAD', 'POST',
              'PUT', 'DELETE', 'TRACE', 'CONNECT',
              'PATCH', 'LINK', 'UNLINK')

DEFAULT_REF_REGEX = r'(?P<source>`((?P<prefix>[\w-]+):\s*)?' +\
                    rf'(?P<verb>{"|".join(HTTP_VERBS)})\s+' +\
                    r'(?P<command>\S+)`)'
DEFAULT_HEADER_TEMPLATE = '{verb} {command}'
REQUIRED_REF_REGEX_GROUPS = ['source', 'command']


class GenURLError(Exception):
    '''Exception in the full url generation process'''
    pass


class API:
    '''Helper class representing an API documentation website'''

    def __init__(self, name: str, url: str, htempl: str, offline: bool):
        self.name = name
        self.url = url.rstrip('/')
        self.offline = offline
        self.headers = self._fill_headers()
        self.header_template = htempl

    def format_header(self, format_dict: dict) -> str:
        '''
        Generate a header of correct format used in the API documentation
        website.

        format_dict (dict) — dictionary with values needed to generate a header
                             like 'verb' or 'command'
        '''
        return self.header_template.format(**format_dict)

    def format_anchor(self, format_dict):
        '''
        Generate an anchor of correct format used to represend headers  in the
        API documentation website.

        format_dict (dict) — dictionary with values needed to generate an anchor
                             like 'verb' or 'command'
        '''
        return convert_to_anchor(self.format_header(format_dict))

    def gen_full_url(self, format_dict):
        '''
        Generate a full url to a method documentation on the API documentation
        website.

        format_dict (dict) — dictionary with values needed to generate an URL
                             like 'verb' or 'command'
        '''
        return f'{self.url}/#{self.format_anchor(format_dict)}'

    def _fill_headers(self) -> dict:
        '''
        Parse self.url and generate headers dictionary {'anchor': header_title}.
        If self.offline == true — returns an empty dictionary.

        May thrown HTTPError if url is incorrect or unavailable.
        '''

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


def convert_to_anchor(reference: str) -> str:
    '''
    Convert reference string into correct anchor

    >>> convert_to_anchor('GET /endpoint/method{id}')
    'get-endpoint-method-id'
    '''

    result = ''
    accum = False
    header = reference
    for char in header:
        if char == '_' or char.isalpha():
            if accum:
                accum = False
                result += f'-{char.lower()}'
            else:
                result += char.lower()
        else:
            accum = True
    return result.strip(' -')


class Reference:
    '''
    Class representing a reference. It is a reference attribute collection
    with values defaulting to ''.
    '''

    def __init__(self, source='', prefix='', verb='', command=''):
        self.source = source or ''
        self.prefix = prefix or ''
        self.verb = verb or ''
        self.command = command or ''

    def init_from_match(self, match):
        '''init values for all reference attributes from a match object'''

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
        'ref-regex': DEFAULT_REF_REGEX,
        'output-template': '[{verb} {command}]({url})',
        'targets': [],
        'trim-if-targets': [],
        'trim-template': '`{verb} {command}`',
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

        self.counter = 0

    def _warning(self, msg: str):
        '''Log warning and print to user'''

        output(f'WARNING: {msg}', self.quiet)
        self.logger.warning(msg)

    def set_apis(self):
        '''
        Fills self.apis dictionary with API objects representing each API from
        the config. If self.offline == false — they will be filled with headers
        from the actual wep-page.

        Also sets self.default_api. It is the first API from the config marked
        with 'default' option or, if there's not mark, ther first API from the
        config. self.default_api is API class.
        '''

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
        Checks whether the expression expr is valid and has all required
        groups.

        Shows warning if some vital group is missing. Throws error if there's
        a mistake in regular expression'

        Returns compiled pattern.

        expr (str) — string with regular expression to compile.
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

    def find_url(self, verb: str, command: str) -> str:
        '''
        Goes through every header list of every API and looks for the method
        represented by verb and command.

        Trows GenURLError if the method is not found or if the  method with
        such attributes occurs in several APIs.

        verb (str) — verb of the method (GET, POST, etc);
        command (str) — command of the method.
        '''

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
        '''
        Goes through every header list of the API with name == prefix and looks
        for the method represented by verb and command.

        Trows GenURLError if the method is not found or if there's no API with
        such name (the API may be in config but its URL is unavailable).

        prefix (str) — prefix used in the reference. Must equal one of the APIs
                       names.
        verb (str) — verb of the method (GET, POST, etc);
        command (str) — command of the method.
        '''

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
        '''
        Generates a full URL to the method referenced by ref.

        If ref has prefix — take the url from API which name == prefix.
        If there's no such API in config — throw GenURLError.

        If ref has no prefix — take url from the default API. If there's no
        default API — throw GenURLError.

        Does not check whether the method actually exists on the documentation
        web-page. Should be used when self.offline == True.

        ref (Reference) — Reference object for which the url should be generated;
        '''

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
        '''
        Generates a full URL to the method referenced by ref.

        Checks whether the method actually exists on the documentation
        web-page. If not — raises GenURLError. Should be used when
        self.offline == False.

        ref (Reference) — Reference object for which the url should be generated;
        '''

        if ref.prefix:
            return self.get_url(ref.prefix, ref.verb, ref.command)
        else:
            return self.find_url(ref.verb, ref.command)

    def process_links(self, content: str) -> str:
        def _sub(block) -> str:
            '''
            Replaces each occurence of the reference to API method (described
            by regex in 'ref-regex' option) with link to the API documentation
            web-page.

            If can't determine link (mistake in the prefix or method name,
            several methods with this name and no prefix, etc) — shows warning
            and leaves reference unchanged.
            '''

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

            self.counter += 1
            return self.options['output-template'].format(url=url, **ref.__dict__)

        return self.link_pattern.sub(_sub, content)

    def trim_prefixes(self, content: str) -> str:
        def _sub(block) -> str:
            '''
            Replaces each occurence of the reference to API method (described
            by regex in 'ref-regex' option) with its trimmed version.
            '''

            ref = Reference()
            ref.init_from_match(block)
            return self.options['trim-template'].format(**ref.__dict__)

        return self.link_pattern.sub(_sub, content)

    def apply_for_all_files(self, func, log_msg: str):
        '''Apply function func to all Mardown-files in the working dir'''
        self.logger.info(log_msg)
        for markdown_file_path in self.working_dir.rglob('*.md'):
            with open(markdown_file_path,
                      encoding='utf8') as markdown_file:
                content = markdown_file.read()

            processed_content = func(content)

            if processed_content:
                with open(markdown_file_path,
                          'w',
                          encoding='utf8') as markdown_file:
                    markdown_file.write(processed_content)

    def apply(self):
        self.logger.info('Applying preprocessor')
        if not self.options['targets'] or\
                self.context['target'] in self.options['targets']:

            self.apply_for_all_files(self.process_links, 'Converting references')
        if self.context['target'] in self.options['trim-if-targets']:
            self.apply_for_all_files(self.trim_prefixes, 'Trimming prefixes')

        self.logger.info(f'Preprocessor applied. {self.counter} links were added')
