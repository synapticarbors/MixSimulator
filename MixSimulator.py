from SegmentOptimizer import SegmentOptimizer
from centrals.PowerCentral import PowerCentral
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List

class MixSimulator:
    def __init__(self):
        self.__reset_centrals()
        self.__demand = 0
        self.__lost = 0

    def __reset_centrals(self):
        self.__centrals = {}
        self.__centrals.update({"green": []})
        self.__centrals.update({"non_green": []})

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
        centrale_tmp = []
        try :
            for i in range (0,data.shape[0]):
                centrale = data["tuneable"][i]
                centrale = PowerCentral(centrale)
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
                centrale_tmp.append(centrale)
            self.__demand=data["Demand"][0]
            self.__lost=data["lost"][0]
        except KeyError:
            print("Columns must be in: tuneable, green, centrals, fuel_consumption, availability, fuel_cost, init_value, lifetime, carbon_cost, raw_power, nb_employees, mean_salary, demand, lost")
            raise
            
        self.__splitCentrals(centrale_tmp)

    def setCentrals(self, centrals: List[PowerCentral]):
        self.__reset_centrals()
        self.__splitCentrals(centrals)

    def __splitCentrals(self, centrals: List[PowerCentral]):
        for centrale in centrals:
                if centrale.isGreen():
                    self.__centrals["green"].append(centrale)
                else:
                    self.__centrals["non_green"].append(centrale)


    def optimizeMix(self, carbonProdLimit, demand: float= None, lost: float=None, time_interval: float = 1, carbon_cost: float = None ):
        # default parameter
        usage_coef = {}
        productionCost = 0.
        results = {}


        if demand is None:
            demand = self.__demand
        if lost is None:
            lost = self.__lost

        green_mix = SegmentOptimizer()
        non_green_mix = SegmentOptimizer()
        
        green_mix.setCentrals(self.__centrals["green"])
        non_green_mix.setCentrals(self.__centrals["non_green"])

        green_mix.set_time(time_interval)
        non_green_mix.set_time(time_interval)

        # prioriser d'abord les energies renouvelables
        GREEN_RESULT = green_mix.getOptimumUsageCoef(carbonProdLimit=carbonProdLimit, demand= demand, lost=lost)
        new_carbonProdLimit = carbonProdLimit - GREEN_RESULT["carbonProd"]
        demand = demand - GREEN_RESULT["production"]
        production_cost = GREEN_RESULT["production cost"]
        
        index_central = 0
        for coef in GREEN_RESULT["coef"]:
            usage_coef.update({self.__centrals["green"][index_central].get_id():coef})
            index_central += 1

        NON_GREEN_RESULT = non_green_mix.getOptimumUsageCoef(carbonProdLimit=new_carbonProdLimit, demand=demand, lost=lost)
        new_carbonProdLimit = new_carbonProdLimit - NON_GREEN_RESULT["carbonProd"]
        demand = demand - NON_GREEN_RESULT["production"] + lost
        production_cost = production_cost + NON_GREEN_RESULT["production cost"]
        
        index_central = 0
        for coef in NON_GREEN_RESULT["coef"]:
            usage_coef.update({self.__centrals["non_green"][index_central].get_id():coef})
            index_central += 1

        results.update({"production_cost ($)": production_cost})
        results.update({"carbon_impacte (g/MWh)": carbonProdLimit-new_carbonProdLimit})
        if carbon_cost is None:
            pass
        else :
            results.update({"carbon_cost ($/MWh)": (carbonProdLimit - new_carbonProdLimit) * carbon_cost})
        results.update({"unsatisfied_demand (MWh)": demand})
        results.update({"usage_coefficient": usage_coef})

        return results

    def simuleMix(self, current_usage_coef, carbonProdLimit, demand: float= None, lost: float=None, time_interval: float = 1, carbon_cost: float = None, verbose: int = 1, plot: str = "default" ):
        # initialization
        if demand is None:
            demand = self.__demand
        if lost is None:
            lost = self.__lost

        # optimum usage and results/perf
        theorical_optimum = self.optimizeMix(carbonProdLimit, demand, lost, time_interval, carbon_cost)
        
        ##### actual perf
        current_perf = {}

        # current Mix initialization
        current_mix = SegmentOptimizer()
        centrals = []
        for key in self.__centrals.keys():
            for central in self.__centrals[key]:
                centrals.append(central)
        current_mix.setCentrals(centrals)
        current_mix.set_time(time_interval)
        current_perf.update({"production_cost ($)": current_mix.prod_cost_objective_function(current_usage_coef)})
        current_perf.update({"carbon_impacte (g/MWh)": current_mix.get_carbon_prod_constraint(current_usage_coef)})
        current_perf.update({"unsatisfied_demand (MWh)": demand - current_mix.get_production_constraint(current_usage_coef)})
        current_perf.update({"usage_coefficient": current_usage_coef})

        # verbosity
        if verbose == 1 :
            print("theorical_optimum : ",theorical_optimum)
            print("current_perf : ", current_perf)
        
        #plotting
        if plot == "default" :
            self.plotResults(theorical_optimum,current_perf,mode = plot)
        else :
            if plot == "none" :
                pass
            else :
                print("Available plot options : \n \t 'default' : show and save the results plots; \n \t 'none' : no plots.")


    def plotResults(self, optimum : dict = {}, current : dict = {}, mode : str = "default") :
        columns=[]
        tmp=[]
        data=[]
        for keys, values in optimum.items():
            if keys == "usage_coefficient":
                for k, v in values.items():
                    columns.append(k)
                    tmp.append(v)
        data.append(tmp)
        tmp=[]        
        for keys, values in current.items():
            if keys == "usage_coefficient":
                data.append(values)
                
        rows = ["current","optimum"]        
              
        # Get some pastel shades for the colors
        colors = plt.cm.autumn(np.linspace(0, 0.5, len(rows)))
        n_rows = len(data)
        
        index = np.arange(len(columns)) + 0.3
        bar_width = 0.4
        
        # Initialize the vertical-offset for the stacked bar chart.
        y_offset = np.zeros(len(columns))
        
        # Plot bars and create text labels for the table
        cell_text = []
        correction = np.zeros(len(columns))
        for row in range(n_rows):
            for i in range(0,len(columns)):
                if y_offset[i] < data[row][i]:
                    correction[i] = y_offset[i]
                    color_correction = row-1
            y_offset = np.zeros(len(columns))
            plt.bar(index, data[row], bar_width, bottom=y_offset, color=colors[row])
            y_offset = data[row]
            cell_text.append(['%f' % x for x in y_offset])
            
        #correction to avoid hidden bar
        y_offset = np.zeros(len(columns))
        plt.bar(index, correction, bar_width, bottom=y_offset, color=colors[color_correction])            
        
        # Reverse colors and text labels to display the last value at the top.
        colors = colors[::-1]
        cell_text.reverse()
        
        # Add a table at the bottom of the axes
        the_table = plt.table(cellText=cell_text,
                              rowLabels=rows,
                              rowColours=colors,
                              colLabels=columns,
                              loc='bottom')
        
        # Adjust layout to make room for the table:
        plt.subplots_adjust(left=0.2, bottom=0.2)
        values = np.arange(0, 120, 20)
        value_increment = 100 
        plt.ylabel("Usage coef. in % ")
        plt.yticks(values / value_increment, ['%d' % val for val in values])
        plt.xticks([])
        plt.title('Optimum and Current values')
        
        plt.show()