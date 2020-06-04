import lmfit
import numpy as np
import matplotlib.pyplot as plt

def sinefunc(x, amp, freq, phase):
    return amp * np.sin(2 * np.pi * (freq * x + phase))
#
x = np.linspace(1,10,100)
y = np.sin(3*x) + np.random.normal(scale=0.2, size=x.shape)
sinemodel = lmfit.Model(sinefunc)
p0 = sinemodel.make_params(amp=1, freq=0.35, phase=0)
result = sinemodel.fit(y, p0, x=x)

print(result.success)
plt.figure()
plt.plot(x,y)
plt.plot(x, result.best_fit)

