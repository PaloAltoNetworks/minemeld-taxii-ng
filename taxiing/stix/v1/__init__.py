import logging
import datetime
import re

from bs4 import BeautifulSoup

from .package import extract as package_extract_properties
from .observable import extract as observable_extract_properties

from . import domainnameobject
from . import fileobject
from . import uriobject
from . import addressobject
from .. import parse_stix_timestamp


LOG = logging.getLogger(__name__)


DECODERS = {
    'DomainNameObjectType': domainnameobject.decode,
    'FileObjectType': fileobject.decode,
    'WindowsFileObjectType': fileobject.decode,
    'URIObjectType': uriobject.decode,
    'AddressObjectType': addressobject.decode
}


TLP_REGEX = re.compile("TLPMarkingStructureType")


def object_extract_properties(props, kwargs):
    type_ = props.get('xsi:type').rsplit(':')[-1]

    if type_ not in DECODERS:
        LOG.error('Unhandled cybox Object type: {!r} - {!r}'.format(type_, props))
        return []

    return DECODERS[type_](props, **kwargs)


def _deduplicate(indicators):
    result = {}

    for iv in indicators:
        result['{}:{}'.format(iv['indicator'], iv['type'])] = iv

    return result.values()


def decode_observable(observable, props, kwargs):
    result = []

    gprops = observable_extract_properties(observable)

    obj = next((ob for ob in observable if ob.name == 'Object'), None)
    if obj is None:
        return result

    # main properties
    properties = next((c for c in obj if c.name == 'Properties'), None)
    if properties is not None:
        for r in object_extract_properties(properties, kwargs):
            r.update(gprops)
            r.update(props)

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
                r.update(props)
                result.append(r)

    return result


def decode(content, **kwargs):
    result = []
    seen_observables = set([])
    confidence_map = kwargs.get('confidence_map', None)

    package = BeautifulSoup(content, 'xml')

    if package.contents[0].name != 'STIX_Package':
        LOG.error('No STIX package in content')
        return None, []

    package = package.contents[0]

    timestamp = package.get('timestamp', None)
    if timestamp is not None:
        timestamp = parse_stix_timestamp(timestamp)

    pprops = package_extract_properties(package)

    indicators = package.find_all('Indicator')
    for i in indicators:
        iprops = {}
        iprops.update(pprops)

        handling = i.find('Handling', recursive=False)
        if handling is not None:
            marking_structure = handling.find(
                'Marking_Structure',
                attrs={"xsi:type": TLP_REGEX}
            )
            tlp = marking_structure.get('color')
            if tlp is not None:
                iprops['share_level'] = tlp.lower()

        if confidence_map is not None:
            confidence = i.find('Confidence', recursive=False)
            if confidence is not None:
                value = confidence.find('Value')
                if value is not None and value.string.lower() in confidence_map:
                    iprops['confidence'] = confidence_map[value.string.lower()]

        observables = i.find_all('Observable')
        for o in observables:
            oid = o.get('id')
            if not oid or oid in seen_observables:
                continue

            observable_result = decode_observable(o, iprops, kwargs)
            result.extend(observable_result)
            seen_observables.add(oid)

    else:
        observables = package.find_all('Observable')
        for o in observables:
            oid = o.get('id')
            if not oid or oid in seen_observables:
                continue

            observable_result = decode_observable(o, pprops, kwargs)
            result.extend(observable_result)
            seen_observables.add(oid)

    return timestamp, _deduplicate(result)
