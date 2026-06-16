# YouTube Now Playing on Apple TV

A Home Assistant custom integration that follows YouTube playback on an Apple TV, reads the latest YouTube history item, exposes the now playing metadata as a sensor, and patches the Apple TV media player's `entity_picture` with the YouTube thumbnail.

It replaces the earlier AppDaemon, `command_line`, `shell_command`, and automation setup.

## Features

- Apple TV media-player mode filtered to entities from the Apple TV integration
- `sensor.youtube_now_<media_player>` for each selected Apple TV, for example `sensor.youtube_now_apple_tv`
- Optional standalone `sensor.youtube_now_playing` that is not tied to a media player
- YouTube title, channel, video ID, duration, original URL, thumbnail, cookie state, and error attributes
- `maxresdefault.jpg` thumbnail preference with fallback when max resolution is missing
- Automatic `entity_picture` patching when YouTube starts playing, pauses, changes title, or Apple TV clears the image
- Configurable cookie file, YouTube app ID, and standalone polling interval from the integration settings
- Home Assistant Repairs issue when cookies are missing, invalid, logged out, or likely expired

## Installation

### HACS

1. Open HACS.
2. Go to **Integrations**.
3. Open the menu and choose **Custom repositories**.
4. Add `https://github.com/kkqq9320/youtube-now-playing-on-apple-tv` as an **Integration** repository.
5. Install **YouTube Now Playing on Apple TV**.
6. Restart Home Assistant.
7. Add **YouTube Now Playing** from **Settings > Devices & services > Add integration**.

### Manual

Copy `custom_components/youtube_now_playing` into Home Assistant's `/config/custom_components/youtube_now_playing`, then restart Home Assistant.

## Configuration

- Common sensor: optionally create only `sensor.youtube_now_playing`; this is off by default
- Apple TV media player: configured only when standalone sensor creation is declined
- YouTube cookie file: defaults to `/config/.youtube_cookies.txt`
- Polling interval: defaults to 60 seconds for the common sensor and can be changed from **Configure**
- YouTube app ID: optional suggested value `com.google.ios.youtube`

To change these later, open **Settings > Devices & services > YouTube Now Playing > Configure**. Saving options reloads the integration.

When an Apple TV media player is selected, the generated sensor joins that media player's device when Home Assistant exposes it in the registry. New media-player sensors are suggested as `sensor.youtube_now_<media_player_object_id>`, for example `sensor.youtube_now_4k` for `media_player.4k`.

When the common sensor is selected, the integration creates one standalone sensor suggested as `sensor.youtube_now_playing`. This mode is not tied to a media player and polls YouTube history at the configured interval, 60 seconds by default, so updates can lag behind playback and YouTube history availability.

## Cookies

YouTube history pages require authenticated browser cookies. The integration expects a Netscape-format HTTP cookie file, such as `/config/.youtube_cookies.txt`.

Recommended flow:

1. Install a cookie export browser extension such as **Get cookies.txt LOCALLY** for Chrome or **cookies.txt** for Firefox.
2. Open an incognito/private browser window.
3. Sign in to YouTube with the account whose history should be read.
4. Export cookies in Netscape format.
5. Save the file in Home Assistant, for example `/config/.youtube_cookies.txt`.
6. Set the same path in the integration's cookie file setting.
7. Close the incognito/private window.

Using an incognito/private window matters because cookies exported from a normal browsing session can expire very quickly. Cookies are credentials, so do not commit them, paste them into issues, or store them in public backups.

You can use different cookie files per entry. For example, one Apple TV can use `/config/.youtube_cookies1.txt` and another can use `/config/.youtube_cookies2.txt`. Repair issues are tracked per integration entry, so each entry raises and clears its own issue based on its own fetch result and configured cookie file.

When YouTube history cannot be read because the cookie file is missing, invalid, logged out, or likely expired, the integration creates a Home Assistant Repair issue. Export fresh YouTube cookies to the same configured file, then either open the Repair and submit it to check immediately, or wait for the next successful fetch. The Repair issue is cleared automatically after YouTube history is read successfully.

## Behavior

The integration fetches YouTube history when the selected Apple TV is using YouTube and starts playing, pauses, loses its patched `entity_picture`, or changes `media_title`. Fast skips schedule short follow-up refreshes after 1, 3, and 6 seconds because YouTube watch history can lag behind Apple TV playback.

Thumbnails prefer `maxresdefault.jpg` when available, then fall back to the history thumbnail or `hqdefault.jpg`. When Apple TV later rewrites the media player state, the integration patches `entity_picture` only if it differs from the current YouTube Now Playing sensor thumbnail.

If another device is playing YouTube with the same cookie file before the Apple TV media player's `entity_picture` is updated, the latest YouTube history item can belong to that other device. In that case, the Apple TV `entity_picture` can briefly or persistently show the other device's thumbnail.

If the YouTube Now Playing sensor is `none`, check its attributes. `target_entity_id`, `youtube_app_id`, and `cookie_file` show the active settings, while `error` shows whether the integration is waiting for a matching Apple TV trigger or whether YouTube history fetching failed.

If config flow labels show raw keys such as `create_standalone_sensor`, make sure the installed custom component includes `custom_components/youtube_now_playing/translations/en.json`, restart Home Assistant, and hard refresh the browser.
