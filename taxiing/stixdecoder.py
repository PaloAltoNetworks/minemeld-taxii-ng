import logging

from bs4 import BeautifulSoup


LOG = logging.getLogger(__name__)


def _uri_decoder(props):
    utype = props.get('type', 'URL')
    if utype != 'URL':
        return []

    url = props.find('Value')
    if url is None:
        return []

    return [{
        'indicator': url.string.encode('ascii', 'replace'),
        'type': 'URL'
    }]


def _domain_name_decoder(props):
    dtype = props.get('type', 'FQDN')
    if dtype != 'FQDN':
        return []

    domain = props.find('Value')
    if domain is None:
        return []

    return [{
        'indicator': domain.string.encode('ascii', 'replace'),
        'type': 'domain'
    }]


def _file_decoder(props):
    result = []

    hashes = props.find_all('Hash')
    for h in hashes:
        htype = h.find('Type')
        if htype is None:
            continue
        htype = htype.string.lower()
        if htype not in ['md5', 'sha1', 'sha256', 'ssdeep']:
            continue

        value = h.find('Simple_Hash_Value')
        if value is None:
            continue
        value = value.string.lower()

        result.append({
            'indicator': value,
            'type': htype
        })

    return result


DECODERS = {
    'DomainNameObjectType': _domain_name_decoder,
    'FileObjectType': _file_decoder,
    'URIObjectType': _uri_decoder
}


def _decode_cybox_generic_props(observable):
    result = {}

    title = next((c for c in observable if c.name == 'Title'), None)
    if title is not None:
        title = title.text
        result['stix_title'] = title

    description = next((c for c in observable if c.name == 'Description'), None)
    if description is not None:
        description = description.text
        result['stix_description'] = description

    return result


def _decode_cybox_properties(props):
    type_ = props.get('xsi:type').rsplit(':')[-1]

    if type_ not in DECODERS:
        LOG.error('Unhandled cybox Object type: {!r} - {!r}'.format(type_, props))
        return []

    return DECODERS[type_](props)


def _decode_package_properties(package):
    result = {}

    header = package.find_all('STIX_Header')
    if len(header) == 0:
        return result

    # share level
    mstructures = header[0].find_all('Marking_Structure')
    for ms in mstructures:
        type_ = ms.get('xsi:type')
        if type_ is result:
            continue

        color = ms.get('color')
        if color is result:
            continue

        type_ = type_.lower()
        if 'tlpmarkingstructuretype' not in type_:
            continue

        result['share_level'] = color.lower()
        break

    # decode title
    title = next((c for c in header[0] if c.name == 'Title'), None)
    if title is not None:
        result['stix_package_title'] = title.text

    # decode description
    description = next((c for c in header[0] if c.name == 'Description'), None)
    if description is not None:
        result['stix_package_description'] = description.text

    return result


def decode(content):
    result = []

    package = BeautifulSoup(content, 'xml')

    if package.contents[0].name != 'STIX_Package':
        LOG.error('No STIX package in content')
        return []
    package = package.contents[0]

    pprops = _decode_package_properties(package)

    observables = package.find_all('Observable')
    for o in observables:
        gprops = _decode_cybox_generic_props(o)

        obj = next((ob for ob in o if ob.name == 'Object'), None)
        if obj is None:
            continue

        # main properties
        properties = next((c for c in obj if c.name == 'Properties'), None)
        if properties is not None:
            for r in _decode_cybox_properties(properties):
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

                for r in _decode_cybox_properties(properties):
                    r.update(gprops)
                    r.update(pprops)
                    result.append(r)

    return result
