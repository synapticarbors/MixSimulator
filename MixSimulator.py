from .centrals import PowerCentral as pc
from .centrals import HydroCentral as hc 
from .Demand import Demand
from .nevergradBased.Optimizer import Optimizer
import numpy as np
import pandas as pd
#import warnings
#import time
#from typing import List
#from datetime import datetime
#import matplotlib.pyplot as plt

class MixSimulator:
    """
        The simulator Base            
    """
    def __init__(self):
        self.__centrals = []
        self.__reset_centrals()
        self.__demand = Demand(20, 0.2, 0.2)
        self.__lost = 0
        self.__penalisation_cost = 1000000000000
        self.__optimizer =  Optimizer()

    def __reset_centrals(self):
        self.__centrals = []

    def set_data_csv(self, bind: str, delimiter: str=";"):
        try :
            data = pd.DataFrame(pd.read_csv(bind,delimiter=delimiter))
            
        except FileNotFoundError as e :
            print("Error occured on pandas.read_csv : ",e)
            print("Please check your file")
            raise           
        except Exception as e:
            print("Error occured on pandas.read_csv : ",e)
            raise
            
        self.__reset_centrals()
        try :
            for i in range (0,data.shape[0]):
                isHydro = data["hydro"][i]
                if isHydro == True :
                    centrale = hc.HydroCentral(data["height"][i],data["flow"][i],data["capacity"][i],data["stock_available"][i],0.1,0.8)
                else :
                    centrale = pc.PowerCentral()
                centrale.set_tuneable(data["tuneable"][i])
                centrale.set_id(str(data["centrals"][i]))
                centrale.set_fuel_consumption(data["fuel_consumption"][i])
                centrale.set_availability(data["availability"][i])
                centrale.set_fuel_cost(data["fuel_cost"][i])
                centrale.set_initial_value(data["init_value"][i])
                centrale.set_lifetime(data["lifetime"][i])
                centrale.set_carbon_prod(data["carbon_production"][i])
                centrale.set_raw_power(data["raw_power"][i])
                centrale.set_nb_employees(data["nb_employees"][i])
                centrale.set_mean_employees_salary(data["mean_salary"][i])
                self.__centrals.append(centrale)
            self.__demand.set_mean_demand(data["Demand"][0])
            self.__lost=data["lost"][0]
        except KeyError:
            print("Columns must be in: tuneable, centrals, fuel_consumption, availability, fuel_cost, init_value, lifetime, carbon_cost, raw_power, nb_employees, mean_salary, demand, lost")
            raise
            
    def set_demand(self, demand: Demand):
        self.__demand = demand
    
    # def get_demand(self, t, time_interval: float = 1):
    #     return self.__demand.get_demand_approxima(t, time_interval)

    def set_penalisation_cost(self, k):
        self.__penalisation_cost = k

    def get_penalisation_cost(self):
        return self.__penalisation_cost

    ## EVALUATION FONCTION ##

    def get_production_cost_at_t(self, usage_coef, time_index, time_interval):
        production_cost = 0
        for centrale_index in range (0, len(self.__centrals)):
            central = self.__centrals[centrale_index]
            production_cost += ( (central.get_fuel_cost() * central.get_fuel_consumption() 
            * central.get_raw_power() * usage_coef[centrale_index]) + ( central.get_employees_salary()
            + central.get_amortized_cost(time_index) ) ) * time_interval
        return production_cost


    def get_production_at_t(self, usage_coef, time_interval):
        production = 0
        for centrale_index in range (0, len(self.__centrals)):
            central = self.__centrals[centrale_index]
            production += (central.get_raw_power() * usage_coef[centrale_index]) * time_interval
        return production


    def get_unsatisfied_demand_at_t(self, usage_coef, time_index, time_interval):
        return ( self.__demand.get_demand_approxima(time_index, time_interval) - self.get_production_at_t(usage_coef, time_interval))


    def loss_function(self, usage_coef, time_interval : int = 1) -> float : 
        loss = 0
        for t in range(0, len(usage_coef)):
            loss += self.get_production_cost_at_t(usage_coef[t], t, time_interval) + self.get_penalisation_cost() * np.abs( self.get_unsatisfied_demand_at_t(usage_coef[t], t, time_interval))
        return loss


    def get_carbon_production_at_t(self, usage_coef, time_interval):
        carbon_prod = 0
        for centrale_index in range (0, len(self.__centrals)):
            central = self.__centrals[centrale_index]
            carbon_prod += (central.get_carbon_production() * usage_coef[centrale_index] * central.get_raw_power()) * time_interval
        return carbon_prod


    ## CONSTRAINTS ##
    def check_carbon_production_limit_constraint(self, usage_coef, time_interval, carbon_production_limit: float = 50000):
        emited_carbon = 0 # (g)
        total_production = 0
        for t in range(0, len(usage_coef)):
            emited_carbon += self.get_carbon_production_at_t(usage_coef[t], time_interval)
            total_production += self.get_production_at_t(usage_coef[t], time_interval)
        carbon_production = emited_carbon/total_production
        return carbon_production<carbon_production_limit


    def check_availability_constraint(self, usage_coef):
        satisfied_constraint = True
        for t in range(0, len(usage_coef)):
            for central_index in range(0, len(usage_coef[t])):
                if usage_coef[t][central_index] > self.__centrals[central_index].get_availability(t):
                    satisfied_constraint = False
                    break
            if not satisfied_constraint:
                break
        return satisfied_constraint


    def check_tuneablity_constraint(self, usage_coef):
        satisfied_constraint = True
        for t in range(0, len(usage_coef)):
            for central_index in range(0, len(usage_coef[t])):
                if not self.__centrals[central_index].is_tuneable():
                    if usage_coef[t][central_index] > 0.1 and np.abs(usage_coef[t][central_index] - self.__centrals[central_index].get_availability(t)) > 0.1:
                        satisfied_constraint = False
                        break
            if not satisfied_constraint:
                break
        return satisfied_constraint
        
        
    ## OPTiMiZATION ##
        
    
    def optimizeMix(self, carbonProdLimit, demand: Demand = None, lost: float = None, 
                    optimizer: Optimizer = None, step : int = 1,
                    time_index: int = 24*365, time_interval: float = 1,
                    penalisation : float = None):
        
        #init params                
        if demand is not None : self.__demand = demand
        if lost is not None : self.__lost = lost
        if penalisation is not None : self.set_penalisation_cost(penalisation)
            
        #init constraints
        constraints = {}
        constraints.update({"carbonLimit_function":self.check_carbon_production_limit_constraint})
        constraints.update({"carbonLimit":carbonProdLimit})
        constraints.update({"time_interval":time_interval})
        constraints.update({"availability_function":self.check_availability_constraint})
        constraints.update({"tuneablity_function":self.check_tuneablity_constraint})

        #let's optimize
        if optimizer is None :
            optimizer = self.__optimizer
        optimizer.setDim(n = time_index, m = len(self.__centrals))
        results = optimizer.optimize(self.loss_function, constraints = constraints,
                                    step = step, k = self.get_penalisation_cost())
        
        return results