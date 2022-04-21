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

optimization_horizon = 5


# %%
def Price_Opt(spec_elec_cons, spec_ng_cons, spec_coal_cons, iron_mass_ratio, steel_prod, optimization_horizon):
    model = pyo.ConcreteModel()
    
    model.t = pyo.RangeSet(1, optimization_horizon)
        
    model.iron_ore = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (62.5,250))
    model.dri = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (40,155))
    model.liquid_steel = pyo.Var(model.t, domain = pyo.NonNegativeReals, bounds = (37.5,150))

    model.elec_cons = pyo.Var(model.t, domain = pyo.NonNegativeReals)
    model.ng_cons = pyo.Var(model.t, domain = pyo.NonNegativeReals)
    model.coal_cons = pyo.Var(model.t, domain = pyo.NonNegativeReals)

    model.elec_cost = pyo.Var(model.t)
    model.ng_cost = pyo.Var(model.t)
    model.coal_cost = pyo.Var(model.t)

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

    #cost objective function
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
    
    model.obj = pyo.Objective(rule = cost_obj_rule, sense = pyo.minimize)

    return model
# %%
steel_prod = 500
model = Price_Opt(spec_elec_cons, spec_ng_cons, spec_coal_cons, iron_mass_ratio, steel_prod, optimization_horizon)
solved_model = solver.solve(model)
# %%
def get_values(model):
    iron_ore = []
    dri = []
    liquid_steel = []
    elec_cons = []
    elec_cost = []
    ng_cons = []
    ng_cost = []
    coal_cons = []
    coal_cost = []
    
    
    for i in range(1,optimization_horizon+1):
        iron_ore.append(model.iron_ore[i].value)
        dri.append(model.dri[i].value)
        liquid_steel.append(model.liquid_steel[i].value)
        elec_cons.append(model.elec_cons[i].value)
        elec_cost.append(model.elec_cost[i].value)
        ng_cons.append(model.ng_cons[i].value)
        ng_cost.append(model.ng_cost[i].value)
        coal_cons.append(model.coal_cons[i].value)
        coal_cost.append(model.coal_cost[i].value)

    return iron_ore, dri, liquid_steel, elec_cons, elec_cost, ng_cons, ng_cost, coal_cons, coal_cost

# %%
iron_ore, dri, liquid_steel, elec_cons, elec_cost, ng_cons, ng_cost, coal_cons, coal_cost = get_values(model)




    
    
# %%
