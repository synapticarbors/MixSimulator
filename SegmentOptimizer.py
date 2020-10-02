import mixsimulator.nevergradBased.Optimizer as opt
import mixsimulator.centrals.PowerCentral as pc
from typing import List
import numpy as np
import pandas as pd
from nevergrad import p
#from centrals.PowerCentral import PowerCentral

class SegmentOptimizer:
    """
        Initiate the appropriate optimization and the power plants:
             Define the objective function;
             Define the constraints;
             Manage data sets;
             Calculates the value of the explanatory variables;
            
    """
    def __init__(self):
        self.__optimizer = opt.Optimizer()
        self.__centrals = []
        self.__demand = 1
        #Static lost
        self.__lost = 0
        self.duration = 1
        pass
    
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
        
        centrals = []
        
        try :
            for i in range (0,data.shape[0]):
                centrale = data["tuneable"][i]
                centrale = pc.PowerCentral(centrale)
                centrale.set_id(str(data["centrals"][i]))
                centrale.set_fuel_consumption(data["fuel_consumption"][i])
                centrale.setAvailability(data["availability"][i])
                centrale.set_fuel_cost(data["fuel_cost"][i])
                centrale.set_initial_value(data["init_value"][i])
                centrale.set_lifetime(data["lifetime"][i])
                centrale.setCarbonProd(data["carbon_production"][i])
                centrale.setRawPower(data["raw_power"][i])
                centrale.set_nb_employees(data["nb_employees"][i])
                centrale.setMeanEmployeesSalary(data["mean_salary"][i])
                centrale.setGreenEnergy(data["green"][i])
                centrals.append(centrale)
            self.__demand=data["Demand"][0]
            self.__lost=data["lost"][0]
        except KeyError:
            print("One of columns missing : tuneable, centrals, fuel_consumption, availability, fuel_cost, init_value, lifetime, carbon_cost, raw_power, nb_employees, mean_salary")
        return centrals
        

    def setCentrals(self, centrals: List[str]):
        self.__centrals.clear()
        for central in centrals:
            self.__centrals.append(central)
    
    def get_fuel_cost(self,centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        fuel_costs = []
        for central in centrals:
            if(central.isTuneable()) :
                #waiting better way to specification, we supposed that tuneable == Thermal Power plant 
                fuel_costs.append(central.get_fuel_cost())
            else :
                fuel_costs.append(1)
        return np.array(fuel_costs)
        
    def get_fuel_consumption(self,centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        consumption = []
        for central in centrals:
            if(central.isTuneable()) : 
                #waiting better way to specification, we supposed that tuneable == Thermal Power plant 
                consumption.append(central.get_fuel_consumption())
            else:
                consumption.append(1)
        return np.array(consumption)
    
    def get_rawPower(self,centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        raw_power = []
        for central in centrals:
            raw_power.append(central.getRawPower())
        return np.array(raw_power)
        
    def get_salary_cost(self,centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        salary_cost = []
        for central in centrals:
            salary_cost.append(central.getEmployeesSalary())
        return np.array(salary_cost)
    
    def get_amortized_cost(self,centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        amortized_cost = []
        for central in centrals:
            amortized_cost.append(central.get_amortized_cost())
        return np.array(amortized_cost)
    
    def get_carbon_prod(self, centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        carbon_prod = []
        for central in centrals:
            carbon_prod.append(central.getCarbonProd())
        return np.array(carbon_prod)

    def get_avaibility_limit(self, centrals: List[str] = None):
        centrals = self.__getCentrals(centrals)
        avaibility_limit = []
        for central in centrals:
            avaibility_limit.append(central.getAvailability())
        return np.array(avaibility_limit)

    def set_time(self, duration):
        self.duration = duration
    
    def get_time(self):
        return self.duration
    
    def prod_cost_objective_function(self,coef_usage):
        return sum((( self.get_fuel_cost() * self.get_fuel_consumption() * coef_usage * self.get_rawPower() )
        + (self.get_salary_cost() + self.get_amortized_cost()))* self.get_time()) 

    def get_carbon_prod_constraint(self, coef_usage):
        return sum(self.get_carbon_prod() * coef_usage)
    
    def get_production_constraint(self, coef_usage):
        return sum(self.get_rawPower() * coef_usage * self.get_time())
        
    # def get_normalized_production_constraint(self, coef_usage, coef_norm):
        # return sum(self.get_rawPower() * coef_usage * self.get_time())

    def getOptimumUsageCoef(self, carbonProdLimit: float = None, demand: float = None,
                            lost: float = None, optimize_with = ["OnePlusOne"], budgets = [100], instrum = None) -> List[float]:
        centrals = self.__getCentrals() 
        if demand == None : 
            demand = self.__demand
            
        #static lost
        if lost == None : 
            lost = self.__lost
            
        # self.set_fuel_cost(centrals)        

        #initiate constraints
        constrains = {}
        constrains.update({"production": self.get_production_constraint})
        constrains.update({"demand": demand})
        constrains.update({"lost": lost})
        constrains.update({"nonTuneable": self.__getNonTuneableCentralIndex(centrals)})
        constrains.update({"carbonProdLimit": carbonProdLimit})
        constrains.update({"carbonProd": self.get_carbon_prod_constraint})
        constrains.update({"availability": self.get_avaibility_limit()})

        #setting all parameters
        if instrum == None :
            self.__optimizer.set_parametrization(p.Array(shape=(len(centrals),)), np.amax(self.get_avaibility_limit()))
        else :
            self.__optimizer.set_parametrization(instrum, np.amax(self.get_avaibility_limit()))

        
        prod_cost_optimal = self.__optimizer.opt_With(self.prod_cost_objective_function, constrains, optimize_with,budgets)
        
        return prod_cost_optimal

    def __getNonTuneableCentralIndex(self, centrals: List[str]= None):
        #split tuneable and non tuneable power plant
        i = 0
        nonTuneableCentral = []
        centrals = self.__getCentrals(centrals)
        for central in centrals:
            if central.isTuneable():
                pass
            else:
                nonTuneableCentral.append(i)
            i+=1
        return nonTuneableCentral

    def __getCentrals(self, centrals: List[str]=None):
        if(centrals==None):
            centrals = self.__centrals
        return centrals