def ensure_root(route):
    '''ensure that rote starts with forward slash. Trim trailing slah also.'''
    if route:
        return '/' + route.strip('/ ')
    return route


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


