'''
@ author louis

'''

import matplotlib.pyplot as plt

x1 = [1,2,3,4]
x2 = [7,8,9,10]
t = [0,1,2,3]

 
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
        fig, ax = plt.subplots(nrows=len(args),ncols=1, sharex=(True)) 
              
        y_values =[]
                
        for data in args:           
            y_values.append(data) 
                            
        for i in range(0,len(args)):           
                                      
            ax[i].plot(time, y_values[i]) 
           
                        #x[i]._get_lines.get_next_color()
                    
   plt.xticks(time)             
   plt.xlabel('Time[h]')    
                                        
   return fig
     
#%%

def get_values(model,optimization_horizon, input_data, fuel_data, spec_elec_cons):
    
    time = []
    elec_price = []
    iron_ore = []
    dri = []
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
    pos_flex = []
    neg_flex = []

# list to check flexibility calc in model 
    elec_cons_EH = []
    elec_cons_DRP = []
    elec_cons_AF = []
    
    
    
    for i in range(1,optimization_horizon+1):
        time.append(i)
        elec_price.append(input_data['electricity_price'][i])
        iron_ore.append(model.iron_ore[i].value)
        dri.append(model.dri[i].value)
        liquid_steel.append(model.liquid_steel[i].value)
        elec_cons.append(model.elec_cons[i].value)
        elec_cost.append(model.elec_cost[i].value)
        ng_cons.append(model.ng_cons[i].value)
        ng_cost.append(model.ng_cost[i].value)
        coal_cons.append(model.coal_cons[i].value)
        coal_cost.append(model.coal_cost[i].value)
                
        elec_cons_EH.append(spec_elec_cons['electric_heater']*model.iron_ore[i].value)
        elec_cons_DRP.append(spec_elec_cons['iron_reduction']*model.dri[i].value)
        elec_cons_AF.append( spec_elec_cons['arc_furnace']*model.liquid_steel[i].value)
        
 # quick model check that consumption increases with decreasing fuel price 
        total_energy_cons.append(model.elec_cons[i].value + model.ng_cons[i].value + model.coal_cons[i].value) 
        total_fuel_price.append(input_data['electricity_price'].iat[i] +\
                                 fuel_data['natural gas'].iat[i] +\
                                 fuel_data['hard coal'].iat[i])
        total_energy_cost.append(model.elec_cost[i].value + model.ng_cost[i].value + model.coal_cost[i].value )

        pos_flex.append(model.pos_flex[i].value) 
        neg_flex.append(model.neg_flex[i].value)

    return time,elec_price,iron_ore, dri, liquid_steel, elec_cons, elec_cost, ng_cons, ng_cost, coal_cons, coal_cost,\
        total_energy_cons,total_fuel_price, total_energy_cost, elec_cons_EH, elec_cons_DRP, elec_cons_AF, pos_flex, neg_flex