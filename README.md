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

Yomichan Forvo Server supports a few configuration options, which you can edit by going to Add-Ons > Yomichan Forvo Server > Config.

Here is a sample configuration.

```json
{
    "port":8770,
    "language":"ja",
    "preferred_usernames": [],
    "show_gender":true
}
```

| Field               | Description |
|---------------------|-------------|
| port                | Port that YomiChan will call. Default is 8770 |
| language            | Language code to use in Forvo. On the Forvo website, you can see which the language code in square brackets beside the language name. Some examples are `ja` for Japanese or `zh` for Mandarin Chinese. |
| preferred_usernames | A list of Forvo usernames. This will order the results on top based on this priority. |
| show_gender         | Show the gender symbols (♂, ♀,) beside the username based on their gender. |
