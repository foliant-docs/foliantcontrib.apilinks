HTTP_VERBS = ('OPTIONS', 'GET', 'HEAD', 'POST',
              'PUT', 'DELETE', 'TRACE', 'CONNECT',
              'PATCH', 'LINK', 'UNLINK')

DEFAULT_REF_REGEX = r'(?P<source>`((?P<prefix>[\w-]+):\s*)?' +\
                    rf'(?P<verb>{"|".join(HTTP_VERBS)})\s+' +\
                    r'(?P<command>\S+)`)'
DEFAULT_HEADER_TEMPLATE = '{verb} {endpoint_prefix}{command}'
REQUIRED_REF_REGEX_GROUPS = ['source', 'command']

DEFAULT_IGNORING_PREFIX = 'Ignore'
