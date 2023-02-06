#%%
import os as os
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
from misc_v02 import time_series_plot, get_values, flexibility_available, power_limits
from optimization_v02 import Price_Opt
import numpy as np

# %%
solver = pyo.SolverFactory('gurobi')  # alternative : gurobi 

input_data = pd.read_csv('input/Data.csv', sep = ';', index_col=0)
input_data2 = pd.read_csv('input/fun_prices.csv', sep = ',', index_col=0)


fuel_data = pd.read_csv('input/Fuel.csv', sep = ',', index_col=0)

price_elec = np.array(input_data['electricity_price'])  # cents/MWh


price_ng = np.array(fuel_data['natural gas'])
price_coal = np.array(fuel_data['hard coal'])

# Dictionaries for Specific ELec and Mass Balance Ratio Coefficients 
spec_elec_cons = {'electric_heater': .37,
                  'iron_reduction': .127,
                  'arc_furnace': .575}

spec_ng_cons = {'iron_reduction': 1.56,
                'arc_furnace' : .216}

spec_coal_cons = {'arc_furnace' : .028}

iron_mass_ratio = {'iron': 1.66,
                   'DRI': 1.03,
                   'liquid_steel': 1}

plant_cap =   1200       #hourly steel production target   
optimization_horizon = 24 *7   #24
steel_prod =  1200*optimization_horizon 

#%%
#hourly limits
limits = power_limits(plant_cap, spec_elec_cons, iron_mass_ratio)

#%%
# Run model without flexibility 
base_model = Price_Opt(input_data=input_data,
                       fuel_data=fuel_data,
                       spec_elec_cons=spec_elec_cons,
                       spec_ng_cons=spec_ng_cons,
                       spec_coal_cons=spec_coal_cons,
                       iron_mass_ratio=iron_mass_ratio,
                       steel_prod=steel_prod,
                       optimization_horizon=optimization_horizon,
                       limits=limits,
                       flexibility_params=None)

solved_model = solver.solve(base_model)

base_model_params = get_values(base_model, optimization_horizon, input_data, fuel_data, spec_elec_cons)
            
# %%
pos_flex_total, neg_flex_total = flexibility_available(base_model, base_model_params['elec_cons'], limits, optimization_horizon) 

flex_amt = pd.DataFrame()
flex_amt['pos'] = pos_flex_total
flex_amt['neg'] = neg_flex_total

flex_amt.to_csv('flex_amt.csv')
# %%
