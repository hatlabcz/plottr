"""fitting_models.py

Model functions for data fitting. The functions are categorized into different
classes (Actually I'm not sure if I should just put them in different modules
instead of using different classes here).

Each function must be defined as a static method of its category class, the first
argument must be the independent variable and the rest are parameters.

For now, all parameters must be float type.
"""
import numpy as np

PI = np.pi


#
class GenericFunctions:
    @staticmethod
    def Sinusoidal(x, amp, omega, phase):
        return amp * np.sin(omega * x + phase)

    @staticmethod
    def Exponential(x, a, b):
        return a * b ** x


class ExperimentFunctions:
    @staticmethod
    def T1_Decay(x, amp, tau):
        """ T1 Decay function
        amp * exp(-1.0 * x / tau)
        """
        return amp * np.exp(-1.0 * x / tau)

    @staticmethod
    def T2_Ramsey(x, amp, tau, freq, phase):
        """ T2 Ramsey function
        amp * exp(-1.0 * x / tau) * sin(2 * PI * freq * x + phase)
        """
        return amp * np.exp(-1.0 * x / tau) * np.sin(2 * PI * freq * x + phase)
