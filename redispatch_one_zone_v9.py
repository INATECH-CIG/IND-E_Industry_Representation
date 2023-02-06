#%%

import pypsa
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from pypsa.descriptors import get_switchable_as_dense as as_dense
from netCDF4 import Dataset
import h5py
import matplotlib.colors as mcolors
import pandas as pd
import numpy as np 

#%%

germany =pypsa.Network()
pypsa.Network.import_from_netcdf(germany, path = 'germany_for_luisa/elec_s_337.nc', skip_time=False)
#germany.set_snapshots([germany.snapshots[64]])
n = germany.copy()  # for redispatch model
m = germany.copy()  # for market model
# %%
horizon_start = 0
horizon_end = 74
solver = 'gurobi'
germany.lopf(solver_name=solver, pyomo=False,snapshots = germany.snapshots[horizon_start:horizon_end]) #snapshots = germany.snapshots[0:168])

# %%
'''
Build One Zone market model for unconstrained transmission
'''
zones = (n.buses.y > 51).map(lambda x: "Germany" if x else "Germany")

#assign buses to zones 
for c in m.iterate_components(m.one_port_components):
    c.df.bus = c.df.bus.map(zones)

for c in m.iterate_components(m.branch_components):
    c.df.bus0 = c.df.bus0.map(zones)
    c.df.bus1 = c.df.bus1.map(zones)
    internal = c.df.bus0 == c.df.bus1
    m.mremove(c.name, c.df.loc[internal].index)

m.mremove("Bus", m.buses.index)
m.madd("Bus", ["Germany"]);
# %%
#solve one zone model 
m.lopf(solver_name=solver, pyomo=False, snapshots = m.snapshots[horizon_start:horizon_end]) #snapshots = m.snapshots[0:168])

# %%
'''
redispatch model - ramp up/down generators at same cost as original dispatch 
'''

#set power output of generators equal to dispatch in two node model 
p = m.generators_t.p / m.generators.p_nom
n.generators_t.p_min_pu = p
n.generators_t.p_max_pu = p

#add new generators that ramp up/down
g_up = n.generators.copy()
g_down = n.generators.copy()

#change names to reflect up or down 
g_up.index = g_up.index.map(lambda x: x + " ramp up")
g_down.index = g_down.index.map(lambda x: x + " ramp down")

#create dataframe with time varying values for component 
#create p_max_pu time series (up) for generators : diff between nominal and dispatched - ramp up potential 
#create time series for p_min_pu : negative of dispatched power 
up = (
    as_dense(m, "Generator", "p_max_pu") * m.generators.p_nom - m.generators_t.p
).clip(0) / m.generators.p_nom
down = -m.generators_t.p / m.generators.p_nom                #former neg

#add ramp up/ramp down to name of each pu_max/min column
up.columns = up.columns.map(lambda x: x + " ramp up")
down.columns = down.columns.map(lambda x: x + " ramp down")

#add ramp up generators and drop old p_max_pu values 
n.madd("Generator", g_up.index, p_max_pu=up, **g_up.drop("p_max_pu", axis=1))

#add ramp down generators 
#set p_max pu to 0 (no dispatch allowed)
#drop prior p_max pu and p_min_pu values 
n.madd(
    "Generator",
    g_down.index,
    p_min_pu=down,             #down
    p_max_pu=0,
     sign = 1,
    **g_down.drop(["p_max_pu", "p_min_pu",'sign'], axis=1)
    
);

n.generators.loc[n.generators.index.str.contains("ramp down"), "marginal_cost"] *= -1
n.generators.loc[n.generators.index.str.contains(" ror ramp down"), "marginal_cost"] = -1

n.generators.loc[n.generators.index.str.contains(" solar ramp down"), "marginal_cost"] *= 10000
n.generators.loc[n.generators.index.str.contains(" ror ramp down"), "marginal_cost"] *= 1000
n.generators.loc[n.generators.index.str.contains(" onwind ramp down"), "marginal_cost"] *= 10000
n.generators.loc[n.generators.index.str.contains(" offwind-ac ramp down"), "marginal_cost"] *= 10000
n.generators.loc[n.generators.index.str.contains(" offwind-dc ramp down"), "marginal_cost"] *= 10000
n.generators.loc[n.generators.index.str.contains(" biomass ramp down"), "marginal_cost"] *= 100


#%%
n.lopf(solver_name=solver, pyomo=False, snapshots = n.snapshots[horizon_start:horizon_end]) 

n_flex = n.copy()

#%%
'''
Dispatch without flexibility 
'''

ramp_up_gen_noflex  = n.generators.loc[n.generators.index.str.contains("ramp up")]
ramp_up_dispatch_noflex = n.generators_t.p[ramp_up_gen_noflex.index][horizon_start:horizon_end].T.squeeze()
total_ramp_up_noflex = n.generators_t.p[ramp_up_gen_noflex.index][horizon_start:horizon_end].T.squeeze().sum().sum()

ramp_down_gen_noflex  = n.generators.loc[n.generators.index.str.contains("ramp down")]
ramp_down_dispatch_noflex = n.generators_t.p[ramp_down_gen_noflex.index][horizon_start:horizon_end].T.squeeze()
total_ramp_down_noflex = n.generators_t.p[ramp_down_gen_noflex.index][horizon_start:horizon_end].T.squeeze().sum().sum()

