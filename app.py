
import panel as pn
import param

pn.extension()


class DACModel(pn.viewable.Viewer):

    # pressure drop
    length = param.Number(0.005)
    air_density = param.Number(0)
    air_velocity = param.Number(1)
    particle_sphericity = param.Number(0.8)
    channel_diameter = param.Number(0.0001)
    void_fraction = param.Number(0.4)
    
    temperature_celsius = param.Number(20)
    air_viscosity = param.Number()
    pressure_drop_bar = param.Number()
    
    def __init__(self, **params):
        super().__init__(**params)

        self._panel = pn.Column(
            pn.pane.Markdown('### DAC Model'), 
            pn.widgets.NumberInput.from_param(self.param.length),
            pn.widgets.NumberInput.from_param(self.param.air_density),
            pn.widgets.NumberInput.from_param(self.param.air_velocity),
            pn.widgets.NumberInput.from_param(self.param.particle_sphericity),
            pn.widgets.NumberInput.from_param(self.param.channel_diameter),
            pn.widgets.NumberInput.from_param(self.param.void_fraction),
            pn.widgets.NumberInput.from_param(self.param.temperature_celsius),
            pn.widgets.NumberInput.from_param(
                self.param.air_viscosity,
                disabled=True,
            ),
            pn.widgets.NumberInput.from_param(
                self.param.pressure_drop_bar,
                disabled=True,
            ),
        )  

    @param.depends('temperature_celsius', watch=True, on_init=True)
    def update_air_viscosity(self):
        self.air_viscosity = 2.791 * 10**-7 * (self.temperature_celsius + 273)**(0.7355)

    @param.depends(
        'length',
        'air_velocity',
        'air_viscosity',
        'particle_sphericity',
        'channel_diameter',
        'void_fraction',
        'air_density',
        watch=True,
        on_init=True
    )
    def update_pressure_drop(self):
        term1 = 150 * self.air_velocity * self.air_viscosity
        term1 = term1 / (self.particle_sphericity**2 * self.channel_diameter**2)
        term1 = term1 * (1-self.void_fraction)**2
        term1 = term1 / (self.void_fraction ** 3)
        term2 = 1.75 * self.air_density * self.air_velocity**2
        term2 = term2 / (self.particle_sphericity * self.channel_diameter)
        term2 = term2 * (1 - self.void_fraction)
        term2 = term2 / (self.void_fraction ** 3)

        self.pressure_drop_bar = self.length * (term1 + term2) / 100000
    
    def __panel__(self):
        return self._panel

DACModel().servable()
