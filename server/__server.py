from queue import Queue
import socket
import errno
from .__http_parser import HttpRequestStream, HttpRespondStream, HttpParser
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import selectors

from colorprt.default import success
from colorprt.default import warn

RECV_BUFFER_LEN = 8120


class ProxyServer:
    def __init__(self, port=8080):
        self.proxy_sock = None
        self.port = port

        self.proxy_thread_pool = ThreadPoolExecutor()
        self.proxy_log_thread_pool = ThreadPoolExecutor()

        self.connections_queue = Queue(-1)
        self.request_logs = Queue(100)
        self.__sock_init()

    def __sock_init(self):
        """
        init socket server
        :return:
        """
        try:
            self.proxy_sock = socket.socket()
        except OSError as msg:
            self.proxy_sock = None
            sys.exit(-1)
        try:
            self.proxy_sock.bind(("", self.port))
            self.proxy_sock.listen()
        except OSError as msg:
            self.proxy_sock.close()
            self.proxy_sock = None

        if self.proxy_sock is None:
            print('could not open socket')
            sys.exit(1)

        self.proxy_log_thread_pool.submit(self.log_connections_action)
        success("server started on port: %d.." % self.port)

    def start(self):
        try:
            self.__loop()

        except KeyboardInterrupt:
            self.proxy_log_thread_pool.shutdown()
            self.proxy_thread_pool.shutdown()

    def log_connections_action(self):
        while True:
            if not self.connections_queue.empty():
                host_name, port = self.connections_queue.get()
                print("client: {}:{}".format(host_name, port))
                self.connections_queue.task_done()

    def __loop(self):
        """
        start a client thread
        :return: None
        """
        while True:
            try:
                client_sock, addr = self.proxy_sock.accept()
            except OSError as oe:
                continue
            self.connections_queue.put(addr)
            self.proxy_thread_pool.submit(ProxyRequest(client_sock).run)


class ProxyRequest(object):
    def __init__(self, client_sock: socket.socket) -> None:
        super().__init__()
        self.client_sock = client_sock
        self.client_sock.setblocking(False)
        self.server_sock = None

        self.connected = False

        self.request_stream = HttpRequestStream()

        self.respond_stream = HttpRespondStream()

        self.selector = selectors.DefaultSelector()

        self.sub_server_thread = threading.Thread(target=self.server_thread)

    def run(self) -> None:
        """
        start thread and recv from client and connect to server
        :return:
        """
        while True:
            try:
                recv_res = self.client_sock.recv(RECV_BUFFER_LEN)
            except OSError as e:
                if e.errno == errno.EWOULDBLOCK:
                    continue
                else:
                    self.client_sock.close()
                    self.server_sock.close()
                    return
            try:
                self.request_stream.add_bytes(recv_res)
            except HttpParser.HeaderError:
                continue
            print(recv_res)
            if self.request_stream.header_pos > 0 and self.request_stream.host is not None and self.server_sock is None:
                # if it's the http header comes the first time, connect it
                self.try_connect()

    def send_to_server(self):
        """
        send stream to http server
        :return:
        """
        if self.request_stream.header_pos > 0:
            self.server_sock.sendall(self.request_stream.get_header())

        elif self.request_stream.header_pos == -1:
            self.server_sock.sendall(self.request_stream.http_stream)
            self.request_stream.clear_stream()

        if self.request_stream.check_end():
            self.request_stream.clear()

    def get_from_server(self):
        add_res = False
        if self.server_sock is not None:
            if self.request_stream.http_stream != b"":
                self.send_to_server()
            try:
                data = self.server_sock.recv(RECV_BUFFER_LEN)
            except OSError as os:
                warn(os)
                return True
            add_res = self.respond_stream.add_bytes(data)

            self.client_sock.sendall(self.respond_stream.http_stream)

            self.respond_stream.clear_stream()

        if add_res:
            return True
        return False

    def server_thread(self):
        while True:
            if self.get_from_server():
                self.client_sock.close()
                self.server_sock.close()
                return

    def try_connect(self):
        """
        connect the http server
        :return:
        """
        if self.request_stream.host is not None:
            addrinfos = socket.getaddrinfo(
                self.request_stream.host[0], port=self.request_stream.host[1], type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP)
            for addrinfo in addrinfos:
                try:
                    self.server_sock = socket.socket(*addrinfo[0:3])
                except OSError as oe:
                    self.server_sock = None
                    continue
                try:
                    self.server_sock.connect(addrinfo[-1])
                except OSError as oe:
                    self.server_sock.close()
                    self.server_sock = None
                    continue

            if self.server_sock is None:
                return
            print(f"connected => {self.request_stream.host[0]}:{self.request_stream.host[1]}")
            self.connected = True
            self.sub_server_thread.start()
