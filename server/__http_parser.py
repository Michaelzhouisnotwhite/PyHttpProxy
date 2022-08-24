import copy


class HttpParser:
    http_stream = b""  # store http stream
    add_count = 0
    content_length = None
    header_pos = 0
    connection = None
    host = None
    header_popped = False

    class HeaderError(Exception):
        pass

    class HttpEnd(Exception):
        pass

    def __init__(self):
        pass

    def get_header(self, pop=True):
        """
        get header from stream
        :param pop: if True: get and delete the header part
        :return: header part
        """
        if self.header_pos > 0:
            return self.http_stream[:self.header_pos]
        if pop:
            if self.header_pos > 0:
                self.header_popped = True
                header = copy.copy(self.http_stream[:self.header_pos])
                self.http_stream = self.http_stream[self.header_pos:]
                self.header_pos = -1
                return header

        raise self.HeaderError

    def check_end(self):
        """
        check if the http has ending EOF
        :return: Ture or False
        """
        if self.content_length >= 0:
            if self.add_count >= self.content_length + self.header_pos:
                return True
            else:
                return False
        if self.content_length == -1:
            by_double_enter = self.http_stream.split(b"\x30\x0d\x0a\x0d\x0a")
            if len(by_double_enter) > 1:
                if len(by_double_enter[-1]) == 0:
                    return True

            else:
                return False

    def add_bytes(self, data: bytes):
        """
        add bytes to http stream buffer
        :param data: bytes
        :return: if the data has http EOF
        """
        self.http_stream += data
        self.add_count += len(data)
        if self.header_pos == 0:
            # there is no headers
            by_double_enter = self.http_stream.split(b"\r\n\r\n")  # split header

            if len(by_double_enter) > 1:  # found header EOF
                self.header_pos = len(by_double_enter[0]) + len(b"\r\n\r\n")

            self._parse_http_stream()
            # if self.host is None or self.connection is None or self.content_length is None:
            #     raise self.HeaderError

        if self.content_length >= 0:
            if self.add_count >= self.content_length + self.header_pos:
                return True
            else:
                return False
        if self.content_length == -1:
            by_double_enter = self.http_stream.split(b"\x30\x0d\x0a\x0d\x0a")
            if len(by_double_enter) > 1:
                if len(by_double_enter[-1]) == 0:
                    return True

            else:
                return False

    def clear(self):
        """
        clear the http streams
        :return: None
        """
        self.http_stream = b""
        self.content_length = None
        self.header_pos = 0
        self.add_count = 0
        self.connection = None
        self.host = None
        self.header_popped = False

    def clear_stream(self):
        """
        clear http stream
        :return: None
        """
        self.http_stream = b""

    def _parse_http_stream(self) -> None:
        """
        parse the http header key: Content-Length, Host, Connection, Transfer-Encoding
        :return: None
        """
        header: bytes = b""
        res_list = self.http_stream.split(b"\r\n\r\n")
        if len(res_list) > 1:  # find header
            header = res_list[0]

        else:
            return

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
                self.host = (host_name, host_port)
            else:
                self.host = None

            by_content_length = header.split(b"Content-Length:")
            by_transfer_encode = header.split(b"Transfer-Encoding:")

            if len(by_content_length) > 1 and len(by_transfer_encode) == 1:
                # has Content-Length
                content_length = int(by_content_length[1].split(b"\r\n")[0])
                self.content_length = content_length

            elif len(by_content_length) == 1 and len(by_transfer_encode) > 1:
                # has Transfer-Encoding
                self.content_length = -1

            elif len(by_content_length) == 1 and len(by_transfer_encode) == 1:
                # no Content Length
                self.content_length = 0

            by_connect = header.split(b"Connection:")
            if len(by_connect) > 1:
                self.connection = by_connect[1].split(b"\r\n")[0].strip()
        else:
            return


class HttpRequestStream(HttpParser):
    def __init__(self):
        super(HttpRequestStream, self).__init__()


class HttpRespondStream(HttpParser):
    def __init__(self):
        super(HttpRespondStream, self).__init__()
