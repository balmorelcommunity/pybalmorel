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
                    title: tuple, size: tuple, xaxis: tuple):
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
    """
    
    # Unit
    unit = df['Unit'][0]
    
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
        
        # print(temp)
        
        # Object oriented plotting
        fig, ax = plt.subplots(figsize=size)
        
        # Colors 
        try:
            temp.plot(ax=ax, kind='bar', stacked=True, legend=False, color=balmorel_colours)
        except KeyError:
            temp.plot(ax=ax, kind='bar', stacked=True, legend=False)

        ax.legend(bbox_to_anchor=(0.9, 0.8), loc=2)
        
        # Customizing x-axis
        dict_fw = {True:'bold',False:'normal'}
        categories_final = temp.index.get_level_values(-1).unique()
        ax.set_xticks(range(len(temp)))
        if xaxis[0]==True :
            ax.set_xticklabels([f'{i[-1]}' for i in temp.index], fontsize=xaxis[1], fontweight=dict_fw[xaxis[2]], rotation=0, ha='center')
        else :
            ax.set_xticklabels([f'' for i in temp.index])

        # Add x-axis labels for double stage
        if len(temp.index[0]) == 2 :
            categories_second = temp.index.get_level_values(-2).unique()
            category_positions_second = [temp.index.get_level_values(-2).tolist().index(cat) for cat in categories_second]
            
            for cat, pos in zip(categories_second, category_positions_second):
                if xaxis[3]==True :
                    ax.text(pos + len(categories_final)/2-0.5, xaxis[4], cat, ha='center', va='center', fontsize=xaxis[5], fontweight=dict_fw[xaxis[6]], rotation=0)
                    if pos != 0 :
                        ax.axvline(x=pos-0.5, ymin=xaxis[7], ymax=-0.001, clip_on=False, color='black', linestyle='-', linewidth=1)
                
        # Add x-axis labels for triple stage
        if len(temp.index[0]) == 3 :
            categories_second = temp.index.get_level_values(-2).unique()
            category_positions_second = [temp.index.get_level_values(-2).tolist().index(cat) for cat in categories_second]
            categories_third = temp.index.get_level_values(-3).unique()
            category_positions_third = [temp.index.get_level_values(-3).tolist().index(cat) for cat in categories_third]
            
            for cat1, pos1 in zip(categories_third, category_positions_third):
                if xaxis[8]==True :
                    ax.text(pos1 + (len(categories_final)*len(categories_second))/2-0.5, xaxis[9], cat1, ha='center', va='center', fontsize=xaxis[10], fontweight=dict_fw[xaxis[11]], rotation=0)
                    if pos1 != 0 :
                        ax.axvline(x=pos1-0.5, ymin=xaxis[12], ymax=-0.001, clip_on=False, color='black', linestyle='-', linewidth=1)
                for cat2, pos2 in zip(categories_second, category_positions_second):
                    if xaxis[3]==True :
                        ax.text(pos1 + pos2 + len(categories_final)/2-0.5, xaxis[4], cat2, ha='center', va='center', fontsize=xaxis[5], fontweight=dict_fw[xaxis[6]], rotation=0)
                        if pos2 != 0 :
                            ax.axvline(x=pos1+pos2-0.5, ymin=xaxis[7], ymax=-0.001, clip_on=False, color='black', linestyle='-', linewidth=1)
        
        
        ax.set_ylabel(f'Value ({unit})')
        ax.set_xlabel('')
        
        ax.set_title(title[0], fontsize=title[1])
        
        return fig

