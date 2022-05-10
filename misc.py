'''
@ author louis

'''

import matplotlib.pyplot as plt

x1 = [1,2,3,4]
x2 = [7,8,9,10,11,12,12]
t = [0,1,2,3]

 
#%%    

def time_series_plot(time,*args):
    
    fig, ax = plt.subplots(nrows=len(args),ncols=1, sharex=(True)) 
    
    y_values =[]
        
    for data in args:           
        y_values.append(data)                     
        
    for i in range(0,len(args)):           
                      
        ax[i].plot(time, y_values[i]) 
        #x[i]._get_lines.get_next_color()
        
             
        plt.xlabel('Time[h]')    
                                        
    return fig
     
#%%


# =============================================================================
# def time_series_plot(time,*args):
#     
#     fig, ax = plt.subplots(nrows=len(args),ncols=1, sharex=(True)) 
#     
#     y_values =[]
#         
#     for data in args: 
#                 
#         y_values.append(data) 
#     
#         y_cut = []
#         
#         for t in range(0, len(time)+1):
#             print(t)
#             y_cut.append(y_values[data])
#             
#             print(y_cut[t])
#                     
#         
#     for i in range(0,len(args)):           
#                       
#         ax[i].plot(time, y_values[i]) 
#         #x[i]._get_lines.get_next_color()
#        
#         plt.xlabel('Time[h]')    
#                                         
#     return fig
#      
# 
# =============================================================================

   
   

 
    
  

