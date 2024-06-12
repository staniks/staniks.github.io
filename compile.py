import glob
import os
from markdown import markdown
from jinja2 import Environment, BaseLoader
import json


DEFAULT_METADATA_TITLE = "Marko Stanić"
DEFAULT_METADATA_DESCRIPTION = "Personal website and blog."
DEFAULT_METADATA_IMAGE = "/img/og-logo.jpg"


if __name__ == '__main__':

    script_path = os.path.dirname(os.path.abspath(__file__))
    dist_path = os.path.join(script_path, 'dist')

    template_path = os.path.join(script_path, 'src', 'html')

    site_header = open(os.path.join(template_path, 'header.html'), 'r', encoding='utf-8').read()
    site_footer = open(os.path.join(template_path, 'footer.html'), 'r', encoding='utf-8').read()

    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    for page_config in config['pages']:

        metadata_title = page_config.get('metadata_title', DEFAULT_METADATA_TITLE)
        metadata_description = page_config.get('metadata_description', DEFAULT_METADATA_DESCRIPTION)
        metadata_image = page_config.get('metadata_image', DEFAULT_METADATA_IMAGE)

        src_path = os.path.join(script_path, page_config['src'])
        dst_path = os.path.join(dist_path, page_config['dst'])

        page_body = markdown(open(src_path, 'r', encoding='utf-8').read())

        page_template = site_header + page_body + site_footer

        # TODO: Just use this exact tag in markdown.
        page_template = page_template.replace("<pre><code>", "<pre><code class=\"cpp\">")

        jinja_template = Environment(loader=BaseLoader).from_string(page_template)
        page = jinja_template.render(metadata_title=metadata_title, metadata_description=metadata_description, metadata_image=metadata_image)

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as output_file:
            output_file.write(page)
