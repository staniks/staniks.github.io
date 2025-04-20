import glob
import os
from markdown import markdown
from jinja2 import Environment, BaseLoader
import json
import shutil

DEFAULT_METADATA_TITLE = "Marko Stanić"
DEFAULT_METADATA_DESCRIPTION = "Personal website and blog."
DEFAULT_METADATA_IMAGE = "/img/og-logo.jpg"


if __name__ == '__main__':

    script_path = os.path.dirname(os.path.abspath(__file__))
    dist_path = os.path.join(script_path, 'dist')

    src_path = os.path.join(script_path, 'src')
    template_path = os.path.join(src_path, 'html')
    css_path = os.path.join(src_path, 'css')

    site_template = open(os.path.join(template_path, 'layout.html'), 'r', encoding='utf-8').read()

    os.makedirs(os.path.join(dist_path, 'css'), exist_ok=True)
    shutil.copy2(os.path.join(css_path, 'styles.css'), os.path.join(os.path.join(dist_path, 'css'), 'styles.css'))

    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)

    for page_config in config['pages']:

        metadata_title = page_config.get('metadata_title', DEFAULT_METADATA_TITLE)
        metadata_description = page_config.get('metadata_description', DEFAULT_METADATA_DESCRIPTION)
        metadata_image = page_config.get('metadata_image', DEFAULT_METADATA_IMAGE)

        src_path = os.path.join(script_path, page_config['src'])
        dst_path = os.path.join(dist_path, page_config['dst'])

        page_body = markdown(open(src_path, 'r', encoding='utf-8').read())

        # TODO: Just use this exact tag in markdown.
        page_body = page_body.replace("<pre><code>", "<pre><code class=\"cpp\">")

        jinja_template = Environment(loader=BaseLoader).from_string(site_template)
        page = jinja_template.render(metadata_title=metadata_title, metadata_description=metadata_description, metadata_image=metadata_image, content=page_body)

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as output_file:
            output_file.write(page)
