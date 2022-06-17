# -*- coding: utf-8 -*-
"""
Created on Thu May 19 14:48:30 2022

@author: louis
"""
# %%
import os as os
import pandas as pd
import pyomo.environ as pyo
from misc import time_series_plot, get_values, flexibility_available, power_limits
from optimization import Price_Opt
import numpy as np

# %%
solver = pyo.SolverFactory('glpk')  # alternative : gurobi 

input_data = pd.read_csv('input/Data.csv', sep = ';', index_col=0)

fuel_data = pd.read_csv('input/Fuel.csv', sep = ',', index_col=0)

price_elec = np.array(input_data['electricity_price'])  # cents/KWh
price_elec = price_elec*10    #euro/MWh
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
steel_prod = 2000
optimization_horizon = 24
#limits = power_limits(1, spec_elec_cons, iron_mass_ratio, optimization_horizon, steel_prod)

#MW
limits = {'max_ls': 150,
            'min_ls': 37.5,
            'max_dri': 155,
            'min_dri': 40,
            'max_iron': 250,
            'min_iron': 62.5,
            'EH_max': 93 ,               #93
            'EH_min': 23,               #23
            'DRP_max': 20,              #20
            'DRP_min': 5,               #5
            'AF_max': 85,               #85
            'AF_min': 21,               #21
            'Total_max': 198,           #198
            'Total_min': 49             #49

            }
 

#%%
# Run model without flexibility 
steel_prod = 2000
optimization_horizon = 24

model = Price_Opt(input_data=input_data,
                  fuel_data=fuel_data,
                  spec_elec_cons=spec_elec_cons,
                  spec_ng_cons=spec_ng_cons,
                  spec_coal_cons=spec_coal_cons,
                  iron_mass_ratio=iron_mass_ratio,
                  steel_prod=steel_prod,
                  optimization_horizon=optimization_horizon,
                  limits = limits,
                  flexibility_params=None)

solved_model = solver.solve(model)

model_params = get_values(model,optimization_horizon, input_data, fuel_data, spec_elec_cons)
                                                                                  
time_series_plot(model_params['time_step'],model_params['elec_cons'])
time_series_plot(model_params['time_step'],model_params['dri_direct'],model_params['dri_to_storage'], model_params['AF_elec_cons'],model_params['storage'])
time_series_plot(model_params['time_step'],model_params['EH_elec_cons'],model_params['DRP_elec_cons'],model_params['AF_elec_cons'])
time_series_plot(model_params['time_step'],price_elec[0:optimization_horizon])

base_case_cons = np.array(model_params['elec_cons'])
base_case_cost = sum(base_case_cons*price_elec[0:optimization_horizon])

 
#%%
#Flexibility available at each time step - quanity and cost 
pos_flex_total, neg_flex_total = flexibility_available(model, model_params['elec_cons'], limits, optimization_horizon) 
    
time_series_plot(model_params['time_step'],model_params['elec_cons'],neg_flex_total,pos_flex_total)

pos_flex_hourly = np.array(pos_flex_total)
neg_flex_hourly = np.array(neg_flex_total)

pos_flex_cost_hourly = pos_flex_hourly*price_elec[0:optimization_horizon]
neg_flex_cost_hourly = neg_flex_hourly*price_elec[0:optimization_horizon]



# %%
# Run model with flexibility called 

flex_hour = 10
flexibility = {'hour_called': flex_hour,
               'amt_called': 28,
               'type': 'pos'}

steel_prod = 2000
optimization_horizon = 24

model = Price_Opt(input_data=input_data,
                  fuel_data=fuel_data,
                  spec_elec_cons=spec_elec_cons,
                  spec_ng_cons=spec_ng_cons,
                  spec_coal_cons=spec_coal_cons,
                  iron_mass_ratio=iron_mass_ratio,
                  steel_prod=steel_prod,
                  optimization_horizon=optimization_horizon,
                  limits = limits,
                  flexibility_params=flexibility)

solved_model = solver.solve(model)


model_params = get_values(model=model,
                          optimization_horizon=optimization_horizon,
                          input_data=input_data,
                          fuel_data=fuel_data,
                          spec_elec_cons=spec_elec_cons)

time_series_plot(model_params['time_step'], model_params['elec_cons'])

flex_case_cons = np.array(model_params['elec_cons'])
flex_case_cost = sum(flex_case_cons*price_elec[0:optimization_horizon])

cost_flexibility = (flex_case_cost - base_case_cost)/100   #Euro/MWh

#%%
