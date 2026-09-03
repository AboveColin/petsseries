"""Tests for the typed models.

Most of these are plain dataclasses. The cases here are the ones with logic:
the from_dict builders that have to survive a missing block, the enums that
parse strings coming off the wire, and the invite role that arrives in either
case.
"""

from __future__ import annotations

import pytest

from petsseries.models import (
    AppRelease,
    CountryInfo,
    Device,
    DeviceSettings,
    DiscoveryConfig,
    Event,
    EventType,
    FeederVoiceAudio,
    FilterTime,
    Home,
    HomeInvite,
    HomeInviteRole,
    HomeInviteStatus,
    Meal,
    MotionEvent,
)


class TestHomeAndDevice:
    """The two accessors the integration calls by name."""

    def test_a_home_reports_its_id_and_name(self) -> None:
        home = Home(id="h1", name="Thuis", shared=False, number_of_devices=1, external_id="e", url="u")
        assert home.get_home_id() == "h1"
        assert home.get_home_name() == "Thuis"

    def test_a_device_reports_its_id_and_name(self) -> None:
        device = Device(id="d1", name="Voerbak")
        assert device.get_device_id() == "d1"
        assert device.get_device_name() == "Voerbak"

    def test_the_optional_device_fields_default_to_absent(self) -> None:
        device = Device(id="d1", name="Voerbak")
        assert device.product_ctn is None
        assert device.mcu_version is None
        assert device.wifi_version is None

    def test_the_ota_versions_are_kept_apart(self) -> None:
        # The mobile app labels type 9 as MCU and type 0 as WiFi. Reporting one
        # as the other makes a firmware watcher chase the wrong component.
        device = Device(id="d1", name="Voerbak", mcu_version="1.2.3", wifi_version="4.5.6")
        assert device.mcu_version == "1.2.3"
        assert device.wifi_version == "4.5.6"


class TestEventTypes:
    """The event catalogue the integration switches on."""

    def test_every_event_type_is_listed(self) -> None:
        assert set(Event.get_event_types()) == set(EventType)

    def test_the_catalogue_covers_the_nine_known_events(self) -> None:
        assert len(list(EventType)) == 9

    @pytest.mark.parametrize(
        "value",
        [
            "motion_detected",
            "meal_dispensed",
            "meal_upcoming",
            "food_level_low",
            "meal_enabled",
            "filter_replacement_due",
            "food_outlet_stuck",
            "device_online",
            "device_offline",
        ],
    )
    def test_each_wire_value_parses_to_a_type(self, value: str) -> None:
        assert EventType(value).value == value

    def test_an_unknown_event_value_is_refused(self) -> None:
        with pytest.raises(ValueError):
            EventType("something_new")

    def test_the_repr_carries_the_type_and_time(self) -> None:
        event = Event(id="e1", type="motion_detected", source="s", time="2026-09-01T10:00:00Z", url="u")
        assert "motion_detected" in repr(event)
        assert "2026-09-01T10:00:00Z" in repr(event)

    def test_a_motion_repr_adds_the_device(self) -> None:
        event = MotionEvent(
            id="e1",
            type="motion_detected",
            source="s",
            time="t",
            url="u",
            cluster_id=None,
            metadata=None,
            thumbnail_key=None,
            device_id="d1",
            device_name="Voerbak",
            thumbnail_url=None,
            product_ctn=None,
            device_external_id=None,
        )
        assert "d1" in repr(event)
        assert "Voerbak" in repr(event)


class TestHomeInvite:
    """Invites, whose role arrives in either case."""

    def test_a_lowercase_role_is_accepted(self) -> None:
        # The API is not consistent about case, and a ValueError here would
        # take out the whole home listing.
        invite = HomeInvite.from_dict({"id": "i1", "role": "admin", "status": "created"})
        assert invite.role is HomeInviteRole.ADMIN

    def test_an_uppercase_role_is_accepted(self) -> None:
        invite = HomeInvite.from_dict({"id": "i1", "role": "MEMBER", "status": "created"})
        assert invite.role is HomeInviteRole.MEMBER

    def test_a_missing_role_defaults_to_member(self) -> None:
        assert HomeInvite.from_dict({"id": "i1", "status": "created"}).role is HomeInviteRole.MEMBER

    @pytest.mark.parametrize("status", ["created", "accepted", "expired", "pending"])
    def test_each_status_parses(self, status: str) -> None:
        assert HomeInvite.from_dict({"id": "i", "status": status}).status.value == status

    def test_a_missing_status_defaults_to_created(self) -> None:
        assert HomeInvite.from_dict({"id": "i"}).status is HomeInviteStatus.CREATED

    def test_the_email_and_label_are_read(self) -> None:
        invite = HomeInvite.from_dict(
            {"id": "i1", "email": "a@b.test", "label": "Colin", "createdAt": "2026-09-01", "url": "u"}
        )
        assert invite.email == "a@b.test"
        assert invite.label == "Colin"
        assert invite.created_at == "2026-09-01"

    def test_an_empty_payload_does_not_raise(self) -> None:
        assert HomeInvite.from_dict({}).id == ""

    def test_an_unknown_role_is_refused(self) -> None:
        with pytest.raises(ValueError):
            HomeInvite.from_dict({"id": "i", "role": "OWNER"})


