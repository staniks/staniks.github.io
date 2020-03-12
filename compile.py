import binascii
import glob
import os
import subprocess
import sys
import zlib

header = open("html/header.html", "r").read()
footer = open("html/footer.html", "r").read()

src_dir = "markdown"

markdown_extension = "md"
html_extension = "html"
metadata_extension = "meta"

DEFAULT_METADATA_TITLE = "staniks.github.io"
DEFAULT_METADATA_DESCRIPTION = "Personal website and blog."
DEFAULT_METADATA_IMAGE = "img/worship-blog.png"

page_list = []
metadata_list = []

for filename in glob.iglob(f"{src_dir}/**", recursive=True):
    if os.path.isdir(filename):
        continue
    file_extension = os.path.splitext(filename)[1][1:]
    if file_extension == markdown_extension or file_extension == html_extension:
        page_list.append(filename)
    elif file_extension == metadata_extension:
        metadata_list.append(filename)

for filename in page_list:
    filename_without_extension = os.path.splitext(filename)[0]
    metadata_filename = filename_without_extension + "." + metadata_extension

    metadata_title = DEFAULT_METADATA_TITLE
    metadata_description = DEFAULT_METADATA_DESCRIPTION
    metadata_image = DEFAULT_METADATA_IMAGE

    if metadata_filename in metadata_list:
        metadata_file = open(metadata_filename, "r")

        metadata_title = metadata_file.readline().strip()
        metadata_description = metadata_file.readline().strip()
        metadata_image = metadata_file.readline().strip()

    modified_header = header.replace("{{{{METADATA_TITLE}}}}", metadata_title)
    modified_header = modified_header.replace("{{{{METADATA_DESCRIPTION}}}}", metadata_description)
    modified_header = modified_header.replace("{{{{METADATA_IMAGE}}}}", metadata_image)

    extension = os.path.splitext(filename)[1][1:]
    if extension == markdown_extension:
        content = subprocess.Popen(["perl", "C:/Markdown/Markdown.pl", filename], stdout=subprocess.PIPE).stdout.read().decode('utf-8')
        content = content.replace('\r\n', '\n')
    elif extension == html_extension:
        content = open(filename, "r").read()

    finished_page = modified_header + content + footer
    normalized_filename = filename_without_extension[len(src_dir) + 1:]

    output_filename = normalized_filename + ".html"
    output_directory = os.path.dirname(output_filename)
    if output_directory:
        if not os.path.exists(output_directory):
            try:
                os.makedirs(output_directory)
            except OSError as exc:
                raise

    open(output_filename, "w+").write(finished_page)
    continue