# Extensible Vision Recognition: Implementation Guide

This document is both the design reference and progress checklist for the
recognition framework. Keep the checkboxes current as requirements are
implemented and verified.

## Goals and current behavior

- Detect and annotate faces and hands from the camera stream.
- Recognize a finger snap as a configured gesture event.
- Keep detectors independent from event actions and keep actions independent
  from Qt widgets.
- Let configuration enable detectors, adjust detector parameters, and bind an
  event to one or more independently configured action handlers.
- Allow new detector and handler implementations to be registered without
  changing the frame-processing loop.

## Architecture and contracts

The runtime flow is:

1. `VisionWorker` reads a BGR camera frame, mirrors it, converts it to RGB, and
   supplies a strictly increasing millisecond timestamp.
2. `VisionPipeline` passes that frame through each enabled detector strategy.
   Each strategy returns a `DetectionResult` containing the annotated frame,
   zero or more events, and optional metadata.
3. The pipeline publishes each event to an instance of `EventBus`.
4. The bus invokes subscribers for the event's concrete type and its base
   `Event` type. Detector code has no reference to handlers or the UI.
5. Configured action handlers perform their own actions. The banner handler
   emits a Qt signal; it does not create or manipulate a UI widget.
6. `MainWindow` connects the worker's generic notification signal to
   `BannerOverlay`. The worker reports camera, detector, handler, and cleanup
   errors through an error signal and Python logging.

### Design patterns and principles

- **Strategy**: `BaseDetector` defines the frame-processing contract.
- **Publisher/subscriber (event bus)**: Detection and action are decoupled.
- **Registry/factory**: String names in configuration resolve to detector and
  handler classes; constructors receive the configured `params`.
- **Dependency injection**: Pipelines can receive configuration, an event bus,
  and custom component registries.
- **Single responsibility / open-closed principle**: Add a strategy or handler
  by implementing and registering a class; avoid adding gesture-specific
  branches to the camera worker or UI.

## Configuration reference

The default configuration is `config/gestures.json`. Relative model paths are
resolved from the project root. Unknown detector or handler names, malformed
JSON, invalid fields, and absent model files are reported as errors rather than
silently ignored.

```json
{
  "detectors": [
    {
      "id": "finger_snap_detector",
      "type": "FingerSnapDetector",
      "enabled": true,
      "params": {
        "model_path": "assets/hand_landmarker.task",
        "contact_threshold": 0.25,
        "release_threshold": 0.55,
        "snap_velocity_threshold": 1.0,
        "min_snap_travel": 0.08,
        "max_snap_duration_seconds": 0.35,
        "cooldown_seconds": 1.0
      }
    }
  ],
  "actions": [
    {
      "event_type": "FingerSnap",
      "handlers": [
        {
          "type": "UIBannerActionHandler",
          "params": {
            "duration_ms": 2500
          }
        }
      ]
    }
  ]
}
```

- `detectors` is an ordered array. Each `id` must be unique; `type` must be
  registered; `enabled` defaults to true; `params` are passed to the detector
  constructor.
- `actions` associates an event name with an ordered array of handler
  specifications. A handler may be a string name (no constructor options) or
  an object with a `type` and optional `params`.
- An event may have multiple action entries or handlers. An empty handler
  array means the event is still published but causes no configured action.
- The built-in `FaceDetector` emits `FaceDetected` when face presence begins or
  the detected face count changes, and `FaceLost` when the last face leaves.
  This avoids invoking actions on every video frame.
- The default snap event is paired only with the on-screen banner. Add or
  remove a handler in this mapping to change that behavior without modifying
  the snap detector.

## Finger snap algorithm and tuning

The MediaPipe hand landmarker supplies normalized landmarks. For every
recognized hand, the snap detector:

1. Uses landmark 0 (wrist), 4 (thumb tip), 9 (middle-finger MCP), and 12
   (middle-finger tip). It normalizes distances and motion by the wrist-to-MCP
   palm length so thresholds are less sensitive to camera distance.
2. Arms a candidate when thumb-tip to middle-tip distance is at or below
   `contact_threshold`.
3. Measures middle-tip motion toward the wrist while the candidate is armed.
   Motion is expressed in palm-lengths per second; positive motion must point
   toward the palm.
4. On separation at or above `release_threshold`, emits `FingerSnapEvent` only
   if the release is within `max_snap_duration_seconds`, peak speed reaches
   `snap_velocity_threshold`, accumulated palmward travel reaches
   `min_snap_travel`, and `cooldown_seconds` has elapsed since the last snap
   for that hand.
5. Draws hand landmarks and connections for operator feedback.

