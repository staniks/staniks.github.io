import os
from http.server import HTTPServer, SimpleHTTPRequestHandler


class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path.endswith('/') or '.' not in os.path.splitext(self.path)[1]:
            potential_html_path = self.path.rstrip('/') + '.html'
            if os.path.isfile(potential_html_path[1:]):
                self.path = potential_html_path

        super().do_GET()


if __name__ == '__main__':
    server_address = ('', 80)
    httpd = HTTPServer(server_address, CustomHTTPRequestHandler)
    httpd.serve_forever()