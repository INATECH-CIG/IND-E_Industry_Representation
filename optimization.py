# -*- coding: utf-8 -*-
"""
Created on Wed May 18 13:10:55 2022

@author: louis
"""

import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

solver = pyo.SolverFactory('glpk') 

def Price_Opt(input_data,
              fuel_data,
              spec_elec_cons,
              spec_ng_cons,
              spec_coal_cons,
              iron_mass_ratio,
              steel_prod,
              optimization_horizon,
              limits,
              flexibility_params=None,):

    model = pyo.ConcreteModel()
    
    model.t = pyo.RangeSet(1, optimization_horizon)
            
    model.iron_ore = pyo.Var(model.t, domain = pyo.NonNegativeReals) #bounds 62.5- 250
    model.iron_ore_on = pyo.Var(model.t, within=pyo.Binary)

    model.dri_direct = pyo.Var(model.t, domain = pyo.NonNegativeReals)        #bounds 40-155
    model.dri_to_storage = pyo.Var(model.t, domain = pyo.NonNegativeReals)
    model.dri_from_storage = pyo.Var(model.t, domain = pyo.NonNegativeReals)
    
    model.liquid_steel = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (limits['min_ls'],limits['max_ls']))  #bounds 37.5 - 150

    model.storage = pyo.Var(model.t, domain=pyo.NonNegativeReals, bounds=(0,100))
    
    model.elec_cons = pyo.Var(model.t, domain = pyo.NonNegativeReals)
    model.ng_cons = pyo.Var(model.t, domain = pyo.NonNegativeReals)
    model.coal_cons = pyo.Var(model.t, domain = pyo.NonNegativeReals)

    model.elec_cost = pyo.Var(model.t)
    model.ng_cost = pyo.Var(model.t)
    model.coal_cost = pyo.Var(model.t)
    
    #flexibility variables 
    model.pos_flex = pyo.Var(model.t,domain = pyo.NonNegativeReals )  #could set bounds to power limits
    model.neg_flex = pyo.Var(model.t, domain = pyo.NonNegativeReals)

    #represents the step of electric arc furnace
    def eaf_rule(model, t):
        return model.liquid_steel[t] == (model.dri_direct[t] + model.dri_from_storage[t]*0.95) / iron_mass_ratio['DRI']

    #represents the direct reduction plant
    def iron_reduction_rule(model, t):
        return model.dri_direct[t] + model.dri_to_storage[t] == model.iron_ore[t] / iron_mass_ratio['iron']

    def dri_min_rule(model, t):
        return (model.dri_direct[t] + model.dri_to_storage[t]) >= limits['min_dri']*model.iron_ore_on[t]
    
    def dri_max_rule(model, t):
        return (model.dri_direct[t] + model.dri_to_storage[t]) <= limits['max_dri']*model.iron_ore_on[t]
    
    def iron_ore_min_rule(model, t):
        return model.iron_ore[t] >= limits['min_iron']*model.iron_ore_on[t]     #62.5
        
    def iron_ore_max_rule(model, t):
        return model.iron_ore[t] <= limits['max_iron']*model.iron_ore_on[t]
    
    def storage_rule(model, t):
        if t==1:
            return model.storage[t] == 0 + model.dri_to_storage[t] - model.dri_from_storage[t]
        else:
            return model.storage[t] == model.storage[t-1] + model.dri_to_storage[t] - model.dri_from_storage[t]
    
    #total electricity consumption
    def elec_consumption_rule(model, t):
        return model.elec_cons[t] == spec_elec_cons['electric_heater']*model.iron_ore[t] + \
            spec_elec_cons['iron_reduction']*(model.dri_direct[t] + model.dri_from_storage[t]) + \
            spec_elec_cons['arc_furnace']*model.liquid_steel[t]

    #total electricity cost
    def elec_cost_rule(model, t):
        return model.elec_cost[t] == input_data['electricity_price'].iat[t]*model.elec_cons[t]
    
# =============================================================================
#     #flexibility rule
    def elec_flex_rule(model, t):
        if t == flexibility_params['hour_called']:
        #reduce consumption
            if flexibility_params['type'] == 'pos':
                return model.elec_cons[t] <= flexibility_params['amt_called']
            else:
                return model.elec_cons[t] >= flexibility_params['amt_called']
        else:
            return model.elec_cons[t] >= 0
#         
# =============================================================================
        
    #total NG consumption
    def ng_consumption_rule(model,t):
        return model.ng_cons[t] == spec_ng_cons['iron_reduction']*(model.dri_direct[t] + model.dri_from_storage[t]) + \
            spec_ng_cons['arc_furnace']*model.liquid_steel[t] 
    
    #total NG cost
    def ng_cost_rule(model,t):
        return model.ng_cost[t] == fuel_data['natural gas'].iat[t]*model.ng_cons[t]
    
    #total coal consumption
    def coal_consumption_rule(model, t):
        return model.coal_cons[t] == spec_coal_cons['arc_furnace']*model.liquid_steel[t]
    
    #total coal cost
    def coal_cost_rule(model,t):
        return model.coal_cost[t] == fuel_data['hard coal'].iat[t]*model.coal_cons[t]

    def total_steel_prod_rule(model):
        return pyo.quicksum(model.liquid_steel[t] for t in model.t) >= steel_prod

    #cost objective function (elec, NG, and coal)
    def cost_obj_rule(model):
        return pyo.quicksum(model.elec_cost[t] + model.ng_cost[t] + model.coal_cost[t] for t in model.t)

    model.eaf_rule = pyo.Constraint(model.t, rule=eaf_rule)
    model.iron_reduction_rule = pyo.Constraint(model.t, rule=iron_reduction_rule)
    model.elec_consumption_rule = pyo.Constraint(model.t, rule=elec_consumption_rule)
    model.elec_cost_rule = pyo.Constraint(model.t, rule=elec_cost_rule)
    model.ng_consumption_rule = pyo.Constraint(model.t, rule = ng_consumption_rule)
    model.ng_cost_rule = pyo.Constraint(model.t, rule = ng_cost_rule)
    model.coal_consumption_rule = pyo.Constraint(model.t, rule = coal_consumption_rule)
    model.coal_cost_rule = pyo.Constraint(model.t, rule = coal_cost_rule)
    model.total_steel_prod_rule = pyo.Constraint(rule = total_steel_prod_rule)

    model.storage_rule = pyo.Constraint(model.t, rule = storage_rule)
    model.dri_min_rule = pyo.Constraint(model.t, rule = dri_min_rule)
    model.dri_max_rule = pyo.Constraint(model.t, rule = dri_max_rule)

    model.iron_ore_min_rule = pyo.Constraint(model.t, rule = iron_ore_min_rule)
    model.iron_ore_max_rule = pyo.Constraint(model.t, rule = iron_ore_max_rule)
    
    #flexibility constraint included if called
    if flexibility_params is not None:
        model.elec_flex_rule = pyo.Constraint(model.t, rule = elec_flex_rule)
        
    model.obj = pyo.Objective(rule = cost_obj_rule, sense = pyo.minimize)

    return model
# %%
