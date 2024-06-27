#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

import os
import copy
import gams
import datetime
import pandas as pd
import numpy as np
from typing import Union
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from IPython.display import display
import ipywidgets as widgets
from ipywidgets import interact, interactive
from ..plotting.plot_functions import plot_bar_chart
from ..formatting import  mainresults_symbol_columns


#%% ------------------------------- ###
###     1. Bar chart interactive    ###
### ------------------------------- ###


def interactive_bar_chart(MainResults_instance):
    """
    GUI for bar chart plotting
    
    MainResults_instance (MainResults): Takes an instance of the MainResults class and opens a GUI for plotting
    """

    """ Buttons definition """
    # Initial selection for plotting
    table_select_button = widgets.Dropdown(options= list(mainresults_symbol_columns.keys()), value=None, description='Table:', disabled=False)
    series_select_button = widgets.SelectMultiple(options=[], value=[], description='Series:', disabled=False)
    categories_select_button = widgets.SelectMultiple(options=[], value=[], description='Categories:', disabled=False)
    
    # Order options for series and categories
    series_order_button1 = widgets.Dropdown(options=[], value=None, description='First:', disabled=False)
    series_order_button2 = widgets.Dropdown(options=[], value=None, description='Second:', disabled=False)
    series_order_button3 = widgets.Dropdown(options=[], value=None, description='Third:', disabled=False)
    
    # Filter buttons
    filter_buttons = {symbol : [widgets.SelectMultiple(options=['None'], value=['None'], description=column, disabled=False)
                        for column in mainresults_symbol_columns[symbol]]
                        for symbol in mainresults_symbol_columns.keys()    
                    }
    
    # For the plotting layout
    plot_title_button = widgets.Text(description='Title:', disabled=False)
    plot_sizetitle_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                            orientation='horizontal', readout=True, readout_format='.1f')
    plot_sizex_button = widgets.BoundedFloatText(value=12, min=5, max=20, step=0.1, description='Size x:', disabled=False)
    plot_sizey_button = widgets.BoundedFloatText(value=8, min=5, max=20, step=0.1, description='Size y:', disabled=False)
    
    # For the y-axis layout
    yaxis_title_button = widgets.Text(value='', description='Y Title:', disabled=False)
    yaxis_max_button = widgets.FloatText(value=1000000000000, description='Y max:', disabled=False)
    
    # For the x-axis layout
    xaxis1_button = widgets.ToggleButton(value=True, description='First series', disabled=False, icon='check')
    xaxis1_size_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    xaxis1_bold_button = widgets.Checkbox(value=False, description='Bold', disabled=False, indent=False)
    xaxis2_button = widgets.ToggleButton(value=True, description='Second series', disabled=False, icon='check')
    xaxis2_position_button = widgets.FloatText(value=-2, description='Position:', disabled=False, 
                                               orientation='horizontal', readout=True, readout_format='.1f')
    xaxis2_size_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    xaxis2_bold_button = widgets.Checkbox(value=False, description='Bold', disabled=False, indent=False)
    xaxis2_sep_button = widgets.FloatSlider(value=-0.05, min=-0.5, max=-0.001, step=0.001, description='Separation', disabled=False,
                                            orientation='horizontal', readout=True, readout_format='.3f')
    xaxis3_button = widgets.ToggleButton(value=True, description='Third series', disabled=False, icon='check')
    xaxis3_position_button = widgets.FloatText(value=-3, description='Position:', disabled=False, 
                                               orientation='horizontal', readout=True, readout_format='.1f')
    xaxis3_size_button = widgets.FloatSlider(value=12, min=2, max=20, step=0.1, description='Size:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.1f')
    xaxis3_bold_button = widgets.Checkbox(value=False, description='Bold', disabled=False, indent=False)
    xaxis3_sep_button = widgets.FloatSlider(value=-0.1, min=-0.5, max=-0.001, step=0.001, description='Separation', disabled=False,
                                            orientation='horizontal', readout=True, readout_format='.3f')
    
    # For the legend layout
    legend_button = widgets.ToggleButton(value=True, description='Legend', disabled=False, icon='check')
    legend_location_button = widgets.Dropdown(value='center left', options=['upper right', 'upper left', 'lower left', 'lower right', 'center left', 'center right', 'lower center',
                                                                       'upper center', 'center'], description='Location:', disabled=False)
    legend_xpos_button = widgets.FloatSlider(value=1.1, min=0, max=2, step=0.01, description='X position:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.2f')
    legend_ypos_button = widgets.FloatSlider(value=0.5, min=0, max=2, step=0.01, description='Y position:', disabled=False, 
                                             orientation='horizontal', readout=True, readout_format='.2f')
    legend_col_button = widgets.BoundedIntText(value=1, min=1, max=10, step=1, description='Number columns:', disabled=False)
    
    # Plotting buttons
    plot_button = widgets.Button( description='Plot', disabled=False, button_style='', tooltip='Click to plot', icon='check')
    print_button = widgets.Button( description='Print', disabled=False, button_style='', tooltip='Click to save', icon='check')
    namefile_button = widgets.Text(description='Name file:', disabled=False)
    
    # For the pivot table order selection
    series_order_stack = widgets.Stack([widgets.VBox([series_order_button1]),widgets.VBox([series_order_button1,series_order_button2]),
                                        widgets.VBox([series_order_button1,series_order_button2,series_order_button3])])   
    xaxis_order_stack =  widgets.Stack([widgets.VBox([widgets.HBox([xaxis1_button,xaxis1_size_button,xaxis1_bold_button])]),
                                        widgets.VBox([widgets.HBox([xaxis1_button,xaxis1_size_button,xaxis1_bold_button]),widgets.HBox([xaxis2_button,xaxis2_position_button,xaxis2_size_button,xaxis2_bold_button,xaxis2_sep_button])]),
                                        widgets.VBox([widgets.HBox([xaxis1_button,xaxis1_size_button,xaxis1_bold_button]),widgets.HBox([xaxis2_button,xaxis2_position_button,xaxis2_size_button,xaxis2_bold_button,xaxis2_sep_button]),widgets.HBox([xaxis3_button,xaxis3_position_button,xaxis3_size_button,xaxis3_bold_button,xaxis3_sep_button])])])
    
    # For the pivot table options selection
    pivot_selection_layout = widgets.GridBox([table_select_button, widgets.VBox([series_select_button,series_order_stack]) , categories_select_button], layout=widgets.Layout(width='100%', grid_template_columns='repeat(3, 1fr)', grid_gap='2px'))
    pivot_selection_out = widgets.Output()
    
    # For the filtering of the table
    filter_layout = [widgets.GridBox(filter_buttons[key], layout=widgets.Layout(width='100%', grid_template_columns='repeat(3, 1fr)', grid_gap='2px')) for key in list(mainresults_symbol_columns.keys())]
    filter_stack = widgets.Stack(filter_layout)
    widgets.jslink((table_select_button,'index'),(filter_stack,'selected_index'))
    filter_out = widgets.Output()
    
    # For the plotting 
    plot_options_layout = widgets.VBox([widgets.HBox([plot_title_button, plot_sizetitle_button]), widgets.HBox([plot_sizex_button, plot_sizey_button]), widgets.HBox([yaxis_title_button, yaxis_max_button]),
                                        xaxis_order_stack, widgets.HBox([legend_button, legend_location_button, legend_xpos_button, legend_ypos_button, legend_col_button])])
    plot_options_out = widgets.Output()
    
    # Plotting button
    plot_layout = widgets.HBox([plot_button, print_button, namefile_button])
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
                series_order_stack.selected_index=len(series_name)-1
                series_order_button1.options = series_name
                series_order_button2.options = series_name
                series_order_button3.options = series_name
        
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

    def wrap_plot_bar_chart(click):
        with plot_out:
            plot_out.clear_output()  # Clear previous output
            # Filtering options
            filter = {}
            for filter_button in filter_buttons[table_select_button.value]:
                filter[filter_button.description] = list(filter_button.value)
            nb_series = len(series_select_button.value)
            series_order_selection=[series_order_button3.value, series_order_button2.value, series_order_button1.value][-nb_series:]
            if None in series_order_selection:
                fig = plot_bar_chart(MainResults_instance.df, filter, series_select_button.value, categories_select_button.value,
                                    (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                    (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                     xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                    (yaxis_title_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                    False, '')
            else:
                fig = plot_bar_chart(MainResults_instance.df, filter, series_order_selection, categories_select_button.value,
                                    (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                    (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                     xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                    (yaxis_title_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                    False, '')
            plt.show(fig)
            
    def wrap_print_bar_chart(click):
        with plot_out:
            plot_out.clear_output()  # Clear previous output
            # Filtering options
            filter = {}
            for filter_button in filter_buttons[table_select_button.value]:
                filter[filter_button.description] = list(filter_button.value)
            nb_series = len(series_select_button.value)
            series_order_selection=[series_order_button3.value, series_order_button2.value, series_order_button1.value][-nb_series:]
            # Name of the file
            if namefile_button.value == '':
                namefile = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
            else : 
                namefile = namefile_button.value
            
            if None in series_order_selection:
                fig = plot_bar_chart(MainResults_instance.df, filter, series_select_button.value, categories_select_button.value,
                                    (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                    (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                     xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                    (yaxis_title_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                    True, namefile)
            else:
                fig = plot_bar_chart(MainResults_instance.df, filter, series_order_selection, categories_select_button.value,
                                    (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value),
                                    (xaxis1_button.value,xaxis1_size_button.value,xaxis1_bold_button.value,xaxis2_button.value,xaxis2_position_button.value,xaxis2_size_button.value,
                                     xaxis2_bold_button.value,xaxis2_sep_button.value,xaxis3_button.value,xaxis3_position_button.value,xaxis3_size_button.value,xaxis3_bold_button.value,xaxis3_sep_button.value),
                                    (yaxis_title_button.value, yaxis_max_button.value),(legend_button.value, legend_location_button.value, legend_xpos_button.value, legend_ypos_button.value, legend_col_button.value),
                                    True, namefile)
            plt.show(fig)
            
            
    # Dynamic behaviour of the buttons
    table_select_function(table_select_button.value)
    table_select_button.observe(lambda change: table_select_function(change['new']), names='value')
    table_select_button.observe(lambda change: df_update(change['new']), names='value')
    series_select_button.observe(lambda change: series_order_function(change['new']), names='value')
    series_select_button.observe(lambda change: xaxis_option_function(change['new']), names='value')

    # Activate the plotting of the bar chart on the click
    plot_button.on_click(wrap_plot_bar_chart)
    print_button.on_click(wrap_print_bar_chart)
    
    # Display the UI and output areas
    display(pivot_selection_layout, pivot_selection_out)
    display(filter_stack, filter_out)
    display(plot_options_layout, plot_options_out)
    display(plot_layout, plot_print_out)
    display(plot_out)
