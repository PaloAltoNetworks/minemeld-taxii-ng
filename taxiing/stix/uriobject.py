def decode(props):
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
