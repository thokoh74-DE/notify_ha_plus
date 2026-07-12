# Changelog / Änderungsprotokoll

## [1.0.0] – 2025-07-12

### Neu / Added
- Erstveröffentlichung / Initial release
- Gruppenfähiger Benachrichtigungsdienst (`notify_ha_plus.send_notification`)
- UI-basierte Verwaltung von Personen, Geräten und Gruppen (Config- und Options-Flow)
- Anwesenheitsbasierte Ziele: `home`, `away`, `home_or_last_away`
- Zusätzlicher `device_tracker` pro Person für erweiterte Anwesenheitserkennung (z.B. FRITZ!Box)
- Automatisches Alexa-Lautstärke-Ducking während Ansagen
- Konfigurierbarer Android-Benachrichtigungskanal für lautlose Meldungen
- iOS: `presentation_options` für zuverlässiges Stummschalten
- Notify-Entitäten als auswählbare Ziele im Automatisierungs-Editor
- Profilbilder für Personen-Entitäten, typ-spezifische Icons (Gruppen, Geräte, Anwesenheit)
- Persistenter Benachrichtigungsstatus (überlebt HA-Neustarts)
- Erkennung der auslösenden Automation pro Benachrichtigung
- 3 Diagnose-Sensoren: Anwesende Personen, Abwesende Personen, Zuletzt abwesend
- Dynamische Entität-Erstellung ohne Integrations-Neustart
- Config-Flow mit geführter Ersteinrichtung
- Diagnostics-Support
- Zweisprachig (DE/EN)
- HACS-kompatibel mit CI/CD (hassfest, HACS, Ruff, CodeQL, automatisches Release-Versioning)