ren_ramp_down = n.generators.loc[n.generators.index.str.contains("onwind ramp down" or 'offwind-ac ramp down' or 'offwind-dc ramp down' or 'biomass ramp down' or 'solar ramp down' or 'ror ramp down')]
ren_ramp_down_dispatch = n.generators_t.p[ren_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_ren_ramp_down_noflex = n.generators_t.p[ren_ramp_down.index][horizon_start:horizon_end].T.squeeze().sum().sum()

ren_ramp_up = n.generators.loc[n.generators.index.str.contains("onwind ramp up" or 'offwind-ac ramp up' or 'offwind-dc ramp up' or 'biomass ramp up' or 'solar ramp up' or 'ror ramp up')]
ren_ramp_up_dispatch = n.generators_t.p[ren_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_ren_ramp_up_noflex = n.generators_t.p[ren_ramp_up.index][horizon_start:horizon_end].T.squeeze().sum().sum()


#Ramp Up/ Down Conventional Gen - without Flex
conv_gen_ramping_no_flex = pd.DataFrame(index=['OCGT','CCGT' ,'lignite', 'coal', 'oil', 'nuclear'], columns=['ramp up', 'ramp down'])

for i, j in enumerate(conv_gen_ramping_no_flex.index):    
    
    carrier_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains(j)]
    carrier_ramp_up_noflex = carrier_ramp_up_noflex[carrier_ramp_up_noflex.index.str.contains('ramp up')]
    carrier_ramp_up_dispatch_noflex = n.generators_t.p[carrier_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
    carrier_ramp_up_noflex_total =  carrier_ramp_up_dispatch_noflex.sum().sum()
    conv_gen_ramping_no_flex['ramp up'][j]= carrier_ramp_up_noflex_total
        
    carrier_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains(j)]
    carrier_ramp_down_noflex = carrier_ramp_down_noflex[carrier_ramp_down_noflex.index.str.contains('ramp down')]
    carrier_ramp_down_dispatch_noflex = n.generators_t.p[carrier_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
    carrier_ramp_down_noflex_total =  carrier_ramp_down_dispatch_noflex.sum().sum() 
    conv_gen_ramping_no_flex['ramp down'][j]= carrier_ramp_down_noflex_total


#%%
#Emissions

conv_gen_emissions = pd.DataFrame(index=['OCGT','CCGT' ,'lignite', 'coal', 'oil', 'nuclear'], columns=['co2_emissions'])

for i, j in enumerate(conv_gen_emissions.index):   
        
    plant_list = n.generators.loc[n.generators.index.str.contains('j')]
    plant_list = plant_list[plant_list.index.str.contains('ramp') == False]
    emissions = n.generators_t.p[plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum() * n.carriers.loc[j]['co2_emissions']

    ramp_up_noflex = n.generators.loc[n.generators.index.str.contains(j)]
    ramp_up_noflex = ramp_up_noflex[ramp_up_noflex.index.str.contains('ramp up')]
    ramp_up_dispatch_noflex = n.generators_t.p[ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
    ramp_up_noflex_total_emissions =  ramp_up_dispatch_noflex.sum().sum() * n.carriers.loc[j]['co2_emissions']

    ramp_down_noflex = n.generators.loc[n.generators.index.str.contains(j)]
    ramp_down_noflex = ramp_down_noflex[ramp_down_noflex.index.str.contains('ramp down')]
    ramp_down_dispatch_noflex = n.generators_t.p[ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
    ramp_down_noflex_total_emissions =  ramp_down_dispatch_noflex.sum().sum() * n.carriers.loc[j]['co2_emissions']

    conv_gen_emissions['co2_emissions'][j] = emissions - ramp_down_noflex_total_emissions + ramp_up_noflex_total_emissions


#

#%%
'''
Plots for generation - carrier & location 
'''

coal_gen_list = n.generators.loc[n.generators.carrier.str.contains('coal')]
coal_dispatch  = n.generators_t.p[coal_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= coal_dispatch,
    bus_colors="green",
    title="Total Coal Dispatch",
) 

nuclear_gen_list = n.generators.loc[n.generators.carrier.str.contains('nuclear')]
nuclear_dispatch  = n.generators_t.p[nuclear_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= nuclear_dispatch,
    bus_colors="green",
    title="Total Nuclear Dispatch",)

lignite_gen_list = n.generators.loc[n.generators.carrier.str.contains('lignite')]
lignite_dispatch  = n.generators_t.p[lignite_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= lignite_dispatch,
    bus_colors="green",
    title="Total lignite Dispatch",)

CCGT_gen_list = n.generators.loc[n.generators.carrier.str.contains('CCGT')]
CCGT_dispatch  = n.generators_t.p[CCGT_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= CCGT_dispatch,
    bus_colors="green",
    title="Total CCGT Dispatch",)


OCGT_gen_list = n.generators.loc[n.generators.carrier.str.contains('OCGT')]
OCGT_dispatch  = n.generators_t.p[OCGT_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= OCGT_dispatch,
    bus_colors="green",
    title="Total OCGT Dispatch",)

oil_gen_list = n.generators.loc[n.generators.carrier.str.contains('oil')]
oil_dispatch  = n.generators_t.p[oil_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= oil_dispatch,
    bus_colors="green",
    title="Total oil Dispatch",)

solar_gen_list = n.generators.loc[n.generators.carrier.str.contains('solar')]
solar_dispatch  = n.generators_t.p[solar_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= solar_dispatch,
    bus_colors="green",
    title="Total solar Dispatch",)

onwind_gen_list = n.generators.loc[n.generators.carrier.str.contains('onwind')]
onwind_dispatch  = n.generators_t.p[onwind_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= onwind_dispatch,
    bus_colors="green",
    title="Total onwind Dispatch",)

offwind_gen_list = n.generators.loc[n.generators.carrier.str.contains('offwind')]
offwind_dispatch  = n.generators_t.p[offwind_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= offwind_dispatch,
    bus_colors="green",
    title="Total offwind Dispatch",)

biomass_gen_list = n.generators.loc[n.generators.carrier.str.contains('biomass')]
biomass_dispatch  = n.generators_t.p[biomass_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= biomass_dispatch,
    bus_colors="green",
    title="Total biomass Dispatch",)

ror_gen_list = n.generators.loc[n.generators.carrier.str.contains('ror')]
ror_dispatch  = n.generators_t.p[ror_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,1] = n.plot(
       bus_sizes= ror_dispatch,
    bus_colors="green",
    title="Total ror Dispatch",)

#%%
'''
Sytem Cost
'''
coal_cost = n.generators_t.p[coal_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* abs(n.generators[n.generators.carrier == 'coal'].marginal_cost).mean()
coal_up_list = coal_gen_list[coal_gen_list.index.str.contains('ramp up')]
coal_up_cost = n.generators_t.p[coal_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('coal ramp up')].marginal_cost).mean()
coal_down_list = coal_gen_list[coal_gen_list.index.str.contains('ramp down')]
coal_down_cost = n.generators_t.p[coal_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('coal ramp down')].marginal_cost).mean()
coal_list = n.generators.loc[n.generators.index.str.contains('coal')]
coal_list = coal_list[coal_list.index.str.contains('ramp') == False]
coal_org_cost = n.generators_t.p[coal_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[coal_list.index].marginal_cost).mean()
coal_total_cost = coal_up_cost + coal_down_cost + coal_org_cost 

nuclear_cost = n.generators_t.p[nuclear_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* abs(n.generators[n.generators.carrier == 'nuclear'].marginal_cost).mean()
nuclear_up_list = nuclear_gen_list[nuclear_gen_list.index.str.contains('ramp up')]
nuclear_up_cost = n.generators_t.p[nuclear_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('nuclear ramp up')].marginal_cost).mean()
nuclear_down_list = nuclear_gen_list[nuclear_gen_list.index.str.contains('ramp down')]
nuclear_down_cost = n.generators_t.p[nuclear_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('nuclear ramp down')].marginal_cost).mean()
nuclear_list = n.generators.loc[n.generators.index.str.contains('nuclear')]
nuclear_list = nuclear_list[nuclear_list.index.str.contains('ramp') == False]
nuclear_org_cost = n.generators_t.p[nuclear_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[nuclear_list.index].marginal_cost).mean()
nuclear_total_cost = nuclear_up_cost + nuclear_down_cost + nuclear_org_cost 


lignite_cost = n.generators_t.p[lignite_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* abs(n.generators[n.generators.carrier == 'lignite'].marginal_cost).mean()
lignite_up_list = lignite_gen_list[lignite_gen_list.index.str.contains('ramp up')]
lignite_up_cost = n.generators_t.p[lignite_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('lignite ramp up')].marginal_cost).mean()
lignite_down_list = lignite_gen_list[lignite_gen_list.index.str.contains('ramp down')]
lignite_down_cost = n.generators_t.p[lignite_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('lignite ramp down')].marginal_cost).mean()
lignite_list = n.generators.loc[n.generators.index.str.contains('lignite')]
lignite_list = lignite_list[lignite_list.index.str.contains('ramp') == False]
lignite_org_cost = n.generators_t.p[lignite_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[lignite_list.index].marginal_cost).mean()
lignite_total_cost = lignite_up_cost + lignite_down_cost + lignite_org_cost 


oil_cost = n.generators_t.p[oil_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* abs(n.generators[n.generators.carrier == 'oil'].marginal_cost).mean()
oil_up_list = oil_gen_list[oil_gen_list.index.str.contains('ramp up')]
oil_up_cost = n.generators_t.p[oil_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('oil ramp up')].marginal_cost).mean()
oil_down_list = oil_gen_list[oil_gen_list.index.str.contains('ramp down')]
oil_down_cost = n.generators_t.p[oil_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('oil ramp down')].marginal_cost).mean()
oil_list = n.generators.loc[n.generators.index.str.contains('oil')]
oil_list = oil_list[oil_list.index.str.contains('ramp') == False]
oil_org_cost = n.generators_t.p[oil_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[oil_list.index].marginal_cost).mean()
oil_total_cost = oil_up_cost + oil_down_cost + oil_org_cost 


CCGT_cost = n.generators_t.p[CCGT_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* abs(n.generators[n.generators.carrier == 'CCGT'].marginal_cost).mean()
CCGT_up_list = CCGT_gen_list[CCGT_gen_list.index.str.contains('ramp up')]
CCGT_up_cost = n.generators_t.p[CCGT_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('CCGT ramp up')].marginal_cost).mean()
CCGT_down_list = CCGT_gen_list[CCGT_gen_list.index.str.contains('ramp down')]
CCGT_down_cost = n.generators_t.p[CCGT_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('CCGT ramp down')].marginal_cost).mean()
CCGT_list = n.generators.loc[n.generators.index.str.contains('CCGT')]
CCGT_list = CCGT_list[CCGT_list.index.str.contains('ramp') == False]
CCGT_org_cost = n.generators_t.p[CCGT_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[CCGT_list.index].marginal_cost).mean()
CCGT_total_cost = CCGT_up_cost + CCGT_down_cost + CCGT_org_cost 

OCGT_cost = n.generators_t.p[OCGT_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* abs(n.generators[n.generators.carrier == 'OCGT'].marginal_cost).mean()
OCGT_up_list = OCGT_gen_list[OCGT_gen_list.index.str.contains('ramp up')]
OCGT_up_cost = n.generators_t.p[OCGT_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('OCGT ramp up')].marginal_cost).mean()
OCGT_down_list = OCGT_gen_list[OCGT_gen_list.index.str.contains('ramp down')]
OCGT_down_cost = n.generators_t.p[OCGT_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('OCGT ramp down')].marginal_cost).mean()
OCGT_list = n.generators.loc[n.generators.index.str.contains('OCGT')]
OCGT_list = OCGT_list[OCGT_list.index.str.contains('ramp') == False]
OCGT_org_cost = n.generators_t.p[OCGT_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[OCGT_list.index].marginal_cost).mean()
OCGT_total_cost = OCGT_up_cost + OCGT_down_cost + OCGT_org_cost 


solar_up_list = n.generators.loc[n.generators.index.str.contains('solar ramp up')]
solar_up_cost = n.generators_t.p[solar_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('solar ramp up')].marginal_cost).mean()
solar_down_list = n.generators.loc[n.generators.index.str.contains('solar ramp down')]
solar_down_cost = n.generators_t.p[solar_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('solar ramp down')].marginal_cost).mean()
solar_list = n.generators.loc[n.generators.index.str.contains('solar')]
solar_list = solar_list[solar_list.index.str.contains('ramp') == False]
solar_cost = n.generators_t.p[solar_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[solar_list.index].marginal_cost).mean()
solar_total_cost = solar_up_cost + solar_down_cost + solar_cost

onwind_up_list = n.generators.loc[n.generators.index.str.contains('onwind ramp up')]
onwind_up_cost = n.generators_t.p[onwind_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('onwind ramp up')].marginal_cost).mean()
onwind_down_list = n.generators.loc[n.generators.index.str.contains('onwind ramp down')]
onwind_down_cost = n.generators_t.p[onwind_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('onwind ramp down')].marginal_cost).mean()
onwind_list = n.generators.loc[n.generators.index.str.contains('onwind')]
onwind_list = onwind_list[onwind_list.index.str.contains('ramp') == False]
onwind_cost = n.generators_t.p[onwind_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[onwind_list.index].marginal_cost).mean()
onwind_total_cost = onwind_up_cost + onwind_down_cost + onwind_cost

offwind_up_list = n.generators.loc[n.generators.index.str.contains('offwind')]
offwind_up_list = offwind_up_list[offwind_up_list.index.str.contains('ramp up')]
offwind_up_cost = n.generators_t.p[offwind_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[offwind_up_list.index].marginal_cost).mean()
offwind_down_list = n.generators.loc[n.generators.index.str.contains('offwind')]
offwind_down_list = offwind_down_list[offwind_down_list.index.str.contains('ramp down')]
offwind_down_cost = n.generators_t.p[offwind_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[offwind_down_list.index].marginal_cost).mean()
offwind_list = n.generators.loc[n.generators.index.str.contains('offwind')]
offwind_list = offwind_list[offwind_list.index.str.contains('ramp') == False]
offwind_cost = n.generators_t.p[offwind_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[offwind_list.index].marginal_cost).mean()
offwind_total_cost = offwind_up_cost + offwind_down_cost + offwind_cost 

