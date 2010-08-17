cgiturl = "http://example.com/cgit/cgit.cgi/exampleproject/commit/?id="

import re
class CustomTags:
    substitute = [r"(?P<kw>git):(?P<id>[a-fA-F0-9]+)",
                  '%(kw)s:<a href="' + cgiturl + '%(id)s">%(id)s</a>']

    @classmethod
    def replace(cls, text):
        """Returns a copy of text with its contents replaced."""

        ntext = text
        for regex, template in cls.substitute:
            for match in re.finditer(regex, text):
                ntag = template % match.groupdict()
                ntext = ntext.replace(match.group(0), ntag, 1)
        return ntext

def localReplace(message):
    return CustomTags.replace(message)

def init(instance):
         instance.registerUtil('localReplace', localReplace)
