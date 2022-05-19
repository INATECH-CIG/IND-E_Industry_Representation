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

power_limits = {'EH_max': 93,
                'EH_min': 23,
                'DRP_max': 20,
                'DRP_min': 5,
                'AF_max': 85,
                'AF_min': 21,
                'Total_max': 198,
                'Total_min':49 }

#%%
# Run model without flexibility 

steel_prod = 2000
optimization_horizon = 24

model = Price_Opt(input_data, fuel_data, spec_elec_cons, spec_ng_cons, spec_coal_cons, iron_mass_ratio, \
                  steel_prod, optimization_horizon, None)
solved_model = solver.solve(model)


time,elec_price, iron_ore, dri, liquid_steel, elec_cons, elec_cost, ng_cons, ng_cost, coal_cons,\
    coal_cost, total_energy_cons,total_fuel_price, total_energy_cost,\
        elec_cons_EH, elec_cons_DRP, elec_cons_AF, pos_flex, neg_flex = get_values(model,optimization_horizon,\
                                                                                   input_data, fuel_data, \
                                                                                       spec_elec_cons)

time_series_plot(time,elec_cons)

base_case_cons = elec_cons
base_case_cost = sum(elec_cost)
  
    
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

# Available Flexibility at each time step

p_elec_max = power_limits['EH_max'] + power_limits['DRP_max'] + power_limits['AF_max']    #max power eh, drp, arc furnace

p_elec_min = power_limits['EH_min'] + power_limits['DRP_min'] + power_limits['AF_min']  

def flexibility_available(model, elec_cons) :
    
    pos_flex_total = []
    neg_flex_total = []
        
    for i in range(1, optimization_horizon+1):
                 
    # potential to increase elec consumption from grid
      neg_flex_total.append(p_elec_max - elec_cons[i-1])
      
     # potential to reduce elec consumption         
      pos_flex_total.append(elec_cons[i-1] - p_elec_min)
                      
    return pos_flex_total, neg_flex_total


pos_flex_total, neg_flex_total = flexibility_available(model, elec_cons) 

