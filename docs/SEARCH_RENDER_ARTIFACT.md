# Search-field rendering artifact

## Root cause

The two visible lines had independent causes:

1. KivyMD 1.2 draws an `MDTextField` with `mode: "round"` using two half
   ellipses and a rectangle between them. The middle rectangle did not cover
   the flat diameter of the right ellipse, leaving a full-height, darker seam
   at the ellipse center. It was not the cursor: live SDL measurement showed
   the field at `focus=False`, with the cursor on the left while the line
   remained at the center of the right cap.
2. The home `ScrollView` used its default `bar_width=2` indicator, which looked
   like a separate line attached to the right edge of the window.

## Resolution

The search field was replaced by a `SearchBar` component with one
`RoundedRectangle` surface and one rounded `SmoothLine` border. Its standard
inner `TextInput` draws the cursor only while actually focused. No arbitrary
pixel offset or background-colored cover is used. The home screen's visual
scrollbar is disabled while mouse-wheel and touch scrolling remain available.

`scripts/dev/verify_search_bar_visual.py` captures light/dark,
focus/unfocus, and window-resize cases in a real SDL window. It measures both
the continuous contrast column at the right-cap center and any scrollbar line
in the final two window columns. A high-DPI run also executes with
`KIVY_METRICS_DENSITY=2`.
