#!/usr/bin/env python
import socket
from urllib import request, parse, error
import re
import logging
from html import unescape as unescape_html
from spiders.VideoSpiderV1.fs import legitimize
import uuid,os
from spiders.VideoSpiderV1.ProcessBar import SimpleProgressBar,PiecesProgressBar


fake_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'UTF-8,*;q=0.5',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:51.0) Gecko/20100101 Firefox/51.0'
}


def parse_host(host):
    """Parses host name and port number from a string.
    """
    if re.match(r'^(\d+)$', host) is not None:
        return ("0.0.0.0", int(host))
    if re.match(r'^(\w+)://', host) is None:
        host = "//" + host
    o = parse.urlparse(host)
    hostname = o.hostname or "0.0.0.0"
    port = o.port or 0
    return (hostname, port)

def set_proxy(proxy):
    proxy_handler = request.ProxyHandler({
        'http': '%s:%s' % proxy,
        'https': '%s:%s' % proxy,
    })
    opener = request.build_opener(proxy_handler)
    request.install_opener(opener)

def unset_proxy():
    proxy_handler = request.ProxyHandler({})
    opener = request.build_opener(proxy_handler)
    request.install_opener(opener)


def match1(text, *patterns):
    """Scans through a string for substrings matched some patterns (first-subgroups only).

    Args:
        text: A string to be scanned.
        patterns: Arbitrary number of regex patterns.

    Returns:
        When only one pattern is given, returns a string (None if no match found).
        When more than one pattern are given, returns a list of strings ([] if no match found).
    """

    if len(patterns) == 1:
        pattern = patterns[0]
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        else:
            return None
    else:
        ret = []
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                ret.append(match.group(1))
        return ret


def parse_query_param(url, param):
    """Parses the query string of a URL and returns the value of a parameter.

    Args:
        url: A URL.
        param: A string representing the name of the parameter.

    Returns:
        The value of the parameter.
    """
    try:
        return parse.parse_qs(parse.urlparse(url).query)[param][0]
    except:
        return None


def mime_to_container(mime):
    mapping = {
        'video/3gpp': '3gp',
        'video/mp4': 'mp4',
        'video/webm': 'webm',
        'video/x-flv': 'flv',
    }
    if mime in mapping:
        return mapping[mime]
    else:
        return mime.split('/')[1]


def urlopen_with_retry(*args):
    for i in range(2):
        try:
            return request.urlopen(*args)
        except socket.timeout:
            logging.debug('request attempt %s timeout' % str(i + 1))
        except error.HTTPError as http_error:
            logging.debug('HTTP Error with code{}'.format(http_error.code))

def get_content(url, headers={}, decoded=True):
    """Gets the content of a URL via sending a HTTP GET request.

    Args:
        url: A URL.
        headers: Request headers used by the client.
        decoded: Whether decode the response body using UTF-8 or the charset specified in Content-Type.

    Returns:
        The content as a string.
    """

    logging.debug('get_content: %s' % url)

    req = request.Request(url, headers=headers)

    '''
    if cookies:
        cookies.add_cookie_header(req)
        req.headers.update(req.unredirected_hdrs)
    '''

    response = urlopen_with_retry(req)
    data = response.read()

    # Handle HTTP compression for gzip and deflate (zlib)
    content_encoding = response.getheader('Content-Encoding')
    if content_encoding == 'gzip':
        data = ungzip(data)
    elif content_encoding == 'deflate':
        data = undeflate(data)

    # Decode the response body
    if decoded:
        charset = match1(response.getheader('Content-Type'), r'charset=([\w-]+)')
        if charset is not None:
            data = data.decode(charset)
        else:
            data = data.decode('utf-8', 'ignore')

    return data

def url_size(url, faker = False, headers = {}):
    if faker:
        response = urlopen_with_retry(request.Request(url, headers=fake_headers))
    elif headers:
        response = urlopen_with_retry(request.Request(url, headers=headers))
    else:
        response = urlopen_with_retry(url)

    size = response.headers['content-length']
    return int(size) if size!=None else float('inf')

def urls_size(urls, faker = False, headers = {}):
    return sum([url_size(url, faker=faker, headers=headers) for url in urls])

def url_save(url, filepath, bar, refer=None, is_part=False, faker=False, headers=None, timeout=None):
    tmp_headers = headers.copy() if headers is not None else {}
