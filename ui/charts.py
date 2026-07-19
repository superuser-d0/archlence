import math
from math import sin, cos, radians
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import NumericProperty, ColorProperty
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, RoundedRectangle, Ellipse, Mesh, Rectangle
from kivy.core.text import Label as CoreLabel  # type: ignore
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.app import MDApp
from services.transaction_service import TransactionService

# Forward import
from ui.components import LegendWidget

class CurvedTrendChart(Widget):
    """Zaman içindeki gelir ve gider trendlerini gösteren eğimli alan (area) grafiği çizer.
    Beklenen veri formatı (self.chart_data):
    [{'label': '01 Eki', 'income': 1500.0, 'expense': 800.0}, ...]
    """

    anim_progress = NumericProperty(0.0)

    # Palette
    COLOR_INCOME_LINE  = (0.16, 0.84, 0.60, 1.0)    # teal
    COLOR_INCOME_FILL  = (0.16, 0.84, 0.60, 0.20)
    COLOR_EXPENSE_LINE = (0.30, 0.45, 0.95, 1.0)    # blue
    COLOR_EXPENSE_FILL = (0.30, 0.45, 0.95, 0.15)
    COLOR_AXIS         = (0.60, 0.60, 0.60, 0.70)
    COLOR_GRID         = (0.55, 0.55, 0.55, 0.12)
    COLOR_LABEL        = (0.72, 0.72, 0.72, 1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chart_data = []
        self.bind(pos=self._redraw, size=self._redraw, anim_progress=self._redraw)

    def request_redraw(self):
        self.anim_progress = 0.0
        from kivy.animation import Animation
        Animation(anim_progress=1.0, duration=1.1, t="out_cubic").start(self)


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

        # ── Layout margins ────────────────────────────────────────────────
        PAD_LEFT  = dp(50)   # Y-axis label gutter (wider for larger font)
        PAD_RIGHT = dp(14)
        PAD_TOP   = dp(14)
        PAD_BOT   = dp(28)   # X-axis label gutter

        cx0 = self.x     + PAD_LEFT
        cx1 = self.right - PAD_RIGHT
        cy0 = self.y     + PAD_BOT
        cy1 = self.top   - PAD_TOP
        cw  = max(1, cx1 - cx0)
        ch  = max(1, cy1 - cy0)

        with self.canvas:

            # ── No-data state ─────────────────────────────────────────────
            if not data:
                Color(*self.COLOR_AXIS)
                Line(points=[cx0, cy0, cx1, cy0], width=dp(1))
                Line(points=[cx0, cy0, cx0, cy1], width=dp(1))
                msg = CoreLabel(text="Bu dönemde veri yok",  # type: ignore
                                font_size=dp(13), color=(0.6, 0.6, 0.6, 1))
                msg.refresh()
                mt = msg.texture
                Color(1, 1, 1, 0.75)
                Rectangle(texture=mt,
                          pos=(self.center_x - mt.width / 2,
                               self.center_y - mt.height / 2),
                          size=mt.size)
                return

            n = len(data)

            # ── Nice Y-axis range ───────────────────────────────────────────
            all_inc = [d['income']  for d in data]
            all_exp = [d['expense'] for d in data]
            raw_max = max(max(all_inc), max(all_exp), 1.0)

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
                Color(*self.COLOR_GRID)
                Line(points=[cx0, gy, cx1, gy], width=dp(0.5))
                # Y label
                lbl = CoreLabel(text=self._fmt_k(val), font_size=dp(11),  # type: ignore
                                color=(*self.COLOR_LABEL[:3], 0.9))
                lbl.refresh()
                lt = lbl.texture
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
                xl = CoreLabel(text=d['label'], font_size=dp(11),  # type: ignore
                               color=(*self.COLOR_LABEL[:3], 0.9))
                xl.refresh()
                xt = xl.texture
                Color(1, 1, 1, 0.9)
                Rectangle(texture=xt,
                          pos=(max(cx0, min(lx - xt.width / 2, cx1 - xt.width)),
                               cy0 - xt.height - dp(4)),
                          size=xt.size)

            # ── Axis lines ───────────────────────────────────────────────
            Color(*self.COLOR_AXIS)
            Line(points=[cx0, cy0, cx1, cy0], width=dp(1.2))
            Line(points=[cx0, cy0, cx0, cy1], width=dp(1.2))

            # ── Series drawing helper ──────────────────────────────────────
            def draw_series(key, line_col, fill_col, dot_r=dp(3.5)):
                raw_pts  = [(px(i), py(d[key])) for i, d in enumerate(data)]
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
                    last_val = data[last_idx][key]
                    if last_val > 0:
                        vl = CoreLabel(text=self._fmt_k(last_val), font_size=dp(11),  # type: ignore
                                       color=(*line_col[:3], la), bold=True)
                        vl.refresh()
                        vt = vl.texture
                        Color(1, 1, 1, la)
                        vx2 = min(cx1 - vt.width, visible[-1][0] + dp(4))
                        Rectangle(texture=vt,
                                  pos=(vx2, visible[-1][1] - vt.height / 2),
                                  size=vt.size)

            # Draw expense first (below income)
            draw_series('expense', self.COLOR_EXPENSE_LINE, self.COLOR_EXPENSE_FILL)
            draw_series('income',  self.COLOR_INCOME_LINE,  self.COLOR_INCOME_FILL)

            # ── Mini legend top-right ─────────────────────────────────────
            if p > 0.8:
                leg_alpha = min(1.0, (p - 0.8) * 5.0)
                leg_y     = cy1 - dp(2)
                leg_x     = cx1
                for ltext, lcol in [('Gider', self.COLOR_EXPENSE_LINE),
                                     ('Gelir', self.COLOR_INCOME_LINE)]:
                    ll = CoreLabel(text=ltext, font_size=dp(11),  # type: ignore
                                   color=(*lcol[:3], leg_alpha), bold=True)
                    ll.refresh()
                    lt2 = ll.texture
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

        if pie_box:
            pie_box.add_widget(self.pie_widget)
            pie_box.add_widget(self.legend_widget)
        if comp_box:
            comp_box.add_widget(self.trend_chart)


    # ── Public API ───────────────────────────────────────────────────────────

    def refresh_dashboard(self, period):
        """Fetch data in a background thread, then update all charts on the main thread."""
        import threading

        def _load():
            raw_data = TransactionService.get_transactions_by_period(period)
            Clock.schedule_once(lambda dt: self._apply_data(raw_data, period), 0)

        threading.Thread(target=_load, daemon=True).start()

    # Legacy shim so any existing callers (on_tab_press etc.) keep working
    def render_dashboard(self, period):
        self.refresh_dashboard(period)

    # ── Internal update (always runs on the main thread) ─────────────────────

    def _apply_data(self, raw_data, period):
        # 1. Aggregate 4-category totals for PieChart + Legend
        cat_totals = {
            'Ana Gelir': 0, 'Ek Gelir': 0,
            'Temel Gider': 0, 'Ekstra Gider': 0,
        }
        for tx in raw_data:
            t_type     = tx.get('type')
            amount     = tx.get('amount', 0)
            importance = tx.get('importance', 'extra')
            if t_type == 'income':
                if importance == 'main': cat_totals['Ana Gelir']   += amount
                else:                    cat_totals['Ek Gelir']     += amount
            elif t_type == 'expense':
                if importance == 'main': cat_totals['Temel Gider'] += amount
                else:                    cat_totals['Ekstra Gider'] += amount

        # Update PieChart
        self.pie_widget.data = cat_totals
        self.pie_widget.request_redraw()

        # Update Legend with percentages
        self.legend_widget.update_percentages(cat_totals)

        # 2. Build time-bucketed data for CurvedTrendChart
        buckets = self._build_time_buckets(raw_data, period)
        self.trend_chart.chart_data = buckets
        self.trend_chart.request_redraw()

    def _build_time_buckets(self, raw_data, filter_text):
        """Return list of {label, income, expense} dicts for the chosen period."""
        import datetime
        now = datetime.datetime.now()
        result = []

        if filter_text == 'Bugün':
            hour_map = {}
            for tx in raw_data:
                dt = datetime.datetime.strptime(tx['transaction_date'], '%Y-%m-%d %H:%M:%S')
                if dt.date() == now.date():
                    h = f'{dt.hour:02d}'
                    hour_map.setdefault(h, {'inc': 0, 'exp': 0})
                    if tx['type'] == 'income': hour_map[h]['inc'] += tx['amount']
                    else:                       hour_map[h]['exp'] += tx['amount']

            min_h = int(min(hour_map)) if hour_map else max(0, now.hour - 4)
            max_h = max(int(max(hour_map)), now.hour) if hour_map else now.hour
            for h in range(min_h, max_h + 1):
                k = f'{h:02d}'
                entry = hour_map.get(k, {'inc': 0, 'exp': 0})
                result.append({'label': f'{k}:00', 'income': entry['inc'], 'expense': entry['exp']})

        elif filter_text in ('1 Hafta', '1 Ay'):
            days = 7 if filter_text == '1 Hafta' else 30
            start_dt = now - datetime.timedelta(days=days - 1)
            day_map = {}
            for tx in raw_data:
                dt = datetime.datetime.strptime(tx['transaction_date'], '%Y-%m-%d %H:%M:%S')
                if dt.date() >= start_dt.date():
                    k = dt.strftime('%Y-%m-%d')
                    day_map.setdefault(k, {'inc': 0, 'exp': 0})
                    if tx['type'] == 'income': day_map[k]['inc'] += tx['amount']
                    else:                       day_map[k]['exp'] += tx['amount']

            for d in range(days):
                dt  = start_dt + datetime.timedelta(days=d)
                k   = dt.strftime('%Y-%m-%d')
                lbl = dt.strftime('%d %b')
                entry = day_map.get(k, {'inc': 0, 'exp': 0})
                result.append({'label': lbl, 'income': entry['inc'], 'expense': entry['exp']})

        elif filter_text == '1 Yıl':
            month_names = ['Oca','Şub','Mar','Nis','May','Haz','Tem','Ağu','Eyl','Eki','Kas','Ara']
            start_dt = now - datetime.timedelta(days=364)
            month_map = {}
            for tx in raw_data:
                dt = datetime.datetime.strptime(tx['transaction_date'], '%Y-%m-%d %H:%M:%S')
                if dt.date() >= start_dt.date():
                    k = dt.strftime('%Y-%m')
                    month_map.setdefault(k, {'inc': 0, 'exp': 0})
                    if tx['type'] == 'income': month_map[k]['inc'] += tx['amount']
                    else:                       month_map[k]['exp'] += tx['amount']

            for i in range(11, -1, -1):
                m = now.month - i
                y = now.year
                while m < 1:
                    m += 12
                    y -= 1
                k   = f'{y}-{m:02d}'
                lbl = f"{month_names[m-1]} '{str(y)[2:]}"
                entry = month_map.get(k, {'inc': 0, 'exp': 0})
                result.append({'label': lbl, 'income': entry['inc'], 'expense': entry['exp']})

        elif filter_text == 'Hayat Boyu':
            year_map = {}
            for tx in raw_data:
                dt = datetime.datetime.strptime(tx['transaction_date'], '%Y-%m-%d %H:%M:%S')
                k = dt.strftime('%Y')
                year_map.setdefault(k, {'inc': 0, 'exp': 0})
                if tx['type'] == 'income': year_map[k]['inc'] += tx['amount']
                else:                       year_map[k]['exp'] += tx['amount']
            
            if year_map:
                min_year = int(min(year_map.keys()))
                max_year = now.year
                for y in range(min_year, max_year + 1):
                    k = str(y)
                    entry = year_map.get(k, {'inc': 0, 'exp': 0})
                    result.append({'label': k, 'income': entry['inc'], 'expense': entry['exp']})

        # Filter out all-zero rows only when ALL rows are zero (keep axis visible)
        any_data = any(r['income'] > 0 or r['expense'] > 0 for r in result)
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
        self.data = {"Veri Bekleniyor": 1}
        # Premium Banking teması: çubuklar marka indigo'suyla çizilir
        from ui.theme import FINORA_PRIMARY
        self.colors = [tuple(FINORA_PRIMARY)]

    def highlight_bar(self, targets):
        self.selected_targets = targets
        self.update_chart()

    def update_chart(self, *args):
        if not self.canvas: return
        self.canvas.clear()
        total = sum(self.data.values())
        if total == 0: return

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




class LiquidWaveWidget(Widget):
    """Yatay, soldan sağa dolan ve üst kısmı dalgalı (sıvı animasyonlu) bir ilerleme çubuğu çizer.
    Beklenen veri formatı:
    Sözlük veya liste beklemez; 'progress' adlı NumericProperty üzerinden (0.0 ile 100.0 arası) değer alır.
    """
    phase      = NumericProperty(0.0)
    progress   = NumericProperty(0.0)   # 0–100
    wave_color = ColorProperty((0.1, 0.8, 0.2, 0.9))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            pos=self._redraw, size=self._redraw,
            phase=self._redraw, progress=self._redraw,
            wave_color=self._redraw,
        )
        self._clock = Clock.schedule_interval(self._tick, 1 / 60.0)

    def _tick(self, dt):
        self.phase += 0.06
        self._redraw()

    def _redraw(self, *args):
        from kivy.graphics import (
            Color, Mesh, Line, RoundedRectangle,
            StencilPush, StencilUse, StencilUnUse, StencilPop,
        )
        if not self.canvas: return
        self.canvas.clear()
        self.canvas.before.clear()
        self.canvas.after.clear()
        
        if self.width <= 0 or self.height <= 0:
            return

        # Daha kibar: Tam hap şeklinde kenarlar
        r          = self.height / 2.0
        ratio      = max(0.0, min(1.0, self.progress / 100.0))
        fill_width = self.width * ratio
        base_y     = self.y
        
        # Daha dalgalı: Yüksek genlik, sıfırda ve yüzde yüzde sönümlü
        if ratio <= 0.01:
            amp = 0
        elif ratio >= 0.99:
            amp = dp(1)
        else:
            amp = dp(4.5)
            
        top_y_base = self.y + self.height - amp - dp(1)

        wr, wg, wb, wa = self.wave_color

        with self.canvas.before:
            StencilPush()
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            StencilUse()
            
            # Empty track background (Daha yumuşak, entegre gri)
            Color(0.5, 0.5, 0.5, 0.2)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])

        with self.canvas:
            if fill_width > 0:
                # Dalganın ucunu (sağ taraf) küt değil, hap şeklinde maskelemek için 2. Stencil
                StencilPush()
                RoundedRectangle(pos=self.pos, size=(fill_width, self.height), radius=[r])
                StencilUse()

                wave_top = []
                steps = max(1, int(self.width / 2))
                # Dalga tüm genişlik boyunca hesaplanır, maske sayesinde sadece dolan kısım görünür
                for i in range(steps + 1):
                    px = self.x + (self.width * i / steps)
                    # Daha hareketli, frekansı yüksek sıvı efekti
                    py = top_y_base + math.sin(self.phase * 2.0 + px * 0.08) * amp
                    wave_top.append((px, py))

                Color(wr, wg, wb, wa)
                mesh_verts = []
                for (px, py) in wave_top:
                    mesh_verts += [px, py,      0, 0]
                    mesh_verts += [px, base_y,  0, 0]
                indices = []
                n = len(wave_top)
                for i in range(n - 1):
                    b = i * 2
                    indices += [b, b+1, b+2, b+2, b+1, b+3]
                if indices:
                    Mesh(vertices=mesh_verts, indices=indices, mode='triangles')

                # Wavy top üzerine beyaz parlama (Shine)
                Color(1, 1, 1, 0.50)
                crest = []
                for px, py in wave_top:
                    crest += [px, py]
                if len(crest) >= 4:
                    Line(points=crest, width=1.2)

                # 2. Stencil'i doğru şekilde kapat (Kivy kuralları)
                StencilUnUse()
                RoundedRectangle(pos=self.pos, size=(fill_width, self.height), radius=[r])
                StencilPop()

        with self.canvas.after:
            # 1. Stencil'i kapat
            StencilUnUse()
            RoundedRectangle(pos=self.pos, size=self.size, radius=[r])
            StencilPop()
            
            # Capsule outline border in the fill colour
            Color(wr, wg, wb, 0.45)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height, r], width=1.0)

    def on_parent(self, *args):
        if not self.parent:
            self._clock.cancel()


