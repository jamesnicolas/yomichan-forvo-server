# Yomichan Forvo Server for Anki

![image](https://user-images.githubusercontent.com/2841145/111932339-97690580-8a93-11eb-9f2a-4fa791dd5954.png)

Simple server to take advantage of Yomichan's custom audio sources feature. Requires Anki Connect. It web scrapes Forvo's search and word page to get a list of words.

Prerequisites:

- Anki
- Yomichan
- Anki Connect

Install:

1. Copy the code and install like you would for any other Anki addon
2. Restart Anki
3. Allow network connections (required since this is a local server)
4. In yomichan settings, go to Audio > Configure Audio Playback Sources > Custom Audio Source
5. Select Type as JSON and set URL to http://localhost:8770/?term={term}&reading={reading}
6. In your Audio Sources list below, make sure one of them is set to Custom

Now when you scan a word in Yomichan, you should be able to right click the audio icon and the Forvo custom audio sources should appear.

## Configuration

Yomichan Forvo Server supports a few configuration options, which you can edit by going to Tools > Add-Ons > Yomichan Forvo Server > Config. **Note configuration changes requires you to restard Anki to see effects**.

- `port`                Port that YomiChan will call. Default is 8770
- `language`            Language code to use in Forvo. Some examples are `ja` for Japanese or `zh` for Mandarin Chinese. Default `ja`. On the Forvo website, you can see what language code is in square brackets beside the language name on a pronunciation.
- `preferred_usernames` A list of Forvo usernames. This will order the results on top based on this priority. If empty, results will show based on the Forvo website order. Default empty.
- `show_gender`         Show the gender symbols (♂, ♀,) beside the username based on their gender. Default `true`.

## Links

- GitHub: https://github.com/jamesnicolas/yomichan-forvo-server
- Anki Add-on page: https://ankiweb.net/shared/info/580654285

## Changelog

### 2022-09-05
- add support for preferred usernames
- fixed bug where it was using the raw audio from forvo, now uses the normalized audio from forvo
- added gender symbols to results
- support configuration where port, username order, language, and showing gender symbols are configurable

### 2022-07-25
- update selectors for new forvo layout

### 2022-01-30
- add Content-length header

### 2021-03-22
- fixed bug with empty reading/expression inputs returning unrelated words
- added basic retries/timeouts to deal with connection issues

### 2021-11-14
- change timeout to 10 seconds