ror_up_list = n.generators.loc[n.generators.index.str.contains('ror ramp up')]
ror_up_cost = n.generators_t.p[ror_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('ror ramp up')].marginal_cost).mean()
ror_down_list = n.generators.loc[n.generators.index.str.contains('ror ramp down')]
ror_down_cost = n.generators_t.p[ror_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('ror ramp down')].marginal_cost).mean()
ror_list = n.generators.loc[n.generators.index.str.contains('ror')]
ror_list = ror_list[ror_list.index.str.contains('ramp') == False]
ror_cost = n.generators_t.p[ror_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[ror_list.index].marginal_cost).mean()
ror_total_cost = ror_up_cost + ror_down_cost + ror_cost

biomass_up_list = n.generators.loc[n.generators.index.str.contains('biomass ramp up')]
biomass_up_cost = n.generators_t.p[biomass_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('biomass ramp up')].marginal_cost).mean()
biomass_down_list = n.generators.loc[n.generators.index.str.contains('biomass ramp down')]
biomass_down_cost = n.generators_t.p[biomass_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators[n.generators.index.str.contains('biomass ramp down')].marginal_cost).mean()
biomass_list = n.generators.loc[n.generators.index.str.contains('biomass')]
biomass_list = biomass_list[biomass_list.index.str.contains('ramp') == False]
biomass_cost = n.generators_t.p[biomass_list.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().sum()* (n.generators.loc[biomass_list.index].marginal_cost).mean()
biomass_total_cost = biomass_up_cost + biomass_down_cost + biomass_cost

total_cost = coal_total_cost+ nuclear_total_cost + lignite_total_cost + oil_total_cost + CCGT_total_cost + OCGT_total_cost + solar_total_cost + onwind_total_cost + offwind_total_cost + ror_total_cost + biomass_total_cost

total_ramp_down_cost = coal_down_cost + nuclear_down_cost + lignite_down_cost + oil_down_cost + CCGT_down_cost+OCGT_down_cost +solar_down_cost + onwind_down_cost + offwind_down_cost + ror_down_cost + biomass_down_cost

total_ramp_up_cost = coal_up_cost + nuclear_up_cost + lignite_up_cost + oil_up_cost + CCGT_up_cost + OCGT_up_cost + solar_up_cost + onwind_up_cost + offwind_up_cost + ror_up_cost + biomass_up_cost

redispatch_cost = total_ramp_down_cost + total_ramp_up_cost 



#%%

plt.figure(figsize=[6, 6])


market = n.generators_t.p[m.generators.index].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e6)  

onezone = n.plot( bus_sizes=market, title="One bidding zone market simulation")

image_format = 'svg' # e.g .png, .svg, etc.
image_name = 'onezone.svg'

plt.savefig(image_name, format=image_format, dpi=1200)

