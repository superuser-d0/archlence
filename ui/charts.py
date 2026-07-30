from math import sin, cos, radians
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import NumericProperty
from kivy.uix.widget import Widget
from kivy.graphics import (
    Color, Line, RoundedRectangle, Ellipse, Rectangle,
    PushMatrix, PopMatrix, Translate,
)
from kivy.core.text import Label as CoreLabel  # type: ignore
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.app import MDApp
from services.transaction_service import TransactionService
from ui.i18n import tr as _t
from ui import theme as ftheme

# Forward import
from ui.components import LegendWidget


# Metin dokuları çizim animasyonu boyunca her karede yeniden üretilmesin diye
# önbelleklenir. Renk dokuya (texture) pişirilir; kaybolma/belirme efektleri
# dokuyu değil, önüne konan Color komutunun alfasını değiştirir — böylece aynı
# metin animasyon boyunca tek doku kullanır.
_LABEL_TEXTURE_CACHE = {}


def _label_texture(text, font_size, color, bold=False):
    key = (text, round(float(font_size), 1),
           tuple(round(float(c), 3) for c in color), bold)
    tex = _LABEL_TEXTURE_CACHE.get(key)
    if tex is None:
        if len(_LABEL_TEXTURE_CACHE) > 512:
            _LABEL_TEXTURE_CACHE.clear()
        lbl = CoreLabel(text=text, font_size=font_size, color=color, bold=bold)  # type: ignore
        lbl.refresh()
        tex = lbl.texture
        _LABEL_TEXTURE_CACHE[key] = tex
    return tex