class ConfettiWidget(Widget):
    """Birikim hedefinde bir eşik (%25/50/75/100) geçildiğinde tetiklenen kısa
    süreli konfeti patlaması. burst() çağrılana kadar tamamen pasif kalır; tüm
    parçacıklar söndüğünde kendi Clock'unu iptal eder (LiquidWaveWidget'taki
    sürekli tick'in aksine, burada yalnızca aktifken tick atan bir döngü kullanılır).
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
    {'Ana Gelir': 5000, 'Ek Gelir': 1500, 'Temel Gider': 3000, 'Ekstra Gider': 800} (Dict)
    """
    anim_progress = NumericProperty(0)
    selected_targets = []
    
    def highlight_slice(self, targets):
        self.selected_targets = targets
        self.update_chart()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_chart, size=self.update_chart, anim_progress=self.update_chart)
        self.data = {"Veri Bekleniyor": 1}
        self.colors = [(0.8, 0.8, 0.8, 1)] 

    def fetch_real_data(self):
        # Deprecated: The logic was moved to FinoraApp.update_metrics_and_goals()
        # This is kept empty temporarily to avoid crashes if called before restart
        pass
    def update_chart(self, *args):
        if not self.canvas: return
        self.canvas.clear()
        
        # Persistent categories and colors
        self.category_colors = {
            'Ana Gelir': '#00C853',
            'Ek Gelir': '#2979FF',
            'Temel Gider': '#FF5252',
            'Ekstra Gider': '#FFD600'
        }
        
        from kivy.utils import get_color_from_hex
        
        # Calculate total
        total = sum(self.data.get(k, 0) for k in self.category_colors.keys()) if isinstance(self.data, dict) else 0

        with self.canvas:
            angle_start = 0
            d = min(self.width, self.height) * 0.8
            r = d / 2
            x = self.center_x - r
            y = self.center_y - r
            
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
                # Render a light grey donut when there's no data
                Color(0.8, 0.8, 0.8, 1)
                Ellipse(pos=(x, y), size=(d, d), angle_start=0, angle_end=360 * self.anim_progress)
                texts.append((0, 0)) # Placeholder for 0%
            
            # 2. Halka (Donut) Kesimi
            app = MDApp.get_running_app()
            if app:
                Color(*app.theme_cls.bg_normal)
            else:
                Color(1, 1, 1, 1)
            
            inner_d = d * 0.65
            inner_r = inner_d / 2
            Ellipse(pos=(self.center_x - inner_r, self.center_y - inner_r), size=(inner_d, inner_d))
            
            # 3. Yüzdelik Metinler
            if total > 0:
                for value, mid_angle in texts:
                    percentage = (value / total) * 100
                    if percentage >= 5 and total > 1 and self.anim_progress > 0.9:
                        alpha = min(1.0, max(0.0, (self.anim_progress - 0.9) * 10))
                        text_label = CoreLabel(text=f"%{percentage:.1f}", font_size=14, color=(1, 1, 1, alpha), bold=True)  # type: ignore
                        text_label.refresh()
                        texture = text_label.texture
                        
                        label_x = self.center_x + (r * 0.85) * cos(radians(mid_angle))
                        label_y = self.center_y + (r * 0.85) * sin(radians(mid_angle))
                        
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
            else:
                if self.anim_progress > 0.9:
                    alpha = min(1.0, max(0.0, (self.anim_progress - 0.9) * 10))
                    text_label = CoreLabel(text="%0", font_size=16, color=(0.5, 0.5, 0.5, alpha), bold=True)  # type: ignore
                    text_label.refresh()
                    texture = text_label.texture
                    Rectangle(texture=texture, pos=(self.center_x - texture.size[0]/2, self.center_y - texture.size[1]/2), size=texture.size)
                        
            # 4. Legend rendering is now handled in set_data to avoid animating widgets 60fps
            
    def request_redraw(self):
        self.anim_progress = 0
        from kivy.animation import Animation
        Animation(anim_progress=1, duration=1.2, t='out_cubic').start(self)


