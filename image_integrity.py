"""Pure image-container bounds and closure checks, independent of Pillow flags.

Shared by publication and optional OCR. No decoder globals, disk writes or
recompression. Pixel decoding and size/frame budgets remain with each caller.
"""
import zlib
from error_messages import message as backend_message


def jpeg_without_metadata(blob):
    """Drop all APP/COM segments and trailing bytes without recompressing pixels."""
    if not blob.startswith(b'\xff\xd8'): raise ValueError(backend_message('JPEG inválido / Invalid JPEG'))
    out=bytearray(blob[:2]);pos=2
    while pos<len(blob):
        if blob[pos]!=255: raise ValueError(backend_message('Marcador JPEG inválido / Invalid JPEG marker'))
        while pos<len(blob) and blob[pos]==255: pos+=1
        if pos>=len(blob): break
        marker=blob[pos];pos+=1
        if marker==0xD9: out.extend(b'\xff\xd9');return bytes(out)
        if marker in (0x00,0xD8): raise ValueError(backend_message('JPEG inválido / Invalid JPEG'))
        if marker==1 or 0xD0<=marker<=0xD7:
            out.extend(bytes((255,marker)));continue
        if pos+2>len(blob): break
        length=int.from_bytes(blob[pos:pos+2],'big')
        if length<2 or pos+length>len(blob): raise ValueError(backend_message('JPEG truncado / Truncated JPEG'))
        if not (0xE0<=marker<=0xEF or marker==0xFE): out.extend(bytes((255,marker))+blob[pos:pos+length])
        pos+=length
        if marker==0xDA:
            start=pos
            while pos<len(blob):
                next_marker=blob.find(b'\xff',pos)
                if next_marker<0: raise ValueError(backend_message('JPEG truncado / Truncated JPEG'))
                end=next_marker+1
                while end<len(blob) and blob[end]==255: end+=1
                if end>=len(blob): raise ValueError(backend_message('JPEG truncado / Truncated JPEG'))
                if blob[end]==0 or 0xD0<=blob[end]<=0xD7:pos=end+1;continue
                out.extend(blob[start:next_marker]);pos=next_marker;break
    raise ValueError(backend_message('JPEG sin terminador / JPEG without terminator'))


def verify_container(blob, image_format):
    """Reject incomplete containers, independent of Pillow's permissive decoder.

    This is not a guarantee of pixel correctness or of OCR recognition quality.
    PNG includes a CRC check for every complete chunk.
    """
    try:
        _verify_container(blob,image_format)
    except ValueError as error:
        if str(error):
            raise
        raise ValueError(backend_message('La imagen está incompleta o dañada.',
                                        en='The image is incomplete or damaged.')) from None


def _verify_container(blob, image_format):
    if image_format == 'PNG':
        if blob[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError
        position = 8
        while position + 12 <= len(blob):
            size = int.from_bytes(blob[position:position + 4], 'big')
            end = position + size + 12
            if end > len(blob):
                raise ValueError
            if zlib.crc32(memoryview(blob)[position + 4:end - 4]) != int.from_bytes(blob[end - 4:end], 'big'):
                raise ValueError
            if blob[position + 4:position + 8] == b'IEND':
                if size != 0 or end != len(blob):
                    raise ValueError
                return
            position = end
        raise ValueError
    elif image_format == 'JPEG':
        jpeg_without_metadata(blob)  # Existing parser requires EOI.
    elif image_format == 'WEBP':
        if (len(blob) < 12 or blob[:4] != b'RIFF' or blob[8:12] != b'WEBP'
                or int.from_bytes(blob[4:8], 'little') + 8 != len(blob)):
            raise ValueError
        position = 12
        while position < len(blob):
            if position + 8 > len(blob):
                raise ValueError
            size = int.from_bytes(blob[position + 4:position + 8], 'little')
            position += 8 + size + size % 2
        if position != len(blob):
            raise ValueError
    elif image_format == 'GIF':
        if len(blob) < 14 or blob[:6] not in (b'GIF87a', b'GIF89a'):
            raise ValueError
        position = 13
        packed = blob[10]
        if packed & 128:
            position += 3 * (2 ** ((packed & 7) + 1))
        while position < len(blob):
            marker = blob[position]
            position += 1
            if marker == 0x3B:
                if position != len(blob):
                    raise ValueError
                return
            if marker == 0x21:  # Extension label followed by data sub-blocks.
                position += 1
            elif marker == 0x2C:  # Image descriptor, optional local color table.
                if position + 9 > len(blob):
                    raise ValueError
                packed = blob[position + 8]
                position += 9
                if packed & 128:
                    position += 3 * (2 ** ((packed & 7) + 1))
                position += 1  # LZW minimum code size precedes data sub-blocks.
            else:
                raise ValueError
            while True:
                if position >= len(blob):
                    raise ValueError
                size = blob[position]
                position += 1 + size
                if position > len(blob):
                    raise ValueError
                if size == 0:
                    break
        raise ValueError  # A complete GIF ends with its trailer block.

