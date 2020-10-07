'''apilinks preprocessor for Foliant. Replaces API references with links to API
docs'''
import re
from pathlib import Path
from collections import OrderedDict
from urllib import error

from foliant.preprocessors.base import BasePreprocessor
from foliant.utils import output

from .constants import (DEFAULT_REF_REGEX, DEFAULT_HEADER_TEMPLATE,
                        REQUIRED_REF_REGEX_GROUPS, DEFAULT_IGNORING_PREFIX)

from .classes import (API, SwaggerAPI, RedocAPI, Reference, GenURLError,
                      WrongModeError)
from foliant.preprocessors.utils.combined_options import (Options,
                                                          CombinedOptions)


class Preprocessor(BasePreprocessor):
    defaults = {
        'reference': [],
        'regex': DEFAULT_REF_REGEX,  # ref
        'only_defined_prefixes': False,  # ref
        'only_with_prefixes': False,  # ref
        'prefix_to_ignore': DEFAULT_IGNORING_PREFIX,
        'output_template': '[{verb} {command}]({url})',  # ref
        'targets': [],
        'trim_if_targets': [],
        'trim_template': '`{verb} {command}`',  # ref
        'API': {},
        'offline': False}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = self.logger.getChild('apilinks')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')
        self.current_filename = ''

        self.offline = bool(self.options['offline'])
        self.apis = OrderedDict()
        self.default_api = None
        self.set_apis()

        self.counter = 0

    def _warning(self, msg: str):
        '''Log warning and print to user'''

        output(f'WARNING: [{self.current_filename}] {msg}', self.quiet)
        self.logger.warning(msg)

    def _apply_for_all_files(self, func, log_msg: str):
        '''Apply function func to all Mardown-files in the working dir'''
        self.logger.info(log_msg)
        for markdown_file_path in self.working_dir.rglob('*.md'):
            self.current_filename = Path(markdown_file_path).relative_to(self.working_dir)
            with open(markdown_file_path,
                      encoding='utf8') as markdown_file:
                content = markdown_file.read()

            processed_content = func(content)

            if processed_content:
                with open(markdown_file_path,
                          'w',
                          encoding='utf8') as markdown_file:
                    markdown_file.write(processed_content)
        self.current_filename = ''

    def is_prefix_defined(self, prefix):
        '''Return True if prefix is defined in config under API or prefix-to-ignore'''
        defined_prefixes = [*self.apis.keys(), self.options['prefix_to_ignore'].lower()]

        return (prefix or '').lower() in defined_prefixes

    def set_apis(self):
        '''
        Fills self.apis dictionary with API objects representing each API from
        the config. If self.offline == false — they will be filled with headers
        from the actual web-page.

        Also sets self.default_api. It is the first API from the config marked
        with 'default' option or, if there's not mark, ther first API from the
        config. self.default_api is API class instance.
        '''

        for api in self.options.get('API', {}):
            try:
                api_dict = self.options['API'][api]
                if api_dict.get('site_backend') == 'swagger' or \
                        api_dict.get('site_backend') is None and api_dict.get('spec'):
                    # by default is spec stated we assume it's a Swagger UI
                    if not api_dict.get('spec'):
                        self._warning(
                            f'API {api} has "swagger" site backend but no "spec"'
                            ' stated. Skipping')
                        continue
                    try:
                        api_obj = SwaggerAPI(
                            api,
                            api_dict['url'],
                            api_dict['spec'],
                            self.offline,
                            api_dict.get('endpoint_prefix', ''),
                        )
                    except WrongModeError:
                        self._warning(
                            f'Swagger UI APIs only work in online mode. Skipping {api}')
                        continue
                elif api_dict.get('site_backend') == 'redoc':
                    if not api_dict.get('spec'):
                        self._warning(
                            f'API {api} has "redoc" site backend but no "spec"'
                            ' stated. Skipping')
                        continue
                    try:
                        api_obj = RedocAPI(
                            api,
                            api_dict['url'],
                            api_dict['spec'],
                            self.offline,
                            api_dict.get('endpoint_prefix', ''),
                        )
                    except WrongModeError:
                        self._warning(
                            f'Redoc APIs only work in online mode. Skipping {api}')
                        continue
                else:  # not a swagger site_backend
                    api_obj = API(
                        api,
                        api_dict['url'],
                        api_dict.get('header_template',
                                     DEFAULT_HEADER_TEMPLATE),
                        self.offline,
                        api_dict.get('site_backend', 'slate'),
                        api_dict.get('endpoint_prefix', '')
                    )
                self.apis[api.lower()] = api_obj
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
                found[api.name] = api
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

        if self.is_prefix_defined(ref.prefix):
            api = self.apis[ref.prefix.lower()]
            if api.find_reference(ref):
                return api
            else:
                raise GenURLError(f'Cannot find method {ref.verb} {ref.command} in {api.name}.')
        else:
            prefixes = [*self.options.get('API', {}).keys(), self.options['prefix_to_ignore']]
            raise GenURLError(f'"{ref.prefix}" is a wrong prefix. Should be one of: '
                              f'{", ".join(prefixes)}.')

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
            if not self.is_prefix_defined(ref.prefix):
                prefixes = [*self.options.get('API', {}).keys(), self.options['prefix_to_ignore']]
                raise GenURLError(f'"{ref.prefix}" is a wrong prefix. Should be one of: '
                                  f'{", ".join(prefixes)}.')
            return self.apis[ref.prefix.lower()]
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

            self.logger.debug(f'Found ref: {block.group(0)}')

            if options['only_with_prefixes'] and not ref.prefix:
                return ref.source

            if options['only_defined_prefixes'] and not self.is_prefix_defined(ref.prefix):
                return ref.source

            if (ref.prefix or '').lower() == options['prefix_to_ignore'].lower():
                return ref.source

            try:
                if self.offline:
                    api = self.assume_api(ref)
                else:
                    api = self.determine_api(ref)
            except GenURLError as e:
                self._warning(f'{e} Skipping.')
                return ref.source

            ref.endpoint_prefix = api.endpoint_prefix
            url = api.gen_full_url(ref.__dict__)
            self.counter += 1
            return options['output_template'].format(url=url, **ref.__dict__)

        processed = content
        main_options = Options(self.options, self.defaults)
        if main_options['reference']:  # several references stated in config
            for ref in main_options['reference']:
                ref_options = Options(ref)
                options = CombinedOptions({'main': main_options,
                                           'ref': ref_options},
                                          priority='ref')
                pattern = self._compile_link_pattern(options['regex'])
                processed = pattern.sub(_sub, processed)
        else:  # only one reference stated
            options = main_options
            pattern = self._compile_link_pattern(options['regex'])
            processed = pattern.sub(_sub, processed)

        return processed

    def trim_prefixes(self, content: str) -> str:
        def _sub(block) -> str:
            '''
            Replaces each occurence of the reference to API method (described
            by regex in 'ref-regex' option) with its trimmed version.

            Only those references are replaced which prefixes are defined in
            config + prefix-to-ignore. All the others are left unchanged.
            '''

            ref = Reference()
            ref.init_from_match(block)
            if not self.is_prefix_defined(ref.prefix):
                return ref.source
            return options['trim_template'].format(**ref.__dict__)

        processed = content
        main_options = Options(self.options, self.defaults)
        if main_options['reference']:  # several references stated in config
            for ref in main_options['reference']:
                ref_options = Options(ref)
                options = CombinedOptions({'main': main_options,
                                           'ref': ref_options},
                                          priority='ref')
                pattern = self._compile_link_pattern(options['regex'])
                processed = pattern.sub(_sub, processed)
        else:  # only one reference stated
            options = main_options
            pattern = self._compile_link_pattern(options['regex'])
            processed = pattern.sub(_sub, processed)

        return processed

    def apply(self):
        self.logger.info('Applying preprocessor')
        if not self.options['targets'] or\
                self.context['target'] in self.options['targets']:
            self._apply_for_all_files(self.process_links, 'Converting references')

        if self.context['target'] in self.options['trim_if_targets']:
            self._apply_for_all_files(self.trim_prefixes, 'Trimming prefixes')

        self.logger.info(f'Preprocessor applied. {self.counter} links were added')
