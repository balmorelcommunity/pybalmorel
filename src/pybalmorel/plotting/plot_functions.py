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
                    title: tuple, size: tuple, xaxis: tuple, yaxis: tuple, legend: tuple, series_order: dict, categories_order:dict,
                    save: bool, namefile: str, plot_style: str = 'light'):
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
        series_order (dict): Order of the index
        categories_order (dict): Order of the stacking
        save (bool): Do the plot have to be saved
        namefile (str): Name of the saved file
        plot_style (str): Style of the plot, light or dark. Defaults to light
    """
    
    # Unit
    if 'Unit' in df.columns:
        unit = df['Unit'][0]  # Get the first unit value if the column exists
    else:
        unit = None  # Set to an empty list

    # Continue with unit_dict as normal
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
        
        # Ordering the index
        order_list = []
        for serie, order in series_order.items() :
            serie_string = f'{serie}_order'
            order_list.append(serie_string)
            # To make sure we give an order when the user does not specify it
            if len(order) >= 1 :
                used_order = order
            else : 
                used_order = temp.index.get_level_values(serie).unique()
            # Creating a column for ordering
            temp[serie_string] = temp.index.get_level_values(serie).map({value: idx for idx, value in enumerate(used_order)})
        # Ordering with the columns created
        temp = temp.sort_values(by=order_list)
        temp = temp.drop(columns=order_list)

        if len(categories) >= 1 and len(categories_order) >= 1 :
            # Ordering the categories
            order_list = []
            if len(categories_order) == 1 :
                for categorie, order in categories_order.items():
                    order_list = order_list + order
                all_categories = temp.columns.tolist()
                for element in all_categories :
                    if element not in order_list :
                        order_list.append(element)
                # Make sure we don't have the element if they are not there :
                order_list = [item for item in order_list if item in all_categories]
            elif len(categories_order) >= 1 :
                # Create a dictionary for fast look-up of index
                order_index = []
                all_categories = temp.columns.tolist()
                i = 0
                for categorie, order in categories_order.items():
                    ordered_index = {value: index for index, value in enumerate(order)}
                    index_nb = len(ordered_index)
                    for item in all_categories :
                        if item[i] not in list(ordered_index.keys()) :
                            ordered_index[item[i]] = index_nb
                            index_nb += 1 
                    order_index.append(ordered_index)
                    i += 1
                
                # Custom key function for sorting
                def custom_sort_key(item):
                    if len(item) == 2 :
                        first_value, second_value = item
                        return (order_index[0][first_value], order_index[1][second_value])
                    if len(item) == 3 :
                        first_value, second_value, third_value = item
                        return (order_index[0][first_value], order_index[1][second_value], order_index[2][third_value])

                # Sort the list
                order_list = sorted(all_categories, key=custom_sort_key)
                
            temp = temp[order_list]
        
        #Sometimes one instance of index combination is missing and it's creating plotting issue. For now we'll complete by 0 this instance.
        # if type(temp.index[0]) == list:
        #     all_combinations = pd.MultiIndex.from_product([temp.index.get_level_values(i).unique() for i in range(len(temp.index[0]))], names=series)
        #     temp = temp.reindex(all_combinations).reset_index()
        #     temp = df.pivot_table(index=series,
        #                     columns=categories,
        #                     values='Value',
        #                     aggfunc='sum',
        #                     dropna=False).fillna(0)
        
        max_bar = temp.sum(axis=1).max()
        
        # Object oriented plotting
        fig, ax = plt.subplots(figsize=size)
        transform_to_axes = ax.transData + ax.transAxes.inverted()
        
        # Colors 
        try:
            temp.plot(ax=ax, kind='bar', stacked=True, legend=False, color=balmorel_colours)
        except KeyError:
            temp.plot(ax=ax, kind='bar', stacked=True, legend=False)
        
        if legend[0] == True:
            # To deal with double legend
            handles, labels = plt.gca().get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax.legend(by_label.values(), by_label.keys(), bbox_to_anchor=(legend[2], legend[3]), loc=legend[1], ncols=legend[4], reverse=True)
        
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
        if plot_style == 'dark':
            line_colour = 'white'
        else:
            line_colour = 'black'
            
        if type(temp.index[0]) == tuple and len(temp.index[0]) == 2 :
            categories_second = temp.index.get_level_values(-2).unique()
            category_positions_second = [temp.index.get_level_values(-2).tolist().index(cat) for cat in categories_second]
            
            for ind, cat in enumerate(categories_second):
                if xaxis[3]==True :
                    try :
                        x_data_coord = (category_positions_second[ind] + category_positions_second[ind+1]-1)/2
                    except IndexError :
                        x_data_coord = (category_positions_second[ind] + len(temp)-1)/2
                    x_ax_coord = transform_to_axes.transform((x_data_coord, 0))[0]
                    ax.text(x_ax_coord, xaxis[4]*0.01, cat, ha='center', va='center', fontsize=xaxis[5], fontweight=dict_fw[xaxis[6]], rotation=0, transform=ax.transAxes)
                    if ind != 0 :
                        x_data_coord = category_positions_second[ind]-0.5
                        x_ax_coord = transform_to_axes.transform((x_data_coord, 0))[0]
                        line = plt.Line2D([x_ax_coord, x_ax_coord], [xaxis[7]*xaxis[4]*0.01, 0], transform=ax.transAxes, clip_on=False, color=line_colour, linestyle='-', linewidth=1)
                        ax.add_line(line)
                
        # Add x-axis labels for triple stage
        if type(temp.index[0]) == tuple and len(temp.index[0]) == 3 :
            categories_third = temp.index.get_level_values(-3).unique()
            category_positions_third = [temp.index.get_level_values(-3).tolist().index(cat) for cat in categories_third]
            categories_second = temp.index.get_level_values(-2).tolist()
            
            for ind3, cat3 in enumerate(categories_third):
                if xaxis[8]==True :
                    try :
                        x_data_coord = (category_positions_third[ind3] + category_positions_third[ind3+1]-1)/2
                    except IndexError :
                        x_data_coord = (category_positions_third[ind3] + len(temp)-1)/2
                    x_ax_coord = transform_to_axes.transform((x_data_coord, 0))[0]
                    ax.text(x_ax_coord, xaxis[9]*0.01, cat3, ha='center', va='center', fontsize=xaxis[10], fontweight=dict_fw[xaxis[11]], rotation=0, transform=ax.transAxes)
                    if ind3 != 0 :
                        x_data_coord = category_positions_third[ind3]-0.5
                        x_ax_coord = transform_to_axes.transform((x_data_coord, 0))[0]
                        line = plt.Line2D([x_ax_coord, x_ax_coord], [xaxis[12]*xaxis[9]*0.01, -0.001], transform=ax.transAxes, clip_on=False, color=line_colour, linestyle='-', linewidth=1)
                        ax.add_line(line)
                
                if xaxis[3]==True :     
                    ind21, ind22 = category_positions_third[ind3], category_positions_third[ind3]
                    try :
                        next = category_positions_third[ind3+1]
                    except IndexError :
                        next = len(temp)
                    while ind21 != next :
                        if ind22+1 == next or categories_second[ind22] != categories_second[ind22+1] :
                            x_data_coord = (ind21 + ind22)/2
                            x_ax_coord = transform_to_axes.transform((x_data_coord, 0))[0]
                            ax.text(x_ax_coord, xaxis[4]*0.01, categories_second[ind21], ha='center', va='center', fontsize=xaxis[5], fontweight=dict_fw[xaxis[6]], rotation=0, transform=ax.transAxes)
                            ind21 = ind22+1
                            ind22 += 1
                            if ind21 != 0 and ind21 != next:
                                x_ax_coord = transform_to_axes.transform((ind21-0.5, 0))[0]
                                line = plt.Line2D([x_ax_coord, x_ax_coord], [xaxis[7]*xaxis[4]*0.01, 0], transform=ax.transAxes, clip_on=False, color=line_colour, linestyle='-', linewidth=1)
                                ax.add_line(line)
                        else :
                            ind22 += 1
        
        # Y label
        if yaxis[0] != '':
            ax.set_ylabel(yaxis[0])
        else :
            if unit in unit_dict:
                ax.set_ylabel(f'{unit_dict[unit]} ({unit})', fontsize=yaxis[1])
            elif unit==None:
                ax.set_ylabel(f'Value', fontsize=yaxis[1])
            else :
                ax.set_ylabel(f'Value ({unit})', fontsize=yaxis[1])
                
        if yaxis[2] != yaxis[3]:
            ax.set_ylim(yaxis[2],yaxis[3])
        
        ax.set_xlabel('')
        
        ax.set_title(title[0], fontsize=title[1])
        
        if plot_style == 'dark':
            plt.style.use('dark_background')
            ax.set_facecolor('none')
            transparent = True
        else:
            transparent = False
        
        if save == True :
            # Ensure the 'output' directory exists
            output_dir = 'output'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            if '.' not in namefile:
                namefile += '.png'
                
            output_path = os.path.join(output_dir, namefile)
            plt.savefig(output_path, dpi=300, bbox_inches='tight', transparent=transparent)
        
        return fig
            
        

