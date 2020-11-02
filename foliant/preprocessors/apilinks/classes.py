'''Helper classes for apilinks preprocessor'''

import yaml
import ssl

from io import BytesIO
from pathlib import PosixPath
from logging import getLogger
from lxml import etree
from urllib.request import urlopen

from foliant.preprocessors.utils.header_anchors import to_id
from .tools import ensure_root
from .constants import HTTP_VERBS

logger = getLogger('flt.APILinks.classes')


class Reference:
    '''
    Class representing a reference. It is a reference attribute collection
    with values defaulting to ''

    If you want to modify this class, note that it SHOULD NOT introduce
    attributes that are not reference properties because ut is widely used with
    the __dict__ method.
    '''

    def __init__(self, **kwargs):
        self.__dict__ = {'source': '',
                         'prefix': '',
                         'verb': '',
                         'command': '',
                         'endpoint_prefix': ''}
        self.__dict__.update(kwargs)

    def init_from_match(self, match):
        '''init values for all reference attributes from a match object'''
        self.__dict__.update(match.groupdict())

    def __setattr__(self, name, value):
        '''
        If name of the attr is command or endpoint_prefix — ensure that
        endpoint_prefix has or doesn't have trailing slash needed to correctly
        add endpoint_prefix with command.
        '''
        if name == 'command':
            command = value
            ep = self.__dict__.get('endpoint_prefix', '')
        elif name == 'endpoint_prefix':
            command = self.__dict__.get('command', '')
            ep = value
        else:
            super().__setattr__(name, value)
            return

        add_slash = command and not command.startswith('/')
        self.__dict__['command'] = command
        self.__dict__['endpoint_prefix'] = ep.rstrip('/') + add_slash * '/'
        self._fix_command()

    def _fix_command(self):
        '''If command contains endpoint prefix — strip it out'''

        command = self.command.lstrip('/')
        ep = self.endpoint_prefix.strip('/')
        if not (command and ep):
            return
        if command.startswith(ep):
            self.__dict__['command'] = command[len(ep):]
            self.__dict__['endpoint_prefix'] = '/' + ep
        logger.debug(
            'Parsed reference:\n' +
            '\n'.join(f'{k}: {v}' for k, v in self.__dict__.items())
        )

class API:
    '''Helper class representing an API documentation website'''

    def __init__(self,
                 name: str,
                 url: str,
                 htempl: str,
                 offline: bool,
                 site_backend: str,
                 endpoint_prefix: str = ''):
        self.name = name
        self.url = url.rstrip('/')
        self.offline = offline
        self.headers = self._fill_headers()
        self.header_template = htempl
        self.site_backend = site_backend
        self.endpoint_prefix = ensure_root(endpoint_prefix) if endpoint_prefix else ''

    def _fill_headers(self) -> dict:
        '''
        Parse self.url and generate headers dictionary {'anchor': header_title}.
        If self.offline == true — returns an empty dictionary.

        May throw HTTPError (403, 404, ...) or URLError if url is incorrect or
        unavailable.
        '''

        if self.offline:
            return {}
        context = ssl._create_unverified_context()
        page = urlopen(self.url, context=context).read()  # may throw HTTPError, URLError
        headers = {}
        for event, elem in etree.iterparse(BytesIO(page), html=True):
            if elem.tag in ('h1', 'h2', 'h3', 'h4'):
                anchor = elem.attrib.get('id', None)
                if anchor:
                    headers[anchor] = elem.text
        return headers

    def format_header(self, format_dict: dict) -> str:
        '''
        Generate a header of correct format used in the API documentation
        website.

        format_dict (dict) — dictionary with values needed to generate a header
                             like 'verb' or 'command'
        '''
        logger.debug(
            'Formatting header from:\n' +
            '\n'.join(f'{k}: {v}' for k, v in format_dict.items())
        )
        return self.header_template.format(**format_dict)

    def format_anchor(self, format_dict):
        '''
        Generate an anchor of correct format used to represent headers in the
        API documentation website.

        format_dict (dict) — dictionary with values needed to generate an anchor
                             like 'verb' or 'command'
        '''
        return to_id(self.format_header(format_dict), self.site_backend)

    def gen_full_url(self, format_dict):
        '''
        Generate a full url to a method documentation on the API documentation
        website.

        format_dict (dict) — dictionary with values needed to generate an URL
                             like 'verb' or 'command'
        '''
        return f'{self.url}/#{self.format_anchor(format_dict)}'

    def find_reference(self, ref: Reference) -> bool:
        '''
        Look for method by its reference and, if found, return True.
        If not — False.
        '''

        apiref = ref
        apiref.endpoint_prefix = self.endpoint_prefix
        anchor = self.format_anchor(apiref.__dict__)
        logger.debug(f'Looking for reference in {self.name} by anchor: "{anchor}"')
        result = anchor in self.headers
        if result:
            logger.debug(f'Reference found in {self.name}')
            return result
        else:
            apiref.endpoint_prefix = ''
            anchor = self.format_anchor(apiref.__dict__)
            logger.debug(f'Looking for reference in {self.name} by anchor: "{anchor}"')
            result = anchor in self.headers
            if result:
                logger.debug(f'Reference found in {self.name}')
            return result

    def __str__(self):
        return f'<API: {self.name}>'


