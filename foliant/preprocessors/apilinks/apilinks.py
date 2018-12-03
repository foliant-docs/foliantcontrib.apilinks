'''apilinks preprocessor for Foliant. Replaces API references with links to API
docs'''
import re
from collections import OrderedDict
from urllib import error

from foliant.preprocessors.base import BasePreprocessor
from foliant.utils import output

from .constants import (DEFAULT_REF_REGEX, DEFAULT_HEADER_TEMPLATE,
                        REQUIRED_REF_REGEX_GROUPS, DEFAULT_IGNORING_PREFIX)

from .classes import API, Reference, GenURLError


class Preprocessor(BasePreprocessor):
    defaults = {
        'ref-regex': DEFAULT_REF_REGEX,
        'require-prefix': False,
        'ignoring-prefix': DEFAULT_IGNORING_PREFIX,
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

    def _apply_for_all_files(self, func, log_msg: str):
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
                              self.offline,
                              api_dict.get('endpoint-prefix', ''))
                self.apis[api] = api_obj
                if api_dict.get('default', False) and self.default_api is None:
                    self.default_api = api_obj
            except (error.HTTPError, error.URLError) as e:
                self._warning(f'Could not open url {api_dict["url"]} for API {api}: {e}. '
                              'Skipping.')
        if not self.apis:
            raise RuntimeError('No APIs are set up')
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

    def find_api(self, ref: Reference) -> API:
        '''
        Goes through every header list of every API and looks for the method
        represented by verb and command. Returns the API which has this method.

        Trows GenURLError if the method is not found or if the  method with
        such attributes occurs in several APIs.

        ref (Reference) — Reference object for which the API should be found.
        '''

        found = {}
        for api_name in self.apis:
            api = self.apis[api_name]
            if api.find_reference(ref):
                found[api_name] = api
        if len(found) == 1:
            return next(iter(found.values()))
        elif len(found) > 1:
            raise GenURLError(f'{ref.verb} {ref.command} is present in several APIs'
                              f' ({", ".join(found)}). Please, use prefix.')
        raise GenURLError(f'Cannot find method {ref.verb} {ref.command}.')

    def get_api(self, ref: Reference) -> API:
        '''
        Goes through every header list of the API with name == prefix and looks
        for the method represented by reference.

        Trows GenURLError if the method is not found or if there's no API with
        such name (the API may be in config but its URL is unavailable).

        ref (Reference) — Reference object for which the API should be found.
        '''

        if ref.prefix in self.apis:
            api = self.apis[ref.prefix]
            if api.find_reference(ref):
                return api
            else:
                raise GenURLError(f'Cannot find method {ref.verb} {ref.command} in {ref.prefix}.')
        else:
            raise GenURLError(f'"{ref.prefix}" is a wrong prefix. Should be one of: '
                              f'{", ".join(self.apis.keys())}.')

    def assume_api(self, ref: Reference) -> API:
        '''
        Finds the correct API object by by method reference.

        If ref has prefix — return API with name == prefix.
        If there's no such API in config — throw GenURLError.

        If ref has no prefix — return the default API. If there's no
        default API — throw GenURLError.

        Does not check whether the method actually exists on the documentation
        web-page. Should be used when self.offline == True.

        ref (Reference) — Reference object for which the API should be found;
        '''

        if ref.prefix:
            if ref.prefix not in self.apis:
                raise GenURLError(f'"{ref.prefix}" is a wrong prefix. Should be one of: '
                                  f'{", ".join(self.apis.keys())}.')
            return self.apis[ref.prefix]
        else:
            if self.default_api is None:
                raise GenURLError(f'Default API is not set.')
            return self.default_api

    def determine_api(self, ref: Reference) -> API:
        '''
        Determines the right API object to whose method ref referenced.

        Checks whether the method actually exists on the documentation
        web-page. If not — raises GenURLError. Should be used when
        self.offline == False.

        ref (Reference) — Reference object for which the API should be determined;
        '''

        if ref.prefix:
            return self.get_api(ref)
        else:
            return self.find_api(ref)

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

            if self.options['require-prefix'] and not ref.prefix:
                return ref.source

            if ref.prefix == self.options['ignoring-prefix']:
                return ref.source

            try:
                api = self.assume_api(ref) if self.offline else self.determine_api(ref)
            except GenURLError as e:
                self._warning(f'{e} Skipping.')
                return ref.source

            ref = ref.convert_to_api_reference(api.endpoint_prefix)
            url = api.gen_full_url(ref.__dict__)
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

    def apply(self):
        self.logger.info('Applying preprocessor')
        if not self.options['targets'] or\
                self.context['target'] in self.options['targets']:
            self._apply_for_all_files(self.process_links, 'Converting references')

        if self.context['target'] in self.options['trim-if-targets']:
            self._apply_for_all_files(self.trim_prefixes, 'Trimming prefixes')

        self.logger.info(f'Preprocessor applied. {self.counter} links were added')
