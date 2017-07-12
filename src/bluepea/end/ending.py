# -*- encoding: utf-8 -*-
"""
Ending Module

ReST endpoints

"""
from __future__ import generator_stop

from collections import OrderedDict as ODict, deque
import enum
try:
    import simplejson as json
except ImportError:
    import json

import falcon

from ioflo.aid.sixing import *
from ioflo.aid import getConsole

from ..bluepeaing import SEPARATOR

from ..help.helping import (parseSignatureHeader, verify64u,
                            validateSignedAgentReg, validateSignedThingReg,
                            validateSignedResource, validateSignedAgentWrite)
from ..db import dbing
from ..keep import keeping

console = getConsole()

AGENT_BASE_PATH = "/agent"
SERVER_BASE_PATH = "/server"
THING_BASE_PATH = "/thing"

class ServerResource:
    """
    Server Agent Resource

    Attributes:
        .store is reference to ioflo data store

    """
    def  __init__(self, store=None, **kwa):
        """
        Parameters:
            store is reference to ioflo data store
        """
        super(**kwa)
        self.store = store

    def on_get(self, req, rep):
        """
        Handles GET request for the Server Agent
        """
        did = keeping.gKeeper.did

        # read from database
        try:
            dat, ser, sig = dbing.getSelfSigned(did)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_400,
                            'Resource Verification Error',
                            'Error verifying resource. {}'.format(ex))

        if dat is None:
            raise falcon.HTTPError(falcon.HTTP_NOT_FOUND,
                                               'Not Found Error',
                                               'DID resource does not exist')

        rep.set_header("Signature", 'signer="{}"'.format(sig))
        rep.set_header("Content-Type", "application/json; charset=UTF-8")
        rep.status = falcon.HTTP_200  # This is the default status
        rep.body = ser

class AgentResource:
    """
    Agent Resource

    Attributes:
        .store is reference to ioflo data store

    """
    def  __init__(self, store=None, **kwa):
        """
        Parameters:
            store is reference to ioflo data store
        """
        super(**kwa)
        self.store = store

    def on_post(self, req, rep):
        """
        Handles POST requests
        """
        signature = req.get_header("Signature")
        sigs = parseSignatureHeader(signature)
        sig = sigs.get('signer')  # str not bytes
        if not sig:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                           'Invalid or missing Signature header.')

        try:
            regb = req.stream.read()  # bytes
        except Exception:
            raise falcon.HTTPError(falcon.HTTP_400,
                                       'Read Error',
                                       'Could not read the request body.')

        registration = regb.decode("utf-8")

        result = validateSignedAgentReg(sig, registration)
        if not result:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                            'Could not validate the request body.')

        if "hids" in result:
            # validate hid control here
            pass

        did = result['did']  # unicode version

        # save to database
        try:
            dbing.putSigned(registration, sig, did, clobber=False)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_412,
                                  'Database Error',
                                  '{}'.format(ex.args[0]))

        didURI = falcon.uri.encode_value(did)
        rep.status = falcon.HTTP_201  # post response status with location header
        rep.location = "{}?did={}".format(AGENT_BASE_PATH, didURI)
        rep.body = json.dumps(result)

    def on_get(self, req, rep):
        """
        Handles GET request for an AgentResources given by query parameter
        with did


        """
        did = req.get_param("did")  # already has url-decoded query parameter value

        # read from database
        try:
            dat, ser, sig = dbing.getSelfSigned(did)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_400,
                            'Resource Verification Error',
                            'Error verifying resource. {}'.format(ex))

        if dat is None:
            raise falcon.HTTPError(falcon.HTTP_NOT_FOUND,
                                               'Not Found Error',
                                               'DID resource does not exist')

        rep.set_header("Signature", 'signer="{}"'.format(sig))
        rep.set_header("Content-Type", "application/json; charset=UTF-8")
        rep.status = falcon.HTTP_200  # This is the default status
        rep.body = ser


class AgentDidResource:
    """
    Agent Did Resource
    Access agent by DID

    /agent/{did}

    Attributes:
        .store is reference to ioflo data store

    """
    def  __init__(self, store=None, **kwa):
        """
        Parameters:
            store is reference to ioflo data store
        """
        super(**kwa)
        self.store = store

    def on_put(self, req, rep, did):
        """
        Handles PUT requests

        /agent/{did}

        Falcon url decodes path parameters such as {did}
        """
        signature = req.get_header("Signature")
        sigs = parseSignatureHeader(signature)
        sig = sigs.get('signer')  # str not bytes
        if not sig:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                           'Invalid or missing Signature header.')
        csig = sigs.get('current')  # str not bytes
        if not csig:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                           'Invalid or missing Signature header.')

        try:
            serb = req.stream.read()  # bytes
        except Exception:
            raise falcon.HTTPError(falcon.HTTP_400,
                                       'Read Error',
                                       'Could not read the request body.')
        ser = serb.decode("utf-8")

        # Get validated current resource from database
        try:
            rdat, rser, rsig = dbing.getSelfSigned(did)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_400,
                            'Resource Verification Error',
                            'Error verifying signer resource. {}'.format(ex))


        # validate request
        dat = validateSignedAgentWrite(cdat=rdat, csig=csig, sig=sig, ser=ser)
        if not dat:
            raise falcon.HTTPError(falcon.HTTP_400,
                                               'Validation Error',
                                           'Could not validate the request body.')

        if "hids" in dat:
            pass  # validate hid namespaces here

        # save to database
        try:
            dbing.putSigned(ser, sig, did, clobber=True)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_412,
                                  'Database Error',
                                  '{}'.format(ex.args[0]))

        rep.set_header("Signature", 'signer="{}"'.format(sig))
        rep.set_header("Content-Type", "application/json; charset=UTF-8")
        rep.status = falcon.HTTP_200  # This is the default status
        rep.body = ser

    def on_get(self, req, rep, did):
        """
        Handles GET request for an Agent Resource by did

        /agent/{did}

        Falcon url decodes path parameters such as {did}
        """
        # read from database
        try:
            dat, ser, sig = dbing.getSelfSigned(did)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_400,
                            'Resource Verification Error',
                            'Error verifying resource. {}'.format(ex))

        if dat is None:
            raise falcon.HTTPError(falcon.HTTP_NOT_FOUND,
                                               'Not Found Error',
                                               'DID resource does not exist')

        rep.set_header("Signature", 'signer="{}"'.format(sig))
        rep.set_header("Content-Type", "application/json; charset=UTF-8")
        rep.status = falcon.HTTP_200  # This is the default status
        rep.body = ser


