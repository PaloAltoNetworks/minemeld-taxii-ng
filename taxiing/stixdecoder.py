import logging

from bs4 import BeautifulSoup


LOG = logging.getLogger(__name__)


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
    'FileObjectType': _file_decoder
}


def _decode_cybox_properties(props):
    type_ = props.get('xsi:type').rsplit(':')[-1]

    if type_ in DECODERS:
        return DECODERS[type_](props)

    LOG.error('Unhandled cybox Object type: {!r}'.format(type_))

    return []


def decode(content):
    result = []

    package = BeautifulSoup(content, 'xml')

    if package.contents[0].name != 'STIX_Package':
        LOG.error('No STIX package in content')
        return []
    package = package.contents[0]

    observables = package.find_all('Observable')
    for o in observables:
        oid_ = o.get('id')
        obj = next((ob for ob in o if ob.name == 'Object'), None)
        if obj is None:
            continue

        properties = next((c for c in obj if c.name == 'Properties'), None)
        if properties is None:
            continue

        result.extend(_decode_cybox_properties(properties))

    return result