#for time horizon
ramp_up_noflex = n.generators_t.p[ramp_up_gen_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
#for single time step 
#ramp_up_noflex = n.generators_t.p[ramp_up_gen_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().div(2e4)
axs[0,1] = n.plot(
       bus_sizes= ramp_up_noflex,
    bus_colors="red",
    title="Ramp Up Dispatch",
) 
#for time horizon
ramp_down_noflex = n.generators_t.p[ramp_down_gen_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
#for single time step 
#ramp_down_noflex = n.generators_t.p[ramp_down_gen_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().div(-2e4)

axs[0,2] = n.plot(
       bus_sizes= ramp_down_noflex,
    bus_colors="red",
    title="Ramp Down Dispatch / Curtail",
)

ccgt_ramp_up_noflex = n.generators_t.p[ccgt_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
axs[0,2] = n.plot(
       bus_sizes= ccgt_ramp_up_noflex,
    bus_colors="red",
    title="Ramp Up Dispatch - CCGT ",
)

ccgt_ramp_down_noflex = n.generators_t.p[ccgt_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
axs[0,2] = n.plot(
       bus_sizes= ccgt_ramp_down_noflex,
    bus_colors="red",
    title="Ramp Down Dispatch - CCGT ",
)


ren_down= n.generators_t.p[ren_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
ax[2] = n.plot(
       bus_sizes= ren_down,
    bus_colors="blue",
    title="Ren_ramp_down",
)


ren_up= n.generators_t.p[ren_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
ax[2] = n.plot(
       bus_sizes= ren_up,
    bus_colors="blue",
    title="Ren_ramp_up",
)

coal_down = n.generators_t.p[coal_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
ax[4]=n.plot(
       bus_sizes= coal_down,
    bus_colors="blue",
    title="coal_ramp_down",
)

coal_up = n.generators_t.p[coal_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
ax[4]=n.plot(
       bus_sizes= coal_ramp_up_change,
    bus_colors="blue",
    title="coal_ramp_up",
)

ramp_down_noflex = n.generators_t.p[ramp_down_gen_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
#for single time step 

'''

Plots for line loading without steel plants 
'''

loading = abs(n.lines_t.p0[horizon_start:horizon_end]).mean() / n_flex.lines.s_nom_opt
loading.fillna(0,inplace=True)

fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()}, figsize=(9, 9))
cmap= plt.cm.OrRd
norm = mcolors.Normalize(min(loading),max(loading))
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])

colors = list(map(mcolors.to_hex, cmap(norm(loading))))

n.plot(ax=ax, line_colors=colors, line_cmap=plt.cm.jet, title="Line loading", bus_sizes=0.25e-3, bus_alpha=0.7)
plt.colorbar(sm, orientation='vertical', shrink=0.7, ax=ax, label='Line Loading (p.u.)')
fig.tight_layout()



# %%
'''
Re-dispatch with:
cost based re-dispatch prices for ramp up and ramp down generators 
add steel plant flexibility 
'''

#make additional generators crazy expensive 
n_flex.generators.loc[n.generators.index.str.contains("ramp up"), "marginal_cost"] *= 1

#ramp down generators are also crazy expensive 
n_flex.generators.loc[n.generators.index.str.contains("ramp down"), "marginal_cost"] *= 1

#read in pos/neg flixibilty from optimization 
flex = pd.read_csv('flex_amt_v2.csv')


#read in updated steel plant data
steel_plant_buses = pd.read_csv('Steel_Plant_Data/updated_from_opt_v2.csv')
steel_plant_buses['pnom_x10'] = steel_plant_buses['pnom']*10
steel_plant_buses['pnom_x100'] = steel_plant_buses['pnom']*100

for idx, bus in steel_plant_buses.iterrows():

    #neg flex gen to act as additional load (ramp down)
    n_flex.add('Generator',
     steel_plant_buses['location'].iloc[idx] +'_neg_flex', 
     bus = steel_plant_buses['bus'].iloc[idx],
     p_nom = steel_plant_buses['pnom'].iloc[idx],
     p_min_pu = (flex[str(steel_plant_buses['bus'].iloc[idx])+ '_neg'].to_list()*53)[0:8760] ,
     #exapnd flex values to cover entire year
     p_max_pu = 0 ,    #[0:24]  
     marginal_cost = -50,
     sign = 1,
     carrier = 'flexibility',
     )
    
    #pos flex acts to provide gen (ramp up)
    n_flex.add('Generator',
     steel_plant_buses['location'].iloc[idx] +'_pos_flex', 
     bus = steel_plant_buses['bus'].iloc[idx],
     p_nom = steel_plant_buses['pnom'].iloc[idx] ,
     p_min_pu = 0,
     p_max_pu = (flex[str(steel_plant_buses['bus'].iloc[idx])+ '_pos'].to_list()*53)[0:8760]   ,  
     marginal_cost = 50,
     sign = 1,
     carrier = 'flexibility',
     )

#%%
n_flex.lopf(solver_name=solver, pyomo=False, snapshots = n_flex.snapshots[horizon_start:horizon_end])  
#%%
'''
dispatch of each generator
'''
                

ramp_up_gen  = n_flex.generators.loc[n_flex.generators.index.str.contains("ramp up")]
ramp_up_dispatch = n_flex.generators_t.p[ramp_up_gen.index][horizon_start:horizon_end].T.squeeze()
total_ramp_up_flex = n_flex.generators_t.p[ramp_up_gen.index][horizon_start:horizon_end].T.squeeze().sum().sum()

ramp_down_gen  = n_flex.generators.loc[n_flex.generators.index.str.contains("ramp down")]
ramp_down_dispatch = n_flex.generators_t.p[ramp_down_gen.index][horizon_start:horizon_end].T.squeeze()
total_ramp_down_flex =  n_flex.generators_t.p[ramp_down_gen.index][horizon_start:horizon_end].T.squeeze().sum().sum()


flex_pos_gen = n_flex.generators.loc[n_flex.generators.index.str.contains("pos_flex")]
pos_flex_dispatch = n_flex.generators_t.p[flex_pos_gen.index][horizon_start:horizon_end].T.squeeze()
total_pos_flex = n_flex.generators_t.p[flex_pos_gen.index][horizon_start:horizon_end].T.squeeze().sum().sum()


flex_neg_gen = n_flex.generators.loc[n_flex.generators.index.str.contains("neg_flex")]
neg_flex_dispatch = n_flex.generators_t.p[flex_neg_gen.index][horizon_start:horizon_end].T.squeeze()
total_neg_flex = n_flex.generators_t.p[flex_neg_gen.index][horizon_start:horizon_end].T.squeeze().sum().sum()

#change in ramp up by generation carrier (%)
ramping_up_change = (total_ramp_up_noflex - total_ramp_up_flex)/total_ramp_up_noflex

ramping_down_change = (total_ramp_down_noflex - total_ramp_down_flex)/total_ramp_down_noflex

solar_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("solar ramp down")]
solar_ramp_down_dispatch = n_flex.generators_t.p[solar_ramp_down.index][horizon_start:horizon_end].T.squeeze()

ren_ramp_down_flex = n_flex.generators.loc[n_flex.generators.index.str.contains("onwind ramp down" or 'offwind-ac ramp down' or 'offwind-dc ramp down' or 'biomass ramp down' or 'solar ramp down' or 'ror ramp down')]
ren_ramp_down_dispatch_flex = n_flex.generators_t.p[ren_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze()
total_ren_ramp_down_dispatch_flex =n_flex.generators_t.p[ren_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze().sum().sum()

ren_ramp_up_flex = n_flex.generators.loc[n_flex.generators.index.str.contains("onwind ramp up" or 'offwind-ac ramp up' or 'offwind-dc ramp up' or 'biomass ramp up' or 'solar ramp up' or 'ror ramp up')]
ren_ramp_up_dispatch_flex = n_flex.generators_t.p[ren_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze()
total_ren_ramp_up_dispatch_flex =n_flex.generators_t.p[ren_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze().sum().sum()


ren_ramp_down_change = (total_ren_ramp_down_noflex - total_ren_ramp_down_dispatch_flex)/ total_ren_ramp_down_noflex
ren_ramp_up_change = (total_ren_ramp_up_noflex - total_ren_ramp_down_dispatch_flex )/total_ren_ramp_up_noflex



#%%
'''
For plotting dispatch 
'''
fig, axs = plt.subplots(nrows = 2, ncols=3, figsize=(20, 10), subplot_kw={"projection": ccrs.AlbersEqualArea()}
)
#size = 6
#fig.set_size_inches(size * 3, size * 2)
    

market = (
    n_flex.generators_t.p[m.generators.index]
    .T.squeeze()
    .groupby(n.generators.bus)
    .sum().T.sum()
    .div(2e6)
)

axs[0,0] = n_flex.plot( bus_sizes=market, title="2 bidding zones market simulation")


ramp_up = n_flex.generators_t.p[ramp_up_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

axs[0,1] = n_flex.plot(
       bus_sizes= ramp_up,
    bus_colors="red",
    title="Ramp Up Dispatch",
) 

ramp_down = n_flex.generators_t.p[ramp_down_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)

axs[0,2] = n_flex.plot(
       bus_sizes= ramp_down,
    bus_colors="red",
    title="Ramp Down Dispatch / Curtail",
)

#%%
#CCGT

ccgt_ramp_up_flex = n_flex.generators_t.p[ccgt_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

axs[0,2] = n_flex.plot(
       bus_sizes= ccgt_ramp_up_flex,
    bus_colors="red",
    title="Ramp Down Dispatch -Coal" )

ccgt_up_dif = ccgt_ramp_up_noflex - ccgt_ramp_up_flex

ax[3] = n_flex.plot(
       bus_sizes= ccgt_up_dif,
    bus_colors="red",
    title="Ramp Up Dispatch Diff -CCGT" )

ccgt_ramp_down_flex = n_flex.generators_t.p[ccgt_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)
ccgt_down_diff = ccgt_ramp_down_noflex - ccgt_ramp_down_flex

ax[3] = n_flex.plot(
       bus_sizes= ccgt_down_diff,
    bus_colors="red",
    title="Ramp Down Dispatch Diff -CCGT" )


#dispatch positive flexibility
pos = n_flex.generators_t.p[flex_pos_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

axs[1,0] = n_flex.plot(
       bus_sizes= pos,
    bus_colors="red",
    title="Pos Flex Dispatch",
)

#dispatch negative flexibility
neg = n_flex.generators_t.p[flex_neg_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)

axs[1,1] = n_flex.plot(
       bus_sizes= neg*2,
    bus_colors="red",
    title="Neg Flex Dispatch",
)

ramp_up_dif = (ramp_up_noflex - ramp_up  )
ax[1] = n_flex.plot(
       bus_sizes= ramp_up_dif,
    bus_colors="blue",
    title="Diff in Ramp Up: No Flex and Flex",
)

ramp_down_diff = (ramp_down_noflex -ramp_down )
ax[1] = n_flex.plot(
       bus_sizes= ramp_down_diff,
    bus_colors="blue",
    title="Diff in Ramp Down: No Flex and Flex",
)

solar_down = n_flex.generators_t.p[solar_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
ax[2] = n_flex.plot(
       bus_sizes= solar_down,
    bus_colors="blue",
    title="Solar_ramp_down",
)

ren_down_flex = n_flex.generators_t.p[ren_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
ax[2] = n_flex.plot(
       bus_sizes= ren_down_flex,
    bus_colors="blue",
    title="Ren_ramp_down",
)

ren_down_diff = (total_ren_ramp_down_noflex - total_ren_ramp_down_dispatch_flex)

ax[2] = n_flex.plot(
       bus_sizes= ren_down_diff,
    bus_colors="blue",
    title="Diff in ren_ramp_down",
)


ren_up_flex = n_flex.generators_t.p[ren_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)
ax[2] = n_flex.plot(
       bus_sizes= ren_up_flex,
    bus_colors="blue",
    title="Ren_ramp_up",
)

ren_up_diff = (total_ren_ramp_up_noflex - total_ren_ramp_up_dispatch_flex)

ax[2] = n_flex.plot(
       bus_sizes= ren_down_diff,
    bus_colors="blue",
    title="Diff in ren_ramp_down",
)

#%%


ccgt_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains('CCGT ramp up')]
ccgt_ramp_up_dispatch_noflex = n.generators_t.p[ccgt_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
ccgt_ramp_up_noflex_total =  ccgt_ramp_up_dispatch_noflex.sum().sum() 

ccgt_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains('CCGT ramp down')]
ccgt_ramp_down_dispatch_noflex = n.generators_t.p[ccgt_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
ccgt_ramp_down_noflex_total =  ccgt_ramp_down_dispatch_noflex.sum().sum() 


ccgt_ramp_up_noflex = n.generators_t.p[ccgt_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
# axs[0,2] = n.plot(
#        bus_sizes= ccgt_ramp_up_noflex,
#     bus_colors="red",
#     title="Ramp Up Dispatch - CCGT ",
# )

ccgt_ramp_down_noflex = n.generators_t.p[ccgt_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
# axs[0,2] = n.plot(
#        bus_sizes= ccgt_ramp_down_noflex,
#     bus_colors="red",
#     title="Ramp Down Dispatch - CCGT ",
# )


ccgt_ramp_up = n_flex.generators.loc[n_flex.generators.index.str.contains("CCGT ramp up")]
ccgt_ramp_up_dispatch = n_flex.generators_t.p[ccgt_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_ccgt_ramp_up_flex = ccgt_ramp_up_dispatch.sum().sum()

ccgt_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("CCGT ramp down")]
ccgt_ramp_down_dispatch = n_flex.generators_t.p[ccgt_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_ccgt_ramp_down_flex = ccgt_ramp_down_dispatch.sum().sum()


ccgt_up_change = (ccgt_ramp_up_noflex_total - total_ccgt_ramp_up_flex)/ccgt_ramp_up_noflex_total
ccgt_down_change = (ccgt_ramp_down_noflex_total - total_ccgt_ramp_down_flex)/ccgt_ramp_down_noflex_total


ccgt_ramp_up_flex = n_flex.generators_t.p[ccgt_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

# axs[0,2] = n_flex.plot(
#        bus_sizes= ccgt_ramp_up_flex,
#     bus_colors="red",
#     title="Ramp Up Dispatch -CCGT" )

ccgt_up_dif = (ccgt_ramp_up_noflex - ccgt_ramp_up_flex)*10

ax[3] = n_flex.plot(
       bus_sizes= ccgt_up_dif,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -CCGT" )

ccgt_ramp_down_flex = n_flex.generators_t.p[ccgt_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
ccgt_down_diff = ccgt_ramp_down_noflex - ccgt_ramp_down_flex

ax[3] = n_flex.plot(
       bus_sizes= ccgt_down_diff,
    bus_colors="blue",
    title="Ramp Down Dispatch Diff -CCGT" )

#%%
#Coal 

coal_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains('coal ramp up')]
coal_ramp_up_dispatch_noflex = n.generators_t.p[coal_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
coal_ramp_up_noflex_total =  coal_ramp_up_dispatch_noflex.sum().sum() 

coal_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains('coal ramp down')]
coal_ramp_down_dispatch_noflex = n.generators_t.p[coal_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
coal_ramp_down_noflex_total =  coal_ramp_down_dispatch_noflex.sum().sum() 


coal_ramp_up_noflex = n.generators_t.p[coal_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
# axs[0,2] = n.plot(
#        bus_sizes= coal_ramp_up_noflex,
#     bus_colors="red",
#     title="Ramp Up Dispatch - coal ",
# )

coal_ramp_down_noflex = n.generators_t.p[coal_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
# axs[0,2] = n.plot(
#        bus_sizes= coal_ramp_down_noflex,
#     bus_colors="red",
#     title="Ramp Down Dispatch - coal ",
# )


coal_ramp_up = n_flex.generators.loc[n_flex.generators.index.str.contains("coal ramp up")]
coal_ramp_up_dispatch = n_flex.generators_t.p[coal_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_coal_ramp_up_flex = coal_ramp_up_dispatch.sum().sum()

coal_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("coal ramp down")]
coal_ramp_down_dispatch = n_flex.generators_t.p[coal_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_coal_ramp_down_flex = coal_ramp_down_dispatch.sum().sum()


coal_up_change = (coal_ramp_up_noflex_total - total_coal_ramp_up_flex)/coal_ramp_up_noflex_total
coal_down_change = (coal_ramp_down_noflex_total - total_coal_ramp_down_flex)/coal_ramp_down_noflex_total


coal_ramp_up_flex = n_flex.generators_t.p[coal_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

# axs[0,2] = n_flex.plot(
#        bus_sizes= coal_ramp_up_flex,
#     bus_colors="red",
#     title="Ramp Up Dispatch -coal" )

coal_up_dif = coal_ramp_up_noflex - coal_ramp_up_flex

ax[3] = n_flex.plot(
       bus_sizes= coal_up_dif,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -coal" )

coal_ramp_down_flex = n_flex.generators_t.p[coal_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
coal_down_diff = (coal_ramp_down_noflex - coal_ramp_down_flex)*10

ax[3] = n_flex.plot(
       bus_sizes= coal_down_diff,
    bus_colors="blue",
    title="Ramp Down Dispatch Diff -coal" )

#%%
#Oil

oil_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains('oil ramp up')]
oil_ramp_up_dispatch_noflex = n.generators_t.p[oil_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
oil_ramp_up_noflex_total =  oil_ramp_up_dispatch_noflex.sum().sum() 

oil_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains('oil ramp down')]
oil_ramp_down_dispatch_noflex = n.generators_t.p[oil_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
oil_ramp_down_noflex_total =  oil_ramp_down_dispatch_noflex.sum().sum() 


oil_ramp_up_noflex = n.generators_t.p[oil_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
# axs[0,2] = n.plot(
#        bus_sizes= oil_ramp_up_noflex,
#     bus_colors="red",
#     title="Ramp Up Dispatch - oil ",
# )

oil_ramp_down_noflex = n.generators_t.p[oil_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
# axs[0,2] = n.plot(
#        bus_sizes= oil_ramp_down_noflex,
#     bus_colors="red",
#     title="Ramp Down Dispatch - oil ",
# )


oil_ramp_up = n_flex.generators.loc[n_flex.generators.index.str.contains("oil ramp up")]
oil_ramp_up_dispatch = n_flex.generators_t.p[oil_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_oil_ramp_up_flex = oil_ramp_up_dispatch.sum().sum()

oil_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("oil ramp down")]
oil_ramp_down_dispatch = n_flex.generators_t.p[oil_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_oil_ramp_down_flex = oil_ramp_down_dispatch.sum().sum()


oil_up_change = (oil_ramp_up_noflex_total - total_oil_ramp_up_flex)/oil_ramp_up_noflex_total
oil_down_change = (oil_ramp_down_noflex_total - total_oil_ramp_down_flex)/oil_ramp_down_noflex_total


oil_ramp_up_flex = n_flex.generators_t.p[oil_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

# axs[0,2] = n_flex.plot(
#        bus_sizes= oil_ramp_up_flex,
#     bus_colors="red",
#     title="Ramp Up Dispatch -oil" )

oil_up_dif = (oil_ramp_up_noflex - oil_ramp_up_flex)*100

ax[3] = n_flex.plot(
       bus_sizes= oil_up_dif,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -oil" )

oil_ramp_down_flex = n_flex.generators_t.p[oil_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
oil_down_diff = (oil_ramp_down_noflex - oil_ramp_down_flex)*100

ax[3] = n_flex.plot(
       bus_sizes= oil_down_diff,
    bus_colors="blue",
    title="Ramp Down Dispatch Diff -oil" )

#%%
#lignite



lignite_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains('lignite ramp up')]
lignite_ramp_up_dispatch_noflex = n.generators_t.p[lignite_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
lignite_ramp_up_noflex_total =  lignite_ramp_up_dispatch_noflex.sum().sum() 

lignite_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains('lignite ramp down')]
lignite_ramp_down_dispatch_noflex = n.generators_t.p[lignite_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
lignite_ramp_down_noflex_total =  lignite_ramp_down_dispatch_noflex.sum().sum() 


lignite_ramp_up_noflex = n.generators_t.p[lignite_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
# axs[0,2] = n.plot(
#        bus_sizes= lignite_ramp_up_noflex,
#     bus_colors="red",
#     title="Ramp Up Dispatch - lignite ",
# )

lignite_ramp_down_noflex = n.generators_t.p[lignite_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
# axs[0,2] = n.plot(
#        bus_sizes= lignite_ramp_down_noflex,
#     bus_colors="red",
#     title="Ramp Down Dispatch - lignite ",
# )


lignite_ramp_up = n_flex.generators.loc[n_flex.generators.index.str.contains("lignite ramp up")]
lignite_ramp_up_dispatch = n_flex.generators_t.p[lignite_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_lignite_ramp_up_flex = lignite_ramp_up_dispatch.sum().sum()

lignite_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("lignite ramp down")]
lignite_ramp_down_dispatch = n_flex.generators_t.p[lignite_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_lignite_ramp_down_flex = lignite_ramp_down_dispatch.sum().sum()


lignite_up_change = (lignite_ramp_up_noflex_total - total_lignite_ramp_up_flex)/lignite_ramp_up_noflex_total
lignite_down_change = (lignite_ramp_down_noflex_total - total_lignite_ramp_down_flex)/lignite_ramp_down_noflex_total


lignite_ramp_up_flex = n_flex.generators_t.p[lignite_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

# axs[0,2] = n_flex.plot(
#        bus_sizes= lignite_ramp_up_flex,
#     bus_colors="red",
#     title="Ramp Up Dispatch -lignite" )

lignite_up_dif = lignite_ramp_up_noflex - lignite_ramp_up_flex

ax[3] = n_flex.plot(
       bus_sizes= lignite_up_dif,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -lignite" )

lignite_ramp_down_flex = n_flex.generators_t.p[lignite_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
lignite_down_diff = (lignite_ramp_down_noflex - lignite_ramp_down_flex)

ax[3] = n_flex.plot(
       bus_sizes= lignite_down_diff,
    bus_colors="blue",
    title="Ramp Down Dispatch Diff -lignite" )

#%%

#Nuclear


nuclear_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains('nuclear ramp up')]
nuclear_ramp_up_dispatch_noflex = n.generators_t.p[nuclear_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
nuclear_ramp_up_noflex_total =  nuclear_ramp_up_dispatch_noflex.sum().sum() 

nuclear_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains('nuclear ramp down')]
nuclear_ramp_down_dispatch_noflex = n.generators_t.p[nuclear_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
nuclear_ramp_down_noflex_total =  nuclear_ramp_down_dispatch_noflex.sum().sum() 


nuclear_ramp_up_noflex = n.generators_t.p[nuclear_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
# axs[0,2] = n.plot(
#        bus_sizes= nuclear_ramp_up_noflex,
#     bus_colors="red",
#     title="Ramp Up Dispatch - nuclear ",
# )

nuclear_ramp_down_noflex = n.generators_t.p[nuclear_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
# axs[0,2] = n.plot(
#        bus_sizes= nuclear_ramp_down_noflex,
#     bus_colors="red",
#     title="Ramp Down Dispatch - nuclear ",
# )


nuclear_ramp_up = n_flex.generators.loc[n_flex.generators.index.str.contains("nuclear ramp up")]
nuclear_ramp_up_dispatch = n_flex.generators_t.p[nuclear_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_nuclear_ramp_up_flex = nuclear_ramp_up_dispatch.sum().sum()

nuclear_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("nuclear ramp down")]
nuclear_ramp_down_dispatch = n_flex.generators_t.p[nuclear_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_nuclear_ramp_down_flex = nuclear_ramp_down_dispatch.sum().sum()


nuclear_up_change = (nuclear_ramp_up_noflex_total - total_nuclear_ramp_up_flex)/nuclear_ramp_up_noflex_total
nuclear_down_change = (nuclear_ramp_down_noflex_total - total_nuclear_ramp_down_flex)/nuclear_ramp_down_noflex_total


nuclear_ramp_up_flex = n_flex.generators_t.p[nuclear_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

# axs[0,2] = n_flex.plot(
#        bus_sizes= nuclear_ramp_up_flex,
#     bus_colors="red",
#     title="Ramp Up Dispatch -nuclear" )

nuclear_up_dif = nuclear_ramp_up_noflex - nuclear_ramp_up_flex

ax[3] = n_flex.plot(
       bus_sizes= nuclear_up_dif,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -nuclear" )

nuclear_ramp_down_flex = n_flex.generators_t.p[nuclear_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
nuclear_down_diff = (nuclear_ramp_down_noflex - nuclear_ramp_down_flex)

ax[3] = n_flex.plot(
       bus_sizes= nuclear_down_diff,
    bus_colors="blue",
    title="Ramp Down Dispatch Diff -nuclear" )

#%%

#ocgt


OCGT_ramp_up_noflex = n.generators.loc[n.generators.index.str.contains('OCGT ramp up')]
OCGT_ramp_up_dispatch_noflex = n.generators_t.p[OCGT_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
OCGT_ramp_up_noflex_total =  OCGT_ramp_up_dispatch_noflex.sum().sum() 

OCGT_ramp_down_noflex = n.generators.loc[n.generators.index.str.contains('OCGT ramp down')]
OCGT_ramp_down_dispatch_noflex = n.generators_t.p[OCGT_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
OCGT_ramp_down_noflex_total =  OCGT_ramp_down_dispatch_noflex.sum().sum() 


OCGT_ramp_up_noflex = n.generators_t.p[OCGT_ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(2e5)
# axs[0,2] = n.plot(
#        bus_sizes= OCGT_ramp_up_noflex,
#     bus_colors="red",
#     title="Ramp Up Dispatch - OCGT ",
# )

OCGT_ramp_down_noflex = n.generators_t.p[OCGT_ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze().groupby(n.generators.bus).sum().T.sum().div(-2e5)
# axs[0,2] = n.plot(
#        bus_sizes= OCGT_ramp_down_noflex,
#     bus_colors="red",
#     title="Ramp Down Dispatch - OCGT ",
# )


OCGT_ramp_up = n_flex.generators.loc[n_flex.generators.index.str.contains("OCGT ramp up")]
OCGT_ramp_up_dispatch = n_flex.generators_t.p[OCGT_ramp_up.index][horizon_start:horizon_end].T.squeeze()
total_OCGT_ramp_up_flex = OCGT_ramp_up_dispatch.sum().sum()

OCGT_ramp_down = n_flex.generators.loc[n_flex.generators.index.str.contains("OCGT ramp down")]
OCGT_ramp_down_dispatch = n_flex.generators_t.p[OCGT_ramp_down.index][horizon_start:horizon_end].T.squeeze()
total_OCGT_ramp_down_flex = OCGT_ramp_down_dispatch.sum().sum()


OCGT_up_change = (OCGT_ramp_up_noflex_total - total_OCGT_ramp_up_flex)/OCGT_ramp_up_noflex_total
OCGT_down_change = (OCGT_ramp_down_noflex_total - total_OCGT_ramp_down_flex)/OCGT_ramp_down_noflex_total


OCGT_ramp_up_flex = n_flex.generators_t.p[OCGT_ramp_up.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)

axs[0,2] = n_flex.plot(
       bus_sizes= OCGT_ramp_up_flex,
    bus_colors="red",
    title="Ramp Up Dispatch -OCGT" )

OCGT_up_dif = (OCGT_ramp_up_noflex - OCGT_ramp_up_flex)*10

ax[3] = n_flex.plot(
       bus_sizes= OCGT_up_dif,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -OCGT" )

OCGT_ramp_down_flex = n_flex.generators_t.p[OCGT_ramp_down.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(-2e5)
OCGT_down_diff = (OCGT_ramp_down_noflex - OCGT_ramp_down_flex)

ax[3] = n_flex.plot(
       bus_sizes= OCGT_down_diff,
    bus_colors="blue",
    title="Ramp Down Dispatch Diff -OCGT" )

#%%

gas_combined_ramp_up_flex = OCGT_ramp_up_flex + ccgt_ramp_up_flex 
gas_combined_ramp_up = OCGT_ramp_up_noflex + ccgt_ramp_up_noflex

gas_combined_ramp_up_diff = gas_combined_ramp_up - gas_combined_ramp_up_flex 

ax[3] = n_flex.plot(
       bus_sizes= gas_combined_ramp_up_diff,
    bus_colors="blue",
    title="Ramp Up Dispatch Diff -Gas" )

gas_up_diff = pd.DataFrame()

for idx in  range(0, len(ccgt_ramp_up_flex)):
        if OCGT_up_dif.index[idx] == ccgt_up_dif.index[idx] :
            gas_up_diff.index[idx] = OCGT_up_dif.index[idx] 
            gas_up_diff[idx] = OCGT_up_dif[idx] + ccgt_up_dif[idx]
        
        else: 
            gas_up_diff[idx] = OCGT_up_dif[idx] + 0.0



#%%

'''
Sytem cost_flex
'''
coal_cost_flex = n_flex.generators_t.p[coal_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* abs(n_flex.generators[n_flex.generators.carrier == 'coal'].marginal_cost).mean()
coal_up_list = coal_gen_list[coal_gen_list.index.str.contains('ramp up')]
coal_up_cost_flex = n_flex.generators_t.p[coal_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('coal ramp up')].marginal_cost).mean()
coal_down_list = coal_gen_list[coal_gen_list.index.str.contains('ramp down')]
coal_down_cost_flex = n_flex.generators_t.p[coal_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('coal ramp down')].marginal_cost).mean()
coal_list = n_flex.generators.loc[n_flex.generators.index.str.contains('coal')]
coal_list = coal_list[coal_list.index.str.contains('ramp') == False]
coal_org_cost_flex = n_flex.generators_t.p[coal_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[coal_list.index].marginal_cost).mean()
coal_total_cost_flex = coal_up_cost_flex + coal_down_cost_flex + coal_org_cost_flex 

nuclear_cost_flex = n_flex.generators_t.p[nuclear_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* abs(n_flex.generators[n_flex.generators.carrier == 'nuclear'].marginal_cost).mean()
nuclear_up_list = nuclear_gen_list[nuclear_gen_list.index.str.contains('ramp up')]
nuclear_up_cost_flex = n_flex.generators_t.p[nuclear_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('nuclear ramp up')].marginal_cost).mean()
nuclear_down_list = nuclear_gen_list[nuclear_gen_list.index.str.contains('ramp down')]
nuclear_down_cost_flex = n_flex.generators_t.p[nuclear_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('nuclear ramp down')].marginal_cost).mean()
nuclear_list = n_flex.generators.loc[n_flex.generators.index.str.contains('nuclear')]
nuclear_list = nuclear_list[nuclear_list.index.str.contains('ramp') == False]
nuclear_org_cost_flex = n_flex.generators_t.p[nuclear_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[nuclear_list.index].marginal_cost).mean()
nuclear_total_cost_flex = nuclear_up_cost_flex + nuclear_down_cost_flex + nuclear_org_cost_flex 


lignite_cost_flex = n_flex.generators_t.p[lignite_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* abs(n_flex.generators[n_flex.generators.carrier == 'lignite'].marginal_cost).mean()
lignite_up_list = lignite_gen_list[lignite_gen_list.index.str.contains('ramp up')]
lignite_up_cost_flex = n_flex.generators_t.p[lignite_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('lignite ramp up')].marginal_cost).mean()
lignite_down_list = lignite_gen_list[lignite_gen_list.index.str.contains('ramp down')]
lignite_down_cost_flex = n_flex.generators_t.p[lignite_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('lignite ramp down')].marginal_cost).mean()
lignite_list = n_flex.generators.loc[n_flex.generators.index.str.contains('lignite')]
lignite_list = lignite_list[lignite_list.index.str.contains('ramp') == False]
lignite_org_cost_flex = n_flex.generators_t.p[lignite_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[lignite_list.index].marginal_cost).mean()
lignite_total_cost_flex = lignite_up_cost_flex + lignite_down_cost_flex + lignite_org_cost_flex 


oil_cost_flex = n_flex.generators_t.p[oil_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* abs(n_flex.generators[n_flex.generators.carrier == 'oil'].marginal_cost).mean()
oil_up_list = oil_gen_list[oil_gen_list.index.str.contains('ramp up')]
oil_up_cost_flex = n_flex.generators_t.p[oil_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('oil ramp up')].marginal_cost).mean()
oil_down_list = oil_gen_list[oil_gen_list.index.str.contains('ramp down')]
oil_down_cost_flex = n_flex.generators_t.p[oil_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('oil ramp down')].marginal_cost).mean()
oil_list = n_flex.generators.loc[n_flex.generators.index.str.contains('oil')]
oil_list = oil_list[oil_list.index.str.contains('ramp') == False]
oil_org_cost_flex = n_flex.generators_t.p[oil_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[oil_list.index].marginal_cost).mean()
oil_total_cost_flex = oil_up_cost_flex + oil_down_cost_flex + oil_org_cost_flex 


CCGT_cost_flex = n_flex.generators_t.p[CCGT_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* abs(n_flex.generators[n_flex.generators.carrier == 'CCGT'].marginal_cost).mean()
CCGT_up_list = CCGT_gen_list[CCGT_gen_list.index.str.contains('ramp up')]
CCGT_up_cost_flex = n_flex.generators_t.p[CCGT_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('CCGT ramp up')].marginal_cost).mean()
CCGT_down_list = CCGT_gen_list[CCGT_gen_list.index.str.contains('ramp down')]
CCGT_down_cost_flex = n_flex.generators_t.p[CCGT_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('CCGT ramp down')].marginal_cost).mean()
CCGT_list = n_flex.generators.loc[n_flex.generators.index.str.contains('CCGT')]
CCGT_list = CCGT_list[CCGT_list.index.str.contains('ramp') == False]
CCGT_org_cost_flex = n_flex.generators_t.p[CCGT_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[CCGT_list.index].marginal_cost).mean()
CCGT_total_cost_flex = CCGT_up_cost_flex + CCGT_down_cost_flex + CCGT_org_cost_flex 

OCGT_cost_flex = n_flex.generators_t.p[OCGT_gen_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* abs(n_flex.generators[n_flex.generators.carrier == 'OCGT'].marginal_cost).mean()
OCGT_up_list = OCGT_gen_list[OCGT_gen_list.index.str.contains('ramp up')]
OCGT_up_cost_flex = n_flex.generators_t.p[OCGT_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('OCGT ramp up')].marginal_cost).mean()
OCGT_down_list = OCGT_gen_list[OCGT_gen_list.index.str.contains('ramp down')]
OCGT_down_cost_flex = n_flex.generators_t.p[OCGT_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('OCGT ramp down')].marginal_cost).mean()
OCGT_list = n_flex.generators.loc[n_flex.generators.index.str.contains('OCGT')]
OCGT_list = OCGT_list[OCGT_list.index.str.contains('ramp') == False]
OCGT_org_cost_flex = n_flex.generators_t.p[OCGT_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[OCGT_list.index].marginal_cost).mean()
OCGT_total_cost_flex = OCGT_up_cost_flex + OCGT_down_cost_flex + OCGT_org_cost_flex 


solar_up_list = n_flex.generators.loc[n_flex.generators.index.str.contains('solar ramp up')]
solar_up_cost_flex = n_flex.generators_t.p[solar_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('solar ramp up')].marginal_cost).mean()
solar_down_list = n_flex.generators.loc[n_flex.generators.index.str.contains('solar ramp down')]
solar_down_cost_flex = n_flex.generators_t.p[solar_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('solar ramp down')].marginal_cost).mean()
solar_list = n_flex.generators.loc[n_flex.generators.index.str.contains('solar')]
solar_list = solar_list[solar_list.index.str.contains('ramp') == False]
solar_cost_flex = n_flex.generators_t.p[solar_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[solar_list.index].marginal_cost).mean()
solar_total_cost_flex = solar_up_cost_flex + solar_down_cost_flex + solar_cost_flex

onwind_up_list = n_flex.generators.loc[n_flex.generators.index.str.contains('onwind ramp up')]
onwind_up_cost_flex = n_flex.generators_t.p[onwind_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('onwind ramp up')].marginal_cost).mean()
onwind_down_list = n_flex.generators.loc[n_flex.generators.index.str.contains('onwind ramp down')]
onwind_down_cost_flex = n_flex.generators_t.p[onwind_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('onwind ramp down')].marginal_cost).mean()
onwind_list = n_flex.generators.loc[n_flex.generators.index.str.contains('onwind')]
onwind_list = onwind_list[onwind_list.index.str.contains('ramp') == False]
onwind_cost_flex = n_flex.generators_t.p[onwind_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[onwind_list.index].marginal_cost).mean()
onwind_total_cost_flex = onwind_up_cost_flex + onwind_down_cost_flex + onwind_cost_flex

offwind_up_list = n_flex.generators.loc[n_flex.generators.index.str.contains('offwind')]
offwind_up_list = offwind_up_list[offwind_up_list.index.str.contains('ramp up')]
offwind_up_cost_flex = n_flex.generators_t.p[offwind_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[offwind_up_list.index].marginal_cost).mean()
offwind_down_list = n_flex.generators.loc[n_flex.generators.index.str.contains('offwind')]
offwind_down_list = offwind_down_list[offwind_down_list.index.str.contains('ramp down')]
offwind_down_cost_flex = n_flex.generators_t.p[offwind_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[offwind_down_list.index].marginal_cost).mean()
offwind_list = n_flex.generators.loc[n_flex.generators.index.str.contains('offwind')]
offwind_list = offwind_list[offwind_list.index.str.contains('ramp') == False]
offwind_cost_flex = n_flex.generators_t.p[offwind_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[offwind_list.index].marginal_cost).mean()
offwind_total_cost_flex = offwind_up_cost_flex + offwind_down_cost_flex + offwind_cost_flex 

ror_up_list = n_flex.generators.loc[n_flex.generators.index.str.contains('ror ramp up')]
ror_up_cost_flex = n_flex.generators_t.p[ror_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('ror ramp up')].marginal_cost).mean()
ror_down_list = n_flex.generators.loc[n_flex.generators.index.str.contains('ror ramp down')]
ror_down_cost_flex = n_flex.generators_t.p[ror_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('ror ramp down')].marginal_cost).mean()
ror_list = n_flex.generators.loc[n_flex.generators.index.str.contains('ror')]
ror_list = ror_list[ror_list.index.str.contains('ramp') == False]
ror_cost_flex = n_flex.generators_t.p[ror_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[ror_list.index].marginal_cost).mean()
ror_total_cost_flex = ror_up_cost_flex + ror_down_cost_flex + ror_cost_flex

biomass_up_list = n_flex.generators.loc[n_flex.generators.index.str.contains('biomass ramp up')]
biomass_up_cost_flex = n_flex.generators_t.p[biomass_up_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('biomass ramp up')].marginal_cost).mean()
biomass_down_list = n_flex.generators.loc[n_flex.generators.index.str.contains('biomass ramp down')]
biomass_down_cost_flex = n_flex.generators_t.p[biomass_down_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators[n_flex.generators.index.str.contains('biomass ramp down')].marginal_cost).mean()
biomass_list = n_flex.generators.loc[n_flex.generators.index.str.contains('biomass')]
biomass_list = biomass_list[biomass_list.index.str.contains('ramp') == False]
biomass_cost_flex = n_flex.generators_t.p[biomass_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum()* (n_flex.generators.loc[biomass_list.index].marginal_cost).mean()
biomass_total_cost_flex = biomass_up_cost_flex + biomass_down_cost_flex + biomass_cost_flex

total_cost_flex = coal_total_cost_flex+ nuclear_total_cost_flex + lignite_total_cost_flex + oil_total_cost_flex + CCGT_total_cost_flex + OCGT_total_cost_flex + solar_total_cost_flex + onwind_total_cost_flex + offwind_total_cost_flex + ror_total_cost_flex + biomass_total_cost_flex

total_ramp_down_cost_flex = coal_down_cost_flex + nuclear_down_cost_flex + lignite_down_cost_flex + oil_down_cost_flex + CCGT_down_cost_flex+OCGT_down_cost_flex +solar_down_cost_flex + onwind_down_cost_flex + offwind_down_cost_flex + ror_down_cost_flex + biomass_down_cost_flex

total_ramp_up_cost_flex = coal_up_cost_flex + nuclear_up_cost_flex + lignite_up_cost_flex + oil_up_cost_flex + CCGT_up_cost_flex + OCGT_up_cost_flex + solar_up_cost_flex + onwind_up_cost_flex + offwind_up_cost_flex + ror_up_cost_flex + biomass_up_cost_flex

redispatch_cost_flex = total_ramp_down_cost_flex + total_ramp_up_cost_flex 


#%%

labels = ['System Cost Without Flex','System Cost With 100x Flex']
 
width = 0.35       # the width of the bars: can also be len(x) sequence
redispatch = [redispatch_cost,redispatch_cost_flex]
total = [total_cost, total_cost_flex]
fig, ax = plt.subplots()

ax.bar(labels, total, width, label = 'Total System Cost' )
ax.bar(labels, redispatch , width, bottom=(0.0 ), label = 'Re-dispatch Cost' )
#total_cost -redispatch_cost 

ax.set_ylabel('Euros')
ax.set_title('System Costs')
ax.legend(loc = 'lower center')

fraction_org = redispatch_cost/total_cost
fraction_flex = redispatch_cost_flex/ total_cost_flex

plt.text(x=labels[0] ,
                 y=redispatch_cost,
                 s=f'{np.round(fraction_org * 100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")

plt.text(x=labels[1],
                 y=redispatch_cost_flex,
                 s=f'{np.round(fraction_flex * 100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")

plt.show()

#%%
'''
Emissions
'''

CCGT_plant_list = n_flex.generators.loc[n_flex.generators.index.str.contains('CCGT')]
CCGT_plant_list = CCGT_plant_list[CCGT_plant_list.index.str.contains('ramp') == False]
CCGT_emissions = n_flex.generators_t.p[CCGT_plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum() * n_flex.carriers .loc['CCGT']['co2_emissions']

CCGT_ramp_up_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('CCGT ramp up')]
CCGT_ramp_up_dispatch_flex = n_flex.generators_t.p[CCGT_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze()
CCGT_ramp_up_flex_total =  CCGT_ramp_up_dispatch_flex.sum().sum() * n_flex.carriers .loc['CCGT']['co2_emissions']

CCGT_ramp_down_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('CCGT ramp down')]
CCGT_ramp_down_dispatch_flex = n_flex.generators_t.p[CCGT_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze()
CCGT_ramp_down_flex_total =  CCGT_ramp_down_dispatch_flex.sum().sum() * n_flex.carriers .loc['CCGT']['co2_emissions']

CCGT_total_emissions_flex = CCGT_emissions - CCGT_ramp_down_flex_total + CCGT_ramp_up_flex_total 

OCGT_plant_list = n_flex.generators.loc[n_flex.generators.index.str.contains('OCGT')]
OCGT_plant_list = OCGT_plant_list[OCGT_plant_list.index.str.contains('ramp') == False]
OCGT_emissions = n_flex.generators_t.p[OCGT_plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum() * n_flex.carriers .loc['OCGT']['co2_emissions']

OCGT_ramp_up_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('OCGT ramp up')]
OCGT_ramp_up_dispatch_flex = n_flex.generators_t.p[OCGT_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze()
OCGT_ramp_up_flex_total =  OCGT_ramp_up_dispatch_flex.sum().sum() * n_flex.carriers .loc['OCGT']['co2_emissions']

OCGT_ramp_down_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('OCGT ramp down')]
OCGT_ramp_down_dispatch_flex = n_flex.generators_t.p[OCGT_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze()
OCGT_ramp_down_flex_total =  OCGT_ramp_down_dispatch_flex.sum().sum() * n_flex.carriers .loc['OCGT']['co2_emissions']

OCGT_total_emissions_flex = OCGT_emissions - OCGT_ramp_down_flex_total + OCGT_ramp_up_flex_total 

coal_plant_list = n_flex.generators.loc[n_flex.generators.index.str.contains('coal')]
coal_plant_list = coal_plant_list[coal_plant_list.index.str.contains('ramp') == False]
coal_emissions = n_flex.generators_t.p[coal_plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum() * n_flex.carriers .loc['coal']['co2_emissions']

coal_ramp_up_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('coal ramp up')]
coal_ramp_up_dispatch_flex = n_flex.generators_t.p[coal_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze()
coal_ramp_up_flex_total =  coal_ramp_up_dispatch_flex.sum().sum() * n_flex.carriers .loc['coal']['co2_emissions']

coal_ramp_down_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('coal ramp down')]
coal_ramp_down_dispatch_flex = n_flex.generators_t.p[coal_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze()
coal_ramp_down_flex_total =  coal_ramp_down_dispatch_flex.sum().sum() * n_flex.carriers .loc['coal']['co2_emissions']

coal_total_emissions_flex = coal_emissions - coal_ramp_down_flex_total + coal_ramp_up_flex_total 

lignite_plant_list = n_flex.generators.loc[n_flex.generators.index.str.contains('lignite')]
lignite_plant_list = lignite_plant_list[lignite_plant_list.index.str.contains('ramp') == False]
lignite_emissions = n_flex.generators_t.p[lignite_plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum() * n_flex.carriers .loc['lignite']['co2_emissions']

lignite_ramp_up_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('lignite ramp up')]
lignite_ramp_up_dispatch_flex = n_flex.generators_t.p[lignite_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze()
lignite_ramp_up_flex_total =  lignite_ramp_up_dispatch_flex.sum().sum() * n_flex.carriers .loc['lignite']['co2_emissions']

lignite_ramp_down_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('lignite ramp down')]
lignite_ramp_down_dispatch_flex = n_flex.generators_t.p[lignite_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze()
lignite_ramp_down_flex_total =  lignite_ramp_down_dispatch_flex.sum().sum() * n_flex.carriers .loc['lignite']['co2_emissions']

lignite_total_emissions_flex = lignite_emissions - lignite_ramp_down_flex_total + lignite_ramp_up_flex_total 

oil_plant_list = n_flex.generators.loc[n_flex.generators.index.str.contains('oil')]
oil_plant_list = oil_plant_list[oil_plant_list.index.str.contains('ramp') == False]
oil_emissions = n_flex.generators_t.p[oil_plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum() * n_flex.carriers .loc['oil']['co2_emissions']

oil_ramp_up_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('oil ramp up')]
oil_ramp_up_dispatch_flex = n_flex.generators_t.p[oil_ramp_up_flex.index][horizon_start:horizon_end].T.squeeze()
oil_ramp_up_flex_total =  oil_ramp_up_dispatch_flex.sum().sum() * n_flex.carriers .loc['oil']['co2_emissions']

oil_ramp_down_flex = n_flex.generators.loc[n_flex.generators.index.str.contains('oil ramp down')]
oil_ramp_down_dispatch_flex = n_flex.generators_t.p[oil_ramp_down_flex.index][horizon_start:horizon_end].T.squeeze()
oil_ramp_down_flex_total =  oil_ramp_down_dispatch_flex.sum().sum() * n_flex.carriers .loc['oil']['co2_emissions']

oil_total_emissions_flex = oil_emissions - oil_ramp_down_flex_total + oil_ramp_up_flex_total 


total_emmisions_flex = CCGT_total_emissions_flex + OCGT_total_emissions_flex + coal_total_emissions_flex + lignite_total_emissions_flex + oil_total_emissions_flex 
#%%

conv_gen_emissions_flex = pd.DataFrame(index=['OCGT','CCGT' ,'lignite', 'coal', 'oil', 'nuclear'], columns=['co2_emissions'])

for i, j in enumerate(conv_gen_emissions_flex.index):   
        
    plant_list = n_flex.generators.loc[n_flex.generators.index.str.contains('j')]
    plant_list = plant_list[plant_list.index.str.contains('ramp') == False]
    emissions = n_flex.generators_t.p[plant_list.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().sum() * n_flex.carriers.loc[j]['co2_emissions']

    ramp_up_noflex = n_flex.generators.loc[n_flex.generators.index.str.contains(j)]
    ramp_up_noflex = ramp_up_noflex[ramp_up_noflex.index.str.contains('ramp up')]
    ramp_up_dispatch_noflex = n_flex.generators_t.p[ramp_up_noflex.index][horizon_start:horizon_end].T.squeeze()
    ramp_up_noflex_total_emissions =  ramp_up_dispatch_noflex.sum().sum() * n_flex.carriers.loc[j]['co2_emissions']

    ramp_down_noflex = n_flex.generators.loc[n_flex.generators.index.str.contains(j)]
    ramp_down_noflex = ramp_down_noflex[ramp_down_noflex.index.str.contains('ramp down')]
    ramp_down_dispatch_noflex = n_flex.generators_t.p[ramp_down_noflex.index][horizon_start:horizon_end].T.squeeze()
    ramp_down_noflex_total_emissions =  ramp_down_dispatch_noflex.sum().sum() * n_flex.carriers.loc[j]['co2_emissions']

    conv_gen_emissions_flex['co2_emissions'][j] = emissions - ramp_down_noflex_total_emissions + ramp_up_noflex_total_emissions



#%%
#Emissions Plots 

labels = ['Emissions Without Flex','Emissions With Flex']
 
width = 0.35       # the width of the bars: can also be len(x) sequence
emmissions_CCGT = np.array([conv_gen_emissions['co2_emissions']['CCGT'], conv_gen_emissions_flex['co2_emissions']['CCGT']])
emissions_OCGT = np.array([conv_gen_emissions['co2_emissions']['OCGT'], conv_gen_emissions_flex['co2_emissions']['OCGT']])
emissions_coal = np.array([conv_gen_emissions['co2_emissions']['coal'], conv_gen_emissions_flex['co2_emissions']['coal']])
emissions_oil = np.array([conv_gen_emissions['co2_emissions']['oil'], conv_gen_emissions_flex['co2_emissions']['oilT']])
emissions_lignite = np.array([conv_gen_emissions['co2_emissions']['lignite'], conv_gen_emissions_flex['co2_emissions']['lignite']])

fig, ax = plt.subplots()

ax.bar(labels, emmissions_CCGT, width, label = 'CCGT Emissions' )
ax.bar(labels, emissions_OCGT , width, bottom=(emmissions_CCGT ), label = 'OCGT Emissions' )
ax.bar(labels, emissions_coal , width, bottom=(emmissions_CCGT + emissions_OCGT   ), label = 'Coal Emissions' )
ax.bar(labels, emissions_oil , width, bottom=(emmissions_CCGT + emissions_OCGT + emissions_coal ), label = 'Oil Emissions' )
ax.bar(labels, emissions_lignite , width, bottom=(emissions_oil+ emmissions_CCGT + emissions_OCGT + emissions_coal ), label = 'Lignite Emissions' )

#total_cost -redispatch_cost 

ax.set_ylabel('Tonnes C02')
ax.set_title('System Emissions')
ax.legend(loc = 'lower center')


CCGT_fraction_org = conv_gen_emissions['co2_emissions']['CCGT']/conv_gen_emissions['co2_emissions'].sum()
CCGT_fraction_flex = conv_gen_emissions_flex['co2_emissions']['CCGT']/conv_gen_emissions_flex['co2_emissions'].sum()

plt.text(x=labels[0] ,
                 y=conv_gen_emissions['co2_emissions']['CCGT'],
                 s=f'{np.round(CCGT_fraction_org*100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")

plt.text(x=labels[1],
                 y=conv_gen_emissions_flex['co2_emissions']['CCGT'],
                 s=f'{np.round(CCGT_fraction_flex * 100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")


coal_fraction_org = coal_total_emissions/total_emmisions
coal_fraction_flex = coal_total_emissions_flex/ total_emmisions_flex

plt.text(x=labels[0] ,
                 y=coal_total_emissions,
                 s=f'{np.round(coal_fraction_org*100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")

plt.text(x=labels[1],
                 y=coal_total_emissions_flex,
                 s=f'{np.round(coal_fraction_flex * 100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")

lignite_fraction_org = lignite_total_emissions/total_emmisions
lignite_fraction_flex = lignite_total_emissions_flex/ total_emmisions_flex

plt.text(x=labels[0] ,
                 y=lignite_total_emissions,
                 s=f'{np.round(lignite_fraction_org*100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")

plt.text(x=labels[1],
                 y=lignite_total_emissions_flex,
                 s=f'{np.round(lignite_fraction_flex * 100, 2)}%', 
                 color="black",
                 fontsize=12,
                 fontweight="bold")
plt.show()



#%%
loading = abs(n_flex.lines_t.p0[horizon_start:horizon_end]).mean() / n_flex.lines.s_nom_opt
loading.fillna(0,inplace=True)

fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()}, figsize=(9, 9))
cmap= plt.cm.OrRd
norm = mcolors.Normalize(min(loading),max(loading))
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])

colors = list(map(mcolors.to_hex, cmap(norm(loading))))

n_flex.plot(ax=ax, line_colors=colors, line_cmap=plt.cm.jet, title="Line loading", bus_sizes=0.25e-3, bus_alpha=0.7)
plt.colorbar(sm, orientation='vertical', shrink=0.7, ax=ax, label='Line Loading (p.u.)')
fig.tight_layout()


# %%

#check = n_flex.generators_t.p.T

#Total possible positive flex

total_pos = []
for i in range(0,len(flex_pos_gen.index)):
    for t in range(horizon_start,horizon_end ):
        total_pos.append(n_flex.generators.p_nom[flex_pos_gen.index][i]* n_flex.generators_t.p_max_pu[[flex_pos_gen.index][0][i]][t])



pos_potential =  np.array(total_pos).sum() 
pos_actual = n_flex.generators_t.p[flex_pos_gen.index][horizon_start:horizon_end].sum().sum()

total_neg = []
for i in range(0,len(flex_neg_gen.index)):
    for t in range(horizon_start,horizon_end ):
        total_neg.append(n_flex.generators.p_nom[flex_neg_gen.index][i]* n_flex.generators_t.p_max_pu[[flex_neg_gen.index][0][i]][t])

neg_potential =  np.array(total_pos).sum() 
neg_actual = n_flex.generators_t.p[flex_neg_gen.index][horizon_start:horizon_end].sum().sum()

pos_total = n_flex.generators_t.p[flex_pos_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex.generators.bus).sum().T.sum().div(2e5)


# %%

n_flex_copy = n_flex.copy()

for idx,steel_plant in flex_pos_gen.iterrows() :
    p_nom = n_flex_copy.generators.p_nom[idx]
    p_max = n_flex_copy.generators.p_nom[idx]*n_flex_copy.generators_t.p_max_pu[idx][horizon_start:horizon_end]
    n_flex_copy.generators_t.p[idx][horizon_start:horizon_end] = p_max

pos_max = n_flex_copy.generators_t.p[flex_pos_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex_copy.generators.bus).sum().T.sum().div(2e5)

axs[1,0] = n_flex.plot(
       bus_sizes= pos_max,
    bus_colors="red",
    title="Max Available Pos Flex ",
)


for idx,steel_plant in flex_neg_gen.iterrows() :
    p_nom = n_flex_copy.generators.p_nom[idx]
    p_min = n_flex_copy.generators.p_nom[idx]*n_flex_copy.generators_t.p_min_pu[idx][horizon_start:horizon_end]
    n_flex_copy.generators_t.p[idx][horizon_start:horizon_end] = p_min

neg_max = n_flex_copy.generators_t.p[flex_neg_gen.index][horizon_start:horizon_end].T.squeeze().groupby(n_flex_copy.generators.bus).sum().T.sum().div(-2e5)

axs[1,0] = n_flex.plot(
       bus_sizes= neg_max,
    bus_colors="red",
    title="Max Available Neg Flex ",
)
# %%

ccgt_cost = n.generators.loc[n.generators.index.str.contains("CCGT ramp up")].marginal_cost.mean()
ocgt_cost = n.generators.loc[n.generators.index.str.contains("OCGT ramp up")].marginal_cost.mean()
coal_cost = n.generators.loc[n.generators.index.str.contains("coal ramp up")].marginal_cost.mean()
oil_cost = n.generators.loc[n.generators.index.str.contains("oil ramp up")].marginal_cost.mean()
lignite_cost = n.generators.loc[n.generators.index.str.contains("lignite ramp up")].marginal_cost.mean()
nuclear_cost = n.generators.loc[n.generators.index.str.contains("nuclear ramp up")].marginal_cost.mean()

# %%
