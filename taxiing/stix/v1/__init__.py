import logging
import datetime

import pytz
import dateutil.parser
from bs4 import BeautifulSoup

from .package import extract as package_extract_properties
from .observable import extract as observable_extract_properties

from . import domainnameobject
from . import fileobject
from . import uriobject
from . import addressobject


LOG = logging.getLogger(__name__)
EPOCH = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=pytz.UTC)


DECODERS = {
    'DomainNameObjectType': domainnameobject.decode,
    'FileObjectType': fileobject.decode,
    'WindowsFileObjectType': fileobject.decode,
    'URIObjectType': uriobject.decode,
    'AddressObjectType': addressobject.decode
}


def object_extract_properties(props, kwargs):
    type_ = props.get('xsi:type').rsplit(':')[-1]

    if type_ not in DECODERS:
        LOG.error('Unhandled cybox Object type: {!r} - {!r}'.format(type_, props))
        return []

    return DECODERS[type_](props, **kwargs)


def _parse_stix_timestamp(stix_timestamp):
    dt = dateutil.parser.parse(stix_timestamp)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    delta = dt - EPOCH
    return int(delta.total_seconds()*1000)


def _deduplicate(indicators):
    result = {}

    for iv in indicators:
        result['{}:{}'.format(iv['indicator'], iv['type'])] = iv

    return result.values()


def decode(content, **kwargs):
    result = []

    package = BeautifulSoup(content, 'xml')

    if package.contents[0].name != 'STIX_Package':
        LOG.error('No STIX package in content')
        return None, []

    package = package.contents[0]

    timestamp = package.get('timestamp', None)
    if timestamp is not None:
        timestamp = _parse_stix_timestamp(timestamp)

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
            for r in object_extract_properties(properties, kwargs):
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

                for r in object_extract_properties(properties, kwargs):
                    r.update(gprops)
                    r.update(pprops)
                    result.append(r)

    return timestamp, _deduplicate(result)
