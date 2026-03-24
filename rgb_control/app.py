"""NZXT RGB Control TUI - Visual color controller for NZXT 2023 RGB Controller fans."""

from __future__ import annotations

import colorsys
import subprocess

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Rule,
    Static,
)

# --- Constants ---

COLOR_PRESETS: list[tuple[str, str]] = [
    ("Red", "ff0000"),
    ("Green", "00ff00"),
    ("Blue", "0000ff"),
    ("White", "ffffff"),
    ("Yellow", "ffff00"),
    ("Purple", "8000ff"),
    ("Orange", "ff6600"),
    ("Cyan", "00ffff"),
    ("Pink", "ff0080"),
    ("Warm White", "ffcc66"),
]

COLOR_MODES: list[tuple[str, str]] = [
    ("Fixed", "fixed"),
    ("Breathing", "breathing"),
    ("Fading", "fading"),
    ("Pulse", "pulse"),
    ("Spectrum Wave", "spectrum-wave"),
    ("Rainbow Pulse", "rainbow-pulse"),
    ("Rainbow Flow", "rainbow-flow"),
    ("Super Rainbow", "super-rainbow"),
    ("Covering Marquee", "covering-marquee"),
    ("Starry Night", "starry-night"),
    ("Candle", "candle"),
    ("Off", "off"),
]

NO_COLOR_MODES = {"spectrum-wave", "rainbow-pulse", "rainbow-flow", "super-rainbow", "off"}
SPEED_MODES = {"breathing", "fading", "pulse", "covering-marquee", "starry-night", "candle"}
SPEED_OPTIONS = ["slowest", "slower", "normal", "faster", "fastest"]

CHANNELS: list[tuple[str, str]] = [
    ("All Fans", "sync"),
    ("Fan 1", "led1"),
    ("Fan 2", "led2"),
    ("Fan 3", "led3"),
]

# Build a hue bar string: 36 colored blocks spanning the hue spectrum
HUE_BAR_STEPS = 36
HUE_BAR_CHARS = ""
for i in range(HUE_BAR_STEPS):
    h = i / HUE_BAR_STEPS
    r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
    ri, gi, bi = int(r * 255), int(g * 255), int(b * 255)
    HUE_BAR_CHARS += f"[rgb({ri},{gi},{bi})]\u2588[/]"


CSS = """
Screen {
    background: $surface;
}

#main {
    padding: 1 2;
    height: auto;
}

.section-title {
    text-style: bold;
    color: $text;
    margin-top: 1;
    margin-bottom: 0;
}

#color-preview {
    width: 100%;
    height: 3;
    margin: 1 0;
    content-align: center middle;
    text-align: center;
    text-style: bold;
}

#hue-bar {
    width: 100%;
    height: 1;
    margin: 0 0;
}

.input-row {
    height: 3;
    margin: 0 0;
}

.input-label {
    width: 6;
    height: 3;
    content-align: left middle;
}

.hsv-input {
    width: 12;
    height: 3;
}

#hex-input {
    width: 16;
    height: 3;
}

#presets-row {
    height: auto;
    layout: grid;
    grid-size: 5;
    grid-gutter: 1;
    margin: 0 0;
}

.preset-btn {
    width: 100%;
    min-width: 12;
}

#mode-row {
    height: auto;
    layout: grid;
    grid-size: 4;
    grid-gutter: 1;
    margin: 0 0;
}

.mode-btn {
    width: 100%;
    min-width: 14;
}

.mode-btn.-active {
    background: $accent;
    color: $text;
    text-style: bold;
}

#speed-row {
    height: auto;
    layout: grid;
    grid-size: 5;
    grid-gutter: 1;
    margin: 0 0;
}

.speed-btn {
    width: 100%;
}

.speed-btn.-active {
    background: $accent;
    color: $text;
    text-style: bold;
}

#channel-row {
    height: auto;
    layout: grid;
    grid-size: 4;
    grid-gutter: 1;
    margin: 0 0;
}

.channel-btn {
    width: 100%;
}

.channel-btn.-active {
    background: $accent;
    color: $text;
    text-style: bold;
}

#speed-section {
    height: auto;
}

#apply-btn {
    margin: 1 0;
    width: 100%;
    height: 3;
}

#status-bar {
    height: 1;
    dock: bottom;
    background: $boost;
    padding: 0 2;
}
"""


