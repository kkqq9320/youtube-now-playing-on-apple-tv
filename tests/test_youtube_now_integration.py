import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from custom_components.youtube_now_playing import youtube
from custom_components.youtube_now_playing.youtube import (
    find_first_video_item,
    parse_video_item,
)
from custom_components.youtube_now_playing.cookie_issue import (
    cookie_fetch_succeeded,
    cookie_repair_issue_reason,
)
from custom_components.youtube_now_playing.triggers import (
    should_fetch_for_state_change,
    should_patch_for_state_change,
)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def translation_key_paths(value, prefix=()):
    if not isinstance(value, dict):
        return {prefix}

    paths = set()
    for key, child in value.items():
        paths.update(translation_key_paths(child, (*prefix, key)))
    return paths


class YouTubeParserTest(unittest.TestCase):
    def test_waiting_payload_explains_why_sensor_is_none(self):
        self.assertTrue(hasattr(youtube, "waiting_payload"))

        payload = youtube.waiting_payload()

        self.assertEqual(payload["thumbnail"], "")
        self.assertIn("waiting for selected Apple TV", payload["error"])

    def test_parses_video_renderer_history_item(self):
        data = {
            "items": [
                {
                    "videoRenderer": {
                        "videoId": "abc123",
                        "title": {"runs": [{"text": "Sample title"}]},
                        "ownerText": {"runs": [{"text": "Sample channel"}]},
                        "lengthText": {"simpleText": "3:21"},
                        "thumbnail": {
                            "thumbnails": [
                                {"url": "https://example.test/small.jpg"},
                                {"url": "https://example.test/large.jpg"},
                            ]
                        },
                    }
                }
            ]
        }

        with patch(
            "custom_components.youtube_now_playing.youtube.urlopen",
            return_value=FakeResponse(),
        ):
            payload = parse_video_item(*find_first_video_item(data))

        self.assertEqual(payload["title"], "Sample title")
        self.assertEqual(payload["channel"], "Sample channel")
        self.assertEqual(payload["video_id"], "abc123")
        self.assertEqual(payload["duration_string"], "3:21")
        self.assertEqual(
            payload["thumbnail"], "https://i.ytimg.com/vi/abc123/maxresdefault.jpg"
        )
        self.assertTrue(payload["cookies"])

    def test_prefers_max_thumbnail_when_available(self):
        with patch(
            "custom_components.youtube_now_playing.youtube.urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            thumbnail = youtube.first_thumbnail("abc123")

        self.assertEqual(thumbnail, "https://i.ytimg.com/vi/abc123/maxresdefault.jpg")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 1)

    def test_falls_back_when_max_thumbnail_is_missing(self):
        with patch(
            "custom_components.youtube_now_playing.youtube.urlopen",
            side_effect=URLError("missing"),
        ):
            thumbnail = youtube.first_thumbnail(
                "abc123", fallback="https://example.test/provided.jpg"
            )

        self.assertEqual(thumbnail, "https://example.test/provided.jpg")


