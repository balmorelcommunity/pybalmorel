#%% ------------------------------- ###
###        0. Script Settings       ###
### ------------------------------- ###

from typing import Union
import gams
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from ..functions import symbol_to_df
from ..formatting import balmorel_colours, mainresults_symbol_columns
import ipywidgets as widgets
from ipywidgets import interact, interactive
import os
# import ast
import copy

#%% ------------------------------- ###
###        1. MainResults class
### ------------------------------- ###

class MainResults:
    def __init__(self, SC: Union[str, list], path: str = '.'):
        """
        Initialize the MainResults class by charging a gdx result file

        Args:
            SC (str): Name of the gdx result file
            path (str): Path to the gdx result file
        """

        ws = gams.GamsWorkspace()

        if type(SC) == str:
            self.db = ws.add_database_from_gdx(os.path.join(os.path.abspath(path), SC))
        elif type(SC) == list:
            self.db = pd.DataFrame()
            for sc in SC:
                temp =  ws.add_database_from_gdx(os.path.join(os.path.abspath(path), sc))
                temp['SC'] = sc
                self.db = pd.concat((self.db, temp), ignore_index=True)

        # Think about importing multiple scenarios
        # self:db['SC'] = SC
        # self:db[colcustom] = something
        
        """ We could add this to the formatting file"""
        self.table_select = mainresults_symbol_columns

    def plot_bar_chart(self, df: pd.core.frame.DataFrame, filter: dict, table: str, series: Union[str, list], categories: Union[str, list],
                       title: tuple, size: tuple):
        """
        Plotting function for the bar chart

        Args:
            df (DataFrame): Dataframe with the result
            filter (dict): Dictionnary with the filters to apply
            table (str): Table selected in the result file
            series (Union[str, list]): Columns used as series
            categories (Union[str, list]): Columns used as categories
            title (tuple): Plot title and size
            size (tuple): Size of the plot
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
            
            # Object oriented plotting
            fig, ax = plt.subplots(figsize=size)
            
            # Colors 
            try:
                temp.plot(ax=ax, kind='bar', stacked=True, legend=False, color=balmorel_colours)
            except KeyError:
                temp.plot(ax=ax, kind='bar', stacked=True, legend=False)

            ax.legend(bbox_to_anchor=(0.9, 0.8), loc=2)
            
            # Fixing the labels on x-axis - this deepcopy copies the figure itself
            # list_xticks = copy.deepcopy(ax.get_xticks())
            # list_xticks_label = copy.deepcopy(ax.get_xticklabels())
            # if len(series) == 1 :
            #     ax.set_xticklabels([ticks_label.get_text() for ticks_label in list_xticks_label])
                
            # Not working for now
            # elif len(series) == 2 :
            #     # Set the lower level x-ticks
            #     ax.set_xticklabels([ast.literal_eval(ticks_label.get_text().replace('(',"('").replace(',',"','").replace(')',"')"))[-1] for ticks_label in list_xticks_label])
            #     # Separation bars for different level of x-ticks
            #     series_up = ast.literal_eval(list_xticks_label[0].get_text().replace('(',"('").replace(',',"','").replace(')',"')"))[0]
            #     for i in range(1,len(list_xticks_label)):
            #         if ast.literal_eval(list_xticks_label[i].get_text().replace('(',"('").replace(',',"','").replace(')',"')"))[0] != series_up:
            #             fig.add_artist(Rectangle((i-0.5, 0), 0.005, -0.2, transform=ax.get_xaxis_transform(), color='black', linewidth=2))
            #             # ax.vlines(i-0.5, -20, 0, color='black',linewidth=2)
            #             series_up = ast.literal_eval(list_xticks_label[i].get_text().replace('(',"('").replace(',',"','").replace(')',"')"))[0]
            
            
            ax.set_ylabel(f'Value ({unit})')
            ax.set_xlabel('')
            
            ax.set_title(title[0], fontsize=title[1])
            
            return fig
            
        

    def bar_chart(self):
        """
        GUI for bar chart plotting
        """

        """ Buttons definition """
        # Initial selection for plotting
        table_select_button = widgets.Dropdown(options= list(self.table_select.keys()), value=None, description='Table:', disabled=False)
        series_select_button = widgets.SelectMultiple(options=[], value=[], description='Series:', disabled=False)
        categories_select_button = widgets.SelectMultiple(options=[], value=[], description='Categories:', disabled=False)
        # Order options for series and categories
        series_order_button1 = widgets.Dropdown(options=[], value=None, description='First:', disabled=False)
        series_order_button2 = widgets.Dropdown(options=[], value=None, description='Second:', disabled=False)
        series_order_button3 = widgets.Dropdown(options=[], value=None, description='Third:', disabled=False)
        # Filter buttons
        Y_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Year:', disabled=False)
        C_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Country:', disabled=False)
        R_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Region:', disabled=False)
        A_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Area:', disabled=False)
        G_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Generation:', disabled=False)
        F_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Fuel:', disabled=False)
        Com_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Commodity:', disabled=False)
        Tech_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Technology:', disabled=False)
        Cat_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Category:', disabled=False)
        S_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Season:', disabled=False)
        T_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='Time:', disabled=False)
        From_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='From:', disabled=False)
        To_filter_button = widgets.SelectMultiple(options=['None'], value=['None'], description='To:', disabled=False)
        # Dictionnary useful for the filtering (It would be difficult to put it in formatting I think)
        filter_options = {'F_CONS_YCRA': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, G_filter_button, F_filter_button, Tech_filter_button],
                          'F_CONS_YCRAST': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, G_filter_button, F_filter_button, S_filter_button, T_filter_button, Tech_filter_button],
                          'G_CAP_YCRAF': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, G_filter_button, F_filter_button, Com_filter_button, Tech_filter_button, Cat_filter_button],
                          'G_STO_YCRAF': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, G_filter_button, F_filter_button, Com_filter_button, Tech_filter_button, Cat_filter_button],
                          'H2_DEMAND_YCR': [Y_filter_button, C_filter_button, R_filter_button, Cat_filter_button],
                          'H2_DEMAND_YCRST': [Y_filter_button, C_filter_button, R_filter_button, S_filter_button, T_filter_button, Cat_filter_button],
                          'H2_PRICE_YCR': [Y_filter_button, C_filter_button, R_filter_button, Cat_filter_button],
                          'H2_DEMAND_YCRST': [Y_filter_button, C_filter_button, R_filter_button, S_filter_button, T_filter_button, Cat_filter_button],
                          'H_BALANCE_YCRAST': [Y_filter_button, C_filter_button, R_filter_button, Tech_filter_button, S_filter_button, T_filter_button],
                          'H_DEMAND_YCRA': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, Cat_filter_button],
                          'H_DEMAND_YCRAST': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, S_filter_button, T_filter_button, Cat_filter_button],
                          'H_PRICE_YCRA': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, Cat_filter_button],
                          'H_PRICE_YCRAST': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, S_filter_button, T_filter_button],
                          'OBJ_YCR': [Y_filter_button, C_filter_button, R_filter_button, Cat_filter_button],
                          'PRO_YCRAGF': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, G_filter_button, F_filter_button, Com_filter_button, Tech_filter_button],
                          'PRO_YCRAGFST': [Y_filter_button, C_filter_button, R_filter_button, A_filter_button, G_filter_button, F_filter_button, S_filter_button, T_filter_button, Com_filter_button, Tech_filter_button],
                          'X_CAP_YCR': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button, Cat_filter_button],
                          'X_FLOW_YCR': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button],
                          'X_FLOW_YCRST': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button, S_filter_button, T_filter_button],
                          'XH2_CAP_YCR': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button, Cat_filter_button],
                          'XH2_FLOW_YCR': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button],
                          'XH2_FLOW_YCRST': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button, S_filter_button, T_filter_button],
                          'XH_CAP_YCA': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button, Cat_filter_button],
                          'XH_FLOW_YCA': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button],
                          'XH_FLOW_YCAST': [Y_filter_button, C_filter_button, From_filter_button, To_filter_button, S_filter_button, T_filter_button]}
        button_to_name = {Y_filter_button:'Year', C_filter_button:'Country', R_filter_button:'Region', A_filter_button:'Area',G_filter_button:'Generation',
                          F_filter_button:'Fuel', Com_filter_button:'Commodity', Tech_filter_button:'Technology', Cat_filter_button:'Category',
                          S_filter_button: 'Season', T_filter_button: 'Time', From_filter_button:'From', To_filter_button: 'To'}
        # For the plotting layout
        plot_title_button = widgets.Text(description='Title:', disabled=False)
        plot_sizetitle_button = widgets.FloatSlider(value=12, min=8, max=20, step=0.1, description='Size:', disabled=False, 
                                              orientation='horizontal', readout=True, readout_format='.1f')
        plot_sizex_button = widgets.BoundedFloatText(value=12, min=5, max=20, step=0.1, description='Size x:', disabled=False)
        plot_sizey_button = widgets.BoundedFloatText(value=8, min=5, max=20, step=0.1, description='Size y:', disabled=False)
        # Plotting button
        plot_button = widgets.Button( description='Plot', disabled=False, button_style='', tooltip='Click to plot', icon='check')
        
        # For the pivot table order selection
        series_order_stack = widgets.Stack([widgets.VBox([series_order_button1]),widgets.VBox([series_order_button1,series_order_button2]),
                                            widgets.VBox([series_order_button1,series_order_button2,series_order_button3])])    

        # For the pivot table options selection
        pivot_selection_layout = widgets.GridBox([table_select_button, widgets.VBox([series_select_button,series_order_stack]) , categories_select_button], layout=widgets.Layout(width='100%', grid_template_columns='repeat(3, 1fr)', grid_gap='2px'))
        pivot_selection_out = widgets.Output()
        
        # For the filtering of the table
        filter_layout = [widgets.GridBox(filter_options[key], layout=widgets.Layout(width='100%', grid_template_columns='repeat(3, 1fr)', grid_gap='2px')) for key in list(self.table_select.keys())]
        filter_stack = widgets.Stack(filter_layout)
        widgets.jslink((table_select_button,'index'),(filter_stack,'selected_index'))
        filter_out = widgets.Output()
        
        # For the plotting 
        plot_options_layout = widgets.VBox([widgets.HBox([plot_title_button, plot_sizetitle_button]),widgets.HBox([plot_sizex_button, plot_sizey_button])])
        plot_options_out = widgets.Output()
        plot_out = widgets.Output()

        # Function to update dropdowns based on table selection
        def table_select_function(table_name):
            with pivot_selection_out:
                pivot_selection_out.clear_output()  # Clear previous output
                if table_name :
                    # Update dropdown options based on selected table
                    series_select_button.options = self.table_select[table_name]
                    categories_select_button.options = self.table_select[table_name]
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
                
        def df_update(table_name):
            if table_name :
                global df
                df = symbol_to_df(self.db, table_name, self.table_select[table_name]+['Unit', 'Value'])
                with filter_out:
                    filter_out.clear_output() # Clear previous output
                    for filter_button in filter_options[table_name]:
                        filter_button.options = list(sorted(df[button_to_name[filter_button]].unique()))
                        filter_button.value = list(sorted(df[button_to_name[filter_button]].unique()))

        def wrap_plot_bar_chart(click):
            with plot_out:
                plot_out.clear_output()  # Clear previous output
                # Filtering options
                filter = {}
                for filter_button in filter_options[table_select_button.value] :
                    filter[button_to_name[filter_button]] = list(filter_button.value)
                nb_series = len(series_select_button.value)
                series_order_selection=[series_order_button1.value, series_order_button2.value, series_order_button3.value][:nb_series]
                if None in series_order_selection:
                    fig = self.plot_bar_chart(df, filter, table_select_button.value, series_select_button.value, categories_select_button.value,
                                        (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value))
                else:
                    fig = self.plot_bar_chart(df, filter, table_select_button.value, series_order_selection, categories_select_button.value,
                                        (plot_title_button.value,plot_sizetitle_button.value), (plot_sizex_button.value,plot_sizey_button.value))

                plt.show(fig)
                
        # Dynamic behaviour of the buttons
        table_select_function(table_select_button.value)
        table_select_button.observe(lambda change: table_select_function(change['new']), names='value')
        table_select_button.observe(lambda change: df_update(change['new']), names='value')
        series_select_button.observe(lambda change: series_order_function(change['new']), names='value')

        # Activate the plotting of the bar chart on the click
        plot_button.on_click(wrap_plot_bar_chart)
        
        # Display the UI and output areas
        display(pivot_selection_layout, pivot_selection_out)
        display(filter_stack, filter_out)
        display(plot_options_layout, plot_options_out)
        display(plot_button)
        display(plot_out)
	


    def get_result(self, symbol: str, cols: str = 'None'):
        return symbol_to_df(self.db, symbol, cols)
	
        
        
if __name__ == "__main__":
    mr = MainResults('MainResults_EXP_6_S_TH_FR.gdx', os.path.dirname(os.path.abspath(__file__)))
    mr.bar_chart()
