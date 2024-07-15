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
from dataclasses import dataclass, field
from typing import List

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


# Config default values
@dataclass
class ForvoConfig():
    port: int = 8770
    language: str = 'ja'
    preferred_usernames: List[str] = field(default_factory=list)
    preferred_countries: List[str] = field(default_factory=list)
    show_gender: bool = True
    show_country: bool = False

    def set(self, config):
        self.__init__(**config)

    def __post_init__(self):
        self.preferred_countries = [c.lower() for c in self.preferred_countries]

_forvo_config = ForvoConfig()

class Forvo():
    """
    Forvo web-scraper utility class that matches YomiChan's expected output for a custom audio source
    """
    _SERVER_HOST = "https://forvo.com"
    _AUDIO_HTTP_HOST = "https://audio12.forvo.com"
    def __init__(self, config=_forvo_config):
        self.config = config
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
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        # Use my personal user agent to try to avoid scraping detection
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.27",
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
        results = soup.select(f"#language-container-{self.config.language}>article>ul.pronunciations-list>li:not(.li-ad)")
        pronunciations = []
        for i in results:
            url = self._extract_url(i.div)

            # Capture the username of the user
            # Some users have deleted accounts which is why can't just parse it from the <a> tag
            username_match = re.search(r"Pronunciation by([^(]+)\(", i.get_text(strip=True))
            username = username_match.group(1).strip() if username_match else 'Unknown'

            pronunciation = {
                'username': username,
                'url': url
            }
            if self.config.show_gender:
                m = re.search(r"\((Male|Female)", i.get_text(strip=True))
                if m:
                    pronunciation['gender'] = m.group(1).strip()
            if self.config.show_country or self.config.preferred_countries:
                countryMatch = re.search(r"\((?:Male|Female) from ([^)]+)\)", i.get_text(strip=True))
                if countryMatch:
                    pronunciation['country'] = countryMatch.group(1).strip()

            pronunciations.append(pronunciation)

        # Order the list based on preferred_usernames and preferred_countries
        # preferred usernames takes priority over preferred countries
        if self.config.preferred_usernames or self.config.preferred_countries:
            preferred_usernames = self.config.preferred_usernames
            preferred_countries = self.config.preferred_countries

            def get_index(pronunciation):
                pronunciation_username = pronunciation['username']
                pronunciation_country = pronunciation.get('country', 'unknown').lower()
                if pronunciation_username in preferred_usernames:
                    return preferred_usernames.index(pronunciation_username)

                if pronunciation_country in preferred_countries:
                    return preferred_countries.index(pronunciation_country) + len(preferred_usernames)

                # If the username isn't in the preferred lists, put it at the end
                return len(preferred_usernames) + len(preferred_countries)

            pronunciations = sorted(pronunciations, key=get_index)

        # Transform the list of pronunciations into Yomichan format
        audio_sources = []
        for pronunciation in pronunciations:
            genderSymbol = {
                "Male": '♂',
                "Female": '♀',
            }.get(pronunciation.get("gender"), "")
            
            name = f"Forvo ({genderSymbol}{pronunciation['username']})"
            if(country := pronunciation.get("country")):
                name = re.sub(r"\)$", f", {country})", name)

            audio_sources.append({
                "url": pronunciation['url'],
                "name": name
            })
        return audio_sources

    @classmethod
    def _extract_url(cls, element):
        play = element['onclick']
        # We are interested in Forvo's javascript Play function which takes in some parameters to play the audio
        # Example: Play(3060224,'OTQyN...','OTQyN..',false,'Yy9wL2NwXzk0MjYzOTZfNzZfMzM1NDkxNS5tcDM=','Yy9wL...','h')
        # Match anything that isn't commas, parentheses or quotes to capture the function arguments
        # Regex will match something like ["Play", "3060224", ...]
        play_args = re.findall(r"([^',\(\)]+)", play)

        # Forvo has two locations for mp3, /audios/mp3 and just /mp3
        # /audios/mp3 is normalized and has the filename in the 5th argument of Play base64 encoded
        # /mp3 is raw and has the filename in the 2nd argument of Play encoded
        try:
            file = base64.b64decode(play_args[5]).decode("utf-8")
            url = f"{cls._AUDIO_HTTP_HOST}/audios/mp3/{file}"
        # Some pronunciations don't have a normalized version so fallback to raw
        except:
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
        path = f"/search/{s}/{self.config.language}/"
        html = self._get(path)
        soup = BeautifulSoup(html, features="html.parser")

        # Forvo's search page returns two result sets like:
        # <ul class="word-play-list-icon-size-l">
        #   <li><span class="play" onclick"(some javascript to play the word audio)"></li>
        # </ul>
        results = soup.select('ul.word-play-list-icon-size-l>li>div.play')
        audio_sources = []
        for i in results:
            url = self._extract_url(i)
            audio_sources.append({"name":"Forvo Search","url":url})
        return audio_sources