class TestDeviceSettings:
    """Settings blocks the API omits when unset."""

    def test_a_filter_time_is_read(self) -> None:
        result = FilterTime.from_dict(
            {"type": "fountain", "value": "2026-09-01T00:00:00Z", "format": "datetime"}
        )
        assert result is not None
        assert result.type == "fountain"
        assert result.format == "datetime"

    def test_a_missing_filter_time_is_absent_not_empty(self) -> None:
        # An empty FilterTime would render as a filter due at the epoch.
        assert FilterTime.from_dict(None) is None
        assert FilterTime.from_dict({}) is None

    def test_voice_audio_is_read(self) -> None:
        audio = FeederVoiceAudio.from_dict({"audioId": "a1", "url": "u", "recorded": True})
        assert audio is not None
        assert audio.audio_id == "a1"

    def test_missing_voice_audio_is_absent(self) -> None:
        assert FeederVoiceAudio.from_dict(None) is None

    def test_settings_survive_an_empty_payload(self) -> None:
        settings = DeviceSettings.from_dict({})
        assert settings.filter_replacement_time is None
        assert settings.filter_application_time is None
        assert settings.feeder_voice_audio_id is None

    def test_settings_read_each_block(self) -> None:
        settings = DeviceSettings.from_dict(
            {
                "filter_replacement_time": {"type": "fountain", "value": "2026-10-01"},
                "filter_application_time": {"type": "fountain", "value": "2026-09-01"},
            }
        )
        assert settings.filter_replacement_time is not None
        assert settings.filter_application_time is not None
        assert settings.filter_replacement_time.value == "2026-10-01"


class TestDiscovery:
    """The bootstrap config the app fetches before anything else."""

    def test_a_release_is_read(self) -> None:
        release = AppRelease.from_dict({"minVersion": "1.0.0", "currentVersion": "1.5.0"})
        assert release is not None
        assert release.min_version == "1.0.0"
        assert release.current_version == "1.5.0"

    def test_a_missing_release_is_absent(self) -> None:
        assert AppRelease.from_dict(None) is None

    def test_a_country_is_read(self) -> None:
        country = CountryInfo.from_dict({"code": "NL", "name": "Netherlands", "dialCode": "+31"})
        assert (country.code, country.name, country.dial_code) == ("NL", "Netherlands", "+31")

    def test_a_country_without_a_dial_code_does_not_raise(self) -> None:
        assert CountryInfo.from_dict({"code": "NL", "name": "Netherlands"}).dial_code is None

    def test_the_config_reads_countries_and_both_releases(self) -> None:
        config = DiscoveryConfig.from_dict(
            {
                "id": "c1",
                "apiUrl": "https://api.test",
                "consumerUrl": "https://consumer.test",
                "countries": [{"code": "NL", "name": "Netherlands"}, {"code": "BE", "name": "Belgium"}],
                "appReleases": {
                    "android": {"minVersion": "1.0.0", "currentVersion": "1.5.0"},
                    "ios": {"minVersion": "2.0.0", "currentVersion": "2.5.0"},
                },
            }
        )
        assert [c.code for c in config.countries] == ["NL", "BE"]
        assert config.android_release is not None
        assert config.ios_release is not None
        assert config.ios_release.current_version == "2.5.0"

    def test_a_config_without_releases_does_not_raise(self) -> None:
        config = DiscoveryConfig.from_dict({"id": "c1", "apiUrl": "u", "consumerUrl": "c"})
        assert config.countries == []
        assert config.android_release is None

    def test_an_empty_payload_does_not_raise(self) -> None:
        assert DiscoveryConfig.from_dict({}).id == ""


class TestMeal:
    """The meal record, which the scheduler round-trips."""

    def test_carries_the_schedule(self) -> None:
        meal = Meal(
            id="m1",
            name="Ontbijt",
            portion_amount=2.0,
            feed_time="07:30:00",
            repeat_days=[1, 2, 3, 4, 5],
            device_id="d1",
            enabled=True,
            url="u",
        )
        assert meal.repeat_days == [1, 2, 3, 4, 5]
        assert meal.enabled is True



class TestEveryEventRepr:
    """Every event renders enough to identify it in a log line.

    The subclasses are built from their own dataclass fields rather than by
    hand, so a new event type joins this test the moment it is defined.
    """

    import dataclasses as _dc

    SUBCLASSES = sorted(
        (
            cls
            for cls in __import__("petsseries.models", fromlist=["models"]).__dict__.values()
            if isinstance(cls, type) and issubclass(cls, Event) and cls is not Event
        ),
        key=lambda c: c.__name__,
    )

    @staticmethod
    def build(cls: type) -> Event:
        """Construct one event with a placeholder in every field."""
        import dataclasses

        values = {}
        for field in dataclasses.fields(cls):
            if field.name == "type":
                values[field.name] = "an_event"
            elif field.name == "time":
                values[field.name] = "2026-09-01T10:00:00Z"
            elif field.name == "metadata":
                values[field.name] = None
            elif "amount" in field.name:
                values[field.name] = 1.0
            else:
                values[field.name] = f"{field.name}-value"
        return cls(**values)

    @pytest.mark.parametrize("cls", SUBCLASSES, ids=[c.__name__ for c in SUBCLASSES])
    def test_the_repr_carries_the_type_and_the_time(self, cls: type) -> None:
        rendered = repr(self.build(cls))
        assert "an_event" in rendered
        assert "2026-09-01T10:00:00Z" in rendered

    @pytest.mark.parametrize("cls", SUBCLASSES, ids=[c.__name__ for c in SUBCLASSES])
    def test_every_subclass_is_an_event(self, cls: type) -> None:
        assert isinstance(self.build(cls), Event)

    def test_the_nine_event_types_all_have_a_class(self) -> None:
        assert len(self.SUBCLASSES) == len(list(EventType))