class TriggerLogicTest(unittest.TestCase):
    def test_fetches_when_youtube_starts_playing(self):
        self.assertTrue(
            should_fetch_for_state_change(
                old_state="paused",
                old_attrs={"app_id": "com.google.ios.youtube", "media_title": "Old"},
                new_state="playing",
                new_attrs={"app_id": "com.google.ios.youtube", "media_title": "Old"},
                youtube_app_id="com.google.ios.youtube",
            )
        )

    def test_fetches_when_media_title_changes_while_playing(self):
        self.assertTrue(
            should_fetch_for_state_change(
                old_state="playing",
                old_attrs={"app_id": "com.google.ios.youtube", "media_title": "Old"},
                new_state="playing",
                new_attrs={"app_id": "com.google.ios.youtube", "media_title": "New"},
                youtube_app_id="com.google.ios.youtube",
            )
        )

    def test_fetches_when_app_switches_to_youtube_while_playing(self):
        self.assertTrue(
            should_fetch_for_state_change(
                old_state="playing",
                old_attrs={"app_id": "com.netflix.Netflix", "media_title": "Same"},
                new_state="playing",
                new_attrs={"app_id": "com.google.ios.youtube", "media_title": "Same"},
                youtube_app_id="com.google.ios.youtube",
            )
        )

    def test_fetches_when_youtube_pauses(self):
        self.assertTrue(
            should_fetch_for_state_change(
                old_state="playing",
                old_attrs={"app_id": "com.google.ios.youtube", "media_title": "Old"},
                new_state="paused",
                new_attrs={"app_id": "com.google.ios.youtube", "media_title": "Old"},
                youtube_app_id="com.google.ios.youtube",
            )
        )

    def test_fetches_when_youtube_paused_update_removes_entity_picture(self):
        self.assertTrue(
            should_fetch_for_state_change(
                old_state="paused",
                old_attrs={
                    "app_id": "com.google.ios.youtube",
                    "media_title": "Old",
                    "entity_picture": "https://example.test/thumb.jpg",
                },
                new_state="paused",
                new_attrs={"app_id": "com.google.ios.youtube", "media_title": "Old"},
                youtube_app_id="com.google.ios.youtube",
            )
        )

    def test_does_not_fetch_when_non_youtube_pauses(self):
        self.assertFalse(
            should_fetch_for_state_change(
                old_state="playing",
                old_attrs={"app_id": "com.netflix.Netflix", "media_title": "Old"},
                new_state="paused",
                new_attrs={"app_id": "com.netflix.Netflix", "media_title": "Old"},
                youtube_app_id="com.google.ios.youtube",
            )
        )

    def test_does_not_fetch_for_non_youtube_app(self):
        self.assertFalse(
            should_fetch_for_state_change(
                old_state="paused",
                old_attrs={"app_id": "com.netflix.Netflix", "media_title": "Old"},
                new_state="playing",
                new_attrs={"app_id": "com.netflix.Netflix", "media_title": "Old"},
                youtube_app_id="com.google.ios.youtube",
            )
        )


class PatchLogicTest(unittest.TestCase):
    def test_patches_when_media_picture_differs_from_latest_thumbnail(self):
        self.assertTrue(
            should_patch_for_state_change(
                new_state="playing",
                new_attrs={
                    "app_id": "com.google.ios.youtube",
                    "entity_picture": "https://example.test/old.jpg",
                },
                youtube_app_id="com.google.ios.youtube",
                thumbnail="https://example.test/new.jpg",
            )
        )

    def test_does_not_patch_when_media_picture_already_matches_thumbnail(self):
        self.assertFalse(
            should_patch_for_state_change(
                new_state="playing",
                new_attrs={
                    "app_id": "com.google.ios.youtube",
                    "entity_picture": "https://example.test/new.jpg",
                },
                youtube_app_id="com.google.ios.youtube",
                thumbnail="https://example.test/new.jpg",
            )
        )

    def test_does_not_patch_non_youtube_app(self):
        self.assertFalse(
            should_patch_for_state_change(
                new_state="playing",
                new_attrs={
                    "app_id": "com.netflix.Netflix",
                    "entity_picture": "https://example.test/old.jpg",
                },
                youtube_app_id="com.google.ios.youtube",
                thumbnail="https://example.test/new.jpg",
            )
        )


class CookieRepairIssueTest(unittest.TestCase):
    def test_detects_likely_expired_youtube_cookie_payload(self):
        payload = youtube.empty_payload(
            "video item was not found; refresh YouTube cookies if history is empty or logged out"
        )

        self.assertIn("refresh YouTube cookies", cookie_repair_issue_reason(payload))
        self.assertFalse(cookie_fetch_succeeded(payload))

    def test_cookie_repair_clears_only_after_successful_fetch(self):
        transient_error = youtube.empty_payload("<urlopen error timed out>")
        success = {
            "video_id": "abc123",
            "thumbnail": "https://example.test/thumb.jpg",
            "error": "",
        }

        self.assertIsNone(cookie_repair_issue_reason(transient_error))
        self.assertFalse(cookie_fetch_succeeded(transient_error))
        self.assertTrue(cookie_fetch_succeeded(success))