class SwaggerAPI(API):
    ANCHOR_TEMPLATE = '/{tag}/{operation_id}'
    HEADER_TEMPLATE = '{verb} {path}'

    def __init__(self, name: str, url: str, spec_url: str,
                 offline: bool, endpoint_prefix: str = ''):
        if offline:
            raise WrongModeError('Refs to Swagger UI only work in online mode now')

        self.header_template = self.HEADER_TEMPLATE

        self.name = name
        self.url = url.rstrip('/')

        if not isinstance(spec_url, (str, PosixPath)):
            raise TypeError('spec_url must be str or PosixPath!')
        elif isinstance(spec_url, str) and spec_url.startswith('http'):
            context = ssl._create_unverified_context()
            spec = urlopen(spec_url, context=context).read()  # may throw HTTPError, URLError
        else:  # supplied path, not a link
            with open(spec_url, encoding='utf8') as f:
                spec = f.read()
        self.spec = yaml.load(spec, yaml.Loader)

        self.offline = offline
        self._fill_headers()
        # self.header_template = htempl
        self.endpoint_prefix = ensure_root(endpoint_prefix) if endpoint_prefix else ''

    def _fill_headers(self) -> dict:
        '''
        Parse self.swagger_url and generate headers dictionary {'anchor': header_title}.

        May throw HTTPError (403, 404, ...) or URLError if url is incorrect or
        unavailable.
        '''

        self.headers = {}
        self.anchors = {}
        for path_, path_info in self.spec['paths'].items():
            for verb, method_info in path_info.items():
                if verb.upper() not in HTTP_VERBS:
                    # print('skipping', verb)
                    continue
                tag = method_info['tags'][0]
                # summary = method_info.get('summary', '')
                operation_id = method_info['operationId']
                anchor = self.ANCHOR_TEMPLATE.format(tag=tag,
                                                     operation_id=operation_id)
                header = self.HEADER_TEMPLATE.format(verb=verb.upper(),
                                                     path=path_)
                self.headers[anchor] = header
                self.anchors[header] = anchor

    def format_anchor(self, format_dict):
        '''/store/placeOrder'''
        full_command = format_dict['endpoint_prefix'].rstrip('/') + '/' + format_dict['command'].lstrip('/')
        header = self.HEADER_TEMPLATE.format(verb=format_dict['verb'], path=full_command)
        logger.debug(f'Scanning headers in {self.name} for {header}')
        result = self.anchors.get(header)
        return result


class RedocAPI(SwaggerAPI):
    ANCHOR_TEMPLATE = 'operation/{operation_id}'
    # HEADER_TEMPLATE = '{summary}'


class GenURLError(Exception):
    '''Exception in the full url generation process'''
    pass


class WrongModeError(Exception):
    '''Exception in the full url generation process'''
    pass
