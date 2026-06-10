"""Generate a minimal test EPUB for KDP Translator."""

from ebooklib import epub

book = epub.EpubBook()
book.set_identifier('test-kdp-12345')
book.set_title('Die Schatten des Nordens')
book.set_language('de')
book.add_author('Max Mustermann')

css = epub.EpubItem(
    uid='style', file_name='style/default.css',
    media_type='text/css',
    content=b'body { font-family: serif; } h1 { color: #333; } p { text-indent: 1em; }'
)
book.add_item(css)

ch1_content = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Kapitel 1</title><link rel="stylesheet" type="text/css" href="style/default.css"/></head>
<body>
<h1>Kapitel 1: Die Reise beginnt</h1>
<p>Es war eine <strong>dunkle</strong> und sturmische Nacht, als der junge Bjarne die alte Stadt verliess.</p>
<p>Der Wind peitschte ihm ins Gesicht, wahrend er durch die engen Gassen eilte.</p>
<p>Niemand wusste, dass er den <em>Schluessel der Ahnen</em> bei sich trug.</p>
</body>
</html>"""

ch2_content = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Kapitel 2</title><link rel="stylesheet" type="text/css" href="style/default.css"/></head>
<body>
<h1>Kapitel 2: Der Wald der Schatten</h1>
<p>Der Wald vor ihr war duester und undurchdringlich. Hohe Baeume ragten in den grauen Himmel.</p>
<p>"Wir muessen hindurch", sagte sie mit fester Stimme.</p>
<p>Ein Zweig knackte hinter ihnen.</p>
</body>
</html>"""

ch1 = epub.EpubHtml(title='Kapitel 1', file_name='chap_01.xhtml', lang='de')
ch1.content = ch1_content.encode('utf-8')

ch2 = epub.EpubHtml(title='Kapitel 2', file_name='chap_02.xhtml', lang='de')
ch2.content = ch2_content.encode('utf-8')

book.add_item(ch1)
book.add_item(ch2)
book.toc = [
    epub.Link('chap_01.xhtml', 'Kapitel 1', 'ch1'),
    epub.Link('chap_02.xhtml', 'Kapitel 2', 'ch2'),
]
book.spine = ['nav', ch1, ch2]
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

path = 'input/test_book.epub'
epub.write_epub(path, book, {})
print(f'Test EPUB created: {path}')
import os
print(f'Size: {os.path.getsize(path)} bytes')
