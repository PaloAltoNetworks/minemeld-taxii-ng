def decode(props, **kwargs):
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
