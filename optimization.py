# -*- coding: utf-8 -*-
"""
Created on Wed May 18 13:10:55 2022

@author: louis
"""

import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

solver = pyo.SolverFactory('glpk') 

def Price_Opt(input_data, fuel_data, spec_elec_cons, spec_ng_cons, spec_coal_cons, iron_mass_ratio,
              steel_prod, optimization_horizon, flexibility_params):
   
    model = pyo.ConcreteModel()
    
    model.t = pyo.RangeSet(1, optimization_horizon)
            
    model.iron_ore = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (62.5,250)) #bounds 62.5- 250
    model.dri = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (40,155))        #bounds 40-155
    model.liquid_steel = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (37.5,150))  #bounds 37.5 - 150

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
        return model.liquid_steel[t] == model.dri[t] / iron_mass_ratio['DRI']

    #represents the direct reduction plant
    def iron_reduction_rule(model, t):
        return model.dri[t] == model.iron_ore[t] / iron_mass_ratio['iron']

    #total electricity consumption
    def elec_consumption_rule(model, t):
        return model.elec_cons[t] == spec_elec_cons['electric_heater']*model.iron_ore[t] + \
            spec_elec_cons['iron_reduction']*model.dri[t] + \
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
        return model.ng_cons[t] == spec_ng_cons['iron_reduction']*model.dri[t] + \
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
    
    #flexibility constraint included if called
    if flexibility_params is not None:
        model.elec_flex_rule = pyo.Constraint(model.t, rule = elec_flex_rule)
        
    model.obj = pyo.Objective(rule = cost_obj_rule, sense = pyo.minimize)

    return model
# %%