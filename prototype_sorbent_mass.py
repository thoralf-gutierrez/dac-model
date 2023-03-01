
from dataclasses import dataclass
import math

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from bokeh.models.widgets import DataTable, TableColumn, NumberFormatter

import pandas as pd
import panel as pn
import param


class PrototypeSorbentMass(pn.viewable.Viewer):

    pot_diameter_mm = param.Number(250)
    filter_pod_diameter_mm = param.Number(40)
    filter_pod_space_between_mm = param.Number(10)
    area_covered_mm2 = param.Number()
    area_covered_pct = param.Number()

    depth_mm = param.Number(10)
    volume_l = param.Number()

    sorbent_density_kg_per_l = param.Number(0.630)
    mass_kg = param.Number()
    
    def __init__(self, **params):
        super().__init__(**params)

        self._panel = pn.Row(
            pn.Column(
                pn.pane.Markdown('### Compute sorbent mass'), 
                pn.widgets.FloatInput.from_param(self.param.pot_diameter_mm),
                pn.widgets.FloatInput.from_param(self.param.filter_pod_diameter_mm),
                pn.widgets.FloatInput.from_param(self.param.filter_pod_space_between_mm),
                pn.widgets.FloatInput.from_param(
                    self.param.area_covered_pct,
                    disabled=True,
                ),
                pn.widgets.FloatInput.from_param(self.param.depth_mm),
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
            pn.Column(self.circles_plot),
            pn.Column(self.circles_table),
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
                circles.append(dict(radius=rs, x=x, y=y))

            rc_next = rc - (2 * rs)
            if (rc_next >= rs):
                circles.extend(make_circles(rs, rc_next))
            elif (rc > 2 * rs):
                circles.append(dict(radius=rs, x=0, y=0))

            return circles

        if self.pot_diameter_mm <= 0:
            return []

        if self.filter_pod_diameter_mm <= 0:
            return []

        if self.filter_pod_diameter_mm > self.pot_diameter_mm:
            return []

        # add padding around circles
        small_radius = self.filter_pod_diameter_mm/2 + self.filter_pod_space_between_mm/2
        large_radius = self.pot_diameter_mm/2 - self.filter_pod_space_between_mm/2

        if (large_radius < 2 * small_radius):
            return [dict(radius=self.filter_pod_diameter_mm/2, x=0, y=0)]

        circles = make_circles(small_radius, large_radius - small_radius)

        circles_df = pd.DataFrame.from_records(circles)

        # replace radius with true radius
        circles_df['radius'] = self.filter_pod_diameter_mm/2

        return circles_df

    @param.depends(
        'pot_diameter_mm',
        'filter_pod_diameter_mm',
        'filter_pod_space_between_mm',
        watch=True,
        on_init=True,
    )
    def update_area_coverage(self):
        try:
            circles_df = self.get_small_circles()
            self.area_covered_mm2 = sum(math.pi * circles_df['radius']**2)
            large_circle_area_mm2 = math.pi * (self.pot_diameter_mm/2)**2
            self.area_covered_pct = self.area_covered_mm2/large_circle_area_mm2

        except ValueError:
            self.area_covered_mm2 = 0
            self.area_covered_pct = 0

    @param.depends(
        'pot_diameter_mm',
        'filter_pod_diameter_mm',
        'filter_pod_space_between_mm',
        on_init=True,
    )
    def circles_plot(self):

        circles_df = pd.DataFrame.from_records([dict(radius=self.pot_diameter_mm/2, x=0, y=0)])

        try:
            small_circles_df = self.get_small_circles()
            # also draw padding
            padding_circles_df = small_circles_df.copy()
            padding_circles_df['radius'] += self.filter_pod_space_between_mm/2

            circles_df = pd.concat([
                circles_df,
                small_circles_df,
                padding_circles_df,
            ])

        except ValueError:
            pass

        source = ColumnDataSource(circles_df)

        p = figure(width=500, height=500, match_aspect=True)
        p.circle(x="x", y="y", radius="radius", source=source, alpha=0.1)
        
        # need to draw an invisible rectangle to let the auto-range feature work properly
        # and be able to keep match_aspect=True to draw proper circles
        # see https://github.com/bokeh/bokeh/issues/11082
        p.rect(x=0, y=0, width=self.pot_diameter_mm, height=self.pot_diameter_mm, alpha=0)

        return p

    @param.depends(
        'pot_diameter_mm',
        'filter_pod_diameter_mm',
        'filter_pod_space_between_mm',
        on_init=True,
    )
    def circles_table(self):
        small_circles_df = self.get_small_circles()
        source = ColumnDataSource(small_circles_df)

        columns = [
            TableColumn(field="x", title="X (mm)", formatter=NumberFormatter(format='0.[00]')),
            TableColumn(field="y", title="Y (mm)", formatter=NumberFormatter(format='0.[00]')),
        ]
        return DataTable(source=source, columns=columns, width=200)


    @param.depends('area_covered_mm2', 'depth_mm', watch=True, on_init=True)
    def update_volume(self):
        self.volume_l = self.area_covered_mm2 * self.depth_mm / 1000 / 1000

    @param.depends('volume_l', 'sorbent_density_kg_per_l', watch=True, on_init=True)
    def update_mass(self):
        self.mass_kg = self.volume_l * self.sorbent_density_kg_per_l

    def __panel__(self):
        return self._panel

PrototypeSorbentMass().servable()