class ConfigFlowSourceTest(unittest.TestCase):
    def test_config_flow_uses_legacy_entity_selector_filter_for_compatibility(self):
        source = Path("custom_components/youtube_now_playing/config_flow.py").read_text()

        self.assertNotIn("EntityFilter(", source)
        self.assertIn('integration="apple_tv"', source)
        self.assertIn("domain=MEDIA_PLAYER_DOMAIN", source)

    def test_config_flow_exposes_options_flow_for_settings(self):
        source = Path("custom_components/youtube_now_playing/config_flow.py").read_text()

        self.assertIn("async_get_options_flow", source)
        self.assertIn("class YouTubeThumbnailOptionsFlow", source)
        self.assertIn("async_step_init", source)
        self.assertIn("add_suggested_values_to_schema", source)

    def test_runtime_uses_options_over_initial_config_data(self):
        init_source = Path("custom_components/youtube_now_playing/__init__.py").read_text()
        coordinator_source = Path(
            "custom_components/youtube_now_playing/coordinator.py"
        ).read_text()
        sensor_source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn("entry.options.get(", init_source)
        self.assertIn("CONF_MEDIA_PLAYER_ENTITY_ID", init_source)
        self.assertIn("CONF_YOUTUBE_APP_ID", init_source)
        self.assertIn("entry.add_update_listener", init_source)
        self.assertIn("entry.options.get(", coordinator_source)
        self.assertIn("CONF_COOKIE_FILE", coordinator_source)
        self.assertIn("ATTR_TARGET_ENTITY_ID", sensor_source)

    def test_state_change_callback_is_marked_event_loop_safe(self):
        source = Path("custom_components/youtube_now_playing/__init__.py").read_text()

        self.assertIn("from homeassistant.core import callback", source)
        self.assertIn("@callback\n    def media_player_changed", source)

    def test_refresh_sequence_avoids_stale_fast_skip_results(self):
        source = Path("custom_components/youtube_now_playing/__init__.py").read_text()

        self.assertIn("asyncio.Lock()", source)
        self.assertIn("refresh_generation", source)
        self.assertIn("DELAYED_REFRESH_SECONDS = (1, 3, 6)", source)
        self.assertIn("async_call_later", source)
        self.assertIn("should_patch_for_state_change", source)
        self.assertNotIn("PATCH_RETRY_SECONDS", source)

    def test_manifest_uses_youtube_now_playing_domain_and_name(self):
        manifest = Path("custom_components/youtube_now_playing/manifest.json").read_text()
        translations = Path(
            "custom_components/youtube_now_playing/translations/en.json"
        ).read_text(encoding="utf-8")

        self.assertIn('"domain": "youtube_now_playing"', manifest)
        self.assertIn('"name": "YouTube Now Playing"', manifest)
        self.assertIn('"title": "YouTube Now Playing"', translations)

    def test_sensor_suggests_entity_id_from_selected_media_player(self):
        source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn("_attr_suggested_object_id", source)
        self.assertIn('f"youtube_now_{media_player_object_id}"', source)
        self.assertIn('split(".", 1)[-1]', source)
        self.assertIn("CONF_MEDIA_PLAYER_ENTITY_ID", source)

    def test_sensor_joins_selected_media_player_device_when_available(self):
        source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn("device_registry as dr", source)
        self.assertIn("entity_registry as er", source)
        self.assertIn("entity_registry.async_get", source)
        self.assertIn("device_registry.async_get", source)
        self.assertIn("media_player_registry_entry.device_id", source)
        self.assertIn("device_entry.identifiers", source)
        self.assertIn("device_entry.connections", source)

    def test_config_flow_asks_for_standalone_before_media_player_setup(self):
        source = Path("custom_components/youtube_now_playing/config_flow.py").read_text()
        translations = Path(
            "custom_components/youtube_now_playing/translations/en.json"
        ).read_text(encoding="utf-8")

        self.assertIn("CONF_CREATE_STANDALONE_SENSOR", source)
        self.assertIn("STANDALONE_UNIQUE_ID", source)
        self.assertIn("async_step_media_player", source)
        self.assertIn("selector.BooleanSelector()", source)
        self.assertIn("default=False", source)
        self.assertIn("return await self.async_step_media_player()", source)
        self.assertIn("DEFAULT_COOKIE_FILE", source)
        self.assertIn("data_description", translations)
        self.assertIn("sensor.youtube_now_playing", translations)
        self.assertIn("polls YouTube history", translations)

    def test_custom_integration_uses_translations_directory(self):
        translation_path = Path("custom_components/youtube_now_playing/translations/en.json")
        obsolete_strings_path = Path("custom_components/youtube_now_playing/strings.json")

        translations = json.loads(translation_path.read_text(encoding="utf-8"))

        self.assertTrue(translation_path.exists())
        self.assertFalse(obsolete_strings_path.exists())
        self.assertEqual(translations["title"], "YouTube Now Playing")
        self.assertEqual(
            translations["config"]["step"]["user"]["data"][
                "create_standalone_sensor"
            ],
            "Create common YouTube Now Playing sensor",
        )
        self.assertIn(
            "Polling interval",
            translations["options"]["step"]["init"]["data"][
                "poll_interval_seconds"
            ],
        )

    def test_custom_integration_includes_korean_translations(self):
        english_path = Path("custom_components/youtube_now_playing/translations/en.json")
        korean_path = Path("custom_components/youtube_now_playing/translations/ko.json")

        english = json.loads(english_path.read_text(encoding="utf-8"))
        korean = json.loads(korean_path.read_text(encoding="utf-8"))

        self.assertEqual(translation_key_paths(english), translation_key_paths(korean))
        self.assertEqual(korean["title"], "YouTube Now Playing")
        self.assertEqual(
            korean["config"]["step"]["user"]["data"][
                "create_standalone_sensor"
            ],
            "공통 YouTube Now Playing 센서 생성",
        )
        self.assertNotIn(
            "YouTube 현재 재생",
            json.dumps(korean, ensure_ascii=False),
        )
        self.assertEqual(
            korean["config"]["step"]["standalone"]["data"][
                "poll_interval_seconds"
            ],
            "폴링 간격",
        )
        self.assertEqual(
            korean["options"]["step"]["init"]["data"]["youtube_app_id"],
            "YouTube 앱 ID (선택 사항)",
        )

    def test_poll_interval_is_configurable_for_standalone_sensor(self):
        config_flow_source = Path(
            "custom_components/youtube_now_playing/config_flow.py"
        ).read_text()
        coordinator_source = Path(
            "custom_components/youtube_now_playing/coordinator.py"
        ).read_text()
        const_source = Path("custom_components/youtube_now_playing/const.py").read_text()
        sensor_source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn("CONF_POLL_INTERVAL_SECONDS", const_source)
        self.assertIn("DEFAULT_POLL_INTERVAL_SECONDS = 60", const_source)
        self.assertIn("CONF_POLL_INTERVAL_SECONDS", config_flow_source)
        self.assertIn("selector.NumberSelector", config_flow_source)
        self.assertIn("NumberSelectorConfig", config_flow_source)
        self.assertIn("DEFAULT_POLL_INTERVAL_SECONDS", config_flow_source)
        self.assertIn("CONF_POLL_INTERVAL_SECONDS", coordinator_source)
        self.assertIn("DEFAULT_POLL_INTERVAL_SECONDS", coordinator_source)
        self.assertIn(
            "timedelta(seconds=self.poll_interval_seconds)", coordinator_source
        )
        self.assertIn("ATTR_POLL_INTERVAL_SECONDS", sensor_source)

    def test_config_flow_sets_up_media_player_in_second_step(self):
        source = Path("custom_components/youtube_now_playing/config_flow.py").read_text()

        self.assertIn("async_step_media_player", source)
        self.assertIn("user_input[CONF_MEDIA_PLAYER_ENTITY_ID]", source)
        self.assertIn("vol.Optional(", source)
        self.assertIn("vol.Required(CONF_MEDIA_PLAYER_ENTITY_ID", source)
        self.assertIn("await self.async_set_unique_id(STANDALONE_UNIQUE_ID)", source)
        self.assertIn('title="YouTube Now Playing"', source)

    def test_optional_media_player_selector_does_not_default_to_empty_string(self):
        source = Path("custom_components/youtube_now_playing/config_flow.py").read_text()

        self.assertNotIn(
            'default=defaults.get(CONF_MEDIA_PLAYER_ENTITY_ID, "")', source
        )
        self.assertIn(
            "description=_suggested_value(defaults, CONF_MEDIA_PLAYER_ENTITY_ID)",
            source,
        )
        self.assertIn('return {"suggested_value": value} if value else {}', source)

    def test_youtube_app_id_is_suggested_not_defaulted(self):
        config_flow_source = Path(
            "custom_components/youtube_now_playing/config_flow.py"
        ).read_text()
        init_source = Path("custom_components/youtube_now_playing/__init__.py").read_text()
        sensor_source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn("vol.Optional(CONF_YOUTUBE_APP_ID", config_flow_source)
        self.assertIn("_normalize_user_input", config_flow_source)
        self.assertIn(
            "_suggested_value(defaults, CONF_YOUTUBE_APP_ID, DEFAULT_YOUTUBE_APP_ID)",
            config_flow_source,
        )
        self.assertNotIn("or DEFAULT_YOUTUBE_APP_ID", config_flow_source)
        self.assertNotIn(
            "_entry_value(entry, CONF_YOUTUBE_APP_ID, DEFAULT_YOUTUBE_APP_ID)",
            init_source,
        )
        self.assertNotIn(
            "_entry_value(self._entry, CONF_YOUTUBE_APP_ID, DEFAULT_YOUTUBE_APP_ID)",
            sensor_source,
        )

    def test_standalone_runtime_polls_with_configured_interval(self):
        init_source = Path("custom_components/youtube_now_playing/__init__.py").read_text()
        coordinator_source = Path(
            "custom_components/youtube_now_playing/coordinator.py"
        ).read_text()

        self.assertIn("if not media_player_entity_id:", init_source)
        self.assertIn("coordinator.async_request_refresh()", init_source)
        self.assertIn("CONF_POLL_INTERVAL_SECONDS", coordinator_source)
        self.assertIn("DEFAULT_POLL_INTERVAL_SECONDS", coordinator_source)
        self.assertIn("self.poll_interval_seconds", coordinator_source)
        self.assertIn("timedelta(seconds=self.poll_interval_seconds)", coordinator_source)
        self.assertIn("standalone_waiting_payload", coordinator_source)

    def test_coordinator_updates_cookie_repair_issue_after_fetch(self):
        coordinator_source = Path(
            "custom_components/youtube_now_playing/coordinator.py"
        ).read_text()

        self.assertIn("async_update_cookie_repair_issue", coordinator_source)
        self.assertIn("payload = await self.hass.async_add_executor_job", coordinator_source)
        self.assertIn(
            "await async_update_cookie_repair_issue(", coordinator_source
        )
        self.assertIn("return payload", coordinator_source)

    def test_repairs_issue_created_for_cookie_problem_and_deleted_on_success(self):
        source = Path("custom_components/youtube_now_playing/repairs.py").read_text()
        cookie_issue_source = Path(
            "custom_components/youtube_now_playing/cookie_issue.py"
        ).read_text()

        self.assertIn("cookie_repair_issue_reason", source)
        self.assertIn("cookie_fetch_succeeded", source)
        self.assertIn("async_create_issue", source)
        self.assertIn("async_delete_issue", source)
        self.assertIn("IssueSeverity.ERROR", source)
        self.assertIn("translation_key=\"youtube_cookie_problem\"", source)
        self.assertIn("is_fixable=True", source)
        self.assertIn("is_persistent=True", source)
        self.assertIn("elif cookie_fetch_succeeded(payload):", source)
        self.assertIn("refresh YouTube cookies", cookie_issue_source)
        self.assertIn("ytInitialData was not found", cookie_issue_source)
        self.assertIn("HTTP Error 401", cookie_issue_source)
        self.assertIn("HTTP Error 403", cookie_issue_source)

    def test_repairs_flow_rechecks_cookie_file_and_clears_issue(self):
        source = Path("custom_components/youtube_now_playing/repairs.py").read_text()

        self.assertIn("class YouTubeCookieRepairFlow", source)
        self.assertIn("async_create_fix_flow", source)
        self.assertIn("coordinator.async_request_refresh()", source)
        self.assertIn("errors={\"base\": \"still_invalid\"}", source)
        self.assertIn("def _current_error(self) -> str:", source)
        self.assertIn("cookie_repair_issue_reason(coordinator.data)", source)
        self.assertIn('"error": reason', source)
        self.assertIn('"error": str(error or self._current_error())', source)
        self.assertIn("ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)", source)
        self.assertIn("self.async_create_entry(title=\"\", data={})", source)

    def test_cookie_repair_translations_exist(self):
        english = json.loads(
            Path("custom_components/youtube_now_playing/translations/en.json").read_text(
                encoding="utf-8"
            )
        )
        korean = json.loads(
            Path("custom_components/youtube_now_playing/translations/ko.json").read_text(
                encoding="utf-8"
            )
        )

        for translations in (english, korean):
            issue = translations["issues"]["youtube_cookie_problem"]
            self.assertIn("title", issue)
            self.assertIn("description", issue)
            self.assertIn("fix_flow", issue)
            self.assertIn(
                "{error}",
                issue["fix_flow"]["step"]["confirm"]["description"],
            )
            self.assertIn("still_invalid", issue["fix_flow"]["error"])
            self.assertIn("entry_not_found", issue["fix_flow"]["abort"])
            self.assertNotIn("repairs", translations)

    def test_standalone_sensor_uses_fixed_entity_id_and_own_device(self):
        source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn("STANDALONE_SENSOR_OBJECT_ID", source)
        self.assertIn("if media_player_entity_id", source)
        self.assertIn("self._attr_suggested_object_id = STANDALONE_SENSOR_OBJECT_ID", source)
        self.assertIn("return _fallback_device_info(entry)", source)

    def test_sensor_sets_entity_id_without_device_name_prefix(self):
        source = Path("custom_components/youtube_now_playing/sensor.py").read_text()

        self.assertIn('self.entity_id = f"sensor.youtube_now_{media_player_object_id}"', source)
        self.assertIn('self.entity_id = "sensor.youtube_now_playing"', source)

    def test_docs_use_requested_github_repository_slug(self):
        manifest = Path("custom_components/youtube_now_playing/manifest.json").read_text()
        readme = Path("README.md").read_text()

        expected_slug = "youtube-now-playing-on-apple-tv"
        typo_slug = "youtubue-now-plaing-on-apple-tv"

        self.assertIn(expected_slug, manifest)
        self.assertIn(expected_slug, readme)
        self.assertNotIn(typo_slug, manifest)
        self.assertNotIn(typo_slug, readme)

    def test_hacs_metadata_and_brand_icon_exist(self):
        hacs = json.loads(Path("hacs.json").read_text(encoding="utf-8"))
        manifest = json.loads(
            Path("custom_components/youtube_now_playing/manifest.json").read_text(
                encoding="utf-8"
            )
        )
        icon = Path("custom_components/youtube_now_playing/brand/icon.png")

        self.assertEqual(hacs["name"], "YouTube Now Playing on Apple TV")
        self.assertIn("homeassistant", hacs)
        self.assertEqual(
            manifest["documentation"],
            "https://github.com/kkqq9320/youtube-now-playing-on-apple-tv",
        )
        self.assertEqual(
            manifest["issue_tracker"],
            "https://github.com/kkqq9320/youtube-now-playing-on-apple-tv/issues",
        )
        self.assertEqual(manifest["codeowners"], ["@kkqq9320"])
        self.assertEqual(manifest["version"], "0.1.1")
        self.assertTrue(icon.exists())
        self.assertEqual(icon.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_readme_documents_hacs_install_and_cookie_export(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("HACS", readme)
        self.assertIn(
            "https://github.com/kkqq9320/youtube-now-playing-on-apple-tv", readme
        )
        self.assertIn("custom_components/youtube_now_playing", readme)
        self.assertNotIn("custom_components/youtube_now`", readme)
        self.assertIn("/config/.youtube_cookies.txt", readme)
        self.assertIn("Netscape", readme)
        self.assertIn("incognito", readme.lower())
        self.assertIn("Get cookies.txt LOCALLY", readme)
        self.assertIn("Repair", readme)
        self.assertIn("cookies are credentials", readme.lower())
        self.assertIn("same cookie file", readme)
        self.assertIn("another device", readme)
        self.assertIn("Apple TV", readme)

    def test_readme_omits_migration_tips(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertNotIn("## Migration", readme)
        self.assertNotIn("youtube_thumbnail", readme)


if __name__ == "__main__":
    unittest.main()

