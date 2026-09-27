# Basic Usage

## Start the application

Run the application from the project directory:

```powershell
python main.py
```

The application opens the camera preview using camera device `0`. The preview
shows face and hand landmarks when detected. Keep the hand fully in frame and
well lit for more reliable gesture recognition. When the configured finger
snap gesture is recognized, the application displays a temporary banner.

The first camera frame may take a moment while MediaPipe initializes. If the
camera does not open, check that it is connected, is not being used exclusively
by another application, and that the operating system has granted camera
permission. Model files are expected at:

- `assets/face_landmarker.task`
- `assets/hand_landmarker.task`

## Configure detectors and actions

The default settings are in [config/gestures.json](./config/gestures.json).
The file has two main sections:

- `detectors` lists detector strategies to instantiate. Set `enabled` to
  `false` to disable one. `params` are passed to that detector's constructor.
- `actions` maps an event name to one or more handlers. Each handler can be a
  simple name or an object with a `type` and optional constructor `params`.

The default configuration enables face and finger-snap detection. It maps the
`FingerSnap` event to `UIBannerActionHandler`, with a banner duration of 2500
milliseconds. `FaceDetected` and `FaceLost` events are published but have no
action handlers by default.

### Tune finger-snap recognition

The snap detector uses normalized hand landmarks and detects a thumb/middle
finger pinch followed by a quick release and movement toward the palm. Adjust
these parameters under the `FingerSnapDetector` entry:

| Parameter | Meaning |
| --- | --- |
| `contact_threshold` | Maximum normalized thumb-to-middle-tip distance to arm a snap candidate. |
| `release_threshold` | Minimum normalized distance that counts as release; must exceed the contact threshold. |
| `snap_velocity_threshold` | Minimum palm-lengths per second of palmward movement. |
| `min_snap_travel` | Minimum accumulated palmward movement, in palm lengths. |
| `max_snap_duration_seconds` | Maximum time allowed between pinch and release. |
| `cooldown_seconds` | Minimum delay between snap events for the same hand. |

Thresholds depend on camera angle, frame rate, and the person's gesture. Change
one or two values at a time and test with the live camera; stricter velocity
and travel thresholds usually reduce false positives, while lower thresholds
can make detection more sensitive.

## Understand the extension points

The runtime follows this flow:

1. `VisionWorker` captures and prepares camera frames.
2. `VisionPipeline` calls each configured detector.
3. Detectors return annotated frames and events; they do not call UI code or
   action handlers directly.
4. `EventBus` publishes events to subscribed handlers.
5. Handlers perform their own actions. The banner handler signals the UI
   without depending on the banner widget.

This keeps detection behavior separate from the action taken in response.

### Change an event's action

Edit the matching `actions` entry in `config/gestures.json`. For example, to
use the built-in log handler as well as the banner for snaps:

```json
{
  "event_type": "FingerSnap",
  "handlers": [
    {
      "type": "UIBannerActionHandler",
      "params": { "duration_ms": 2500 }
    },
    "ConsoleLogActionHandler"
  ]
}
```

To suppress the snap banner, remove `UIBannerActionHandler` from that event's
`handlers` array. The event will still be detected and published.

### Add a detector or handler

Configuration selects already registered Python components; it does not load
arbitrary code from JSON. To add a detector:

1. Implement `BaseDetector` in `core/detectors/`. Its `detect(frame,
   timestamp)` method returns a `DetectionResult`, and `close()` releases any
   model resources.
2. Define its event as an `Event` subclass and register the event name in
   `core/interfaces.py`'s `EVENT_TYPES`.
3. Register the detector name in `VisionPipeline._register_builtins` (or
   provide a custom `DetectorRegistry`).
4. Add its `type`, `enabled` setting, and constructor `params` to the
   `detectors` section of `config/gestures.json`.
5. Add the event name and desired handler(s) to `actions`.

To add a handler, implement `BaseActionHandler` in `core/handlers/`, register
its name in `VisionPipeline._register_builtins` (or a custom
`ActionHandlerRegistry`), and select it in the event's `handlers` array. Keep
the action in the handler rather than embedding it in a detector. A handler
that wants to request a UI notification can expose a
`notification_requested(str, int)` Qt signal; other handler types do not need
to use Qt.

For the full architecture, snap algorithm, parameter notes, and completion
checklist, see [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md).
