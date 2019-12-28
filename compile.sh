#!/bin/bash
for filename in markdown/*.md; do
    stripped_name="$(basename -- $filename)"
    stripped_name="${stripped_name%%.*}"
    cat html/header.html > "$stripped_name".html
    Markdown.pl "$filename" >> "$stripped_name".html
    cat html/footer.html >> "$stripped_name".html
done

#!/bin/bash
for filename in subpages/*.html; do
    stripped_name="$(basename -- $filename)"
    stripped_name="${stripped_name%%.*}"
    cat html/header.html > "$stripped_name".html
    cat "$filename" >> "$stripped_name".html
    cat html/footer.html >> "$stripped_name".html
done