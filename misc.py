'''
@ author louis

'''

import matplotlib.pyplot as plt

x1 = [1,2,3,4]
x2 = [1,2,3,4,5]

def time_series_plot(*args):
    
    fig, ax = plt.subplots(nrows=len(args),ncols=1, sharex=(True)) 
    
    y_values =[]
    

    
    for data in args:           
        y_values.append(data)                     
        
    for i in range(0,len(args)):           
                      
        ax[i].plot(y_values[i]) 
        ax[i]._get_lines.get_next_color()
       
        plt.xlabel('Time[h]')    
                                        
    return fig
     






    


   
   

 
    
  