# When a referer specified with param refer, the key must be 'Referer' for the hack here
    if refer is not None:
        tmp_headers['Referer'] = refer
    file_size = url_size(url, faker=faker, headers=tmp_headers)

    if os.path.exists(filepath):
        if file_size == os.path.getsize(filepath):
            if not is_part:
                if bar:
                    bar.done()
                print('Skipping %s: file already exists' % tr(os.path.basename(filepath)))
            else:
                if bar:
                    bar.update_received(file_size)
            return
        else:
            if not is_part:
                if bar:
                    bar.done()
                print('Overwriting %s' % tr(os.path.basename(filepath)), '...')
    elif not os.path.exists(os.path.dirname(filepath)):
        os.mkdir(os.path.dirname(filepath))

    temp_filepath = filepath + '.download' if file_size!=float('inf') else filepath
    received = 0
    open_mode = 'wb'

    if received < file_size:
        if faker:
            tmp_headers = fake_headers

        if received:
            tmp_headers['Range'] = 'bytes=' + str(received) + '-'
        if refer:
            tmp_headers['Referer'] = refer

        if timeout:
            response = urlopen_with_retry(request.Request(url, headers=tmp_headers), timeout=timeout)
        else:
            response = urlopen_with_retry(request.Request(url, headers=tmp_headers))
        try:
            range_start = int(response.headers['content-range'][6:].split('/')[0].split('-')[0])
            end_length = int(response.headers['content-range'][6:].split('/')[1])
            range_length = end_length - range_start
        except:
            content_length = response.headers['content-length']
            range_length = int(content_length) if content_length!=None else float('inf')

        if file_size != received + range_length:
            received = 0
            if bar:
                bar.received = 0
            open_mode = 'wb'

        with open(temp_filepath, open_mode) as output:
            while True:
                buffer = None
                try:
                    buffer = response.read(1024 * 256)
                except socket.timeout:
                    pass
                if not buffer:
                    if received == file_size: # Download finished
                        break
                    # Unexpected termination. Retry request
                    tmp_headers['Range'] = 'bytes=' + str(received) + '-'
                    response = urlopen_with_retry(request.Request(url, headers=tmp_headers))
                    continue
                output.write(buffer)
                received += len(buffer)
                if bar:
                    bar.update_received(len(buffer))

    assert received == os.path.getsize(temp_filepath), '%s == %s == %s' % (received, os.path.getsize(temp_filepath), temp_filepath)

    if os.access(filepath, os.W_OK):
        os.remove(filepath) # on Windows rename could fail if destination filepath exists
    os.rename(temp_filepath, filepath)



def get_filename(htmlstring):
    return legitimize(unescape_html(htmlstring))

def get_output_filename(urls, title, ext, output_dir, merge):

    output_filename = str(uuid.uuid1())
    if ext:
        output_filename = output_filename + "." + ext
    return output_filename

def download_urls(urls, title, ext, total_size, output_dir='.', refer=None, merge=True, faker=False, headers = {}):
    assert urls
    if not total_size:
        try:
            total_size = urls_size(urls, faker=faker, headers=headers)
        except:
            import traceback
            traceback.print_exc(file=sys.stdout)
            pass

    title = str(get_filename(title))
    output_filename = get_output_filename(urls, title, ext, output_dir, merge)
    output_filepath = os.path.join(output_dir, output_filename)

    if total_size:
        if  os.path.exists(output_filepath) and os.path.getsize(output_filepath) >= total_size * 0.9:
            print('Skipping %s: file already exists' % output_filepath)
            print()
            return
        bar = SimpleProgressBar(total_size, len(urls))
    else:
        bar = PiecesProgressBar(total_size, len(urls))

    if len(urls) == 1:
        url = urls[0]
        print('Downloading %s ...' % str(output_filename))
        bar.update()
        url_save(url, output_filepath, bar, refer = refer, faker = faker, headers = headers)
        bar.done()
    else:
        parts = []
        print('Downloading %s.%s ...' % (str(title), ext))
        bar.update()
        for i, url in enumerate(urls):
            filename = '%s[%02d].%s' % (title, i, ext)
            filepath = os.path.join(output_dir, filename)
            parts.append(filepath)
            #print 'Downloading %s [%s/%s]...' % (tr(filename), i + 1, len(urls))
            bar.update_piece(i + 1)
            url_save(url, filepath, bar, refer = refer, is_part = True, faker = faker, headers = headers)
        bar.done()

    print()
        