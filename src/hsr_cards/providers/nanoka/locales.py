from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Locale(str, Enum):
    """Locales published under ``static.nanoka.cc/hsr/<version>/<locale>/``."""

    EN = "en"
    ZH = "zh"
    JA = "ja"
    KO = "ko"

    @classmethod
    def normalize(cls, value: str | "Locale") -> "Locale":
        """Resolve a Locale member or a supported locale alias.

        Aliases include ISO/region variants; unsupported locales raise ValueError.
        """
        if isinstance(value, cls):
            return value
        key = str(value).strip().lower().replace("_", "-")
        aliases = {
            "en": cls.EN,
            "en-us": cls.EN,
            "en-gb": cls.EN,
            "english": cls.EN,
            "zh": cls.ZH,
            "zh-cn": cls.ZH,
            "zh-hans": cls.ZH,
            "zh-sg": cls.ZH,
            "chs": cls.ZH,
            "cn": cls.ZH,
            "chinese": cls.ZH,
            "ja": cls.JA,
            "ja-jp": cls.JA,
            "jp": cls.JA,
            "japanese": cls.JA,
            "ko": cls.KO,
            "ko-kr": cls.KO,
            "kr": cls.KO,
            "korean": cls.KO,
        }
        try:
            return aliases[key]
        except KeyError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ValueError(
                f"Unsupported Nanoka locale {value!r}; choose one of: {supported}"
            ) from exc

    @property
    def folder(self) -> str:
        """Return the provider locale folder: en, zh, ja, or ko."""
        return self.value


DEFAULT_LOCALE = Locale.EN


@dataclass(frozen=True)
class LocaleFamily:
    """Locale-aware helper for the upstream ``en``/``zh``/``ja``/``ko`` shape."""

    locale: Locale = DEFAULT_LOCALE
    fallback_locale: Locale = Locale.EN

    def pick(self, payload: dict | None, *, default: str | None = None) -> str | None:
        """Choose text for this family's locale, or return default when absent.

        Try fallback_locale next, followed by en/zh/ja/ko. Non-mapping payloads
        also return default (None by default). This operation performs no IO.
        """
        if not isinstance(payload, dict):
            return default
        value = payload.get(self.locale.value)
        if value:
            return value
        if self.fallback_locale != self.locale:
            value = payload.get(self.fallback_locale.value)
            if value:
                return value
        for key in ("en", "zh", "ja", "ko"):
            value = payload.get(key)
            if value:
                return value
        return default


__all__ = ["Locale", "LocaleFamily", "DEFAULT_LOCALE"]
