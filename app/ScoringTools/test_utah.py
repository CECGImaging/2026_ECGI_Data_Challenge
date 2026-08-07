import utah_score as us
import numpy as np


t = np.linspace(0,np.pi*2,1000)
v1 = np.sin(t)
v2 = np.sin(t+np.pi/5)

corr = us.calculate_correlation(v1,v2)
print(f"V1 corr with V2: {corr:.4f}")


m1 = np.sin(np.tile(t,(10,1)) + np.tile(np.expand_dims(np.linspace(0,np.pi/10,10),1),(1,1000)))
m2 = np.sin(np.tile(t,(10,1)))

mean_spatial_corr,spatial_corrs = us.calc_spatial_correlation(m1,m2)
print(f"M1 spatial corr with M2: {mean_spatial_corr:.4f}")

mean_temporal_corr,temporal_corrs = us.calc_temporal_correlation(m1,m2)
print(f"M1 temporal corr with M2: {mean_temporal_corr:.4f}")

RMSE = us.calc_RMSE(m1,m2)
print(f"M1 RMSE to M2: {RMSE:.4f}")