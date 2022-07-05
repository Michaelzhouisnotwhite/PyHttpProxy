from typing import Optional, Tuple, Union
from .exceptions import *


class HttpHeaderParser:
    content_length = -1
    host = None


def parse_request(request_stream: bytes) -> Union[Tuple[Tuple[bytes, Union[bytes, int]], int], Tuple[None, None]]:
    header: bytes = b""
    res_list = request_stream.split(b"\r\n\r\n")
    if len(res_list) > 1:  # find header
        header = res_list[0]

    else:
        return None, None

    if len(header) > 0:
        # find Host
        res_list = header.split(b"Host:")
        if len(res_list) > 1:
            host = res_list[1].split(b"\r\n")[0].strip()
            name_port_res = host.split(b":")
            host_name = name_port_res[0].strip()
            if len(name_port_res) > 1:
                host_port = name_port_res[1].strip()
            else:
                host_port = 80

        else:
            return None, None

        by_content_length = header.split(b"Content-Length:")
        by_transfer_encode = header.split(b"Transfer-Encoding:")

        if len(by_content_length) > 1 and len(by_transfer_encode) == 1:
            # has Content-Length
            content_length = int(by_content_length[1].split(b"\r\n")[0])
            return (host_name, host_port), content_length

        if len(by_content_length) == 1 and len(by_transfer_encode) > 1:
            # has Transfer-Encoding
            return (host_name, host_port), -1

        if len(by_content_length) == 1 and len(by_transfer_encode) == 1:
            # no Content Length
            return (host_name, host_port), 0
    else:
        return None, None


def is_http_end(stream: bytes):
    by_double_enter = stream.split(b"\x30\x0d\x0a\x0d\x0a")
    if len(by_double_enter) > 1:
        if len(by_double_enter[-1]) == 0:
            return True

    else:
        return False
