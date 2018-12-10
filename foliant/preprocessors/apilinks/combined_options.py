import yaml


class ValidationError(Exception):
    '''Error for validations when validation is failed'''
    pass


class Options:
    '''
    Helper class which imitates dictionary with options but has some
    handy methods like option validation and conversion.
    '''

    def __init__(self,
                 options: dict,
                 defaults: dict = {},
                 convertors: dict = {},
                 validators: dict = {}):
        self._options = options
        self._validators = validators
        self._convertors = convertors
        self.validate()
        self._convert()

    @property
    def options(self):
        return self._options

    def validate(self):
        '''validate all options with supplied validators'''
        if not self._validators:
            return

        for key in self._validators:
            if key in self.options:
                self._validators[key](self.options[key])

    def _convert(self):
        '''convert all options with supplied convertors'''
        if not self._convertors:
            return

        for key in self._convertors:
            if key in self.options:
                convertor = self._convertors[key]
                self.options[key] = convertor(self.options[key])

    def is_default(self, option):
        '''return True if option value is same as default'''
        if option in self.defaults:
            return self.options[option] == self.defaults[option]
        return False

    def __str__(self):
        return f'<{self.__class__.__name__}{self.options}>'

    def __getitem__(self, ind: str):
        return self.options[ind]

    def __contains__(self, ind: str):
        return ind in self.options

    def get(self, key, default=None):
        return self.options.get(key, default)

    def keys(self):
        return self.options.keys()

    def items(self):
        return self.options.items()

    def values(self):
        return self.options.values()


class CombinedOptions(Options):
    '''
    Helper class which combines several Options objects into one. If options
    interlap the one to be returned is defined by 'priority'.
    Apart from that it is a normal Options object.
    '''

    def __init__(self,
                 options: dict,
                 priority: str = None,
                 defaults: dict = {},
                 convertors: dict = {},
                 validators: dict = {}):
        self._options_dict = options
        self._validators = validators
        self._convertors = convertors
        self.priority = priority or next(iter(options.keys()))

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, val: str):
        if val not in self._options_dict:
            raise ValueError('Priority must be one of: '
                             f'{", ".join(self._options_dict.keys)}. '
                             f'Value received: {val}')
        self._priority = val
        self.set_options()

    def set_options(self) -> dict:
        '''
        Return options dict with options combined from config and tag with
        priority according to priority param or self.priority if param is not
        given.

        priority (str) — override self.priority for choosing overlapping
                         options. Must be one of: 'tag', 'config'.
        '''

        self._options = {}
        priority_dict = self._options_dict[self.priority]

        for key in self._options_dict:
            if key != self.priority:
                self._options.update(self._options_dict[key])
        self._options.update(priority_dict)

        self.validate()
        self._convert()


def validate_in(supported, msg=None):
    '''
    Simple validator to check if option value contiains in supported
    collection.

    Supported may be any object which has __contains__ method. Raises
    ValueError otherwise.

    msg is message given to the ValiadtionError.

    Returns a validator function.'''

    def validate(val):
        if val not in supported:
            raise ValidationError(message.format(val=val, supported=supported))

    if not hasattr(supported, '__contains__'):
        raise ValueError('`supported` should be a collection')

    message = msg if msg else 'Unsupported option value {val}. Should be one'\
        'of: {supported}'

    return validate


def yaml_to_dict_convertor(option: str or dict):
    '''convert yaml string or dict to dict'''

    if type(option) is dict:
        return option
    elif type(option) is str:
        return yaml.load(option)
