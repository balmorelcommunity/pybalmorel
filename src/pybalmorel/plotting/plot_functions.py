#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os
import copy
import gams
import pandas as pd
import numpy as np
from typing import Union
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from ..formatting import balmorel_colours

#%% ------------------------------- ###
###       1. Bar chart function     ###
### ------------------------------- ###


def plot_bar_chart(df: pd.core.frame.DataFrame, filter: dict, series: Union[str, list], categories: Union[str, list],
                    title: tuple, size: tuple, xaxis: tuple, yaxis: tuple, legend: tuple, save: bool, namefile: str):
    """
    Plotting function for the bar chart

    Args:
        df (DataFrame): Dataframe with the result
        filter (dict): Dictionary with the filters to apply
        table (str): Table selected in the result file
        series (Union[str, list]): Columns used as series
        categories (Union[str, list]): Columns used as categories
        title (tuple): Plot title and size
        size (tuple): Size of the plot
        xaxis (tuple): Options for the x axis
        yaxis (tuple): Options for the y axis
        legend (tuple): Options for the legend
        save (bool): Do the plot have to be saved
        namefile (str): Name of the saved file
    """
    
    # Unit
    unit = df['Unit'][0]
    unit_dict = {'GW': 'Capacity', 'TWh': 'Energy', 'GWh': 'Energy'}
    
    # Filtering the dataframe 
    query_parts = []
    for key, value in filter.items():
        if isinstance(value, list):
            values_str = ', '.join([f'"{v}"' for v in value])
            query_parts.append(f'{key} in [{values_str}]')
        else:
            query_parts.append(f'{key} {value}')
    query_str = ' & '.join(query_parts)
    df = df.query(query_str)

    if series : 

        # Pivot
        temp = df.pivot_table(index=series,
                        columns=categories,
                        values='Value',
                        aggfunc='sum').fillna(0)
        
        #Sometimes one instance of index combination is missing and it's creating plotting issue. For now we'll complete by 0 this instance.
        if type(temp.index[0]) == list:
            all_combinations = pd.MultiIndex.from_product([temp.index.get_level_values(i).unique() for i in range(len(temp.index[0]))], names=series)
            temp = temp.reindex(all_combinations).reset_index()
            temp = df.pivot_table(index=series,
                            columns=categories,
                            values='Value',
                            aggfunc='sum',
                            dropna=False).fillna(0)
        
        # print(temp)
        
        max_bar = temp.sum(axis=1).max()
        
        # Object oriented plotting
        fig, ax = plt.subplots(figsize=size)
        
        # Colors 
        try:
            temp.plot(ax=ax, kind='bar', stacked=True, legend=False, color=balmorel_colours)
        except KeyError:
            temp.plot(ax=ax, kind='bar', stacked=True, legend=False)
        
        if legend[0] == True:
            ax.legend(bbox_to_anchor=(legend[2], legend[3]), loc=legend[1], ncols=legend[4])
        
        # Customizing x-axis
        dict_fw = {True:'bold',False:'normal'}
        categories_first = temp.index.get_level_values(-1).unique()
        ax.set_xticks(range(len(temp)))
        if xaxis[0]==True :
            if type(temp.index[0]) != str:
                ax.set_xticklabels([f'{i[-1]}' for i in temp.index], fontsize=xaxis[1], fontweight=dict_fw[xaxis[2]], rotation=0, ha='center')
            else :
                ax.set_xticklabels([f'{i}' for i in temp.index], fontsize=xaxis[1], fontweight=dict_fw[xaxis[2]], rotation=0, ha='center')
        else :
            ax.set_xticklabels([f'' for i in temp.index])

        # Add x-axis labels for double stage
        if type(temp.index[0]) == tuple and len(temp.index[0]) == 2 :
            categories_second = temp.index.get_level_values(-2).unique()
            
            for ind, cat in enumerate(categories_second):
                if xaxis[3]==True :
                    ax.text((2*ind+1)/(2*len(categories_second)), xaxis[4]*0.01, cat, ha='center', va='center', fontsize=xaxis[5], fontweight=dict_fw[xaxis[6]], rotation=0, transform=ax.transAxes)
                    if ind != 0 :
                        line = plt.Line2D([ind*1/(len(categories_second)), ind*1/(len(categories_second))], [xaxis[7]*xaxis[4]*0.01, 0], transform=ax.transAxes, clip_on=False, color='black', linestyle='-', linewidth=1)
                        ax.add_line(line)
                
        # Add x-axis labels for triple stage
        if type(temp.index[0]) == tuple and len(temp.index[0]) == 3 :
            categories_second = temp.index.get_level_values(-2).unique()
            categories_third = temp.index.get_level_values(-3).unique()
            
            for ind3, cat3 in enumerate(categories_third):
                if xaxis[8]==True :
                    ax.text((2*ind3+1)/(2*len(categories_third)), xaxis[9]*0.01, cat3, ha='center', va='center', fontsize=xaxis[10], fontweight=dict_fw[xaxis[11]], rotation=0, transform=ax.transAxes)
                    if ind3 != 0 :
                        line = plt.Line2D([ind3*1/(len(categories_third)), ind3*1/(len(categories_third))], [xaxis[12]*xaxis[9]*0.01, -0.001], transform=ax.transAxes, clip_on=False, color='black', linestyle='-')
                        ax.add_line(line)
                for ind2, cat2 in enumerate(categories_second):
                    if xaxis[3]==True :
                        ax.text(ind3*1/(len(categories_third))+(2*ind2+1)/(2*len(categories_third)*len(categories_second)), xaxis[4]*0.01, cat2, ha='center', va='center', fontsize=xaxis[5], fontweight=dict_fw[xaxis[6]], rotation=0, transform=ax.transAxes)
                        if ind2 != 0 :
                            line = plt.Line2D([ind3*1/(len(categories_third))+ind2*1/(len(categories_third)*len(categories_second)), ind3*1/(len(categories_third))+ind2*1/(len(categories_third)*len(categories_second))], [xaxis[7]*xaxis[4]*0.01, 0], transform=ax.transAxes, clip_on=False, color='black', linestyle='-', linewidth=1)
                            ax.add_line(line)
        
        # Y label
        if yaxis[0] != '':
            ax.set_ylabel(yaxis[0])
        else :
            if unit in unit_dict:
                ax.set_ylabel(f'{unit_dict[unit]} ({unit})', fontsize=yaxis[1])
            else :
                ax.set_ylabel(f'Value ({unit})', fontsize=yaxis[1])
                
        if yaxis[2] != yaxis[3]:
            ax.set_ylim(yaxis[2],yaxis[3])
        
        ax.set_xlabel('')
        
        ax.set_title(title[0], fontsize=title[1])
        
        if save == True :
            # Ensure the 'output' directory exists
            output_dir = 'output'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            output_path = os.path.join(output_dir, f'{namefile}.png')
            plt.savefig(output_path, format='png', dpi=300, bbox_inches='tight')
        
        return fig
            
        

