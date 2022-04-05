# -*- coding: utf-8 -*-
"""
Created on Mon Apr  4 13:07:25 2022

@author: louis
"""
import os as os
#os.chdir('C:/Users/louis/UNI_SSE/Research/IND-E')


import pandas as pd

import pyomo.environ as pyo

from pyomo.opt import SolverFactory

solver = pyo.SolverFactory('glpk')

filename = os.path.join(os.getcwd(), "Data_.csv")
raw_data = pd.read_csv(filename)

#raw_data = pd.read_csv('steel_model_optimization/Data_.csv', sep = ';', index_col=0)

price_elec = raw_data['electricity_price']  #could also use raw_data['electricity_price].iloc[i] below
price_ng = None
price_coal = None
#%%
specific__elec_consumption_EH = .37

specific_elec_consumption_DR = .127
specific_ng_consumption_DR = 1.56

specific_elec_consumption_EAF = .575
specific_ng_consumption_EAF = .216
specific_coal_consumption_EAF = .028


def Cost_Optimization(price_elec, price_ng, price_coal):
    
    model = pyo.ConcreteModel()
    
    model.i = pyo. RangeSet(0, len(price_elec)-1)

    model.Iron = pyo.Var(model.i,domain= pyo.NonNegativeReals, bounds=(62.5, 250)) #variable for amount of iron
    model.DRI = pyo.Var(model.i,domain= pyo.NonNegativeReals, bounds = (40.0, 155.0))  #variable for amount of DRI
    model.LS = pyo.Var(model.i,domain= pyo.NonNegativeReals, bounds = (37.5, 150.0))  #variable for amount of LS
    
    model.P_Elec = pyo.Var(model.i,domain = pyo.NonNegativeReals)
    model.P_NG = pyo.Var(model.i,domain = pyo.NonNegativeReals)
    model.P_Coal = pyo.Var(model.i,domain = pyo.NonNegativeReals)
    
    model.P_Elec_price = pyo.Var(model.i,domain = pyo.NonNegativeReals)
    model.P_NG_price = pyo.Var(model.i,domain = pyo.NonNegativeReals)
    model.P_Coal_price = pyo.Var(model.i,domain = pyo.NonNegativeReals)
    model.Total_cost = pyo.Var(domain = pyo.NonNegativeReals)
    
    
    def P_elec_rule(model,i):
        
      model.P_Elec[i] == (specific__elec_consumption_EH * model.Iron[i]
                                    + specific_elec_consumption_DR * model.DRI[i]
                                    + specific_elec_consumption_EAF * model.LS[i] )
      
      return model.P_Elec_price[i] == model.P_Elec[i] * raw_data['electricity_price'].iloc[i]

    def P_ng_rule(model,i):
        
        model.P_NG[i] == (specific_ng_consumption_DR * model.DRI[i]
                                 + specific_ng_consumption_EAF * model.LS[i])
        
        return model.P_NG_price[i] == model.P_NG[i] * raw_data['electricity_price'].iloc[i]
    
    def P_coal_rule(model,i):
        
         model.P_Coal[i] == (specific_coal_consumption_EAF * model.LS[i])
         
         return model.P_Coal_price[i] == model.P_Coal[i] * raw_data['electricity_price'].iloc[i]
 
    def mass_balance_rule1 (model, i):
        
        return 1.66 * model.Iron[i] == 1.03 * model.DRI[i]
   
    def mass_balance_rule2 (model, i):
        
        return  1.03* model.DRI[i] == model.LS[i]
    
    def Total_cost_rule(model):
        
        return model.Total_cost == pyo.summation(model.P_Elec_price, model.P_NG_price, model.P_Coal_price)
    
    
    
    model.P_elec_rule = pyo.Constraint(model.i, rule = P_elec_rule)   
    model.P_ng_rule = pyo.Constraint(model.i, rule = P_ng_rule)
    model.P_coal_rule = pyo.Constraint(model.i, rule = P_coal_rule)  
    model.mass_balance_rule1 = pyo.Constraint(model.i, rule = mass_balance_rule1)
    model.mass_balance_rule2 = pyo.Constraint(model.i, rule = mass_balance_rule2)
    model.Total_cost_rule = pyo.Constraint(rule = Total_cost_rule)
    
    
    def Obj_rule(model):
        
        return model.Total_cost
    
    
    model.obj = pyo.Objective(rule = Obj_rule, sense = pyo.minimize)
    
    solver.solve(model)
    
    return model


def get_values(model):
    
    Elec = []
    NG = []
    Coal = []
    
    for i in range(len(price_elec)):
        
        Elec.append( model.P_Elec[i].value)
        NG.append(model.P_NG[i].value)
        Coal.append(model.P_Coal[i].value)
        
    return Elec, NG, Coal
        
#%%
model = Cost_Optimization(price_elec, price_ng, price_coal)


Elec, NG, Coal = get_values(model) 
    

print(pyo.value(model.obj))
    
    
    
    