"""Chrome Native Messaging: little-endian length, UTF-8 JSON; no stdout logging."""
import json, struct
MAX_MESSAGE = 900_000

def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size-len(data))
        if not chunk:
            raise EOFError('消息截断')
        data.extend(chunk)
    return bytes(data)

def read_message(stream):
    head = stream.read(4)
    if not head:
        return None
    if len(head) < 4:
        head += read_exact(stream, 4-len(head))
    size = struct.unpack('<I', head)[0]
    if not 0 < size <= MAX_MESSAGE:
        raise ValueError('消息大小超限')
    value = json.loads(read_exact(stream, size).decode('utf-8'))
    if not isinstance(value, dict):
        raise ValueError('消息必须为对象')
    return value

def write_message(stream, obj):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    if len(data) > MAX_MESSAGE:
        raise ValueError('响应过大')
    stream.write(struct.pack('<I', len(data)) + data)
    stream.flush()
