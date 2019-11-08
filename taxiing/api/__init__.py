def blueprint():
    from minemeld.flask import aaa, config  # pylint: disable E0401

    bp = aaa.MMBlueprint('taxiing', __name__, url_prefix='/taxiing')

    if config.get('TAXIING_ENABLE_TAXII1_STIX2_POLL', False):
        from .v1 import poll

        bp.route(
            '/v1/poll', methods=['POST'], feeds=True, read_write=False
        )(poll)

    if config.get('TAXIING_ENABLE_TAXII2_STIX2_POLL', False):
        import taxiing.api.v2 as taxii2

        bp.route('/v2/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_taxii2_server)
        bp.route('/v2/api/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_apiroot)
        bp.route('/v2/api/collections/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_collections)
        bp.route('/v2/api/collections/<collection>/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_collection)
        bp.route('/v2/api/collections/<collection>/objects/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_collection_objects)
        bp.route('/v2/api/collections/<collection>/objects/<objectid>/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_collection_object)
        bp.route('/v2/api/collections/<collection>/manifest/', methods=['GET'], feeds=True, read_write=False)(taxii2.get_collection_manifest)
    return bp