def hex_to_hsv(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s * 100, v * 100


def hsv_to_hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h / 360, s / 100, v / 100)
    return f"{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class RGBControlApp(App):
    TITLE = "NZXT RGB Control"
    CSS = CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+a", "apply", "Apply"),
    ]

    hue: reactive[float] = reactive(0.0)
    saturation: reactive[float] = reactive(100.0)
    brightness: reactive[float] = reactive(100.0)
    selected_mode: reactive[str] = reactive("fixed")
    selected_speed: reactive[str] = reactive("normal")
    selected_channel: reactive[str] = reactive("sync")
    _updating: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            yield Static("", id="color-preview")

            # Hue spectrum bar
            yield Static(HUE_BAR_CHARS, id="hue-bar", markup=True)

            yield Label("Color", classes="section-title")
            with Horizontal(classes="input-row"):
                yield Static("Hue", classes="input-label")
                yield Input(value="0", id="hue-input", classes="hsv-input")
                yield Static("  (0-360)", classes="input-label")
            with Horizontal(classes="input-row"):
                yield Static("Sat", classes="input-label")
                yield Input(value="100", id="sat-input", classes="hsv-input")
                yield Static("  (0-100)", classes="input-label")
            with Horizontal(classes="input-row"):
                yield Static("Val", classes="input-label")
                yield Input(value="100", id="val-input", classes="hsv-input")
                yield Static("  (0-100)", classes="input-label")
            with Horizontal(classes="input-row"):
                yield Static("Hex", classes="input-label")
                yield Input(value="#ff0000", max_length=7, id="hex-input")

            # Presets
            yield Label("Presets", classes="section-title")
            with Horizontal(id="presets-row"):
                for name, _hex in COLOR_PRESETS:
                    yield Button(name, id=f"preset-{_hex}", classes="preset-btn")

            # Mode
            yield Label("Mode", classes="section-title")
            with Horizontal(id="mode-row"):
                for label, mode_id in COLOR_MODES:
                    yield Button(label, id=f"mode-{mode_id}", classes="mode-btn")

            # Speed
            with Vertical(id="speed-section"):
                yield Label("Speed", classes="section-title", id="speed-label")
                with Horizontal(id="speed-row"):
                    for speed in SPEED_OPTIONS:
                        yield Button(speed.capitalize(), id=f"speed-{speed}", classes="speed-btn")

            # Channel
            yield Label("Channel", classes="section-title")
            with Horizontal(id="channel-row"):
                for label, ch_id in CHANNELS:
                    yield Button(label, id=f"channel-{ch_id}", classes="channel-btn")

            yield Rule()
            yield Button("Apply  (Ctrl+A)", id="apply-btn", variant="success")

        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._update_active_buttons()
        self._update_preview()
        self._update_speed_visibility()

    def _update_preview(self) -> None:
        hex_color = hsv_to_hex(self.hue, self.saturation, self.brightness)
        preview = self.query_one("#color-preview", Static)
        preview.styles.background = f"#{hex_color}"
        luma = (self.brightness / 100) * (1 - self.saturation / 200)
        preview.styles.color = "white" if luma < 0.6 else "black"
        preview.update(f"#{hex_color}")

    def _update_active_buttons(self) -> None:
        for _, mode_id in COLOR_MODES:
            try:
                self.query_one(f"#mode-{mode_id}", Button).set_class(
                    mode_id == self.selected_mode, "-active"
                )
            except NoMatches:
                pass
        for speed in SPEED_OPTIONS:
            try:
                self.query_one(f"#speed-{speed}", Button).set_class(
                    speed == self.selected_speed, "-active"
                )
            except NoMatches:
                pass
        for _, ch_id in CHANNELS:
            try:
                self.query_one(f"#channel-{ch_id}", Button).set_class(
                    ch_id == self.selected_channel, "-active"
                )
            except NoMatches:
                pass

    def _update_speed_visibility(self) -> None:
        try:
            self.query_one("#speed-section").display = self.selected_mode in SPEED_MODES
        except NoMatches:
            pass

    def _safe_float(self, val: str, lo: float, hi: float) -> float | None:
        try:
            v = float(val)
            return max(lo, min(hi, v))
        except ValueError:
            return None

    @on(Input.Changed, "#hue-input")
    def on_hue_input(self, event: Input.Changed) -> None:
        if self._updating:
            return
        v = self._safe_float(event.value, 0, 360)
        if v is not None:
            self.hue = v
            self._sync_hex_from_hsv()
            self._update_preview()

    @on(Input.Changed, "#sat-input")
    def on_sat_input(self, event: Input.Changed) -> None:
        if self._updating:
            return
        v = self._safe_float(event.value, 0, 100)
        if v is not None:
            self.saturation = v
            self._sync_hex_from_hsv()
            self._update_preview()

    @on(Input.Changed, "#val-input")
    def on_val_input(self, event: Input.Changed) -> None:
        if self._updating:
            return
        v = self._safe_float(event.value, 0, 100)
        if v is not None:
            self.brightness = v
            self._sync_hex_from_hsv()
            self._update_preview()

    def _sync_hex_from_hsv(self) -> None:
        self._updating = True
        hex_color = hsv_to_hex(self.hue, self.saturation, self.brightness)
        try:
            self.query_one("#hex-input", Input).value = f"#{hex_color}"
        except NoMatches:
            pass
        self._updating = False

    @on(Input.Changed, "#hex-input")
    def on_hex_input_changed(self, event: Input.Changed) -> None:
        if self._updating:
            return
        raw = event.value.lstrip("#")
        if len(raw) == 6:
            try:
                int(raw, 16)
            except ValueError:
                return
            h, s, v = hex_to_hsv(raw)
            self.hue, self.saturation, self.brightness = h, s, v
            self._updating = True
            try:
                self.query_one("#hue-input", Input).value = str(int(h))
                self.query_one("#sat-input", Input).value = str(int(s))
                self.query_one("#val-input", Input).value = str(int(v))
            except NoMatches:
                pass
            self._updating = False
            self._update_preview()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id.startswith("preset-"):
            self._set_color_from_hex(btn_id.removeprefix("preset-"))
        elif btn_id.startswith("mode-"):
            self.selected_mode = btn_id.removeprefix("mode-")
            self._update_active_buttons()
            self._update_speed_visibility()
        elif btn_id.startswith("speed-"):
            self.selected_speed = btn_id.removeprefix("speed-")
            self._update_active_buttons()
        elif btn_id.startswith("channel-"):
            self.selected_channel = btn_id.removeprefix("channel-")
            self._update_active_buttons()
        elif btn_id == "apply-btn":
            self.action_apply()

    def _set_color_from_hex(self, hex_color: str) -> None:
        h, s, v = hex_to_hsv(hex_color)
        self.hue, self.saturation, self.brightness = h, s, v
        self._updating = True
        try:
            self.query_one("#hue-input", Input).value = str(int(h))
            self.query_one("#sat-input", Input).value = str(int(s))
            self.query_one("#val-input", Input).value = str(int(v))
            self.query_one("#hex-input", Input).value = f"#{hex_color}"
        except NoMatches:
            pass
        self._updating = False
        self._update_preview()

    def _set_status(self, msg: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(msg)
        except NoMatches:
            pass

    @work(thread=True)
    def action_apply(self) -> None:
        mode = self.selected_mode
        channel = self.selected_channel
        speed = self.selected_speed
        hex_color = hsv_to_hex(self.hue, self.saturation, self.brightness)

        self.call_from_thread(self._set_status, f"Applying {mode} #{hex_color} to {channel}...")

        cmd = ["liquidctl", "--match", "RGB Controller"]

        try:
            subprocess.run(cmd + ["initialize"], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            self.call_from_thread(self._set_status, f"Init failed: {e.stderr.strip()}")
            return

        color_cmd = cmd + ["set", channel, "color", mode]
        if mode not in NO_COLOR_MODES:
            color_cmd.append(hex_color)
        if mode in SPEED_MODES:
            color_cmd.extend(["--speed", speed])

        try:
            subprocess.run(color_cmd, capture_output=True, text=True, check=True)
            self.call_from_thread(self._set_status, f"Applied {mode} #{hex_color} to {channel}")
        except subprocess.CalledProcessError as e:
            self.call_from_thread(self._set_status, f"Error: {e.stderr.strip()}")


def main() -> None:
    RGBControlApp().run()


if __name__ == "__main__":
    main()
