"""Constants for Notify HA Plus."""

from __future__ import annotations

DOMAIN = "notify_ha_plus"

# hass.data keys
DATA_ENTRY = "entry"
DATA_ENTITY_TARGET_MAP = "entity_target_map"
DATA_LAST_NOTIFICATIONS = "last_notifications"
DATA_STORE = "store"
DATA_ADD_ENTITIES_CB = "add_entities_cb"
DATA_CURRENT_ENTITIES = "current_entities"

SIGNAL_OPTIONS_UPDATED = f"{DOMAIN}_options_updated"
SIGNAL_NOTIFICATION_SENT = f"{DOMAIN}_notification_sent"

# Options storage keys
CONF_TARGETS = "targets"
CONF_VOLUME_NORMAL = "volume_normal"
CONF_VOLUME_CRITICAL = "volume_critical"
CONF_VOLUME_AFTER = "volume_after"
CONF_SILENT_CHANNEL = "silent_channel"

DEFAULT_VOLUME_NORMAL = 0.2
DEFAULT_VOLUME_CRITICAL = 0.3
DEFAULT_VOLUME_AFTER = 0.1
DEFAULT_SILENT_CHANNEL = "silent"

# Target entry fields
FIELD_ID = "id"
FIELD_TYPE = "type"
FIELD_NAME = "name"
FIELD_PERSON_ENTITY = "person_entity"
FIELD_NOTIFY_SERVICE = "notify_service"
FIELD_GROUPS = "groups"
FIELD_DEVICE_TRACKER = "device_tracker_entity"

TARGET_TYPE_PERSON = "person"
TARGET_TYPE_DEVICE = "device"

# Presence keywords
KEYWORD_HOME = "home"
KEYWORD_AWAY = "away"
KEYWORD_HOME_OR_LAST_AWAY = "home_or_last_away"
SPECIAL_KEYWORDS = (KEYWORD_HOME, KEYWORD_AWAY, KEYWORD_HOME_OR_LAST_AWAY)

# Service
SERVICE_SEND_NOTIFICATION = "send_notification"

ATTR_TARGET = "target"
ATTR_MESSAGE = "message"
ATTR_TITLE = "title"
ATTR_IMAGE_PATH = "image_path"
ATTR_VIDEO_PATH = "video_path"
ATTR_LIVE_STREAM_URL = "live_stream_url"
ATTR_DASHBOARD_URL = "dashboard_url"
ATTR_TAG = "tag"
ATTR_TTL = "ttl"
ATTR_PRIORITY = "priority"
ATTR_CRITICAL = "critical"
ATTR_SILENT = "silent"

PRIORITY_OPTIONS = ["high", "normal", "low"]

ALEXA_NOTIFY_PREFIX = "notify.alexa_media_"
ALEXA_MEDIA_PLAYER_PREFIX = "media_player."

# Services to exclude from the dropdown (generic fallback, not per-person)
EXCLUDED_NOTIFY_SERVICES = {"notify", "persistent_notification"}
