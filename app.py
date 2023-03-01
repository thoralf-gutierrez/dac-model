
import panel as pn
import param
import numpy as np
import scipy as sp

pn.extension()


class DACModel(pn.viewable.Viewer):

    ############################################################
    ## Parameters (GL: I write parameters in lower case & Variable with 1 capital letter)
    ###########################################################
    ## Physical constants:
    #  Don't try to change them, you cannot on Earth !
    R = 8.314 # Perfect gas constant [J/K/mol]
    Mm_CO2 = 0.044 # [kg/mol]
    Mm_O2 = 0.032 # [kg/mol]
    Mm_N2 = 0.028 # [kg/mol]
    Mm_air = Mm_O2*0.21 + Mm_N2*0.79 # [kg/mol]
    Rstar_air = R/Mm_air # [J/K/kg]

    cp_CO2 = 850 # [kJ/kg] assumed constant over temperature, TBC

    ## Ambiant conditions:
    p_atm = 101300.0 # [Pa]
    t_atm = param.Number(20) # [°C]
    c_CO2_atm = 400/1000000 # ppm (vol or mol)

    # Constrained parameters:
    air_density = param.Number(0) # [kg/m³]
    air_viscosity = param.Number() # [kg/m/s]

    ## Casing & fan design:
    #  Todo: add image of param significations
    casing_front_area = param.Number(1.0) # [m²]
    inlet_air_velocity = param.Number(2.0) # [m/s]


    ## Sorbent & filter:
    #  To do: description of the different parameters:
    filter_thickness = param.Number(0.005) # [m]
    filter_area = param.Number(1.8) # [m²]
    filter_layers = param.Number(10) # [-], number of layers of filter.

    # Properties - chemical of the sorbent:
    #   Sorbent implemented is: LEWATIT VP OC 1065
    # from https://doi.org/10.1016/j.cej.2018.11.072 
    sorbent_cp = 1580000 # [J/kg] 
    sorbent_reaction_heat = 75000 # [J/mol]
    sorbent_pore_radius = 12.5e-9 # [m]
    sorbent_h_Gibbs = 75000 # [J/mol] 
    sorbent_particle_voidage = 0.23 # [m³_void/m³_solid]
    sorbnet_pore_tortuosity = 2.3 # ??? [m_g/m_s]

    # from : 
    sorbent_work_capa = 0.91 # Tbc - [mol/kg]
    sorbent_reg_temp = 100 # [°C]
    sorbent_spec_work_equiv = 2490000000 # [J/kg]
    # Properties - geometrical of the sorbent:
    particle_sphericity = 0.8 # [-] from Wilcox2012 book.
    channel_diameter = param.Number(0.0001) # [m] - 100µm seems sufficient to ensure optimal kientic, see TODO
    void_fraction = 0.4 # [-] from Wilcox2012 book.

    #

    ############################################################
    ## Outputs (calculated variables)
    #  These are the variables computed by the model:
    ############################################################
    Pressure_drop = param.Number()

    Sorbent_mass = param.Number()
    Sorbent_q = param.Number() # [mol/kg] Sorbent concentration
    
    
    def __init__(self, **params):
        super().__init__(**params)

        self._panel = pn.Column(
            pn.pane.Markdown('### DAC Model'), 
            pn.widgets.NumberInput.from_param(self.param.filter_thickness),
            pn.widgets.NumberInput.from_param(self.param.air_density),
            pn.widgets.NumberInput.from_param(self.param.inlet_air_velocity),
            pn.widgets.NumberInput.from_param(self.param.particle_sphericity),
            pn.widgets.NumberInput.from_param(self.param.channel_diameter),
            pn.widgets.NumberInput.from_param(self.param.void_fraction),
            pn.widgets.NumberInput.from_param(self.param.t_atm),
            pn.widgets.NumberInput.from_param(self.param.t_now),
            pn.widgets.NumberInput.from_param(
                self.param.air_viscosity,
                disabled=True,
            ),
            pn.widgets.NumberInput.from_param(
                self.param.Pressure_drop,
                disabled=True,
            ),
            pn.widgets.NumberInput.from_param(
                self.param.Sorbent_q,
                disabled=True,
            ),
        )  

    @param.depends('t_atm', watch=True, on_init=True)
    def update_air_viscosity(self):
        self.air_viscosity = 2.791 * 10**-7 * (self.t_atm + 273)**(0.7355)

    @param.depends(
        'filter_thickness',
        'inlet_air_velocity',
        'air_viscosity',
        'particle_sphericity',
        'channel_diameter',
        'void_fraction',
        'air_density',
        watch=True,
        on_init=True
    )
    def update_pressure_drop(self):
        # Equation 4.62 from Wilcox2012 book - p164
        term1 = 150 * self.inlet_air_velocity * self.air_viscosity
        term1 = term1 / (self.particle_sphericity**2 * self.channel_diameter**2)
        term1 = term1 * (1-self.void_fraction)**2
        term1 = term1 / (self.void_fraction ** 3)
        term2 = 1.75 * self.air_density * self.inlet_air_velocity**2
        term2 = term2 / (self.particle_sphericity * self.channel_diameter)
        term2 = term2 * (1 - self.void_fraction)
        term2 = term2 / (self.void_fraction ** 3)

        self.Pressure_drop = self.filter_thickness * (term1 + term2) / 100000 
    
    def update_filter_concentration(self):
        # Eq. 5 of https://doi.org/10.1016/j.cej.2018.11.072

         t = self.t_now

         def comp_dqdt(t,y):
            ktoth= 1 # Toth isothermal constant Value to be found
            pp_CO2 = self.c_CO2_atm * self.p_atm # Partial pressure [Pa]
            T0 = 273.15 + 80 # [K] from paper
            T = 273.15 + self.t_atm # [K]
            
            qs0 =  3.4 # [mol/kg] Adsorption saturation mol/kg from paper
            Xi = 0 # [-] here imposed at 0 => no impact of temperature
            qs = qs0 * np.exp(Xi*(1-T/T0))

            th0 = 0.37 # [-] heterogeneity parameter from paper
            alpha = 0.33 # [-] ??? from paper
            th = th0 * alpha * (1 - T0 / T)

            DH0 = 95.3 # kJ/mol TBC, should be given in sorbent properties
            b = b0 * np.exp(DH0/(self.R*T0)*(T0/T - 1)) 

            dqdt = ktoth * ( pp_CO2 * (1 - ( y / qs ) ** th ) ** ( 1 / th ) - 1 / b * y / qs)
         
         #Initial conditions:
         t0 = 0 #starting time of the cycle
         y0 = 0 #starting concentration 

         self.sorbent_q = sp.integrate.RK45(comp_dqdt,t0,y0,t)
        
    def __panel__(self):
        return self._panel

DACModel().servable()
