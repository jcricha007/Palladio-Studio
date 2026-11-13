"""Small, revisioned reference boards; image bytes never name an external resource."""
import base64
import binascii
import struct
import zlib
from uuid import uuid4
from .scene import ValidationError, required_text

MAX_IMAGE_BYTES = 500_000
MAX_REFERENCES = 6


def image(data):
    if not isinstance(data, str) or len(data) > 670_000:
        raise ValidationError('Use a reference image up to 500 KB.')
    try:
        raw = base64.b64decode(data, validate=True)
        if not 20 <= len(raw) <= MAX_IMAGE_BYTES: raise ValueError()
        width = height = 0
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'; offset = 8; seen = set()
            while offset < len(raw):
                length = struct.unpack('>I', raw[offset:offset+4])[0]
                kind = raw[offset+4:offset+8]; end = offset+12+length
                if end > len(raw): raise ValueError()
                chunk = raw[offset+8:end-4]
                if zlib.crc32(kind+chunk) != struct.unpack('>I',raw[end-4:end])[0]: raise ValueError()
                if not seen and kind != b'IHDR': raise ValueError()
                if kind == b'IHDR':
                    if seen or length != 13: raise ValueError()
                    width, height = struct.unpack('>II',chunk[:8])
                seen.add(kind);offset = end
                if kind == b'IEND':
                    if length or offset != len(raw): raise ValueError()
                    break
            if not {b'IHDR', b'IDAT', b'IEND'} <= seen: raise ValueError()
        elif raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9'):
            mime = 'image/jpeg'; offset = 2
            while offset < len(raw)-2:
                if raw[offset] != 255: raise ValueError()
                while raw[offset] == 255: offset += 1
                marker = raw[offset]; offset += 1
                if marker == 0xda: break  # entropy-coded image follows the scan header
                if marker in (0xd8,0xd9,0x01) or 0xd0 <= marker <= 0xd7: continue
                length = struct.unpack('>H',raw[offset:offset+2])[0]
                if length < 2 or offset+length > len(raw): raise ValueError()
                if marker in (0xc0,0xc1,0xc2):
                    if length < 8: raise ValueError()
                    height,width = struct.unpack('>HH',raw[offset+3:offset+7])
                offset += length
        else: raise ValueError()
        if not 1 <= width <= 2048 or not 1 <= height <= 2048: raise ValueError()
    except (ValueError, binascii.Error, struct.error, IndexError) as error:
        raise ValidationError('Use a PNG or JPEG reference with valid headers, up to 500 KB and 2048 × 2048 pixels.') from error
    return {'mime':mime, 'data':data, 'width':width, 'height':height}


def details(data):
    if not isinstance(data, dict) or not data.keys() <= {'name','cues','image'}:
        raise ValidationError('Choose reference name, design cues and an image.')
    cues = data.get('cues','')
    if not isinstance(cues,str) or len(cues)>1600: raise ValidationError('Use up to 1600 characters of design cues.')
    return {'name':required_text(data.get('name'),'Reference name',80),'cues':cues.strip()}


def edit_reference(scene, command):
    items = scene.setdefault('references',[])
    action = command['action']
    if action == 'reference_add':
        if len(items) >= MAX_REFERENCES: raise ValidationError('Keep at most six references on this property.')
        data = command.get('reference'); checked = details(data)
        checked.update(image(data.get('image')))
        checked['id'] = str(uuid4());items.append(checked)
        return 'Added reference '+checked['name']
    target = next((r for r in items if r['id']==command.get('id')),None)
    if target is None: raise ValidationError('This reference is no longer on the property.')
    if action == 'reference_update':
        data = command.get('reference')
        if not isinstance(data,dict) or not data or not data.keys() <= {'name','cues'}:
            raise ValidationError('Edit the reference name or cues; add a new image separately.')
        target.update(details({**{k:target[k] for k in ('name','cues')},**data}))
        return 'Updated reference '+target['name']
    if action == 'reference_remove':
        items.remove(target);return 'Removed reference '+target['name']
    raise ValidationError('Unknown reference command.')


def selected_references(project, ids):
    if ids is None: ids=[]
    if not isinstance(ids,list) or len(ids)>2 or any(not isinstance(key,str) for key in ids) or len(set(ids))!=len(ids):
        raise ValidationError('Choose up to two distinct saved references.')
    lookup = {r['id']:r for r in project['scene'].get('references',[])}
    if any(key not in lookup for key in ids): raise ValidationError('A reference changed. Reload and select it again.')
    return [lookup[key] for key in ids]
