# -*- coding: utf-8 -*-
"""
Created on Thu May 19 14:48:30 2022

@author: louis
"""
# %%
import os as os
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
from misc import time_series_plot, get_values, flexibility_available, power_limits
from optimization import Price_Opt
import numpy as np

# %%
solver = pyo.SolverFactory('glpk')  # alternative : gurobi 

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

plant_cap = 3000
steel_prod = 2000
optimization_horizon = 24

#%%
limits = power_limits(plant_cap, spec_elec_cons, iron_mass_ratio, optimization_horizon)

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
            
#%%                                                                      
time_series_plot(['total elec_consumption', 'elec price'],base_model_params['time_step'],
                 base_model_params['elec_cons'],price_elec[0:optimization_horizon])

time_series_plot(['dri direct', 'dri to storage', 'dri from storage', 'storage'],base_model_params['time_step'], base_model_params['dri_direct'],
                 base_model_params['dri_to_storage'], base_model_params['dri_from_storage'],base_model_params['storage'])


time_series_plot(['EH elec cons', 'DRP elec cons', 'AF elec cons'],base_model_params['time_step'], base_model_params['EH_elec_cons'],
                 base_model_params['DRP_elec_cons'], base_model_params['AF_elec_cons'])

time_series_plot(['elec price'],base_model_params['time_step'],
                 price_elec[0:optimization_horizon])

time_series_plot(['dri direct', 'dri to storage', 'dri from storage','DRP elec cons', 'AF elec cons'],base_model_params['time_step'], base_model_params['dri_direct'],
                 base_model_params['dri_to_storage'], base_model_params['dri_from_storage'],base_model_params['DRP_elec_cons'], base_model_params['AF_elec_cons'])

#%%
base_case_cons = np.array(base_model_params['elec_cons'])
base_case_cost = sum(base_case_cons*price_elec[0:optimization_horizon])

 
#%%
#Flexibility available at each time step - quanity and cost 
pos_flex_total, neg_flex_total = flexibility_available(base_model, base_model_params['elec_cons'], limits, optimization_horizon) 
    
time_series_plot(['total elec consumption', 'Neg Flex', 'Pos Flex'],base_model_params['time_step'], base_model_params['elec_cons'], neg_flex_total, pos_flex_total)

pos_flex_hourly = np.array(pos_flex_total)
neg_flex_hourly = np.array(neg_flex_total)

pos_flex_cost_hourly = pos_flex_hourly*price_elec[0:optimization_horizon]
neg_flex_cost_hourly = neg_flex_hourly*price_elec[0:optimization_horizon]



# %%
# Run model with flexibility called

def calc_flexibility_costs(flex_type='pos'):
    flex_cost = []
    for flex_hour in range(1,24):
        if flex_type == 'pos':
            flex_amount = pos_flex_hourly[flex_hour]
            cons_signal = base_model_params['elec_cons'][flex_hour] - flex_amount
        else:
            flex_amount = neg_flex_hourly[flex_hour]
            cons_signal = base_model_params['elec_cons'][flex_hour] + flex_amount

        if flex_amount == 0:
            flex_cost.append(0)
            continue

        flexibility = {'hour_called': flex_hour,
                    'cons_signal': cons_signal,
                    'type': flex_type}

        flex_model = Price_Opt(input_data=input_data,
                            fuel_data=fuel_data,
                            spec_elec_cons=spec_elec_cons,
                            spec_ng_cons=spec_ng_cons,
                            spec_coal_cons=spec_coal_cons,
                            iron_mass_ratio=iron_mass_ratio,
                            steel_prod=steel_prod,
                            optimization_horizon=optimization_horizon,
                            limits=limits,
                            flexibility_params=flexibility)

        solved_model = solver.solve(flex_model)

        if (solved_model.solver.termination_condition == TerminationCondition.infeasible):
            if flex_type == 'pos':
                pos_flex_hourly[flex_hour] = 0
            else:
                neg_flex_hourly[flex_hour] = 0
            
            flex_cost.append(0)
            continue

        flex_model_params = get_values(model=flex_model,
                                    optimization_horizon=optimization_horizon,
                                    input_data=input_data,
                                    fuel_data=fuel_data,
                                    spec_elec_cons=spec_elec_cons)

        #time_series_plot(flex_model_params['time_step'], flex_model_params['elec_cons'])

        flex_case_cons = np.array(flex_model_params['elec_cons'])
        flex_case_cost = sum(flex_case_cons*price_elec[0:optimization_horizon])

        cost_flexibility = (flex_case_cost - base_case_cost)/flex_amount
        flex_cost.append(cost_flexibility)
    return flex_cost

#%%
flex_cost_pos=calc_flexibility_costs(flex_type='pos')
flex_cost_neg=calc_flexibility_costs(flex_type='neg')
# %%
