"""Strict candidate identity schema; never converts an existing Android identity."""
import base64
import re
import secrets
import uuid
from .macos_memory import valid_store_name

FIELDS={'version','host_uuid','uid','devid','serial','routing','saved'}
def validate_machine(value):
    if not isinstance(value,dict) or set(value)!=FIELDS or type(value['version']) is not int or value['version']!=1:raise ValueError('mac_identity_invalid')
    if not isinstance(value['host_uuid'],str) or not re.fullmatch('[a-f0-9]{32}',value['host_uuid']):raise ValueError('mac_identity_invalid')
    if not isinstance(value['uid'],str) or not re.fullmatch('[A-F0-9]{32}',value['uid']):raise ValueError('mac_identity_invalid')
    if not isinstance(value['devid'],str) or not re.fullmatch('00006000-[A-F0-9]{16}',value['devid']):raise ValueError('mac_identity_invalid')
    if not isinstance(value['serial'],str) or not re.fullmatch('[A-HJ-NP-Z0-9]{12}',value['serial']):raise ValueError('mac_identity_invalid')
    if type(value['routing']) is not int or not 0<=value['routing']<2**64:raise ValueError('mac_identity_invalid')
    saved=value['saved']
    if not isinstance(saved,dict) or not 0<len(saved)<=32:raise ValueError('mac_identity_invalid')
    total=0
    for name,data in saved.items():
        if not valid_store_name(name):raise ValueError('mac_identity_invalid')
        if not isinstance(data,str) or not 0<=len(data)<=1398104:raise ValueError('mac_identity_invalid')
        decoded=base64.b64decode(data,validate=True);total+=len(decoded)
        if not 0<=len(decoded)<=1048576:raise ValueError('mac_identity_invalid')
    if not 0<total<=4194304:raise ValueError('mac_identity_invalid')
    return value

def new_machine():
    return {'version':1,'host_uuid':secrets.token_hex(16),'uid':secrets.token_hex(16).upper(),
            'devid':'00006000-'+secrets.token_hex(8).upper(),
            'serial':'C02'+''.join(secrets.choice('0123456789ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(9)),
            'routing':0,'saved':{}}
