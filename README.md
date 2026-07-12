# Notify HA Plus

<p align="center">
  <img src="custom_components/notify_ha_plus/brand/logo@2x.png" alt="Notify HA Plus Logo" width="200">
</p>

**DE** | [EN](#english)

Gruppenfähiger Benachrichtigungsdienst für Home Assistant. Stellt eine
vollwertige Integration mit einem Service bereit, der aus jeder Automation
und jeder anderen Integration (z.B. `smart-garage`) aufgerufen werden kann.

## Funktionen

- Personen und Geräte (z.B. Alexa-Lautsprecher) werden über die HA-Oberfläche
  (Einstellungen → Geräte & Dienste → Notify HA Plus → Konfigurieren) verwaltet.
- Frei definierbare Gruppen (z.B. `admin`, `family`, `alexa`) – jede Person/jedes
  Gerät kann beliebig vielen Gruppen zugeordnet werden.
- Anwesenheitsbasierte Sonderziele: `home`, `away`, `home_or_last_away`.
- Bild-/Video-Anhang, Live-Stream- und Dashboard-Link als Aktions-Buttons,
  kritische (unterbrechende) Benachrichtigungen, TTL, Priorität, stummer Modus.
- Automatisches Absenken/Wiederherstellen der Lautstärke betroffener
  Alexa-Media-Player während der Ansage.
- **Ziel-Auswahl per Klick**: Für jede Person, jedes Gerät und jede Gruppe
  (sowie für `home`/`away`/`home_or_last_away`) wird eine eigene
  `notify.*`-Entität angelegt. Im Automatisierungs-Editor kannst du unter
  "Aktion → Benachrichtigung senden" das Ziel bequem aus der Liste auswählen,
  Text eintippen – fertig, kein YAML nötig. Für Bild/Video/Live-Stream/
  kritische Benachrichtigungen weiterhin den Service
  `notify_ha_plus.send_notification` verwenden.

## Installation

1. Ordner `custom_components/notify_ha_plus` nach `<config>/custom_components/`
   kopieren.
2. Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → "Notify HA Plus".
4. Über "Konfigurieren" Personen, Geräte und Gruppen anlegen (z.B. Thomas →
   `admin`, `family`; Miriam → `family`).

## Verwendung

```yaml
action: notify_ha_plus.send_notification
data:
  target:
    - family
  title: Haustür
  message: Es hat geklingelt.
  image_path: /media/local/haustuer.jpg
  dashboard_url: http://192.168.5.144:8123/kamera-haustur/0
  critical: true
```

Aus einer eigenen Integration (z.B. `smart-garage`) heraus:

```python
await hass.services.async_call(
    "notify_ha_plus",
    "send_notification",
    {
        "target": ["family"],
        "title": "Garage",
        "message": "Garagentor ist seit 10 Minuten offen.",
        "critical": True,
    },
)
```

---

## English

Group-aware notification dispatcher for Home Assistant. Provides a proper
integration exposing a service that can be called from any automation or
other integration (e.g. `smart-garage`).

### Features

- Persons and devices (e.g. Alexa speakers) are managed via the HA UI
  (Settings → Devices & Services → Notify HA Plus → Configure).
- Freely definable groups (e.g. `admin`, `family`, `alexa`) — each person/device
  can belong to any number of groups.
- Presence-based special targets: `home`, `away`, `home_or_last_away`.
- Image/video attachment, live-stream and dashboard link as action buttons,
  critical (interruptive) notifications, TTL, priority, silent mode.
- Automatically ducks/restores the volume of affected Alexa media players
  during the announcement.

### Installation

1. Copy `custom_components/notify_ha_plus` to `<config>/custom_components/`.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → "Notify HA Plus".
4. Use "Configure" to add persons, devices and groups (e.g. Thomas →
   `admin`, `family`; Miriam → `family`).

### Usage

```yaml
action: notify_ha_plus.send_notification
data:
  target:
    - family
  title: Front door
  message: Someone rang the bell.
```
