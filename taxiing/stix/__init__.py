import logging

from bs4 import BeautifulSoup

from .package import extract as package_extract_properties
from .observable import extract as observable_extract_properties

from . import domainnameobject
from . import fileobject
from . import uriobject


LOG = logging.getLogger(__name__)


DECODERS = {
    'DomainNameObjectType': domainnameobject.decode,
    'FileObjectType': fileobject.decode,
    'URIObjectType': uriobject.decode
}


def object_extract_properties(props):
    type_ = props.get('xsi:type').rsplit(':')[-1]

    if type_ not in DECODERS:
        LOG.error('Unhandled cybox Object type: {!r} - {!r}'.format(type_, props))
        return []

    return DECODERS[type_](props)


def decode(content):
    result = []

    package = BeautifulSoup(content, 'xml')

    if package.contents[0].name != 'STIX_Package':
        LOG.error('No STIX package in content')
        return []
    package = package.contents[0]

    pprops = package_extract_properties(package)

    observables = package.find_all('Observable')
    for o in observables:
        gprops = observable_extract_properties(o)

        obj = next((ob for ob in o if ob.name == 'Object'), None)
        if obj is None:
            continue

        # main properties
        properties = next((c for c in obj if c.name == 'Properties'), None)
        if properties is not None:
            for r in object_extract_properties(properties):
                r.update(gprops)
                r.update(pprops)

                result.append(r)

        # then related objects
        related = next((c for c in obj if c.name == 'Related_Objects'), None)
        if related is not None:
            for robj in related:
                if robj.name != 'Related_Object':
                    continue

                properties = next((c for c in robj if c.name == 'Properties'), None)
                if properties is None:
                    continue

                for r in object_extract_properties(properties):
                    r.update(gprops)
                    r.update(pprops)
                    result.append(r)

    return result
