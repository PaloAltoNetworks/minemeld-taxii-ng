def _decode_basic_props(props):
    result = {}

    name = next((c for c in props if c.name == 'File_Name'), None)
    if name is not None:
        result['stix_file_name'] = name.text

    size = next((c for c in props if c.name == 'File_Size'), None)
    if size is not None:
        result['stix_file_size'] = size.text

    format = next((c for c in props if c.name == 'File_Format'), None)
    if format is not None:
        result['stix_file_format'] = format.text

    return result


def decode(props, **kwargs):
    result = []

    bprops = _decode_basic_props(props)

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

    for r in result:
        for r2 in result:
            if r['type'] == r2['type']:
                continue

            r['stix_file_{}'.format(r2['type'])] = r2['indicator']

        r.update(bprops)

    return result
