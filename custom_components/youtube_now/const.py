from homeassistant.const import Platform

DOMAIN = "youtube_now"
PLATFORMS = [Platform.SENSOR]

CONF_COOKIE_FILE = "cookie_file"
CONF_CREATE_STANDALONE_SENSOR = "create_standalone_sensor"
CONF_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"
CONF_POLL_INTERVAL_SECONDS = "poll_interval_seconds"
CONF_YOUTUBE_APP_ID = "youtube_app_id"

DEFAULT_COOKIE_FILE = "/config/.youtube_cookies.txt"
DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_YOUTUBE_APP_ID = "com.google.ios.youtube"
MAX_POLL_INTERVAL_SECONDS = 3600
MIN_POLL_INTERVAL_SECONDS = 5
POLL_INTERVAL_STEP_SECONDS = 5
STANDALONE_SENSOR_OBJECT_ID = "youtube_now_playing"
STANDALONE_UNIQUE_ID = "youtube_now_playing"

ATTR_APP_ID = "app_id"
ATTR_CHANNEL = "channel"
ATTR_COOKIES = "cookies"
ATTR_COOKIE_FILE = "cookie_file"
ATTR_DURATION_STRING = "duration_string"
ATTR_ERROR = "error"
ATTR_MEDIA_TITLE = "media_title"
ATTR_ORIGINAL_URL = "original_url"
ATTR_POLL_INTERVAL_SECONDS = "poll_interval_seconds"
ATTR_TARGET_ENTITY_ID = "target_entity_id"
ATTR_THUMBNAIL = "thumbnail"
ATTR_TITLE = "title"
ATTR_VIDEO_ID = "video_id"
ATTR_YOUTUBE_APP_ID = "youtube_app_id"

STATE_NONE = "none"
STATE_PLAYING = "playing"
