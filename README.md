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
5. Select Type as JSON and set URL to http://localhost:8770/?expression={expression}&reading={reading}
6. In your Audio Sources list below, make sure one of them is set to Custom

Now when you scan a word in Yomichan, you should be able to right click the audio icon and the Forvo custom audio sources should appear.
