from subservices import RpcSubservices

import time
import cbor
import hashlib
import struct
import random

from kms import NitroKms


def ENSURE_LOCAL_ONLY(rpc):
    # this is to make sure a given rpc method can be called from the enclave only
    assert (rpc.socket_queue.socket.getpeername()
            [0] == 42), "Permission denied"


'''
This requires connection with KMS, CloudTrail and S3
'''

def get_ts():
    ts = int(time.time())
    return ts

# The reasoning behind this format is:
#   - 00 makes the alias appears on the top 100 aliases
#     list given by the Amazon API
#   - 999 is supposed to be decreased when the format
#     evolves
#   - same as for v1
#   - then the param is a decreasing funcion which makes
#     sure the next created alias is within the top 100
KMS_ALIAS_PREFIX = "alias/00999_v1_{}_".format(int(1e12 - get_ts()))

class DbServices(RpcSubservices):

    def __init__(self, STATE):
        self.STATE = STATE
        super().__init__(STATE)
        if not 'credentials' in dir(self.STATE):
            self.STATE.credentials = {}
            self.STATE.cache = {}
            self.STATE.transacting = False
            self.STATE.known_cmks = {}

    def _is_ready(self):
        return self.STATE.credentials

    def _state_hash(self, data):
        # any key prefixed with _EXT_ isn't state integrity guaranteed
        state_det = [i for i in data.items() if not i[0].startswith(b'_EXT_')]
        state_det.sort()
        h = hashlib.sha256(cbor.dumps(state_det)).digest()
        return h

    def _kms_getLatestCMK(self):
        aliases = self.STATE.nitro_kms.kms_list_aliases()
        #print("Found %d aliases" % aliases['AliasCount'])
        # print(aliases)
        prefix = KMS_ALIAS_PREFIX
        valid_aliases = [int(i['AliasName'].replace(prefix, ""))
                         for i in aliases['Aliases'] if i['AliasName'].startswith(prefix)]
        if len(valid_aliases) == 0:
            return {}
        latest_alias = prefix + str(min(valid_aliases))
        latest_keyid = [i['TargetKeyId']
                        for i in aliases['Aliases'] if i['AliasName'] == latest_alias][0]
        return {'alias': latest_alias, 'keyid': latest_keyid}

    def _kms_validateCMK(self, keyid):
        if keyid in self.STATE.known_cmks.keys():
            return True
        # TODO: validity check (if known or analysis passes)
        return True

    def _kms_nextAlias(self, prev_alias=None):
       prefix = KMS_ALIAS_PREFIX
       if not prev_alias:
            return prefix + "9999999999"
       else:
            return prefix + str(int(prev_alias.split("_")[-1])-1)

    def DB__init(self, rpc, credentials):
        #global CREDENTIALS, AWS_SESSION
        # not self.STATE.credentials:#['CREDENTIALS']: #not 'CREDENTIALS' in globals():
        if True:
            print("DB module initialized with credentials!")
            self.STATE.credentials = credentials
            # print(self.CREDENTIALS)
            self.STATE.nitro_kms = NitroKms()
            self.STATE.nitro_kms.set_region('eu-central-1')
            self.STATE.nitro_kms.set_credentials(credentials)

            # NOTE: remember alias is guaranteed unique per region, never change region without resetting.. region can be set just during init

            '''
            aliases = nitro_kms.kms_list_aliases()
            print("Found %d aliases" % aliases['AliasCount'])
            print(aliases)
            prefix = "alias/ltest_"
            validAliases = [int(i['AliasName'].replace(prefix, "")) for i in aliases['Aliases'] if i['AliasName'].startswith(prefix)]
            print(validAliases)
            print(min(validAliases))
            oldalias = prefix + str(min(validAliases))
            newalias = prefix + str(min(validAliases)-1)
            oldkeyid = [i['TargetKeyId'] for i in aliases['Aliases'] if i['AliasName'] == oldalias][0]

            keyid = oldalias
            encrypt_response = nitro_kms.kms_encrypt(                                kms_key_id=keyid,                                            plaintext_bytes=b"ciao"                                                    )
            nitro_kms.kms_decrypt(keyid, encrypt_response['CiphertextBlob'])


            newkey = nitro_kms.kms_create_key()
            print(newkey)
            newkeyid = newkey['KeyMetadata']['KeyId']
            print(nitro_kms.kms_create_alias(newkeyid, newalias))
            print("alias set, now deleting old key '%s'" % oldkeyid)
            nitro_kms.kms_delete_key(oldkeyid)
            print("FIN.")
            '''
            return True

        return False

    '''
    1) erase any open conn and empties state
    2) checks KMS CMK exists (otherwise starts fresh by returning immediately)
    3) checks KMS CMK is safe by checking if (KNOWN or if (Conditions ok + CloudTrail ok)) (otherwise raises Exception)
    4) downloads state locally, if any (otherwise empty)
    5) checks state integrity via KMS (otherwise raises Exception)
    '''

    def DB__start_transaction(self, rpc, *args):
        ENSURE_LOCAL_ONLY(rpc)
        assert self._is_ready(), "Not ready"

        if self.STATE.transacting:  # a previous tx was left open, resetting..
            self.STATE.cache = {}

        print("Loading DATA from storage..")
        print(self.STATE.parent_vm_client)
        cache_items = self.STATE.parent_vm_client.DB__get_all()
        self.STATE.cache = {}
        for k, v in cache_items:
            self.STATE.cache[k] = v
        print("Verifying DATA integrity..")
        state_hash = self._state_hash(self.STATE.cache)
        print("State hash: %s" % state_hash.hex())

        self.STATE.first_run = False
        latest_cmk = self._kms_getLatestCMK()
        # empty state hash, first run? So we expect no CMK
        if state_hash == self._state_hash({}):
            noCMK = (not latest_cmk)
            if noCMK:
                self.STATE.first_run = True
            else:
                print("Non empty CMK with empty state, aborting..")
                raise Exception
        if self.STATE.first_run:
            self.STATE.cache = {}
        else:  # check if sig is valid
            # look for latest CMK, is that whitelisted in memory here _OR_ (if it has a valid attestation document attached (+ CloudTrail logs?))
            if not latest_cmk:
                print("Illegal signature claim (wrong CMK?) for non-empty state, aborting..")
                raise Exception
            ssig = self.STATE.cache[b'_EXT_STATESIG']
            decrypt_response, ssig_state_hash = self.STATE.nitro_kms.kms_decrypt(
                '', ssig)
            validSig = (latest_cmk) and (state_hash == ssig_state_hash) and (decrypt_response['KeyId'].endswith(latest_cmk['keyid']))
            if not validSig:
                print("Invalid signature for non-empty state, aborting..")
                raise Exception
            else:
                print("Valid state detected, continuing.. :)")
        self.STATE.original_hash = state_hash

        self.STATE.transacting = True
        return True

    '''
    returns data from inmemory cache if sensitivity == 0, otherwise returns decrypted data with active CMK
    '''

    def DB__get(self, rpc, el):
        ENSURE_LOCAL_ONLY(rpc)
        assert self._is_ready(), "Not ready"

        # get() called before starttx(), calling starttx() first..
        if not self.STATE.transacting:
            print("NOT TRANSACTING just yet, calling starttx()..")
            self.DB__start_transaction(rpc)

        if el['key'] not in self.STATE.cache.keys():
            return None  # key doesn't exist in state

        if el['sensitivity'] == 0:
            res = self.STATE.cache[el['key']][1:]  # skip sensitivity marker
            return res
        else:
            assert self.STATE.cache[el['key']
                                    ][0] != b'\0', "Inconsistent sensitivity marker"
            # skip sensitivity marker
            encrypted_el = self.STATE.cache[el['key']][1:]
            decrypted_el = encrypted_el  # TODO: decryption needed
            return decrypted_el

    '''
    if any change has to be applied, atomically does the following:
    - create new CMK
    - reencrypt sensitivity>0 data
    - update S3
    - schedule deletion for old CMK
    '''

    def DB__end_transaction(self, rpc, *args):
        ENSURE_LOCAL_ONLY(rpc)
        assert self._is_ready(), "Not ready"

        assert self.STATE.transacting, "Cannot endtx when not transacting"

        if len(args) == 0 and self._state_hash(self.STATE.cache) == self.STATE.original_hash:  # there is no change!
            self.STATE.transacting = False
            self.STATE.cache = {}
            return True

        # time to create CMK1
        if not self.STATE.first_run:
            CMK0 = self._kms_getLatestCMK()
            cmk1_alias = self._kms_nextAlias(CMK0['alias'])
        else:
            cmk1_alias = self._kms_nextAlias()
        cmk1_raw = self.STATE.nitro_kms.kms_create_key() #TODO: add correct key conditions!
        CMK1 = {'alias': cmk1_alias, 'keyid': cmk1_raw['KeyMetadata']['KeyId']}

        if not self.STATE.first_run:  # time to rotate old encrypted material
            # TODO: decrypt with CMK0 + encrypt with CMK1 (reencrypt call can be used!!)
            pass

        # there are changes to apply, on it..
        print("Applying changes..")
        for arg in args:
            if arg['method'] == 'put':
                if arg['sensitivity'] == 0:
                    # the first byte of the value indicates the sensitivity
                    self.STATE.cache[arg['key']] = b'\0' + arg['value']
                else:
                    # TODO: encryption needed
                    encrypted_el = arg['value']
                    self.STATE.cache[arg['key']] = struct.pack(
                        "B", arg['sensitivity']) + encrypted_el
            elif arg['method'] == 'delete':
                del self.STATE.cache[arg['key']]

        # time to sign with CMK1 the new state and add the sig to the state
        encrypt_response = self.STATE.nitro_kms.kms_encrypt(
            kms_key_id=CMK1['keyid'], plaintext_bytes=self._state_hash(self.STATE.cache))
        self.STATE.cache[b'_EXT_STATESIG'] = encrypt_response['CiphertextBlob']

        self.STATE.parent_vm_client.DB__write_all(
            list(self.STATE.cache.items()))

        if not self.STATE.first_run:
            self.STATE.nitro_kms.kms_delete_key(CMK0['keyid'])

        self.STATE.nitro_kms.kms_create_alias(CMK1['keyid'], CMK1['alias'])
        self.STATE.known_cmks[CMK1['keyid']] = True

        self.STATE.transacting = False
        self.STATE.cache = {}
        return True
