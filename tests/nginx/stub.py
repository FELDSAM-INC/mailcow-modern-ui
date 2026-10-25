"""Disposable HTTP/FastCGI echo services; no mail, database, or real credentials."""

import json
import socketserver
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class HTTP(BaseHTTPRequestHandler):
    def handle_request(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        data = {
            "handler": sys.argv[1],
            "uri": self.path,
            "method": self.command,
            "body": body.decode(),
            "host": self.headers.get("Host"),
        }
        if self.path == "/ng/deployment.json":
            data = json.loads(Path("/fixtures/deployment.json").read_text())
        payload = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    do_GET = do_POST = do_HEAD = do_OPTIONS = do_PROPFIND = handle_request

    def log_message(self, *_args):
        pass


def decode_parameters(data):
    values = {}
    position = 0
    while position < len(data):
        lengths = []
        for _ in range(2):
            size = data[position]
            position += 1
            if size & 128:
                size = struct.unpack("!I", data[position - 1 : position + 3])[0] & 0x7FFFFFFF
                position += 3
            lengths.append(size)
        key_length, value_length = lengths
        key = data[position : position + key_length].decode()
        position += key_length
        values[key] = data[position : position + value_length].decode()
        position += value_length
    return values


class FastCGI(socketserver.StreamRequestHandler):
    def handle(self):
        parameters, body = b"", b""
        while True:
            header = self.rfile.read(8)
            if len(header) != 8:
                return
            _version, kind, request_id, length, padding, _reserved = struct.unpack(
                "!BBHHBB", header
            )
            content = self.rfile.read(length)
            self.rfile.read(padding)
            if kind == 4:
                parameters += content
            elif kind == 5:
                body += content
                if length == 0:
                    break
        params = decode_parameters(parameters)
        data = {
            "handler": "php" if self.server.server_address[1] != 9000 else "api-v2",
            "script": params.get("SCRIPT_FILENAME"),
            "uri": params.get("REQUEST_URI"),
            "query": params.get("QUERY_STRING"),
            "method": params.get("REQUEST_METHOD"),
            "internal": params.get("SOGO_AUTH_INTERNAL"),
            "body": body.decode(),
        }
        payload = (
            b"Status: 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(data).encode()
        )
        for kind, data in [(6, payload), (6, b""), (3, b"\0" * 8)]:
            self.wfile.write(struct.pack("!BBHHBB", 1, kind, request_id, len(data), 0, 0) + data)


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    servers = [
        ThreadingHTTPServer(("0.0.0.0", port), HTTP)
        for port in ([8080] if sys.argv[1] == "ui" else [20000, 11334])
    ]
    if sys.argv[1] != "ui":
        servers += [TCPServer(("0.0.0.0", port), FastCGI) for port in [9000, 9001, 9002]]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Event().wait()
