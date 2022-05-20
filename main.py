# -*- coding: utf-8 -*-
"""
Created on Thu May 19 14:48:30 2022

@author: louis
"""

# -*- coding: utf-8 -*-
"""
Created on Sun May  8 07:58:23 2022

@author: louis
"""

# -*- coding: utf-8 -*-
"""
Created on Mon Apr  4 13:07:25 2022

@author: louis
"""
# %%
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import pprint
from misc import time_series_plot
from misc import get_values
from misc import flexibility_available
from optimization import Price_Opt

import matplotlib.pyplot as plt
# %%
solver = pyo.SolverFactory('glpk')  # alternative : gurobi 

input_data = pd.read_csv('input/Data.csv', sep = ';', index_col=0)

fuel_data = pd.read_csv('input/Fuel.csv', sep = ',', index_col=(0))

price_elec = input_data['electricity_price']  #could also use raw_data['electricity_price].iloc[i] below
price_ng = fuel_data['natural gas']
price_coal = fuel_data['hard coal']

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
# Run model without flexibility 

steel_prod = 2000
optimization_horizon = 24

model = Price_Opt(input_data, fuel_data, spec_elec_cons, spec_ng_cons, spec_coal_cons, iron_mass_ratio, \
                  steel_prod, optimization_horizon, None)
solved_model = solver.solve(model)


model_params,time,elec_price, iron_ore, dri, liquid_steel, elec_cons, elec_cost, ng_cons, ng_cost, coal_cons,\
    coal_cost, total_energy_cons,total_fuel_price, total_energy_cost,\
        elec_cons_EH, elec_cons_DRP, elec_cons_AF, pos_flex, neg_flex = get_values(model,optimization_horizon,\
                                                                                   input_data, fuel_data, \
                                                                                       spec_elec_cons)

time_series_plot(time,elec_cons)

base_case_cons = elec_cons
base_case_cost = sum(elec_cost)

#%%

power_limits = {'EH_max': max(elec_cons_EH),               #93
                'EH_min': min(elec_cons_EH),               #23
                'DRP_max':max(elec_cons_DRP),              #20
                'DRP_min': min(elec_cons_DRP),               #5
                'AF_max': max(elec_cons_AF),               #85
                'AF_min': min(elec_cons_AF),               #21
                'Total_max': max(elec_cons_EH) + max(elec_cons_DRP)+ max(elec_cons_AF),           #198
                'Total_min':min(elec_cons_EH) + min(elec_cons_DRP)+ min(elec_cons_AF) }            #49

#Flexibility vailable at each time step 
pos_flex_total, neg_flex_total = flexibility_available(model, elec_cons, power_limits, optimization_horizon) 
    
# %%
# Run model with flexibility called 

flex_hour = 10
flexibility = {'hour_called': flex_hour,
               'amt_called': 60,
               'type': 'pos'}

steel_prod = 2000
optimization_horizon = 24

model = Price_Opt(input_data, fuel_data, spec_elec_cons, spec_ng_cons, spec_coal_cons, iron_mass_ratio, \
                  steel_prod, optimization_horizon, flexibility)
solved_model = solver.solve(model)


time,elec_price, iron_ore, dri, liquid_steel, elec_cons, elec_cost, ng_cons, ng_cost, coal_cons,\
    coal_cost, total_energy_cons,total_fuel_price, total_energy_cost,\
        elec_cons_EH, elec_cons_DRP, elec_cons_AF, pos_flex, neg_flex = get_values(model,optimization_horizon,\
                                                                                   input_data, fuel_data, \
                                                                                       spec_elec_cons)

time_series_plot(time,elec_cons)

flex_case_cons = elec_cons
flex_case_cost = sum(elec_cost)
  

cost_flexibility = (flex_case_cost - base_case_cost)/100   #Euro/MWh

#%%
