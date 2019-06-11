import logging

from netaddr import IPAddress

LOG = logging.getLogger(__name__)


def decode(props, ip_version_auto_detect=False, **kwargs):
    indicator = props.find('Address_Value')
    if indicator is None:
        return []
    indicator = indicator.string.encode('ascii', 'replace')

    acategory = props.get('category', None)
    if acategory is None or ip_version_auto_detect:
        try:
            ip = IPAddress(indicator)
            if ip.version == 4:
                type_ = 'IPv4'
            elif ip.version == 6:
                type_ = 'IPv6'
            else:
                LOG.error('Unknown ip version: {!r}'.format(ip.version))
                return []

        except Exception:
            return []

    elif acategory == 'ipv4-addr':
        type_ = 'IPv4'
    elif acategory == 'ipv6-addr':
        type_ = 'IPv6'
    elif acategory == 'e-mail':
        type_ = 'email-addr'
    else:
        LOG.error('Unknown AddressObjectType category: {!r}'.format(acategory))
        return []

    return [{
        'indicator': indicator,
        'type': type_
    }]