class ForvoHandler(http.server.SimpleHTTPRequestHandler):
    forvo = Forvo(config=_forvo_config)

    # By default, SimpleHTTPRequestHandler logs to stderr
    # This would cause Anki to show an error, even on successful requests
    # log_error is still a useful function though, so replace it with the inherited log_message
    # Make log_message do nothing
    def log_error(self, *args, **kwargs):
        super().log_message(*args, **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        # Extract 'term' and 'reading' query parameters
        query_components = parse_qs(urlparse(self.path).query)
        term = query_components["term"][0] if "term" in query_components else ""

        # Yomichan used to use "expression" but renamed to term. Still support "expression" for older versions
        expression = query_components["expression"][0] if "expression" in query_components else ""
        if term == "":
            term = expression

        reading = query_components["reading"][0] if "reading" in query_components else ""
        debug = query_components["debug"][0] if "debug" in query_components else False

        # Allow overriding the language
        self.forvo.config.language = query_components.get("language", [self.forvo.config.language])[0]
           
        if debug:
            debug_resp = {
                "debug":True
            }
            debug_resp['reading'] = reading
            debug_resp['term'] = term
            debug_resp['word.term'] = self.forvo.word(term)
            debug_resp['word.reading'] = self.forvo.word(reading)
            debug_resp['search.term'] = self.forvo.search(term)
            debug_resp['search.reading'] = self.forvo.search(reading)
            self.wfile.write(bytes(json.dumps(debug_resp), "utf8"))
            return

        audio_sources = []

        # Try looking for word sources for 'term' first
        audio_sources = self.forvo.word(term)

        # Try looking for word sources for 'reading'
        if len(audio_sources) == 0:
            audio_sources += self.forvo.word(reading)

        # Finally use forvo search to look for similar words
        if len(audio_sources) == 0:
            audio_sources += self.forvo.search(term)

        if len(audio_sources) == 0:
            audio_sources += self.forvo.search(reading)

        # Build JSON that yomichan requires
        # Ref: https://github.com/FooSoft/yomichan/blob/master/ext/data/schemas/custom-audio-list-schema.json
        resp = {
            "type": "audioSourceList",
            "audioSources": audio_sources
        }

        # Writing the JSON contents with UTF-8
        payload = bytes(json.dumps(resp), "utf8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            self.log_error("BrokenPipe when sending reply")

        return

if __name__ == "__main__":
    # If we're not in Anki, run the server directly and blocking for easier debugging
    print("Running in debug mode...")
    httpd = socketserver.TCPServer(('localhost', 8770), ForvoHandler)
    httpd.serve_forever()
else:
    # Else, run it in a separate thread so it doesn't block
    # Also import Anki-specific packages here
    from aqt import mw
    _forvo_config.set(mw.addonManager.getConfig(__name__))
    httpd = http.server.ThreadingHTTPServer(('localhost', _forvo_config.port), ForvoHandler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