class CurvedTrendChart(Widget):
    """Zaman içindeki gelir ve gider trendlerini gösteren eğimli alan (area) grafiği çizer.
    Beklenen veri formatı (self.chart_data):
    [{'label': '01 Eki', 'income': 1500.0, 'expense': 800.0, 'opening': 0.0}, ...]

    `opening` (hesap açılış bakiyesi) isteğe bağlıdır: yalnızca sıfırdan
    büyük bir değeri olduğunda kendi serisi ve lejant girdisiyle çizilir —
    her kullanıcıda görünen kalıcı bir sıfır çizgisi eklemez.
    """

    anim_progress = NumericProperty(0.0)

    # Seri renkleri ui.theme'den TEMA-DUYARLI okunur (bkz. ftheme._CHART_SERIES);
    # burada sabit tutulamazlar çünkü açık ve koyu temada farklı basamaklar
    # kullanılır. Pastadaki 'Ana Gelir' / 'Temel Gider' / 'Açılış Bakiyesi'
    # dilimleriyle aynı rolleri paylaşır — tek kaynak olduğu için artık
    # birbirinden ayrışamazlar.
    FILL_ALPHA = 0.16

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_data = []
        self._translate = None
        # pos değişimi (kaydırma, sekme geçiş animasyonu) canvas'ı YENİDEN
        # KURMAZ; yalnızca Translate güncellenir. Tam yeniden çizim sadece
        # boyut/animasyon değişiminde ve aynı kare içinde tek sefer yapılır.
        self._redraw_trigger = Clock.create_trigger(self._redraw, 0)
        self.bind(size=self._redraw_trigger, anim_progress=self._redraw_trigger)
        self.bind(pos=self._sync_translate)

    def _sync_translate(self, *args):
        if self._translate is not None:
            self._translate.x = self.x
            self._translate.y = self.y

    def request_redraw(self):
        self.anim_progress = 0.0
        from kivy.animation import Animation
        Animation(anim_progress=1.0, duration=1.1, t="out_cubic").start(self)

    def draw_immediate(self):
        """Animasyonsuz tek karelik çizim (iskelet/boş şablon için)."""
        from kivy.animation import Animation
        Animation.cancel_all(self, "anim_progress")
        self.anim_progress = 1.0
        self._redraw_trigger()


    # ── Catmull-Rom smooth interpolation ──────────────────────────────────
    @staticmethod
    def _catmull_rom(pts, steps=16):
        if len(pts) < 2:
            return list(pts)
        result = []
        n = len(pts)
        for i in range(n - 1):
            p0 = pts[max(i - 1, 0)]
            p1 = pts[i]
            p2 = pts[min(i + 1, n - 1)]
            p3 = pts[min(i + 2, n - 1)]
            extra = 1 if i == n - 2 else 0
            for s in range(steps + extra):
                t  = s / steps
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t
                            + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2
                            + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
                y = 0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t
                            + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2
                            + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
                result.append((x, max(y, 0)))
        return result

    @staticmethod
    def _fmt_k(val):
        if val >= 1_000_000:
            v = val / 1_000_000
            return f"{v:.0f}M" if v == int(v) else f"{v:.1f}M"
        if val >= 1_000:
            v = val / 1_000
            return f"{v:.0f}k" if v == int(v) else f"{v:.1f}k"
        return str(int(val))

    def _redraw(self, *args):
        if not self.canvas: return
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return

        from kivy.graphics import Mesh as KMesh

        p    = self.anim_progress
        data = self.chart_data
        app = MDApp.get_running_app()
        style = app.theme_cls.theme_style if app is not None else "Light"
        axis_color = ftheme.chart_axis(style)
        grid_color = ftheme.chart_grid(style)
        label_color = ftheme.chart_label(style)
        a = self.FILL_ALPHA
        income_line = ftheme.chart_series(style, "income")
        income_fill = ftheme.chart_series(style, "income", a)
        expense_line = ftheme.chart_series(style, "expense")
        expense_fill = ftheme.chart_series(style, "expense", a)
        opening_line = ftheme.chart_series(style, "opening")
        opening_fill = ftheme.chart_series(style, "opening", a)

        # ── Layout margins ────────────────────────────────────────────────
        PAD_LEFT  = dp(50)   # Y-axis label gutter (wider for larger font)
        PAD_RIGHT = dp(14)
        PAD_TOP   = dp(14)
        PAD_BOT   = dp(28)   # X-axis label gutter

        # Çizim (0,0) tabanlıdır; widget konumu Translate ile uygulanır. Böylece
        # kaydırma/sekme geçişi gibi yalnız pos'un değiştiği karelerde canvas
        # yeniden kurulmaz (layout thrashing'in ana kaynağıydı).
        cx0 = PAD_LEFT
        cx1 = self.width - PAD_RIGHT
        cy0 = PAD_BOT
        cy1 = self.height - PAD_TOP
        cw  = max(1, cx1 - cx0)
        ch  = max(1, cy1 - cy0)

        with self.canvas:
            PushMatrix()
            self._translate = Translate(self.x, self.y)

            # ── No-data state ─────────────────────────────────────────────
            # Yalnız eksen iskeleti çizilir; "Veri Yok" metnini tutucudaki
            # empty_label gösterir (ikisi birden çizilince üst üste biniyordu).
            if not data:
                Color(*axis_color)
                Line(points=[cx0, cy0, cx1, cy0], width=dp(1))
                Line(points=[cx0, cy0, cx0, cy1], width=dp(1))
                PopMatrix()
                return

            n = len(data)

            # ── Nice Y-axis range ───────────────────────────────────────────
            all_inc = [d['income']  for d in data]
            all_exp = [d['expense'] for d in data]
            # 'opening' eski çağıranların sözlüklerinde bulunmayabilir; .get ile
            # okunur ki üçüncü seri opsiyonel kalsın.
            all_opn = [d.get('opening', 0) or 0 for d in data]
            has_opening = any(v > 0 for v in all_opn)
            raw_max = max(max(all_inc), max(all_exp), max(all_opn), 1.0)

            # Round up to a clean step
            mag      = 10 ** (len(str(int(raw_max))) - 1)
            nice_max = (int(raw_max / mag) + 1) * mag
            N_TICKS  = 5
            y_step   = nice_max / N_TICKS

            # ── Coordinate helpers ──────────────────────────────────────────
            def px(i):  return cx0 + i * cw / max(1, n - 1)
            def py(v):  return cy0 + (v / nice_max) * ch

            # ── Horizontal grid + Y labels ────────────────────────────────
            for t in range(N_TICKS + 1):
                val = t * y_step
                gy  = py(val)
                Color(*grid_color)
                Line(points=[cx0, gy, cx1, gy], width=dp(0.5))
                # Y label
                lt = _label_texture(self._fmt_k(val), dp(11),
                                    (*label_color[:3], 0.9))
                Color(1, 1, 1, 0.9)
                Rectangle(texture=lt,
                          pos=(cx0 - lt.width - dp(4), gy - lt.height / 2),
                          size=lt.size)

            # ── X-axis labels (sparse, ≤6 visible) ────────────────────────
            x_step = max(1, n // 6)
            for i, d in enumerate(data):
                if i % x_step != 0 and i != n - 1:
                    continue
                lx = px(i)
                xt = _label_texture(d['label'], dp(11),
                                    (*label_color[:3], 0.9))
                Color(1, 1, 1, 0.9)
                Rectangle(texture=xt,
                          pos=(max(cx0, min(lx - xt.width / 2, cx1 - xt.width)),
                               cy0 - xt.height - dp(4)),
                          size=xt.size)

            # ── Axis lines ───────────────────────────────────────────────
            Color(*axis_color)
            Line(points=[cx0, cy0, cx1, cy0], width=dp(1.2))
            Line(points=[cx0, cy0, cx0, cy1], width=dp(1.2))

            # ── Series drawing helper ──────────────────────────────────────
            def draw_series(key, line_col, fill_col, dot_r=dp(3.5)):
                raw_pts  = [(px(i), py(d.get(key, 0) or 0)) for i, d in enumerate(data)]
                # Clip to animation progress
                clip_x   = cx0 + cw * p
                visible  = [(x, y) for x, y in raw_pts if x <= clip_x]
                if not visible:
                    return
                # Interpolate last partial segment
                if len(visible) < len(raw_pts):
                    x0_, y0_ = raw_pts[len(visible) - 1]
                    x1_, y1_ = raw_pts[len(visible)]
                    frac = (clip_x - x0_) / max(1, x1_ - x0_)
                    frac = max(0.0, min(1.0, frac))
                    visible.append((clip_x, y0_ + (y1_ - y0_) * frac))

                smooth = self._catmull_rom(visible, 16) if len(visible) > 2 else list(visible)

                # — Filled area (mesh triangles) —————————————————
                nv       = len(smooth)
                verts    = []
                indices  = []
                for k2, (sx, sy) in enumerate(smooth):
                    verts += [sx, cy0, 0, 0,
                              sx, sy,  0, 0]
                    if k2 < nv - 1:
                        b = k2 * 2
                        indices += [b, b+1, b+2, b+2, b+1, b+3]

                if indices:
                    Color(*fill_col)
                    KMesh(vertices=verts, indices=indices, mode='triangles')

                # — Smooth line —————————————————————————————————
                flat = [c for xy in smooth for c in xy]
                if len(flat) >= 4:
                    Color(*line_col)
                    Line(points=flat, width=dp(2.0))

                # — Data point dots (appear after 60% animation) ————————
                if p > 0.6:
                    dot_alpha = min(1.0, (p - 0.6) * 2.5)
                    Color(*line_col[:3], dot_alpha)
                    for i_d, d_pt in enumerate(data):
                        dpx_, dpy_ = raw_pts[i_d]
                        if dpx_ <= clip_x + dp(2):
                            Ellipse(pos=(dpx_ - dot_r, dpy_ - dot_r),
                                    size=(dot_r * 2, dot_r * 2))

                # — Value label at rightmost visible point ————————————
                if p > 0.80 and visible:
                    la = min(1.0, (p - 0.80) * 5)
                    last_idx = min(len(visible) - 1, len(data) - 1)
                    last_val = data[last_idx].get(key, 0) or 0
                    if last_val > 0:
                        vt = _label_texture(self._fmt_k(last_val), dp(11),
                                            (*line_col[:3], 1.0), bold=True)
                        Color(1, 1, 1, la)
                        vx2 = min(cx1 - vt.width, visible[-1][0] + dp(4))
                        Rectangle(texture=vt,
                                  pos=(vx2, visible[-1][1] - vt.height / 2),
                                  size=vt.size)

            # Draw expense first (below income)
            draw_series('expense', expense_line, expense_fill)
            draw_series('income',  income_line,  income_fill)
            # Açılış bakiyesi yalnızca gerçekten varsa çizilir; yoksa her
            # kullanıcıya kalıcı bir sıfır çizgisi göstermiş olurduk.
            if has_opening:
                draw_series('opening', opening_line, opening_fill)

            # ── Mini legend top-right ─────────────────────────────────────
            if p > 0.8:
                leg_alpha = min(1.0, (p - 0.8) * 5.0)
                leg_y     = cy1 - dp(2)
                leg_x     = cx1
                legend_items = [('Gider', expense_line),
                                ('Gelir', income_line)]
                if has_opening:
                    legend_items.append(('Açılış', opening_line))
                for ltext, lcol in legend_items:
                    lt2 = _label_texture(ltext, dp(11), (*lcol[:3], 1.0), bold=True)
                    sw_w, sw_h = dp(16), dp(3)
                    # text
                    Color(1, 1, 1, leg_alpha)
                    tx2 = leg_x - lt2.width
                    Rectangle(texture=lt2,
                              pos=(tx2, leg_y - lt2.height / 2),
                              size=lt2.size)
                    # swatch
                    Color(*lcol[:3], leg_alpha)
                    RoundedRectangle(pos=(tx2 - sw_w - dp(3), leg_y - sw_h / 2),
                                     size=(sw_w, sw_h),
                                     radius=[sw_h / 2])
                    leg_x = tx2 - sw_w - dp(16)

            PopMatrix()


class HealthScoreSparkline(Widget):
    """Finansal sağlık skorunun 0-100 aralığındaki günlük mini trendi."""

    anim_progress = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_data = []
        self._translate = None
        self._redraw_trigger = Clock.create_trigger(self._redraw, 0)
        self.bind(size=self._redraw_trigger, anim_progress=self._redraw_trigger)
        self.bind(pos=self._sync_translate)

    def _sync_translate(self, *args):
        if self._translate is not None:
            self._translate.x = self.x
            self._translate.y = self.y

    def request_redraw(self):
        from kivy.animation import Animation
        Animation.cancel_all(self, "anim_progress")
        self.anim_progress = 0.0
        Animation(
            anim_progress=1.0, duration=0.75, t="out_cubic",
        ).start(self)

    def draw_immediate(self):
        from kivy.animation import Animation
        Animation.cancel_all(self, "anim_progress")
        self.anim_progress = 1.0
        self._redraw_trigger()

    @staticmethod
    def _score_role(score):
        if score >= 60:
            return "green"
        if score >= 40:
            return "amber"
        return "red"

    def _redraw(self, *args):
        if not self.canvas:
            return
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return

        data = self.chart_data
        app = MDApp.get_running_app()
        style = app.theme_cls.theme_style if app is not None else "Light"
        axis_color = ftheme.chart_axis(style)
        grid_color = ftheme.chart_grid(style)

        left, right = dp(4), max(dp(5), self.width - dp(4))
        bottom, top = dp(4), max(dp(5), self.height - dp(4))
        width = max(1, right - left)
        height = max(1, top - bottom)

        with self.canvas:
            PushMatrix()
            self._translate = Translate(self.x, self.y)

            # Sabit 0-100 ölçeğinin sınır ve orta çizgileri.
            for value in (0, 50, 100):
                y = bottom + height * value / 100.0
                Color(*(axis_color if value in (0, 100) else grid_color))
                Line(points=[left, y, right, y], width=dp(0.6))

            if len(data) < 2:
                PopMatrix()
                return

            def px(index):
                return left + index * width / (len(data) - 1)

            def py(score):
                value = max(0.0, min(100.0, float(score)))
                return bottom + height * value / 100.0

            raw_points = [
                (px(index), py(item["score"]))
                for index, item in enumerate(data)
            ]
            smooth = CurvedTrendChart._catmull_rom(raw_points, steps=12)
            smooth = [
                (x, max(bottom, min(top, y))) for x, y in smooth
            ]

            clip_x = left + width * self.anim_progress
            visible = [(x, y) for x, y in smooth if x <= clip_x]
            if len(visible) >= 2:
                flat = [coordinate for point in visible for coordinate in point]
                score = float(data[-1]["score"])
                line_color = ftheme.accent(style, self._score_role(score))
                Color(*line_color)
                Line(points=flat, width=dp(2.0))

                if self.anim_progress > 0.85:
                    dot_radius = dp(3)
                    Color(*line_color)
                    Ellipse(
                        pos=(raw_points[-1][0] - dot_radius,
                             raw_points[-1][1] - dot_radius),
                        size=(dot_radius * 2, dot_radius * 2),
                    )

            PopMatrix()


class ScenarioComparisonChart(Widget):
    """Taban ve what-if servet serilerini aynı eksende karşılaştırır."""

    anim_progress = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_series = []
        self.scenario_series = []
        self._translate = None
        self._redraw_trigger = Clock.create_trigger(self._redraw, 0)
        self.bind(size=self._redraw_trigger, anim_progress=self._redraw_trigger)
        self.bind(pos=self._sync_translate)

    def _sync_translate(self, *args):
        if self._translate is not None:
            self._translate.x = self.x
            self._translate.y = self.y

    def set_series(self, base_series, scenario_series):
        self.base_series = list(base_series or [])
        self.scenario_series = list(scenario_series or [])
        self.request_redraw()

    def request_redraw(self):
        from kivy.animation import Animation
        Animation.cancel_all(self, "anim_progress")
        self.anim_progress = 0.0
        Animation(
            anim_progress=1.0, duration=0.8, t="out_cubic",
        ).start(self)

    def draw_immediate(self):
        from kivy.animation import Animation
        Animation.cancel_all(self, "anim_progress")
        self.anim_progress = 1.0
        self._redraw_trigger()

    def _redraw(self, *args):
        if not self.canvas:
            return
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return

        app = MDApp.get_running_app()
        style = app.theme_cls.theme_style if app is not None else "Light"
        axis_color = ftheme.chart_axis(style)
        grid_color = ftheme.chart_grid(style)
        base_color = ftheme.accent(style, "muted")

        left, right = dp(8), max(dp(9), self.width - dp(8))
        bottom, top = dp(12), max(dp(13), self.height - dp(18))
        chart_width = max(1, right - left)
        chart_height = max(1, top - bottom)
        all_values = [
            float(value)
            for series in (self.base_series, self.scenario_series)
            for _day, value in series
        ]

        with self.canvas:
            PushMatrix()
            self._translate = Translate(self.x, self.y)
            Color(*axis_color)
            Line(points=[left, bottom, right, bottom], width=dp(0.8))

            if not all_values:
                PopMatrix()
                return

            low, high = min(all_values), max(all_values)
            if low == high:
                padding = max(1.0, abs(low) * 0.05)
            else:
                padding = (high - low) * 0.08
            low -= padding
            high += padding
            value_span = max(1e-9, high - low)
            max_day = max(
                (day for series in (self.base_series, self.scenario_series)
                 for day, _value in series),
                default=1,
            )

            def px(day):
                return left + (float(day) / max(1, max_day)) * chart_width

            def py(value):
                return bottom + ((float(value) - low) / value_span) * chart_height

            for fraction in (0.0, 0.5, 1.0):
                y = bottom + chart_height * fraction
                Color(*grid_color)
                Line(points=[left, y, right, y], width=dp(0.5))

            if low <= 0 <= high:
                Color(*axis_color)
                Line(points=[left, py(0), right, py(0)], width=dp(0.8))

            difference = (
                self.scenario_series[-1][1] - self.base_series[-1][1]
                if self.base_series and self.scenario_series else 0
            )
            scenario_role = "green" if difference > 0 else (
                "red" if difference < 0 else "amber"
            )
            scenario_color = ftheme.accent(style, scenario_role)
            clip_x = left + chart_width * self.anim_progress

            def draw_series(series, color, width):
                if len(series) < 2:
                    return
                raw = [(px(day), py(value)) for day, value in series]
                smooth = CurvedTrendChart._catmull_rom(raw, steps=10)
                smooth = [
                    (x, max(bottom, min(top, y)))
                    for x, y in smooth if x <= clip_x
                ]
                if len(smooth) >= 2:
                    Color(*color)
                    Line(
                        points=[c for point in smooth for c in point],
                        width=dp(width),
                    )

            draw_series(self.base_series, base_color, 1.4)
            draw_series(self.scenario_series, scenario_color, 2.2)
            PopMatrix()



# ---------------------------------------------------------------------------
# DashboardChartManager — Persistent layout manager (instances created ONCE)
# ---------------------------------------------------------------------------

class DashboardChartManager(MDBoxLayout):
    """Manages PieChart + LegendWidget (left column) and CurvedTrendChart (right column)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pie_widget    = PieChart(size_hint=(1, 1))
        self.legend_widget = LegendWidget(size_hint_x=1, size_hint_y=None, height=dp(64))
        self.trend_chart   = CurvedTrendChart(size_hint=(1, 1))
        Clock.schedule_once(self._attach_widgets, 0)

    def _attach_widgets(self, *args):
        pie_box   = next((c for c in self.children if getattr(c, "id", None) == "pie_chart_box"), None)
        comp_box  = next((c for c in self.children if getattr(c, "id", None) == "comparison_chart_box"), None)

        if pie_box is None or comp_box is None:
            kids = list(reversed(self.children))
            if len(kids) >= 2:
                pie_box  = kids[0]
                comp_box = kids[1]

        # Her grafik, kendi FloatLayout tutucusuna sarılır; böylece grafiğin TAM
        # ORTASINA bir MDSpinner bindirebiliyoruz. Yükleme sırasında grafik
        # opacity=0 (ham 'mavi halka' görünmez), spinner döner; veri gelince
        # spinner kalkar ve grafik fade-in ile pürüzsüzce belirir.
        if pie_box:
            pie_holder = self._make_chart_holder(self.pie_widget, _t("₺0\nVeri Yok"))
            self._pie_spinner = pie_holder._chart_spinner
            self._pie_empty_label = pie_holder._chart_empty_label
            pie_box.add_widget(pie_holder)
            pie_box.add_widget(self.legend_widget)
        if comp_box:
            comp_holder = self._make_chart_holder(self.trend_chart, _t("Veri Yok"))
            self._trend_spinner = comp_holder._chart_spinner
            self._trend_empty_label = comp_holder._chart_empty_label
            comp_box.add_widget(comp_holder)

    def _make_chart_holder(self, chart_widget, empty_text):
        """Grafiği + ortalanmış bir MDSpinner'ı taşıyan FloatLayout döndürür."""
        from kivy.uix.floatlayout import FloatLayout
        from kivymd.uix.spinner import MDSpinner

        holder = FloatLayout(size_hint=(1, 1))
        # DİKKAT: FloatLayout, pos_hint VERİLMEYEN çocuğun konumuna dokunmaz —
        # grafik pencerenin (0,0) köşesinde kalıp öteki kartların arkasında
        # çizilir (Varlıklarım'daki kayma/overlap hatasının kök nedeni buydu).
        # pos_hint ile grafik tutucusuna sabitlenir.
        chart_widget.size_hint = (1, 1)
        chart_widget.pos_hint = {"x": 0, "y": 0}
        holder.add_widget(chart_widget)
        from kivymd.uix.label import MDLabel
        empty_label = MDLabel(
            text=empty_text, halign="center", valign="center",
            theme_text_color="Secondary", font_style="H6",
            opacity=1,
            pos_hint={"x": 0, "y": 0},
        )
        empty_label.bind(size=empty_label.setter("text_size"))
        holder.add_widget(empty_label)
        spinner = MDSpinner(
            size_hint=(None, None), size=(dp(36), dp(36)),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            active=False, opacity=0,
        )
        holder.add_widget(spinner)
        holder._chart_spinner = spinner
        holder._chart_empty_label = empty_label
        return holder

    def _set_chart_empty_state(self, empty):
        opacity = 1 if empty else 0
        for label in (getattr(self, "_pie_empty_label", None),
                      getattr(self, "_trend_empty_label", None)):
            if label is not None:
                label.opacity = opacity

    def _set_charts_loading(self, loading):
        """Yükleme durumunu uygular: grafikleri gizle + spinnerları döndür,
        ya da spinnerları durdurup grafikleri fade-in ile geri getir."""
        from kivy.animation import Animation

        charts = [w for w in (self.pie_widget, self.legend_widget, self.trend_chart) if w is not None]
        spinners = [s for s in (getattr(self, "_pie_spinner", None),
                                getattr(self, "_trend_spinner", None)) if s is not None]
        if loading:
            # Veri gelmese bile boş grafik şablonu görünür kalsın. Önceki
            # opacity=0 yaklaşımı worker hata verdiğinde büyük boş alan bırakıyordu.
            for w in charts:
                Animation.cancel_all(w, "opacity")
                w.opacity = 1
            for s in spinners:
                s.active = True
                s.opacity = 1
        else:
            for s in spinners:
                s.active = False
                s.opacity = 0
            for w in charts:
                Animation.cancel_all(w, "opacity")
                # Ham çizim görünmesin diye 0'dan başlatıp pürüzsüz belirt.
                w.opacity = 0
                Animation(opacity=1, duration=0.35, t="out_quad").start(w)


    # ── Public API ───────────────────────────────────────────────────────────

    def refresh_dashboard(self, period, force=False):
        """Veri değiştiyse arka planda okuyup grafikleri günceller.

        Aynı dönem daha önce güncel finansal sürümle çizildiyse widget/canvas
        olduğu gibi korunur; spinner, sorgu ve animasyon tekrar başlatılmaz.
        """
        import threading
        from services.asset_service import financial_chart_cache_key

        cache_key = financial_chart_cache_key(period)
        if not force and getattr(self, "_rendered_cache_key", None) == cache_key:
            return False

        # Üst üste binen tazelemelerde yalnız en son istek arayüze yazar; eski
        # thread'lerin geciken sonuçları grafikleri geri saramaz.
        self._refresh_generation = getattr(self, "_refresh_generation", 0) + 1
        generation = self._refresh_generation

        # İlk karede güvenli 0 şablonunu ANİMASYONSUZ çiz; spinner bunun
        # üzerinde döner. (Eski request_redraw çağrıları iskelet için bile
        # ~1 sn'lik kare-başına yeniden çizim animasyonu başlatıyordu.)
        empty_totals = {
            'Ana Gelir': 0, 'Ek Gelir': 0,
            'Temel Gider': 0, 'Ekstra Gider': 0, 'Açılış Bakiyesi': 0,
        }
        self.pie_widget.data = empty_totals
        self.pie_widget.draw_immediate()
        self.legend_widget.update_percentages(empty_totals)
        self.trend_chart.chart_data = []
        self.trend_chart.draw_immediate()
        self._set_chart_empty_state(True)
        self._set_charts_loading(True)

        def _load():
            try:
                raw_data = TransactionService.get_transactions_by_period(period)
            except Exception as exc:
                print("Dashboard grafik verisi okunamadı:", exc)
                raw_data = []
            try:
                # Açılış bakiyesi `transactions`'a hiç yazılmaz (bkz.
                # get_opening_events_by_period docstring'i) — yeni açılan
                # tek hesaplı bir kullanıcı hiç işlem girmeden HEM pastayı HEM
                # zaman grafiğini "Veri Yok" olarak görürdü. Her iki grafikte de
                # ayrı bir seri olarak çizilir; tasarruf oranı/sağlık skoru gibi
                # diğer hesaplara katılmaz.
                opening_events = TransactionService.get_opening_events_by_period(period)
            except Exception as exc:
                print("Açılış bakiyesi okunamadı:", exc)
                opening_events = []
            # Başarılı veya hatalı her yol ana thread'de loading'i sonlandırır.
            Clock.schedule_once(
                lambda dt: self._apply_data_safely(
                    raw_data, period, generation, opening_events,
                    cache_key,
                ), 0
            )

        threading.Thread(target=_load, daemon=True).start()
        return True

    def refresh_theme(self):
        """Mevcut veriyi koruyarak tema-duyarlı canvas renklerini tazele."""
        if self.pie_widget is not None:
            self.pie_widget.draw_immediate()
        if self.trend_chart is not None:
            self.trend_chart.draw_immediate()
        # Lejant noktaları canvas değil widget: yeniden çizimle tazelenmez,
        # açıkça güncellenmezse pasta koyu basamağa geçerken lejant açık
        # basamakta kalırdı.
        if self.legend_widget is not None:
            self.legend_widget.refresh_theme()

    # Legacy shim so any existing callers (on_tab_press etc.) keep working
    def render_dashboard(self, period):
        self.refresh_dashboard(period)

    # ── Internal update (always runs on the main thread) ─────────────────────

    def _apply_data_safely(
            self, raw_data, period, generation=None, opening_events=None,
            requested_cache_key=None):
        if generation is not None and generation != getattr(self, "_refresh_generation", 0):
            return  # bayat sonuç — daha yeni bir tazeleme başladı
        if requested_cache_key is not None:
            from services.asset_service import financial_chart_cache_key
            if requested_cache_key != financial_chart_cache_key(period):
                # Okuma sürerken finansal yazım oldu; karışık/bayat snapshot'ı
                # bir kare bile göstermeden yeni sürümü yükle.
                self.refresh_dashboard(period)
                return
        try:
            self._apply_data(raw_data, period, opening_events)
            if requested_cache_key is not None:
                self._rendered_cache_key = requested_cache_key
        except Exception as exc:
            print("Dashboard grafikleri çizilemedi:", exc)
            # Canvas/veri biçimi hatası dahi spinner ve opacity'yi kilitlemez.
            self._set_charts_loading(False)

    def _apply_data(self, raw_data, period, opening_events=None):
        # 1. Aggregate 5-category totals for PieChart + Legend
        cat_totals = {
            'Ana Gelir': 0.0, 'Ek Gelir': 0.0,
            'Temel Gider': 0.0, 'Ekstra Gider': 0.0, 'Açılış Bakiyesi': 0.0,
        }
        for tx in raw_data or []:
            t_type = tx.get('type')
            try:
                amount = float(tx.get('amount') or 0)
            except (TypeError, ValueError):
                amount = 0
            importance = tx.get('importance', 'extra')
            if t_type == 'income':
                if importance == 'main': cat_totals['Ana Gelir']   += amount
                else:                    cat_totals['Ek Gelir']     += amount
            elif t_type == 'expense':
                if importance == 'main': cat_totals['Temel Gider'] += amount
                else:                    cat_totals['Ekstra Gider'] += amount
        cat_totals['Açılış Bakiyesi'] = sum(
            float(event.get('amount') or 0) for event in opening_events or []
        )

        # Update PieChart
        first_render = not getattr(self, "_has_rendered_data", False)
        self.pie_widget.data = cat_totals
        if first_render:
            self.pie_widget.request_redraw()
        else:
            self.pie_widget.draw_immediate()

        # Update Legend with percentages
        self.legend_widget.update_percentages(cat_totals)

        # 2. Build time-bucketed data for CurvedTrendChart
        try:
            buckets = self._build_time_buckets(
                raw_data or [], period, opening_events
            )
        except Exception as exc:
            print("Dashboard zaman grafiği hazırlanamadı:", exc)
            buckets = []
        self.trend_chart.chart_data = buckets
        if first_render:
            self.trend_chart.request_redraw()
        else:
            self.trend_chart.draw_immediate()
        self._has_rendered_data = True
        has_chart_data = any(cat_totals.values()) or any(
            row.get("income", 0) or row.get("expense", 0) or row.get("opening", 0)
            for row in buckets
        )
        self._set_chart_empty_state(not has_chart_data)

        # Çizim işlemi tamamlandı: bir sonraki karede (gerçek veri opacity=0
        # iken çizildikten sonra) spinnerları kaldır ve grafiği fade-in ile
        # getir — kullanıcı ham/boş grafiği hiç görmez.
        Clock.schedule_once(lambda dt: self._set_charts_loading(False), 0)

    @staticmethod
    def _parse_tx_datetime(raw):
        """`transaction_date`'i hem tam zaman damgası hem yalnız tarih olarak okur.

        Kayıtlar iki biçimde bulunabiliyor: normal akış
        "%Y-%m-%d %H:%M:%S" yazar, CSV içe aktarımı ve yeniden planlama gibi
        yollar yalnız "%Y-%m-%d" üretebiliyor (services/insights_service.py
        ::_parse_date de aynı iki biçimi kabul ediyor). Katı tek biçim
        beklemek, tek bir tarih-only satır yüzünden TÜM zaman grafiğinin
        sessizce çizilmemesine yol açıyordu.
        """
        import datetime
        text = str(raw or "").strip()
        for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
            try:
                return datetime.datetime.strptime(text[:width], fmt)
            except ValueError:
                continue
        raise ValueError(f"Tanınmayan işlem tarihi: {raw!r}")

    def _build_time_buckets(
            self, raw_data, filter_text, opening_events=None, now=None):
        """Return list of {label, income, expense, opening} dicts for the period.

        `opening_events` hesap açılış bakiyeleridir (bkz. TransactionService.
        get_opening_events_by_period). `transactions` tablosunda bulunmadıkları
        için ayrı gelir ve grafikte KENDİ serilerinde çizilir — pasta
        grafiğindeki "Açılış Bakiyesi" dilimiyle aynı ilke: görünür olur ama
        gerçek gelir sayılmaz.

        Kovalama artık tek bir olay listesi üzerinden yapılıyor: eskiden her
        dönem dalı işlemleri kendi sözlüğüne ayrı ayrı topluyordu ve açılış
        olaylarını eklemek dört yerde tekrar gerektirirdi. Ayrıca 'Bugün' ve
        'Hayat Boyu' dallarında eksen aralığı (min saat / min yıl) yalnızca
        işlemlerden türetiliyordu; açılış olayı o aralığın dışında kalırsa
        sessizce çizilmezdi — birleşik liste bunu da çözer.
        """
        import datetime
        now = now or datetime.datetime.now()
        result = []

        def new_bucket():
            return {'inc': 0.0, 'exp': 0.0, 'opn': 0.0}

        events = []  # (datetime, 'inc'|'exp'|'opn', tutar)
        for tx in raw_data or []:
            dt = self._parse_tx_datetime(tx['transaction_date'])
            kind = 'inc' if tx.get('type') == 'income' else 'exp'
            events.append((dt, kind, float(tx.get('amount') or 0)))
        for event in opening_events or []:
            dt = self._parse_tx_datetime(event['transaction_date'])
            events.append((dt, 'opn', float(event.get('amount') or 0)))

        buckets = {}

        def add(key, kind, amount):
            buckets.setdefault(key, new_bucket())[kind] += amount

        def row(label, key):
            entry = buckets.get(key) or new_bucket()
            return {
                'label': label, 'income': entry['inc'],
                'expense': entry['exp'], 'opening': entry['opn'],
            }

        if filter_text == 'Bugün':
            for dt, kind, amount in events:
                if dt.date() == now.date():
                    add(f'{dt.hour:02d}', kind, amount)

            hours = sorted(int(k) for k in buckets)
            min_h = hours[0] if hours else max(0, now.hour - 4)
            max_h = max(hours[-1], now.hour) if hours else now.hour
            for h in range(min_h, max_h + 1):
                result.append(row(f'{h:02d}:00', f'{h:02d}'))

        elif filter_text in ('1 Hafta', '1 Ay'):
            days = 7 if filter_text == '1 Hafta' else 30
            start_dt = now - datetime.timedelta(days=days - 1)
            for dt, kind, amount in events:
                if dt.date() >= start_dt.date():
                    add(dt.strftime('%Y-%m-%d'), kind, amount)

            for d in range(days):
                dt = start_dt + datetime.timedelta(days=d)
                result.append(row(dt.strftime('%d %b'), dt.strftime('%Y-%m-%d')))

        elif filter_text == '1 Yıl':
            month_names = ['Oca','Şub','Mar','Nis','May','Haz','Tem','Ağu','Eyl','Eki','Kas','Ara']
            start_dt = now - datetime.timedelta(days=364)
            for dt, kind, amount in events:
                if dt.date() >= start_dt.date():
                    add(dt.strftime('%Y-%m'), kind, amount)

            for i in range(11, -1, -1):
                m = now.month - i
                y = now.year
                while m < 1:
                    m += 12
                    y -= 1
                result.append(
                    row(f"{month_names[m-1]} '{str(y)[2:]}", f'{y}-{m:02d}')
                )

        elif filter_text == 'Hayat Boyu':
            for dt, kind, amount in events:
                add(dt.strftime('%Y'), kind, amount)

            if buckets:
                min_year = int(min(buckets))
                for y in range(min_year, now.year + 1):
                    result.append(row(str(y), str(y)))

        # Filter out all-zero rows only when ALL rows are zero (keep axis visible)
        any_data = any(
            r['income'] > 0 or r['expense'] > 0 or r['opening'] > 0
            for r in result
        )
        if not any_data:
            return []   # empty → chart shows "Bu dönemde veri yok"
        return result


class HorizontalBarChart(Widget):
    """Yatay çubuk grafiği (horizontal bar chart) çizer.
    Beklenen veri formatı (self.data):
    {"Kategori Adı": 1500.0, "Diğer Kategori": 800.0, ...} (Dict)
    """
    anim_progress = NumericProperty(0)
    selected_targets = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_chart, size=self.update_chart, anim_progress=self.update_chart)
        self.data = {"Veri Bekleniyor": 1.0}
        # Gerçek renk update_chart'ta aktif temadan alınır (standart: Teal,
        # premium: Indigo); bu yalnızca tema yüklenmeden önceki geçici değer.
        self.colors = [tuple(ftheme.chart_empty("Light"))]

    def highlight_bar(self, targets):
        self.selected_targets = targets
        self.update_chart()

    def update_chart(self, *args):
        if not self.canvas: return
        self.canvas.clear()
        total = sum(self.data.values())
        if total == 0: return

        # Çubuk rengi aktif temanın primary'sinden gelir: standart temada Teal,
        # premium temada Indigo (#5444E5) — tema değişince otomatik uyar.
        _app = MDApp.get_running_app()
        if _app is not None:
            self.colors = [tuple(_app.theme_cls.primary_color)]

        with self.canvas:
            max_val = max(self.data.values())
            y_offset = self.y + 10
            bar_height = max(10, (self.height - 20) / max(1, len(self.data)) - 10)
            
            for i, (label, value) in reversed(list(enumerate(self.data.items()))):
                if value == 0: continue
                
                alpha = 1.0 if not getattr(self, 'selected_targets', []) or label in self.selected_targets else 0.3
                Color(*self.colors[i % len(self.colors)][:3], alpha)
                
                bar_width = (value / max_val) * self.width * self.anim_progress if max_val > 0 else 0
                RoundedRectangle(pos=(self.x, y_offset), size=(bar_width, bar_height), radius=[bar_height/2])
                
                if self.anim_progress > 0.8:
                    pct = (value / total) * 100
                    txt_alpha = min(1.0, max(0.0, (self.anim_progress - 0.8) * 5))
                    app = MDApp.get_running_app()
                    text_color = app.theme_cls.text_color if app else (0, 0, 0, 1)
                    
                    from kivy.core.text import Label as CoreLabel  # type: ignore
                    lbl = CoreLabel(text=f"%{pct:.1f}", font_size=14, color=(*text_color[:3], txt_alpha), bold=True)  # type: ignore
                    lbl.refresh()
                    tex = lbl.texture
                    
                    Color(1, 1, 1, 1) 
                    Rectangle(texture=tex, pos=(self.x + bar_width + 15, y_offset + (bar_height - tex.size[1]) / 2), size=tex.size)
                
                y_offset += bar_height + 10




