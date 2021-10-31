import http.server
import socketserver
import requests
import re
import json
import base64
import threading

from http import HTTPStatus
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.parse import parse_qs

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class Forvo():
    """
    Forvo web-scraper utility class that matches YomiChan's expected output for a custom audio source
    """
    _SERVER_HOST = "https://forvo.com"
    _AUDIO_HTTP_HOST = "https://audio00.forvo.com"
    def __init__(self, language):
        self.language = language
        self._set_session()
    
    def _set_session(self):
        """
        Sets the session with basic backoff retries.
        Put in a separate function so we can try resetting the session if something goes wrong
        """
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        # Use my personal user agent to try to avoid scraping detection
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 Safari/537.36 Edg/89.0.774.45",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    def _get(self, path):
        """
        Makes a GET request assuming base url. Creates a new session if something goes wrong
        """
        url = self._SERVER_HOST + path
        try:
            return self.session.get(url, timeout=10).text

        except Exception:
            self._set_session()
            return self.session.get(url, timeout=10).text
    
    def word(self, w):
        """
        Scrape forvo's word page for audio sources
        """
        w = w.strip()
        if len(w) == 0:
            return []
        path = f"/word/{w}/"
        html = self._get(path)
        soup = BeautifulSoup(html, features="html.parser")

        # Forvo's word page returns multiple result sets grouped by langauge like:
        # <div id="language-container-ja">
        #   <article>
        #       <ul class="show-all-pronunciations">
        #           <li>
        #              <span class="play" onclick"(some javascript to play the word audio)"></span>
        #                "Pronunciation by <span><a href="/username/link">skent</a></span>" 
        #              <div class="more">...</div>
        #           </li>
        #       </ul>
        #       ...
        #   </article>
        #   <article id="extra-word-info-76">...</article>
        # </ul>
        # We also filter out ads
        results = soup.select('#language-container-ja>article>ul.show-all-pronunciations>li:not(.li-ad)')
        audio_sources = []
        for i in results:
            url = self._extract_url(i.span)

            # Capture the username of the user
            # Some users have deleted accounts which is why can't just parse it from the <a> tag
            username = re.search(r"Pronunciation by([^(]+)\(",i.get_text(strip=True)).group(1).strip()
            audio_sources.append({"name":f"Forvo ({username})","url":url})
        return audio_sources

    @classmethod
    def _extract_url(cls, span):
        play = span['onclick']
        # We are interested in Forvo's javascript Play function which takes in some parameters to play the audio
        # Example: Play(786514,'OTA3Mjk2Ny83Ni85MDcyOTY3Xzc2XzExNDk0NzNfMS5tcDM=',...);return false;
        # Match anything that isn't commas, parentheses or quotes to capture the function arguments
        # Regex will match something like ["Play","786514","OTA3Mjk2Ny83Ni85MDcyOTY3Xzc2XzExNDk0NzNfMS5tcDM=", ...]
        play_args = re.findall(r"([^',\(\)]+)", play)

        # It seems that forvo has two locations for mp3, /audios/mp3 and just /mp3. I don't know what the difference
        # is so I'm just going to use the /mp3 version, which is the second argument in Play() base64 encoded
        file = base64.b64decode(play_args[2]).decode("utf-8")
        url = f"{cls._AUDIO_HTTP_HOST}/mp3/{file}"
        return url
    
    def search(self, s):
        """
        Scrape Forvo's search page for audio sources. Note that the search page omits the username
        """
        s = s.strip()
        if len(s) == 0:
            return []
        path = f"/search/{s}/{self.language}/"
        html = self._get(path)
        soup = BeautifulSoup(html, features="html.parser")

        # Forvo's search page returns two result sets like:
        # <ul class="word-play-list-icon-size-l">
        #   <li><span class="play" onclick"(some javascript to play the word audio)"></li>
        # </ul>
        results = soup.select('ul.word-play-list-icon-size-l>li>span.play')
        audio_sources = []
        for i in results:
            url = self._extract_url(i)
            audio_sources.append({"name":"Forvo Search","url":url})
        return audio_sources


class ForvoHandler(http.server.SimpleHTTPRequestHandler):
    forvo = Forvo('ja')

    # By default, SimpleHTTPRequestHandler logs to stderr
    # This would cause Anki to show an error, even on successful requests
    # log_error is still a useful function though, so replace it with the inherited log_message
    # Make log_message do nothing
    def log_error(self, *args, **kwargs):
        super().log_message(*args, **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(HTTPStatus.OK) 
        self.send_header("Content-type", "application/json")
        self.end_headers()

        # Extract 'expression' and 'reading' query parameters
        query_components = parse_qs(urlparse(self.path).query)
        expression = query_components["expression"][0] if "expression" in query_components else ""
        reading = query_components["reading"][0] if "reading" in query_components else ""
        debug = query_components["debug"][0] if "debug" in query_components else False

        if debug:
            debug_resp = {
                "debug":True
            }
            debug_resp['reading'] = reading
            debug_resp['expression'] = expression
            debug_resp['word.expression'] = self.forvo.word(expression)
            debug_resp['word.reading'] = self.forvo.word(reading)
            debug_resp['search.expression'] = self.forvo.search(expression)
            debug_resp['search.reading'] = self.forvo.search(reading)
            self.wfile.write(bytes(json.dumps(debug_resp), "utf8"))
            return

        audio_sources = []
        
        # Try looking for word sources for 'expression' first
        audio_sources = self.forvo.word(expression)

        # Try looking for word sources for 'reading'
        if len(audio_sources) == 0:
            audio_sources += self.forvo.word(reading)
        
        # Finally use forvo search to look for similar words
        if len(audio_sources) == 0:
            audio_sources += self.forvo.search(expression)

        if len(audio_sources) == 0:
            audio_sources += self.forvo.search(reading)

        # Build JSON that yomichan requires
        # Ref: https://github.com/FooSoft/yomichan/blob/master/ext/data/schemas/custom-audio-list-schema.json
        resp = {
            "type": "audioSourceList",
            "audioSources": audio_sources
        }
        # Writing the JSON contents with UTF-8
        self.wfile.write(bytes(json.dumps(resp), "utf8"))

        return

if __name__ == "__main__":
    # If we're not in Anki, run the server directly and blocking for easier debugging
    print("Running in debug mode...")
    httpd = socketserver.TCPServer(('localhost', 8770), ForvoHandler)
    httpd.serve_forever()
else:
    # Else, run it in a separate thread so it doesn't block
    httpd = http.server.ThreadingHTTPServer(('localhost', 8770), ForvoHandler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
