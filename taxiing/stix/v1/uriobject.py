def decode(props, **kwargs):
    utype = props.get('type', 'URL')
    if utype == 'URL':
        type_ = 'URL'
    elif utype == 'Domain Name':
        type_ = 'domain'
    else:
        return []

    url = props.find('Value')
    if url is None:
        return []

    return [{
        'indicator': url.string.encode('ascii', 'replace'),
        'type': type_
    }]
