'''Helper classes for apilinks preprocessor'''

from io import BytesIO
from lxml import etree
from urllib import request

from .tools import convert_to_anchor, ensure_root


class Reference:
    '''
    Class representing a reference. It is a reference attribute collection
    with values defaulting to ''

    If you want to modify this class, note that it SHOULD NOT introduce
    attributes that are not reference properties because ut is widely used with
    the __dict__ method.
    '''

    def __init__(self, source='', prefix='', verb='', command=''):
        self.source = source or ''
        self.prefix = prefix or ''
        self.verb = verb or ''
        self.command = ensure_root(command)

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
            self.command = ensure_root(match.group('command'))

    def convert_to_api_reference(self, endpoint_prefix):
        '''Profided an endpoint prefix converts Reference instance into an
        APIReference instance'''

        return APIReference(endpoint_prefix=endpoint_prefix, **self.__dict__)


class APIReference(Reference):
    '''
    A Reference class for a certain API. Adds to attributes the endpoint_prefix
    attribute.
    '''

    def __init__(self, endpoint_prefix='', **kwargs):
        super().__init__(**kwargs)
        self.endpoint_prefix = ensure_root(endpoint_prefix) or ''
        if self.endpoint_prefix:
            self._fix_command()

    def _fix_command(self):
        '''Remove endpoint prefix from the beginning of command'''

        if self.command.startswith(self.endpoint_prefix):
            self.command = self.command[len(self.endpoint_prefix):]


class API:
    '''Helper class representing an API documentation website'''

    def __init__(self, name: str, url: str, htempl: str, offline: bool,
                 endpoint_prefix: str = ''):
        self.name = name
        self.url = url.rstrip('/')
        self.offline = offline
        self.headers = self._fill_headers()
        self.header_template = htempl
        self.endpoint_prefix = endpoint_prefix or ''
        if self.endpoint_prefix:
            # ensure that it starts with '/'
            self.endpoint_prefix = '/' + self.endpoint_prefix.strip('/ ')

    def _fill_headers(self) -> dict:
        '''
        Parse self.url and generate headers dictionary {'anchor': header_title}.
        If self.offline == true — returns an empty dictionary.

        May throw HTTPError (403, 404, ...) or URLError if url is incorrect or
        unavailable.
        '''

        if self.offline:
            return {}
        page = request.urlopen(self.url).read()  # may throw HTTPError, URLError
        headers = {}
        for event, elem in etree.iterparse(BytesIO(page), html=True):
            if elem.tag == 'h2':
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

    def find_reference(self, ref: Reference) -> bool:
        '''
        Look for method by its reference and, if found, return True.
        If not — False.
        '''

        apiref = ref.convert_to_api_reference(self.endpoint_prefix)
        anchor = self.format_anchor(apiref.__dict__)
        return anchor in self.headers

    def __str__(self):
        return f'<API: {self.name}>'


class GenURLError(Exception):
    '''Exception in the full url generation process'''
    pass
