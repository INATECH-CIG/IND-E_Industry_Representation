# -*- coding: utf-8 -*-
"""
Created on Mon Apr  4 13:07:25 2022

@author: louis
"""
# %%
import os as os
#os.chdir('C:/Users/louis/UNI_SSE/Research/IND-E')


import pandas as pd

import pyomo.environ as pyo

from pyomo.opt import SolverFactory
# %%
solver = pyo.SolverFactory('glpk')  # alternative : gurobi 

filename = os.path.join(os.getcwd(), "Data_.csv")
raw_data = pd.read_csv(filename, sep = ';', index_col=0)

price_elec = raw_data['electricity_price']  #could also use raw_data['electricity_price].iloc[i] below
price_ng = None
price_coal = None

# Dictionaries for Specific ELec and Mass Balance Ratio Coefficients 
specific_elec_consumption = {1:.37, 2:.127, 3:.575}
ratio = {1:1.66, 2:1.03, 3:1}

# =============================================================================
# Segment Problem to first find optimized electricity consumption
# 
#         - use the solved values for Iron, DRI, and LS to determine NG and Coal demand
#                  -solution for min elec power 
#         - add time step to second optimization problem to include pricing
#                  -need NG and Coal prcies to determine optimized Elec, NG, Coal mixture 
#                        - solution for lowest cost
# =============================================================================
# %%

def Electricity_Opt(specific_elec_consumption, ratio):
    
    model = pyo.ConcreteModel()
    
    model.i = pyo.RangeSet(1, len(specific_elec_consumption.keys()))
    
    model.C = pyo.Param(model.i, initialize = specific_elec_consumption)
    model.F = pyo.Param(model.i, initialize = ratio)
    
    
    model.I = pyo.Var(domain = pyo.NonNegativeReals, bounds = (62.5,250))       
    model.DRI = pyo.Var(domain = pyo.NonNegativeReals, bounds = (40,155))
    model.LS = pyo.Var(domain = pyo.NonNegativeReals, bounds = (37.5,150))
    
    def obj_rule(model):
        return model.C[1]*model.I + model.C[2]*model.DRI + model.C[3]*model.LS
    
    model.obj = pyo.Objective(rule = obj_rule, sense = pyo.minimize)
    
    
    def con_rule1(model):
        return model.F[1]*model.I == model.F[2]* model.DRI
    
    model.con1 = pyo.Constraint(rule = con_rule1)
    
    def con_rule2(model):
        return model.F[2]*model.DRI == model.F[3]*model.LS
    
    model.con2 = pyo.Constraint(rule = con_rule2)
    
    solver.solve(model)
    
    return model
# %%
model = Electricity_Opt(specific_elec_consumption, ratio)

print(pyo.value(model.obj))
print(pyo.value(model.I))
print(pyo.value(model.DRI))
print(pyo.value(model.LS))






    
    
# %%
