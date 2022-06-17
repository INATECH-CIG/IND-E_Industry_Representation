'''
@ author louis

'''

import matplotlib.pyplot as plt
 
#%%    

def time_series_plot(time,*args):
   if len(args) <= 1:
       fig = plt.figure()
       
       y_values = []
       
       for data in args:           
           y_values.append(data) 
                 
           plt.plot(data)
           plt.xticks(time)
           
            
   else:
        fig, ax = plt.subplots(nrows=len(args), ncols=1, sharex=(True)) 
        y_values =[]
                
        for data in args:           
            y_values.append(data) 
            
                            
        for i in range(0,len(args)):           
            ax[i].plot(time, y_values[i]) 
                               
   plt.xticks(time)             
   plt.xlabel('Time[h]')    
                                        
   return fig


#%%

def get_values(model,optimization_horizon, input_data, fuel_data, spec_elec_cons):
    
    model_params = dict()
    
    time = []
    elec_price = []
    iron_ore = []
    dri_direct = []
    dri_to_storage = []
    liquid_steel = []
    elec_cons = []
    elec_cost = []
    ng_cons = []
    ng_cost = []
    coal_cons = []
    coal_cost = []
    total_energy_cons = []
    total_fuel_price = []
    total_energy_cost = []
    #pos_flex = []
    #neg_flex = []

# list to check flexibility calc in model 
    elec_cons_EH = []
    elec_cons_DRP = []
    elec_cons_AF = []
    

    
    for i in range(1,optimization_horizon+1):
        time.append(i)
        elec_price.append(input_data['electricity_price'][i])
        iron_ore.append(model.iron_ore[i].value)
        dri_direct.append(model.dri_direct[i].value)
        dri_to_storage.append(model.dri_to_storage[i].value)
        liquid_steel.append(model.liquid_steel[i].value)
        elec_cons.append(model.elec_cons[i].value)
        elec_cost.append(model.elec_cost[i].value)
        ng_cons.append(model.ng_cons[i].value)
        ng_cost.append(model.ng_cost[i].value)
        coal_cons.append(model.coal_cons[i].value)
        coal_cost.append(model.coal_cost[i].value)
                

        elec_cons_EH.append(spec_elec_cons['electric_heater']*model.iron_ore[i].value)
        elec_cons_DRP.append(spec_elec_cons['iron_reduction']*model.dri_direct[i].value)
        elec_cons_AF.append( spec_elec_cons['arc_furnace']*model.liquid_steel[i].value)

        
 # quick model check that consumption increases with decreasing fuel price 
        total_energy_cons.append(model.elec_cons[i].value + model.ng_cons[i].value + model.coal_cons[i].value) 
        total_fuel_price.append(input_data['electricity_price'].iat[i] +\
                                 fuel_data['natural gas'].iat[i] +\
                                 fuel_data['hard coal'].iat[i])
        total_energy_cost.append(model.elec_cost[i].value + model.ng_cost[i].value + model.coal_cost[i].value )

        #pos_flex.append(model.pos_flex[i].value) 
        #neg_flex.append(model.neg_flex[i].value)
        
        model_params['time_step'] = time
#        model_params['elec_price'] = elec_price
        model_params['iron_ore'] = iron_ore
        model_params['dri_direct'] = dri_direct
        model_params['dri_to_storage'] = dri_to_storage
        model_params['liquid_steel'] =liquid_steel
        model_params['elec_cons'] =elec_cons
        model_params['ng_cons'] = ng_cons
        model_params['coal_cons'] =coal_cons
        model_params['coal_cost'] = coal_cost
        model_params['EH_elec_cons'] = elec_cons_EH
        model_params['DRP_elec_cons'] = elec_cons_DRP
        model_params['AF_elec_cons'] = elec_cons_AF
# =============================================================================
#         model_params['elec_cons_EH'] =elec_cons_EH
#         model_params['elec_cons_DRP'] = elec_cons_DRP
#         model_params['elec_cons_AF'] =elec_cons_AF
# =============================================================================
        model_params['total_energy_cons'] =total_energy_cons
        model_params['total_fuel_price'] = total_fuel_price
        model_params['total_energy_cost'] = total_energy_cost
        #model_params['pos_flex'] = pos_flex
        #model_params['neg_flex'] = neg_flex
        
    return model_params
        
        
        
#%%       
       
# Available Flexibility at each time step

def flexibility_available(model, elec_cons, limits, optimization_horizon) :
    
    pos_flex_total = []
    neg_flex_total = []
        
    for i in range(1, optimization_horizon+1):
                 
    # potential to increase elec consumption from grid
      neg_flex_total.append(limits['Total_max'] - elec_cons[i-1])
      
     # potential to reduce elec consumption         
      pos_flex_total.append(elec_cons[i-1] - limits['Total_min'])
                      
    return pos_flex_total, neg_flex_total

#%%

def power_limits(plant_cap, spec_elec_cons, iron_mass_ratio, optimization_horizon, steel_prod):
    
    liquid_steel_max = plant_cap*steel_prod/optimization_horizon
    liquid_steel_min = .25*liquid_steel_max
    
    dri_max = liquid_steel_max/iron_mass_ratio['DRI']
    dri_min = dri_max*.25 #liquid_steel_min/iron_mass_ratio['DRI']
    
    iron_ore_max = dri_max/iron_mass_ratio['iron']
    iron_ore_min = iron_ore_max*.25
    
    EH_max = spec_elec_cons['electric_heater']*iron_ore_max
    EH_min = spec_elec_cons['electric_heater']*iron_ore_min
    
    DRP_max = spec_elec_cons['iron_reduction']*dri_max
    DRP_min = spec_elec_cons['iron_reduction']*dri_min
    
    AF_max = spec_elec_cons['arc_furnace']*liquid_steel_max
    AF_min = spec_elec_cons['arc_furnace']*liquid_steel_min
        
    
    
    limits = {'max_ls': liquid_steel_max,
              'min_ls': liquid_steel_min,
              'max_dri': dri_max,
              'min_dri': dri_min,
              'max_iron': iron_ore_max,
              'min_iron': iron_ore_min,
              'EH_max': EH_max ,               #93
              'EH_min': EH_min,               #23
              'DRP_max': DRP_max,              #20
              'DRP_min': DRP_min,               #5
              'AF_max': AF_max,               #85
              'AF_min': AF_min,               #21
              'Total_max': EH_max + DRP_max + AF_max,           #198
              'Total_min': EH_min + DRP_min + AF_min             #49

              }
    
    
    return limits
    
    
   
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    


