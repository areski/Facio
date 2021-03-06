"""
facio.opts
----------

Allows for required=True to be parsed into options list, taken from
http://docs.python.org/release/2.3/lib/optparse-extending-examples.html.
"""

import optparse


class Option(optparse.Option):
    ATTRS = optparse.Option.ATTRS + ['required']

    def _check_required(self):
        if self.required and not self.takes_value():
            raise optparse.OptionError(
                "required flag set for option that doesn't take a value",
                self)

    # Make sure _check_required() is called from the constructor!
    CHECK_METHODS = optparse.Option.CHECK_METHODS + [_check_required]

    def process(self, opt, value, values, parser):
        optparse.Option.process(self, opt, value, values, parser)
        parser.option_seen[self] = 1


class OptionParser(optparse.OptionParser):

    def _init_parsing_state(self):
        optparse.OptionParser._init_parsing_state(self)
        self.option_seen = {}

    def check_values(self, values, args):
        for option in self.option_list:
            if (isinstance(option, Option)
                    and option.required
                    and not option in self.option_seen):
                self.error("%s is a required option." % option)
        return (values, args)