class ThingResource:
    """
    Thing Resource

    Attributes:
        .store is reference to ioflo data store

    """
    def  __init__(self, store=None, **kwa):
        """
        Parameters:
            store is reference to ioflo data store
        """
        super(**kwa)
        self.store = store

    def on_post(self, req, rep):
        """
        Handles POST requests
        """
        signature = req.get_header("Signature")
        sigs = parseSignatureHeader(signature)

        dsig = sigs.get('did')  # str not bytes thing's did signature
        if not dsig:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                           'Invalid or missing Signature header.')

        tsig = sigs.get('signer')  # str not bytes thing's signer signature
        if not tsig:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                           'Invalid or missing Signature header.')

        try:
            regb = req.stream.read()  # bytes
        except Exception:
            raise falcon.HTTPError(falcon.HTTP_400,
                                       'Read Error',
                                       'Could not read the request body.')

        registration = regb.decode("utf-8")

        # validate thing resource and verify did signature
        result = validateSignedThingReg(dsig, registration)
        if not result:
            raise falcon.HTTPError(falcon.HTTP_400,
                                           'Validation Error',
                                            'Could not validate the request body.')

        # verify signer signature by looking up signer data resource in database
        try:
            sdid, index = result["signer"].rsplit("#", maxsplit=1)
            index = int(index)  # get index and sdid from signer field
        except (AttributeError, ValueError) as ex:
                raise falcon.HTTPError(falcon.HTTP_400,
                                   'Validation Error',
                                    'Invalid or missing did key index.')   # missing sdid or index

        # read and verify signer agent from database
        try:
            sdat, sser, ssig = dbing.getSelfSigned(sdid)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_400,
                            'Resource Verification Error',
                            'Error verifying signer resource. {}'.format(ex))

        # now use signer agents key indexed for thing signer to verify thing resource
        try:
            tkey = sdat['keys'][index]['key']
        except (IndexError, KeyError) as ex:
            raise falcon.HTTPError(falcon.HTTP_424,
                                           'Data Resource Error',
                                           'Missing signing key')

        if not validateSignedResource(tsig, registration, tkey):
                raise falcon.HTTPError(falcon.HTTP_400,
                                   'Validation Error',
                                    'Could not validate the request body.')

        if "hid" in result and result["hid"]:  # non-empty hid
            # validate hid control here
            pass

        tdid = result['did']  # unicode version

        # save to database core
        try:
            dbing.putSigned(registration, tsig, tdid, clobber=False)
        except DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_412,
                                  'Database Error',
                                  '{}'.format(ex.args[0]))

        if result['hid']:  # add entry to hids table to lookup did by hid
            try:
                dbing.putHid(result['hid'], tdid)
            except DatabaseError as ex:
                raise falcon.HTTPError(falcon.HTTP_412,
                                      'Database Error',
                                      '{}'.format(ex.args[0]))

        didURI = falcon.uri.encode_value(tdid)
        rep.status = falcon.HTTP_201  # post response status with location header
        rep.location = "{}?did={}".format(THING_BASE_PATH, didURI)
        rep.body = json.dumps(result)

    def on_get(self, req, rep):
        """
        Handles GET request for an ThingResources given by query parameter
        with did

        """
        did = req.get_param("did")  # already has url-decoded query parameter value
        #didb = did.encode("utf-8")  # bytes version

        # read from database
        try:
            dat, ser, sig = dbing.getSigned(did)
        except dbing.DatabaseError as ex:
            raise falcon.HTTPError(falcon.HTTP_400,
                            'Resource Verification Error',
                            'Error verifying resource. {}'.format(ex))

        if dat is None:
            raise falcon.HTTPError(falcon.HTTP_NOT_FOUND,
                                               'Not Found Error',
                                               'DID resource does not exist')

        rep.set_header("Signature", 'signer="{}"'.format(sig))
        rep.set_header("Content-Type", "application/json; charset=UTF-8")
        rep.status = falcon.HTTP_200  # This is the default status
        rep.body = ser


def loadEnds(app, store):
    """
    Load endpoints for app with store reference
    This function provides the endpoint resource instances
    with a reference to the data store
    """
    server = ServerResource(store=store)
    app.add_route('{}'.format(SERVER_BASE_PATH), server)

    agent = AgentResource(store=store)
    app.add_route('{}'.format(AGENT_BASE_PATH), agent)

    agentDid = AgentDidResource(store=store)
    app.add_route('{}/{{did}}'.format(AGENT_BASE_PATH), agentDid)

    thing = ThingResource(store=store)
    app.add_route('{}'.format(THING_BASE_PATH), thing)
