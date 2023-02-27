
from dataclasses import dataclass
import math

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure

import panel as pn
import param


@dataclass
class Circle:
    radius: float
    x: float
    y: float


class PrototypeSorbentMass(pn.viewable.Viewer):

    pot_diameter_cm = param.Number(25)
    filter_pod_diameter_cm = param.Number(5)
    filter_pod_space_between_cm = param.Number(0.5)
    area_covered_cm2 = param.Number()
    area_covered_pct = param.Number()

    depth_cm = param.Number(1)
    volume_l = param.Number()

    sorbent_density_kg_per_l = param.Number(0.630)
    mass_kg = param.Number()
    
    def __init__(self, **params):
        super().__init__(**params)

        self._panel = pn.Row(
            pn.Column(
                pn.pane.Markdown('### Compute sorbent mass'), 
                pn.widgets.FloatInput.from_param(self.param.pot_diameter_cm),
                pn.widgets.FloatInput.from_param(self.param.filter_pod_diameter_cm),
                pn.widgets.FloatInput.from_param(self.param.filter_pod_space_between_cm),
                pn.widgets.FloatInput.from_param(
                    self.param.area_covered_pct,
                    disabled=True,
                ),
                pn.widgets.FloatInput.from_param(self.param.depth_cm),
                pn.widgets.FloatInput.from_param(
                    self.param.volume_l,
                    disabled=True,
                ),
                pn.widgets.FloatInput.from_param(self.param.sorbent_density_kg_per_l),
                pn.widgets.FloatInput.from_param(
                    self.param.mass_kg,
                    disabled=True,
                ),
            ),
            pn.Column(self.circles_plot)
        )  

    def get_small_circles(self):
        """
        Inspired by https://www.engineeringtoolbox.com/smaller-circles-in-larger-circle-d_1849.html
        """

        def make_circles(rs, rc):
            circles = []

            no = math.floor((2 * math.pi * rc) / (2 * rs))
            x0 = rc * math.cos(0 * 2 * math.pi / no)
            y0 = rc * math.sin(0 * 2 * math.pi / no)
            x1 = rc * math.cos(1 * 2 * math.pi / no)
            y1 = rc * math.sin(1 * 2 * math.pi / no)
            dist = math.pow((math.pow((x0 - x1), 2) + math.pow((y0 - y1), 2)), 0.5)
            if (dist < 2 * rs):
                no = no - 1
            for i in range(no):
                x = rc * math.cos(i * 2 * math.pi / no)
                y = rc * math.sin(i * 2 * math.pi / no)
                circles.append(Circle(radius=rs, x=x, y=y))

            rc_next = rc - (2 * rs)
            if (rc_next >= rs):
                circles.extend(make_circles(rs, rc_next))
            elif (rc > 2 * rs):
                circles.append(Circle(radius=rs, x=0, y=0))

            return circles

        if self.pot_diameter_cm <= 0:
            return []

        if self.filter_pod_diameter_cm <= 0:
            return []

        if self.filter_pod_diameter_cm > self.pot_diameter_cm:
            return []

        # add padding around circles
        small_radius = self.filter_pod_diameter_cm/2 + self.filter_pod_space_between_cm/2
        large_radius = self.pot_diameter_cm/2 - self.filter_pod_space_between_cm/2

        if (large_radius < 2 * small_radius):
            return [Circle(radius=self.filter_pod_diameter_cm/2, x=0, y=0)]

        circles = make_circles(small_radius, large_radius - small_radius)

        # replace radius with true radius
        return [Circle(radius=self.filter_pod_diameter_cm/2, x=c.x, y=c.y) for c in circles]

    @param.depends(
        'pot_diameter_cm',
        'filter_pod_diameter_cm',
        'filter_pod_space_between_cm',
        watch=True,
        on_init=True,
    )
    def update_area_coverage(self):
        try:
            circles = self.get_small_circles()
            self.area_covered_cm2 = len(circles) * math.pi * (self.filter_pod_diameter_cm/2)**2
            large_circle_area_cm2 = math.pi * (self.pot_diameter_cm/2)**2
            self.area_covered_pct = self.area_covered_cm2/large_circle_area_cm2

        except ValueError:
            self.area_covered_cm2 = 0
            self.area_covered_pct = 0

    @param.depends(
        'pot_diameter_cm',
        'filter_pod_diameter_cm',
        'filter_pod_space_between_cm',
        on_init=True,
    )
    def circles_plot(self):

        circles = [Circle(radius=self.pot_diameter_cm/2, x=0, y=0)]

        try:
            small_circles = self.get_small_circles()
            circles.extend(small_circles)

            # also draw padding
            padding_circles = [
                Circle(radius=sc.radius + self.filter_pod_space_between_cm/2, x=sc.x, y=sc.y)
                for sc in small_circles
            ]
            circles.extend(padding_circles)
        except ValueError:
            pass

        source = ColumnDataSource(
            dict(
                x=[c.x for c in circles],
                y=[c.y for c in circles],
                r=[c.radius for c in circles],
            )
        )

        p = figure(width=500, height=500, match_aspect=True)
        p.circle(x="x", y="y", radius="r", source=source, alpha=0.1)
        
        # need to draw an invisible rectangle to let the auto-range feature work properly
        # and be able to keep match_aspect=True to draw proper circles
        # see https://github.com/bokeh/bokeh/issues/11082
        p.rect(x=0, y=0, width=self.pot_diameter_cm, height=self.pot_diameter_cm, alpha=0)

        return p

    @param.depends('area_covered_cm2', 'depth_cm', watch=True, on_init=True)
    def update_volume(self):
        self.volume_l = self.area_covered_cm2 * self.depth_cm / 1000

    @param.depends('volume_l', 'sorbent_density_kg_per_l', watch=True, on_init=True)
    def update_mass(self):
        self.mass_kg = self.volume_l * self.sorbent_density_kg_per_l

    def __panel__(self):
        return self._panel

PrototypeSorbentMass().servable()
