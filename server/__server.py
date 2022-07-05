from queue import Queue
import socket
import socketserver
import errno
from .__http_parser import HttpParser
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple
import selectors

from colorprt.default import success
from utils import parse_request, is_http_end
from utils.exceptions import *
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
        while True:
            try:
                client_sock, addr = self.proxy_sock.accept()
            except OSError as oe:
                continue
            self.connections_queue.put(addr)
            self.proxy_thread_pool.submit(ProxyRequest(client_sock).run)


class ProxyRequest(threading.Thread):
    def __init__(self, client_sock: socket.socket) -> None:
        super().__init__()
        self.client_sock = client_sock
        self.client_sock.setblocking(False)
        self.server_sock = None

        self.request_stream = HttpParser()
        # self.request_send_pos = 0
        # self.request_header_pos = 0
        # self.request_body_length = None

        self.respond_stream = HttpParser()
        # self.respond_send_pos = 0
        # self.respond_header_pos = 0
        # self.respond_body_length = None

        self.selector = selectors.DefaultSelector()

        self.sub_server_thread = threading.Thread(target=self.server_thread)

    def run(self) -> None:
        # while True:
        #     events = self.selector.select()
        #     for key, _ in events:
        #         key.data()
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
                self.try_connect()
            print(recv_res)

    def send_to_server(self):
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
            self.sub_server_thread.start()

# global_selector = selectors.DefaultSelector()
# global_thread_lock = threading.Lock()


# class http_info:
#     CHUNKED_DATA = 1
#     NORMAL_DATA = 0
#     content_length = -1
#     header_type = NORMAL_DATA


# class event_info:
#     request_data = b""
#     respond_data = b""
#     pos = 0

#     request_host = None
#     header_info = None
#     server_sock = None

#     client_sock = None

#     def __init__(self, client_sock: socket.socket) -> None:
#         self.client_sock = client_sock
#         self.connect_thread = threading.Thread(target=self.try_connect)
#         self.transfer_thread = threading.Thread(target=self.transfer_data)
#         self.connect_thread.start()

#     def add_req_data(self, data: bytes):
#         if len(data) > 0:
#             self.request_data += data
#             if self.request_host is not None:
#                 print(f"send to {self.request_host[0]}:{self.request_host[1]}:\n{data}")

#             else:
#                 print(f"recv: {data}")

#             if self.request_host is None:
#                 self.request_host = parse_request(self.request_data)

#     def transfer_data(self):
#         while True:
#             if self.request_host is not None and self.respond_data is not None and self.server_sock is not None:
#                 global_thread_lock.acquire()
#                 try:
#                     self.server_sock.sendall(self.request_data)
#                 except OSError as e:
#                     self.server_sock.close()
#                     self.client_sock.close()
#                     global_selector.unregister(self.client_sock)
#                     break
#                 self.request_data = b""

#                 recv_data = self.server_sock.recv(RECV_BUFFER_LEN)
#                 if len(recv_data) == 0:
#                     self.server_sock.close()
#                     self.client_sock.close()
#                     global_selector.unregister(self.client_sock)
#                     break
#                 try:
#                     self.client_sock.sendall(recv_data)
#                 except OSError as e:
#                     self.server_sock.close()
#                     self.client_sock.close()
#                     global_selector.unregister(self.client_sock)

#                     break
#         global_thread_lock.release()
#         return

#     def try_connect(self):
#         while True:
#             if self.request_host is not None:
#                 addrinfos = socket.getaddrinfo(
#                     self.request_host[0], port=self.request_host[1], type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
#                 for addrinfo in addrinfos:
#                     try:
#                         self.server_sock = socket.socket(*addrinfo[0:3])
#                     except OSError as oe:
#                         self.server_sock = None
#                         continue

#                     try:
#                         self.server_sock.connect(addrinfo[-1])
#                     except OSError as oe:
#                         self.server_sock.close()
#                         self.server_sock = None
#                         continue

#                     break
#                 if self.server_sock is None:
#                     return

#                 print(f"connected => {self.request_host[0]}:{self.request_host[1]}")
#                 self.transfer_thread.start()
#                 break


# class ProxyServer(object):
#     def __init__(self, port=8080) -> None:
#         self.sk = None
#         self.port = port
#         pass

#     def socket_init(self):
#         sk = None
#         try:
#             sk = socket.socket()
#         except OSError as msg:
#             sk = None
#             sys.exit(-1)
#         try:
#             sk.bind(("", self.port))
#             sk.listen()
#         except OSError as msg:
#             sk.close()
#             sk = None

#         if sk is None:
#             print('could not open socket')
#             sys.exit(1)

#         self.sk = sk
#         self.sk.setblocking(False)
#         success("server started on port: %d.." % self.port)
#         global_selector.register(
#             self.sk,
#             events=selectors.EVENT_READ,
#             data=self.accept_client_request
#         )

#     def start(self):
#         self.socket_init()
#         self.loop()

#     def loop(self):
#         while True:
#             global_thread_lock.acquire()
#             events = global_selector.select()
#             for key, mask in events:
#                 if key.fileobj == self.sk:
#                     call = key.data
#                     call(key.fileobj, mask)

#                 else:
#                     call, client_event_data = key.data
#                     call(key.fileobj, client_event_data)

#             global_thread_lock.release()

#     def handle_client_recv(self, conn: socket.socket, client_event_data: event_info):
#         req_data = conn.recv(RECV_BUFFER_LEN)
#         if len(req_data) == 0:
#             socket.close(conn)
#             return
#         client_event_data.add_req_data(req_data)

#     def accept_client_request(self, sock, mask):
#         client_id, addr = sock.accept()
#         print(f"hear from {addr[0]}:{addr[1]}")
#         client_id.setblocking(False)
#         try:
#             client_event_data = event_info(client_id)

#             global_selector.register(client_id, selectors.EVENT_READ, (self.handle_client_recv, client_event_data))
#         except ValueError as ve:
#             print(ve)
#             socket.close(client_id)