class ConfettiWidget(Widget):
    """Birikim hedefinde bir eşik (%25/50/75/100) geçildiğinde tetiklenen kısa
    süreli konfeti patlaması. burst() çağrılana kadar tamamen pasif kalır; tüm
    parçacıklar söndüğünde kendi Clock'unu iptal eder; yalnızca aktifken
    tick atan bir döngü kullanılır.
    """

    PALETTE = [
        (0.95, 0.75, 0.1, 1), (0.1, 0.8, 0.2, 1), (0.3, 0.45, 0.95, 1),
        (0.9, 0.15, 0.15, 1), (0.8, 0.3, 0.9, 1),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._particles = []
        self._clock = None
        self.bind(pos=self._redraw, size=self._redraw)

    def burst(self, count=60):
        import random
        if self.width <= 0 or self.height <= 0:
            return
        cx, cy = self.center_x, self.top - dp(20)
        for _ in range(count):
            angle = random.uniform(0, 360)
            speed = random.uniform(dp(60), dp(220))
            self._particles.append({
                "x": cx, "y": cy,
                "vx": cos(radians(angle)) * speed,
                "vy": sin(radians(angle)) * speed + dp(150),
                "size": random.uniform(dp(4), dp(9)),
                "color": random.choice(self.PALETTE),
                "life": 1.0,
            })
        if self._clock is None:
            self._clock = Clock.schedule_interval(self._tick, 1 / 60.0)

    def _tick(self, dt):
        gravity = dp(350)
        alive = []
        for p in self._particles:
            p["vy"] -= gravity * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt * 0.6
            if p["life"] > 0 and p["y"] > self.y - dp(40):
                alive.append(p)
        self._particles = alive
        self._redraw()
        if not self._particles and self._clock is not None:
            self._clock.cancel()
            self._clock = None

    def _redraw(self, *args):
        if not self.canvas: return
        self.canvas.clear()
        if not self._particles:
            return
        with self.canvas:
            for p in self._particles:
                r, g, b, a = p["color"]
                Color(r, g, b, max(0.0, min(1.0, p["life"])))
                Ellipse(
                    pos=(p["x"] - p["size"] / 2, p["y"] - p["size"] / 2),
                    size=(p["size"], p["size"]),
                )

    def on_parent(self, *args):
        if not self.parent and self._clock is not None:
            self._clock.cancel()
            self._clock = None


class PieChart(Widget):
    """Ortası boş halka (donut/pie) grafiği çizer. Yüzdelikleri ve dilimleri animasyonlu gösterir.
    Beklenen veri formatı (self.data):
    {'Ana Gelir': 5000, 'Ek Gelir': 1500, 'Temel Gider': 3000, 'Ekstra Gider': 800,
     'Açılış Bakiyesi': 22500} (Dict)
    """
    anim_progress = NumericProperty(0)
    selected_targets = []
    
    def highlight_slice(self, targets):
        self.selected_targets = targets
        self.update_chart()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._translate = None
        # pos değişimi Translate ile uygulanır; tam yeniden çizim yalnızca
        # boyut/animasyon değişiminde ve kare başına tek sefer olur.
        self._redraw_trigger = Clock.create_trigger(self.update_chart, 0)
        self.bind(size=self._redraw_trigger, anim_progress=self._redraw_trigger)
        self.bind(pos=self._sync_translate)
        self.data = {"Veri Bekleniyor": 1.0}
        self.colors = [tuple(ftheme.chart_empty("Light"))]

    def fetch_real_data(self):
        # Deprecated: The logic was moved to ArchlenceApp.update_metrics_and_goals()
        # This is kept empty temporarily to avoid crashes if called before restart
        pass
    def update_chart(self, *args):
        if not self.canvas: return
        self.canvas.clear()
        
        # Dilim renkleri ve ÇİZİM SIRASI tek kaynaktan gelir (ui.theme). Sıra
        # renk körlüğü güvenliğinin parçasıdır: 'Açılış Bakiyesi' gelir ve gider
        # dilimlerinin arasına düşer, böylece yeşil-kırmızı aileleri komşu
        # olmaz (halka kapandığı için sarma çifti de doğrulandı).
        app = MDApp.get_running_app()
        style = app.theme_cls.theme_style if app is not None else "Light"
        self.category_colors = ftheme.chart_category_colors(style)

        from kivy.utils import get_color_from_hex

        # Calculate total
        total = sum(self.data.get(k, 0) for k in self.category_colors.keys()) if isinstance(self.data, dict) else 0

        # Çizim (0,0) tabanlı; widget konumu Translate ile uygulanır (bkz.
        # CurvedTrendChart._redraw'daki açıklama).
        local_cx = self.width / 2
        local_cy = self.height / 2

        with self.canvas:
            PushMatrix()
            self._translate = Translate(self.x, self.y)
            angle_start = 0
            d = min(self.width, self.height) * 0.8
            r = d / 2
            x = local_cx - r
            y = local_cy - r

            texts = []
            
            if total > 0:
                valid_slices = len([k for k in self.category_colors.keys() if self.data.get(k, 0) > 0])
                
                # 1. Dilimlerin Çizimi (Slices)
                for label, hex_color in self.category_colors.items():
                    value = self.data.get(label, 0)
                    if value == 0: continue
                    
                    slice_angle = (value / total) * 360
                    draw_angle = max(0, slice_angle - 2) if total > 1 and valid_slices > 1 else slice_angle
                    angle_end = angle_start + (draw_angle * self.anim_progress)
                    mid_angle = angle_start + (slice_angle / 2)
                    
                    slice_color = get_color_from_hex(hex_color)
                    alpha = 1.0 if not getattr(self, 'selected_targets', []) or label in self.selected_targets else 0.3
                    Color(*slice_color[:3], alpha)
                    
                    Ellipse(pos=(x, y), size=(d, d), angle_start=angle_start, angle_end=angle_end)
                    
                    texts.append((value, mid_angle))
                    angle_start += slice_angle
            else:
                # Verisiz halka aktif yüzey temasına göre nötrleşir.
                Color(*ftheme.chart_empty(style))
                Ellipse(pos=(x, y), size=(d, d), angle_start=0, angle_end=360 * self.anim_progress)
                texts.append((0, 0)) # Placeholder for 0%

            # 2. Halka (Donut) Kesimi
            if app:
                Color(*app.theme_cls.bg_normal)
            else:
                Color(1, 1, 1, 1)
            
            inner_d = d * 0.65
            inner_r = inner_d / 2
            Ellipse(pos=(local_cx - inner_r, local_cy - inner_r), size=(inner_d, inner_d))

            # 3. Yüzdelik Metinler
            if total > 0:
                for value, mid_angle in texts:
                    percentage = (value / total) * 100
                    if percentage >= 5 and total > 1 and self.anim_progress > 0.9:
                        alpha = min(1.0, max(0.0, (self.anim_progress - 0.9) * 10))
                        texture = _label_texture(f"%{percentage:.1f}", 14,
                                                 (1, 1, 1, 1), bold=True)

                        label_x = local_cx + (r * 0.85) * cos(radians(mid_angle))
                        label_y = local_cy + (r * 0.85) * sin(radians(mid_angle))
                        
                        tw, th = texture.size
                        pad_x, pad_y = 6, 4
                        
                        Color(0, 0, 0, alpha * 0.6)
                        RoundedRectangle(
                            pos=(label_x - tw/2 - pad_x, label_y - th/2 - pad_y), 
                            size=(tw + pad_x*2, th + pad_y*2), 
                            radius=[(th + pad_y*2) / 2]
                        )
                        
                        Color(1, 1, 1, alpha)
                        Rectangle(texture=texture, pos=(label_x - tw/2, label_y - th/2), size=texture.size)
            # total == 0 durumunda gri halka yeterli; "₺0 / Veri Yok" metnini
            # tutucudaki empty_label gösterir (çift metin üst üste biniyordu).

            # 4. Legend rendering is now handled in set_data to avoid animating widgets 60fps

            PopMatrix()

    def _sync_translate(self, *args):
        if self._translate is not None:
            self._translate.x = self.x
            self._translate.y = self.y

    def request_redraw(self):
        self.anim_progress = 0
        from kivy.animation import Animation
        Animation(anim_progress=1, duration=1.2, t='out_cubic').start(self)

    def draw_immediate(self):
        """Animasyonsuz tek karelik çizim (iskelet/boş şablon için)."""
        from kivy.animation import Animation
        Animation.cancel_all(self, "anim_progress")
        self.anim_progress = 1
        self._redraw_trigger()
