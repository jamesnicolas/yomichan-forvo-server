import http.server
import socketserver
import requests
import re
import json
import base64
from http import HTTPStatus
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.parse import parse_qs

class Forvo():
    """
    Forvo web-scraper utility class that matches YomiChan's expected output for a custom audio source
    """
    _SERVER_HOST = "https://forvo.com"
    _AUDIO_HTTP_HOST = "https://audio00.forvo.com"
    def __init__(self, language):
        self.language = language
        self.session = requests.Session()
        # Using my personal User-Agent
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 Safari/537.36 Edg/89.0.774.45",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
    def _get(self, path):
        url = self._SERVER_HOST + path
        return self.session.get(url).text
    
    def word(self, w):
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


class SearchHandler(http.server.SimpleHTTPRequestHandler):
    forvo = Forvo('ja')

    def do_GET(self):
        self.send_response(HTTPStatus.OK) 
        self.send_header("Content-type", "application/json")
        self.end_headers()

        # Extract query param
        expression = 'すごい'
        query_components = parse_qs(urlparse(self.path).query)
        if 'expression' in query_components:
            expression = query_components["expression"][0]
        
        audio_sources = self.forvo.word(expression)

        resp = {
            "type": "audioSourceList",
            "audioSources": audio_sources
        }
        print(json.dumps(resp))
        # Writing the JSON contents with UTF-8
        self.wfile.write(bytes(json.dumps(resp), "utf8"))

        return

httpd = socketserver.TCPServer(('', 8770), SearchHandler)
httpd.serve_forever()