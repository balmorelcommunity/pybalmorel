#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os
import copy
import gams
import codecs
import ast
import datetime
import time
import functools
import pandas as pd
import numpy as np
from typing import Union
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from IPython.display import display, HTML, Javascript
import ipywidgets as widgets
from ipywidgets import interact, interactive
from ..plotting.plot_functions import plot_bar_chart
from ..formatting import optiflow_mainresults_symbol_columns, balmorel_mainresults_symbol_columns

#%% ------------------------------- ###
###     1. Bar chart interactive    ###
### ------------------------------- ###


def interactive_bar_chart(MainResults_instance, plot_style: str = 'light'):
    """
    GUI for bar chart plotting
    
    MainResults_instance (MainResults): Takes an instance of the MainResults class and opens a GUI for plotting
    """

    """Result type definition"""
    result_type = MainResults_instance.type.lower()
    print(f"Result type: {result_type}")

    # Initial selection for plotting
    if result_type=='optiflow':
        mainresults_symbol_columns=optiflow_mainresults_symbol_columns
    elif result_type=='balmorel':
        mainresults_symbol_columns=balmorel_mainresults_symbol_columns

    """ Buttons definition """
    
    # Initial selection for plotting
    table_select_button = widgets.Dropdown(options= list(mainresults_symbol_columns.keys()), value=None, description='Table:', disabled=False, layout=widgets.Layout(width='80%'))
    series_select_button = widgets.SelectMultiple(options=[], value=[], description='Series:', disabled=False, layout=widgets.Layout(width='80%'))
    categories_select_button = widgets.SelectMultiple(options=[], value=[], description='Categories:', disabled=False, layout=widgets.Layout(width='80%'))
    
    # Order options for series and categories
    series_order_button1 = widgets.Dropdown(options=[], value=None, description='First:', disabled=False, layout=widgets.Layout(width='99%'))
    series_order_button2 = widgets.Dropdown(options=[], value=None, description='Second:', disabled=False, layout=widgets.Layout(width='99%'))
    series_order_button3 = widgets.Dropdown(options=[], value=None, description='Third:', disabled=False, layout=widgets.Layout(width='99%'))
    categories_order_button1 = widgets.Dropdown(options=[], value=None, description='First:', disabled=False, layout=widgets.Layout(width='99%'))
    categories_order_button2 = widgets.Dropdown(options=[], value=None, description='Second:', disabled=False, layout=widgets.Layout(width='99%'))
    categories_order_button3 = widgets.Dropdown(options=[], value=None, description='Third:', disabled=False, layout=widgets.Layout(width='99%'))
    
    # Filter buttons
    filter_buttons = {symbol : [widgets.SelectMultiple(options=['None'], value=['None'], description=column, disabled=False, layout=widgets.Layout(height='99%', width='80%', overflow='visible'))
                        for column in mainresults_symbol_columns[symbol]]
                        for symbol in mainresults_symbol_columns.keys()    
                    }
    
    # For the plotting layout
    plot_title_button = widgets.Text(description='Title:', disabled=False)
    plot_sizetitle_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                            orientation='horizontal', readout=True, readout_format='.1f')
    plot_fontmin1_button = widgets.Button( description='-1', disabled=False, button_style='', tooltip='-1 on all fonts', icon='')
    plot_fontmin5_button = widgets.Button( description='-0.5', disabled=False, button_style='', tooltip='-0.5 on all fonts', icon='')
    plot_fontlabel_button = widgets.Label(value="Change all fonts")
    plot_fontmax5_button = widgets.Button( description='+0.5', disabled=False, button_style='', tooltip='+0.5 on all fonts', icon='')
    plot_fontmax1_button = widgets.Button( description='+1', disabled=False, button_style='', tooltip='+1 on all fonts', icon='')
    plot_sizex_button = widgets.BoundedFloatText(value=12, min=5, max=20, step=0.1, description='Size x:', disabled=False)
    plot_sizey_button = widgets.BoundedFloatText(value=8, min=5, max=20, step=0.1, description='Size y:', disabled=False)
    
    # For the y-axis layout
    yaxis_title_button = widgets.Text(value='', description='Y Title:', disabled=False)
    yaxis_size_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    yaxis_min_button = widgets.FloatText(value=0, description='Y min:', disabled=False)
    yaxis_max_button = widgets.FloatText(value=0, description='Y max:', disabled=False)
    
    # For the x-axis layout
    xaxis1_button = widgets.ToggleButton(value=True, description='First series', disabled=False, icon='check')
    xaxis1_size_button = widgets.FloatSlider(value=10, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    xaxis1_bold_button = widgets.Checkbox(value=False, description='Bold', disabled=False, indent=False)
    xaxis2_button = widgets.ToggleButton(value=True, description='Second series', disabled=False, icon='check')
    xaxis2_position_button = widgets.FloatText(value=-6, description='Position:', disabled=False, 
                                               orientation='horizontal', readout=True, readout_format='.1f')
    xaxis2_size_button = widgets.FloatSlider(value=11, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    xaxis2_bold_button = widgets.Checkbox(value=False, description='Bold', disabled=False, indent=False)
    xaxis2_sep_button = widgets.FloatSlider(value=1, min=0, max=2, step=0.01, description='Separation', disabled=False,
                                            orientation='horizontal', readout=True, readout_format='.2f')
    xaxis3_button = widgets.ToggleButton(value=True, description='Third series', disabled=False, icon='check')
    xaxis3_position_button = widgets.FloatText(value=-9.5, description='Position:', disabled=False, 
                                               orientation='horizontal', readout=True, readout_format='.1f')
    xaxis3_size_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    xaxis3_bold_button = widgets.Checkbox(value=False, description='Bold', disabled=False, indent=False)
    xaxis3_sep_button = widgets.FloatSlider(value=1, min=0, max=2, step=0.01, description='Separation', disabled=False,
                                            orientation='horizontal', readout=True, readout_format='.2f')
    
    # For the legend layout
    legend_button = widgets.ToggleButton(value=True, description='Legend', disabled=False, icon='check')
    legend_location_button = widgets.Dropdown(value='center left', options=['upper right', 'upper left', 'lower left', 'lower right', 'center left', 'center right', 'lower center',
                                                                       'upper center', 'center'], description='Location:', disabled=False)
    legend_xpos_button = widgets.FloatSlider(value=1, min=0, max=2, step=0.01, description='X position:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.2f')
    legend_ypos_button = widgets.FloatSlider(value=0.5, min=0, max=2, step=0.01, description='Y position:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.2f')
    legend_col_button = widgets.BoundedIntText(value=1, min=1, max=10, step=1, description='Number columns:', disabled=False)
    
    # Ordering elements, initialization
    order_display_button = widgets.Button( description='Choose order', disabled=False, button_style='', tooltip='Click to choose order', icon='')
    global order_buttons
    order_buttons = {}
    
    # Plotting buttons
    plot_button = widgets.Button( description='Plot', disabled=False, button_style='', tooltip='Click to plot', icon='check')
    print_button = widgets.Button( description='Print', disabled=False, button_style='', tooltip='Click to save', icon='check')
    namefile_button = widgets.Text(description='Name file:', disabled=False)
    
    # Iteration printing
    iter_choice_button = widgets.Dropdown(options=[], value=None, description='Iterate on:', disabled=False)
    iter_namefile_button = widgets.Text(description='Name iter:', disabled=False)
    iter_print_button = widgets.Button( description='Iterative print', disabled=False, button_style='', tooltip='Click to print', icon='check')
    iter_title_button = widgets.Checkbox(value=False, description='In the title', disabled=False, indent=False)
    
    # Configuration buttons
    config_save_button = widgets.Button( description='Save config', disabled=False, button_style='', tooltip='Click to save', icon='check')
    nameconfig_button = widgets.Text(description='Name config:', disabled=False)
    config_upload_button = widgets.FileUpload(description='Upload config', tooltip='Click to upload', accept='.txt', multiple=False)
    
    # Dictionnary associating to each button its name
    dict_frombutton = {table_select_button : 'table_select', series_select_button : 'series_select', categories_select_button : 'categories_select', series_order_button1 : 'series_order1',
                       series_order_button2 : 'series_order2', series_order_button3 : 'series_order3', categories_order_button1 : 'categories_order1', categories_order_button2 : 'categories_order2', categories_order_button3 : 'categories_order3', 
                       plot_title_button : 'plot_title', plot_sizetitle_button : 'plot_sizetitle', plot_sizex_button : 'plot_sizex', plot_sizey_button : 'plot_sizey', yaxis_title_button : 'yaxis_title', yaxis_size_button : 'yaxis_size', 
                       yaxis_min_button : 'yaxis_min', yaxis_max_button : 'yaxis_max', xaxis1_size_button : 'xaxis1_size', xaxis1_bold_button : 'xaxis1_bold', xaxis2_position_button : 'xaxis2_position', xaxis2_size_button : 'xaxis2_size', 
                       xaxis2_bold_button : 'xaxis2_bold', xaxis2_sep_button : 'xaxis2_sep', xaxis3_position_button : 'xaxis3_position', xaxis3_size_button : 'xaxis3_size', 
                       xaxis3_bold_button : 'xaxis3_bold', xaxis3_sep_button : 'xaxis3_sep', legend_location_button : 'legend_location', legend_xpos_button : 'legend_xpos', 
                       legend_ypos_button : 'legend_ypos', legend_col_button : 'legend_col', namefile_button : 'namefile', xaxis1_button : 'xaxis1', xaxis2_button : 'xaxis2', xaxis3_button : 'xaxis3', legend_button : 'legend'}
    dict_tobutton = {v: k for k, v in dict_frombutton.items()}
    
    ### Layout and plot part
    
    # For the pivot table order selection
    series_order_stack = widgets.Stack([widgets.VBox([series_order_button1], layout=widgets.Layout(width='80%')),widgets.VBox([series_order_button1,series_order_button2], layout=widgets.Layout(width='80%')),
                                        widgets.VBox([series_order_button1,series_order_button2,series_order_button3], layout=widgets.Layout(width='80%'))])  
    categories_order_stack = widgets.Stack([widgets.VBox([categories_order_button1], layout=widgets.Layout(width='80%')),widgets.VBox([categories_order_button1,categories_order_button2], layout=widgets.Layout(width='80%')),
                                        widgets.VBox([categories_order_button1,categories_order_button2,categories_order_button3], layout=widgets.Layout(width='80%'))])   
    xaxis_order_stack =  widgets.Stack([widgets.VBox([widgets.HBox([xaxis1_button,xaxis1_size_button,xaxis1_bold_button])]),
                                        widgets.VBox([widgets.HBox([xaxis1_button,xaxis1_size_button,xaxis1_bold_button]),widgets.HBox([xaxis2_button,xaxis2_position_button,xaxis2_size_button,xaxis2_bold_button,xaxis2_sep_button])]),
                                        widgets.VBox([widgets.HBox([xaxis1_button,xaxis1_size_button,xaxis1_bold_button]),widgets.HBox([xaxis2_button,xaxis2_position_button,xaxis2_size_button,xaxis2_bold_button,xaxis2_sep_button]),widgets.HBox([xaxis3_button,xaxis3_position_button,xaxis3_size_button,xaxis3_bold_button,xaxis3_sep_button])])])
    
    # For the pivot table options selection
    pivot_selection_layout = widgets.GridBox([table_select_button, widgets.VBox([series_select_button,series_order_stack]) , widgets.VBox([categories_select_button,categories_order_stack])], layout=widgets.Layout(width='100%', grid_template_columns='repeat(3, 1fr)', grid_gap='2px'))
    pivot_selection_out = widgets.Output()
    
    # For the filtering of the table
    filter_layout = [widgets.GridBox(filter_buttons[key], layout=widgets.Layout(height='100%', width='100%', overflow='visible', grid_template_columns='repeat(3, 1fr)', grid_gap='2px')) for key in list(mainresults_symbol_columns.keys())]
    filter_stack = widgets.Stack(filter_layout)
    widgets.jslink((table_select_button,'index'),(filter_stack,'selected_index'))
    filter_out = widgets.Output()
    
    # For putting buttons on opposite side of a same line
    left_button_layout = widgets.Layout(display='flex', flex_flow='row', justify_content='flex-start')
    right_button_layout = widgets.Layout(display='flex', flex_flow='row', justify_content='flex-end')
    
    # Ordering elements, initialization
    order_layout = widgets.HBox([])
    order_out = widgets.Output()
    
    # For the plotting options
    plot_options_layout = widgets.VBox([widgets.HBox([widgets.Box([plot_title_button, plot_sizetitle_button], layout=left_button_layout), widgets.Box(layout=widgets.Layout(flex='1 1 auto')), widgets.Box([plot_fontmin1_button, plot_fontmin5_button, plot_fontlabel_button, plot_fontmax5_button, plot_fontmax1_button], layout=right_button_layout)], layout=widgets.Layout(width='100%')),
                                        widgets.HBox([plot_sizex_button, plot_sizey_button]), widgets.HBox([yaxis_title_button, yaxis_size_button, yaxis_min_button, yaxis_max_button]),
                                        xaxis_order_stack, widgets.HBox([legend_button, legend_location_button, legend_xpos_button, legend_ypos_button, legend_col_button])])
    plot_options_out = widgets.Output()
    
    # Plotting button
    plot_layout = widgets.VBox([widgets.HBox([widgets.Box([plot_button, print_button, namefile_button], layout=left_button_layout), widgets.Box(layout=widgets.Layout(flex='1 1 auto')), widgets.Box([config_save_button, nameconfig_button, config_upload_button], layout=right_button_layout)], layout=widgets.Layout(width='100%')),widgets.HBox([iter_choice_button, iter_namefile_button, iter_print_button, iter_title_button])])
    plot_print_out = widgets.Output()
    plot_out = widgets.Output()

    # Function to update dropdowns based on table selection
    def table_select_function(table_name):
        with pivot_selection_out:
            pivot_selection_out.clear_output()  # Clear previous output
            if table_name :
                # Update dropdown options based on selected table
                series_select_button.options = mainresults_symbol_columns[table_name]
                categories_select_button.options = mainresults_symbol_columns[table_name]
                iter_choice_button.options = mainresults_symbol_columns[table_name]
            else:
                # Reset dropdown options if no table is selected
                series_select_button.options = []
                categories_select_button.options = []
            series_order_button1.value=None
            series_order_button2.value=None
            series_order_button3.value=None

    def series_order_function(series_name):
        with pivot_selection_out:
            pivot_selection_out.clear_output()
            if series_name :
                ser_ord_but1_old, ser_ord_but2_old, ser_ord_but3_old = series_order_button1.value, series_order_button2.value, series_order_button3.value
                series_order_stack.selected_index=len(series_name)-1
                series_order_button1.options, series_order_button2.options, series_order_button3.options = series_name, series_name, series_name
                if ser_ord_but1_old in series_order_button1.options :
                    series_order_button1.value = ser_ord_but1_old
                if ser_ord_but2_old in series_order_button2.options :
                    series_order_button2.value = ser_ord_but2_old
                if ser_ord_but3_old in series_order_button3.options :
                    series_order_button3.value = ser_ord_but3_old
                    
    def categories_order_function(categories_name):
        with pivot_selection_out:
            pivot_selection_out.clear_output()
            if categories_name :
                cat_ord_but1_old, cat_ord_but2_old, cat_ord_but3_old = categories_order_button1.value, categories_order_button2.value, categories_order_button3.value
                categories_order_stack.selected_index=len(categories_name)-1
                categories_order_button1.options, categories_order_button2.options, categories_order_button3.options = categories_name, categories_name, categories_name
                if cat_ord_but1_old in categories_order_button1.options :
                    categories_order_button1.value = cat_ord_but1_old
                if cat_ord_but2_old in categories_order_button2.options :
                    categories_order_button2.value = cat_ord_but2_old
                if cat_ord_but3_old in categories_order_button3.options :
                    categories_order_button3.value = cat_ord_but3_old
        
    def xaxis_option_function(series_name):
        with plot_options_out:
            plot_options_out.clear_output()
            if series_name :
                xaxis_order_stack.selected_index=len(series_name)-1
            
    def df_update(table_name):
        if table_name :
            MainResults_instance.df = MainResults_instance.get_result(table_name)
            with filter_out:
                filter_out.clear_output() # Clear previous output
                for filter_button in filter_buttons[table_name]:
                    filter_button.options = list(sorted(MainResults_instance.df[filter_button.description].unique()))
                    filter_button.value = list(sorted(MainResults_instance.df[filter_button.description].unique()))
                    
    def change_fonts(numb, click):
        with plot_options_out:
            plot_options_out.clear_output()
            dict_font = {plot_sizetitle_button : plot_sizetitle_button.value, yaxis_size_button : yaxis_size_button.value, xaxis1_size_button : xaxis1_size_button.value,
                         xaxis2_size_button : xaxis2_size_button.value, xaxis3_size_button : xaxis3_size_button.value}
            for key, value in dict_font.items():
                key.value = value + float(numb)
                
    def show_order(serie_name):
        with order_out:
            order_out.clear_output()
            table_order = table_select_button.value
            MainResults_instance.df = MainResults_instance.get_result(table_order)
            if serie_name not in order_buttons :
                # Create the list of buttons in the dictionnary
                series_name_options = list(sorted(MainResults_instance.df[serie_name].unique()))
                order_buttons[serie_name] = [widgets.Label(value=f"{serie_name}", layout=widgets.Layout(justify_content='center'))] + [widgets.Dropdown(options=series_name_options, value=None, description=f'Order {i+1}:', disabled=False, layout=widgets.Layout(width='95%')) for i in range(len(series_name_options))]
                    
            # Update the layout to plot the ordering buttons
            list_order = []
            for key in [series_order_button1.value, series_order_button2.value, series_order_button3.value][:len(series_select_button.value)]:
                if key != None :
                    list_order.append(widgets.VBox(order_buttons[key]))
            for key in [categories_order_button1.value, categories_order_button2.value, categories_order_button3.value][:len(categories_select_button.value)]:
                if key != None :
                    list_order.append(widgets.VBox(order_buttons[key]))
                
            order_layout.children = list_order

    def wrap_plot_bar_chart(click):
        with plot_out:
            plot_out.clear_output(wait=True)  # Clear previous output
            
            # Filtering options
            filter = {}
            for filter_button in filter_buttons[table_select_button.value]:
                filter[filter_button.description] = list(filter_button.value)
            
            # Series priority selection 
            nb_series = len(series_select_button.value)
            series_order_selection=[series_order_button3.value, series_order_button2.value, series_order_button1.value][-nb_series:]
            series_order, categories_order = {}, {}
            if None in series_order_selection :
                series_order_selection = series_select_button.value
                print("If you want another index order, you must select the entire order")
            
            # Ordering options
            else :
                for name in series_order_selection :
                    series_order[name] = []
                    for i in range(1,len(order_buttons[name])) :
                        value = order_buttons[name][i].value
                        if value != None :
                            series_order[name].append(value)
            
            # Categories priority selection 
            nb_categories = len(categories_select_button.value)
            categories_order_selection=[categories_order_button1.value, categories_order_button2.value, categories_order_button3.value][:nb_categories]
            if categories_order_selection == [] :
                categories_order_selection = []
            elif None in categories_order_selection :
                categories_order_selection = categories_select_button.value
                print("If you want another categories order, you must select the entire order")
            
            else :
                for name in categories_order_selection :
                    categories_order[name] = []
                    for i in range(1,len(order_buttons[name])) :
                        value = order_buttons[name][i].value
                        if value != None :
                            categories_order[name].append(value)
            
            fig = plot_bar_chart(MainResults_instance.df, filter, series_order_selection, categories_order_selection,
                                (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                 xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                (yaxis_title_button.value, yaxis_size_button.value, yaxis_min_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                series_order, categories_order, False, '', plot_style)
                
            display(fig)
            
            # Close the figure to avoid implicit display by Jupyter
            plt.close(fig)
            
    def wrap_print_bar_chart(click):
        with plot_out:
            plot_out.clear_output(wait=True)  # Clear previous output
            
            # Filtering options
            filter = {}
            for filter_button in filter_buttons[table_select_button.value]:
                filter[filter_button.description] = list(filter_button.value)
            
            # Series priority selection 
            nb_series = len(series_select_button.value)
            series_order_selection=[series_order_button3.value, series_order_button2.value, series_order_button1.value][-nb_series:]
            series_order, categories_order = {}, {}
            if None in series_order_selection :
                series_order_selection = series_select_button.value
                print("If you want another index order, you must select the entire order")
            
            # Ordering options
            else :
                for name in series_order_selection :
                    series_order[name] = []
                    for i in range(1,len(order_buttons[name])) :
                        value = order_buttons[name][i].value
                        if value != None :
                            series_order[name].append(value)
            
            # Categories priority selection 
            nb_categories = len(categories_select_button.value)
            categories_order_selection=[categories_order_button1.value, categories_order_button2.value, categories_order_button3.value][:nb_categories]
            if categories_order_selection == [] :
                categories_order_selection = []
            elif None in categories_order_selection :
                categories_order_selection = categories_select_button.value
                print("If you want another categories order, you must select the entire order")
            
            else :
                for name in categories_order_selection :
                    categories_order[name] = []
                    for i in range(1,len(order_buttons[name])) :
                        value = order_buttons[name][i].value
                        if value != None :
                            categories_order[name].append(value)
            
            # Name of the file
            if namefile_button.value == '':
                namefile = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
            else : 
                namefile = namefile_button.value
            
            fig = plot_bar_chart(MainResults_instance.df, filter, series_order_selection, categories_order_selection,
                                (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                 xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                (yaxis_title_button.value, yaxis_size_button.value, yaxis_min_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                series_order, categories_order, True, namefile, plot_style)
                
            display(fig)
            
            # Close the figure to avoid implicit display by Jupyter
            plt.close(fig)
            
    def wrap_iter_print_bar_chart(click):
        with plot_out:
            plot_out.clear_output(wait=True)  # Clear previous output
            
            # Filtering options
            filter = {}
            for filter_button in filter_buttons[table_select_button.value]:
                filter[filter_button.description] = list(filter_button.value)
            
            # Series priority selection 
            nb_series = len(series_select_button.value)
            series_order_selection=[series_order_button3.value, series_order_button2.value, series_order_button1.value][-nb_series:]
            series_order, categories_order = {}, {}
            if None in series_order_selection :
                series_order_selection = series_select_button.value
                print("If you want another index order, you must select the entire order")
            
            # Ordering options
            else :
                for name in series_order_selection :
                    series_order[name] = []
                    for i in range(1,len(order_buttons[name])) :
                        value = order_buttons[name][i].value
                        if value != None :
                            series_order[name].append(value)
            
            # Categories priority selection 
            nb_categories = len(categories_select_button.value)
            categories_order_selection=[categories_order_button1.value, categories_order_button2.value, categories_order_button3.value][:nb_categories]
            if categories_order_selection == [] :
                categories_order_selection = []
            elif None in categories_order_selection :
                categories_order_selection = categories_select_button.value
                print("If you want another categories order, you must select the entire order")
            
            else :
                for name in categories_order_selection :
                    categories_order[name] = []
                    for i in range(1,len(order_buttons[name])) :
                        value = order_buttons[name][i].value
                        if value != None :
                            categories_order[name].append(value)
            
            # Iteration on
            iteration_cat = iter_choice_button.value
            iteration_cat_index = mainresults_symbol_columns[table_select_button.value].index(iteration_cat)
            iteration_cat_list = filter_buttons[table_select_button.value][iteration_cat_index].options
            
            # Name of the files
            if iter_namefile_button.value == '':
                nameiter = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
            else : 
                nameiter = iter_namefile_button.value
                
            # Iteration of the print
            for value in iteration_cat_list :
                filter[iteration_cat] = [value]
                namefile = nameiter + '-' + value
                
                # Should we put the value in the title
                add_title = ''
                if iter_title_button.value == True:
                    add_title = add_title + ' - ' + value
                
                fig = plot_bar_chart(MainResults_instance.df, filter, series_order_selection, categories_order_selection,
                                (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                 xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                (yaxis_title_button.value, yaxis_size_button.value, yaxis_min_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                series_order, categories_order, True, namefile, plot_style)
                    
                display(fig)
                
                # Close the figure to avoid implicit display by Jupyter
                plt.close(fig)
            

    # Function to save a config
    def save_config(click):
        # Ensure the 'config' directory exists
        config_dir = 'config'
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        # Get the name of the config
        if nameconfig_button.value == '':
            nameconfig = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        else : 
            nameconfig = nameconfig_button.value
        # Create the text file
        file_path = os.path.join(config_dir, f'{nameconfig}.txt')
        
        # Config dict creation
        dict_config = {v: k.value for k,v in dict_frombutton.items()}
        
        # Writting the text file
        with open(file_path, 'w') as file:
            for key, value in dict_config.items():
                file.write(f"{key},{value}\n")
            file.write(".\n")
            for key, value in filter_buttons.items():
                file.write(f'{key},[')
                for i in range(len(value)) :
                    if i == 0 :
                        file.write(f'{value[i].value}')
                    else :
                        file.write(f',{value[i].value}')
                file.write(f']\n')
            file.write(".\n")
            for key, value in order_buttons.items():
                file.write(f'{key},[')
                for i in range(1, len(value)) :
                    if i == 1 :
                        file.write(f'\'{value[i].value}\'')
                    else :
                        file.write(f',\'{value[i].value}\'')
                file.write(f']\n')
                
    # Function to upload a config
    def upload_config(config):
        # Upload the text file
        uploaded_file = config[-1]
        text = codecs.decode(uploaded_file.content, encoding="utf-8")
        # Put the text file as a dict 
        dict_config = {}
        filter = 0
        for line in text.strip().splitlines():
            if line == '.' :
                filter += 1
                # Put back the values inside the buttons
                for k, v in dict_tobutton.items() :
                    v.value = dict_config[k] 
            else :
                if filter == 0 :
                    if line.strip():  
                        key, value = line.split(',', 1) 
                        key = key.strip()  
                        value = value.strip()  
                        # Convert special cases like 'None' or tuples into appropriate Python types
                        if value == 'None':
                            value = None
                        elif value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        elif value.startswith('(') and value.endswith(')'):
                            try:
                                value = eval(value)  # Evaluate tuple-like strings to actual tuples
                            except SyntaxError:
                                pass  # If evaluation fails, keep the string value
                        else:
                            # Try converting the value to float if possible
                            try:
                                value = float(value)
                            except ValueError:
                                pass  # If conversion fails, keep the string value
                        # Assign key-value pair to the dictionary
                        dict_config[key] = value
                elif filter == 1 :
                    key, list_str = line.split(',', 1) 
                    key = key.strip()
                    list_str = list_str.strip()
                    if key == dict_config['table_select'] :
                        # Convert the list string to an actual list using ast.literal_eval
                        value_list = ast.literal_eval(list_str)
                        i = 0
                        for filter_button in filter_buttons[key]:
                            filter_button.value = list(value_list[i])
                            i += 1
                else :
                    key, list_str = line.split(',', 1) 
                    key = key.strip()
                    list_str = list_str.strip()
                    value_list = ast.literal_eval(list_str)
                    for ind, value in enumerate(value_list) :
                        if value != 'None' :
                            order_buttons[key][ind+1].value = value
        
            
    # Dynamic behaviour of the buttons
    table_select_function(table_select_button.value)
    table_select_button.observe(lambda change: table_select_function(change['new']), names='value')
    table_select_button.observe(lambda change: df_update(change['new']), names='value')
    series_select_button.observe(lambda change: series_order_function(change['new']), names='value')
    categories_select_button.observe(lambda change: categories_order_function(change['new']), names='value')
    series_select_button.observe(lambda change: xaxis_option_function(change['new']), names='value')
    series_order_button1.observe(lambda change: show_order(change['new']), names='value')
    series_order_button2.observe(lambda change: show_order(change['new']), names='value')
    series_order_button3.observe(lambda change: show_order(change['new']), names='value')
    categories_order_button1.observe(lambda change: show_order(change['new']), names='value')
    categories_order_button2.observe(lambda change: show_order(change['new']), names='value')
    categories_order_button3.observe(lambda change: show_order(change['new']), names='value')
    config_upload_button.observe(lambda change: upload_config(change['new']), names='value')

    # Activate the plotting of the bar chart on the click
    plot_button.on_click(wrap_plot_bar_chart)
    print_button.on_click(wrap_print_bar_chart)
    config_save_button.on_click(save_config)
    iter_print_button.on_click(wrap_iter_print_bar_chart)
    plot_fontmin1_button.on_click(functools.partial(change_fonts, -1))
    plot_fontmin5_button.on_click(functools.partial(change_fonts, -0.5))
    plot_fontmax5_button.on_click(functools.partial(change_fonts, 0.5))
    plot_fontmax1_button.on_click(functools.partial(change_fonts, 1))
    
    # Display the UI and output areas
    display(pivot_selection_layout, pivot_selection_out)
    display(filter_stack, filter_out)
    display(plot_options_layout, plot_options_out)
    display(order_layout, order_out)
    display(plot_layout, plot_print_out)
    display(plot_out)
