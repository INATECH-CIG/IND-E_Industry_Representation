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
price_data = pd.read_csv('input/avg_nodal_price.csv')

fuel_data = pd.read_csv('input/Fuel.csv', sep = ',', index_col=0)

price_elec = np.array(price_data['0'])  # cents/MWh


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

#%%
'''
Read Plant capacity from Standort sheet
'''
steel_plants = pd.read_csv('optimization/input/Standorte.csv',encoding='iso-8859-1')

optimization_horizon = 24*7    #in hours 

EAF_plants = steel_plants.loc[steel_plants['Process Chain'] == 'Scrap-EAF']
EAF_plants = EAF_plants.dropna(subset = ['Kapazität (Mio. t Rohstahl/yr)'])
EAF_plants['Hourly_steel_prod'] = EAF_plants['Kapazität (Mio. t Rohstahl/yr)']*10**6/365/24
EAF_plants = EAF_plants.drop(['Bundesland', 'Latitude', 'Longitude', 'Subsector', 'Product',
                 'Process', 'Quelle Standort'], axis = 1)
EAF_plants = EAF_plants.drop(EAF_plants.columns[4:20], axis = 1)  

EAF_plants['Opt Target'] =  EAF_plants['Hourly_steel_prod'] * optimization_horizon



steel_plants = pd.read_csv('Steel_Plant_Data/eaf_steel_plants_mapped_to_buses.csv')
steel_plants['capacity'] =  np.array(EAF_plants['Kapazität (Mio. t Rohstahl/yr)'])
steel_plants['hourly production'] = steel_plants['capacity']*10**6/365/24


#%%
#for i in range(0, len(steel_plants['capacity'])):
for i in range(0,1):
    #hourly limits
    limits = power_limits(steel_plants['hourly production'].iloc[i], spec_elec_cons, iron_mass_ratio)

    base_model = Price_Opt(price_data=price_data,
                       fuel_data=fuel_data,
                       spec_elec_cons=spec_elec_cons,
                       spec_ng_cons=spec_ng_cons,
                       spec_coal_cons=spec_coal_cons,
                       iron_mass_ratio=iron_mass_ratio,
                       steel_prod=steel_plants['hourly production'].iloc[i],
                       optimization_horizon=optimization_horizon,
                       limits=limits,
                       flexibility_params=None)

    solved_model = solver.solve(base_model)

    base_model_params = get_values(base_model, optimization_horizon, price_data, fuel_data, spec_elec_cons)

    pos_flex_total, neg_flex_total = flexibility_available(base_model, base_model_params['elec_cons'], limits, optimization_horizon) 

# %%
pos_flex_total, neg_flex_total = flexibility_available(base_model, base_model_params['elec_cons'], limits, optimization_horizon) 

flex_amt = pd.DataFrame()
flex_amt['pos'] = pos_flex_total
flex_amt['neg'] = neg_flex_total

flex_amt.to_csv('flex_amt.csv')
# %%