Tune using live camera footage, not synthetic unit tests alone. If real snaps
are missed, inspect the landmark stream first, then lower the speed/travel
thresholds or widen the candidate duration. If ordinary hand motion triggers
events, raise speed/travel thresholds, tighten the contact/release transition,
or increase the cooldown. Threshold units are palm lengths, except velocity
which is palm lengths per second and time which is seconds.

## Adding a new detector or gesture

1. Define its event type in `core/interfaces.py` as an `Event` subclass, add it
   to `EVENT_TYPES` (or call `register_event_type` before loading configuration),
   and include stable event data fields.
2. Create a strategy under `core/detectors/`. Subclass `BaseDetector`; accept
   model paths and tunables through keyword constructor parameters; implement
   `detect(frame, timestamp) -> DetectionResult`; return the same RGB frame
   with any annotations and event objects; implement `close()` for resources.
3. Register the detector name in `VisionPipeline._register_builtins`, or supply
   a custom `DetectorRegistry` with the detector registered to `VisionPipeline`.
4. Add an enabled detector entry and its parameters to `config/gestures.json`.
5. Add the event name and one or more handler specifications to `actions`.
   The detector must not import or call those handlers.
6. Add unit tests for detector state transitions, event fields, invalid
   parameters, and resource cleanup. Add a separate test for the configuration
   mapping; do not require a camera for unit tests.

## Adding or changing an action

1. Implement `BaseActionHandler.handle_event(event)` in `core/handlers/`.
2. Keep side effects inside the handler (or a service it owns); do not add UI
   conditionals to a detector or to `VisionPipeline`.
3. Register its configuration name in `VisionPipeline._register_builtins`, or
   register it in a custom `ActionHandlerRegistry` passed to the pipeline.
4. Add its handler name and constructor options to the desired event's
   `handlers` array in `config/gestures.json`.
5. If the action needs a UI notification, expose a Qt signal named
   `notification_requested(str, int)`; the worker relays this capability to
   `MainWindow` without depending on the concrete handler class. Other actions
   need no UI changes.
6. Test that the handler receives the expected event and that it can be
   removed/replaced through configuration.

## Face, object, and other recognition types

- Treat face, object, pose, and hand landmark processing as detector strategies
  that share the frame and timestamp contract.
- Give each detector its own model/options and lifecycle; close all resources
  when the pipeline exits.
- Define events around meaningful state changes (entered, changed, exited)
  rather than publishing an action every frame, unless a consumer explicitly
  needs frame-level updates.
- Keep object/class labels and confidence/bounding-box data in event data so
  handlers can make their own decisions without detector-specific imports.
- Add model asset paths to configuration and keep assets in `assets/`; never
  hardcode a machine-specific absolute path.

## Progress checklist

### Core contracts and extensibility

- [x] Define base `Event`, `DetectionResult`, `BaseDetector`, and
  `BaseActionHandler` contracts plus built-in face/snap event types.
- [x] Implement an instance-based, thread-safe event bus with subscribe,
  unsubscribe, base-event subscriptions, and explicit handler error
  propagation.
- [x] Implement JSON loading, structural validation, event-name validation,
  handler parameters, and explicit missing/invalid-config errors.
- [x] Implement detector and action-handler registries with type checking,
  duplicate-name protection, and factory creation.

### Detectors and actions

- [x] Refactor face landmarks into a configurable `FaceDetector`; emit face
  presence/count transitions and draw landmarks.
- [x] Add the MediaPipe hand-landmarker asset and configurable
  `FingerSnapDetector`.
- [x] Implement per-hand pinch, palmward velocity/travel, release, duration,
  and cooldown state; emit `FingerSnapEvent` and draw hand landmarks.
- [x] Implement independent console-log and UI-banner handlers; select the
  visual banner for finger snaps in default JSON configuration.
- [x] Implement a floating banner overlay and a generic worker notification
  signal; keep the banner widget out of detector and handler logic.

### Pipeline, lifecycle, and validation

- [x] Integrate configured detectors and event-to-handler subscriptions in a
  reusable `VisionPipeline`.
- [x] Refactor the camera worker to run the pipeline, use monotonic timestamps,
  convert owned frames safely for Qt, report errors, and release resources.
- [x] Add tests for event routing, configuration validation/handler options,
  registries, and a synthetic snap pinch-release sequence.
- [x] Run the unit tests and syntax checks after the final integration (5
  framework tests pass).
- [x] Verify both configured MediaPipe models process a synthetic frame and
  close cleanly; verify offscreen UI startup, notification relay, banner
  display, and worker shutdown.
- [ ] Verify face/snap detection and banner display using a live camera and
  real gesture footage; tune thresholds if needed.
