'''
This script reads csv file and creates inc file.
'''


import pandas as pd
import yaml

from .functions_demand_to_btc import *





def create_demand_inc(config_fn,year,output_folder):
    
    
    with open(config_fn) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    spaceHeat_to_hotWater_ratio = config['spaceHeat_to_hotWater_ratio']
    ann_corr_fac_ref_year=int(config['ann_corr_fac_ref_year'])
    csv_folder = config['demand_model_results']

    # read full hindcast csv once before looping
    df_classic = pd.read_csv(csv_folder+'/classic_demand.csv',index_col=0,parse_dates=True)
    df_space_heat_profile = pd.read_csv(csv_folder+'/heat_profile_indiv_user.csv',index_col=0,parse_dates=True)
    df_resh_heat_profile = pd.read_csv(csv_folder+'/heat_profile_resh.csv',index_col=0,parse_dates=True)
    df_resh_hotWater_profile = pd.read_csv(csv_folder+'/hotWater_profile_resh.csv',index_col=0)
    df_heat_corr_factors_indiv_user = pd.read_csv(csv_folder+'/heat_yearly_corr_factors_indiv_user.csv',index_col=0)
    df_heat_corr_factors_resh = pd.read_csv(csv_folder+'/heat_yearly_corr_factors_resh.csv',index_col=0)


    check_if_dir_exists(output_folder+'/'+str(year))
    check_if_dir_exists(output_folder+'/'+str(year)+'/to_balmorel/DA/raw')
    check_if_dir_exists(output_folder+'/'+str(year)+'/to_balmorel/DA/scaled')
    check_if_dir_exists(output_folder+'/'+str(year)+'/to_balmorel/CapDev')

    #############################################################################################
    # ELECTRICITY
    #############################################################################################

    # read hindcast output
    df_full, df_cut, df_scaled = treat_timeseries(df_classic,year,year,fix_monday=True)

    check_if_dir_exists(output_folder+'/'+str(year)+'/classic_elec')
    check_if_dir_exists(output_folder+'/'+str(year)+'/classic_elec/raw')
    check_if_dir_exists(output_folder+'/'+str(year)+'/classic_elec/scaled')

    df_cut.to_csv(output_folder+'/'+str(year)+'/classic_elec/raw/classic_elec.csv')
    df_scaled.to_csv(output_folder+'/'+str(year)+'/classic_elec/scaled/classic_elec.csv')


    #-------------------------------------------------------------
    # CREATE INC FILE
    #-------------------------------------------------------------

    time_df = create_time_column()
    df_cut.index = time_df['DA_time']
    df_scaled.index = time_df['DA_time']


    #-------------------------------------------------------------
    # RESE
    #-------------------------------------------------------------

    # create DA raw
    df = convert_to_list_df_new(df_cut,'DE_VAR_T','RESE')
    create_list_inc(df,'DE_VAR_T','DE_VAR_T_RESE',output_folder+'/'+str(year)+'/to_balmorel/DA/raw')

    # create DA scaled
    df = convert_to_list_df_new(df_scaled,'DE_VAR_T','RESE')
    create_list_inc(df,'DE_VAR_T','DE_VAR_T_RESE',output_folder+'/'+str(year)+'/to_balmorel/DA/scaled')

    # create CapDev
    CapDev_timesteps=get_CapDev_timesteps(config)
    df_t_cut=time_df[time_df.CapDev_time.isin(CapDev_timesteps)]
    filtered_df1 = df_scaled[df_scaled.index.isin(df_t_cut.DA_time)]
    df_scaled_capdev=scale_data_to_same_mean_with_full_time_series(df_scaled,filtered_df1)
    df_scaled_capdev.index=df_t_cut.CapDev_time

    df = convert_to_list_df_new(df_scaled_capdev,'DE_VAR_T','RESE')
    create_list_inc(df,'DE_VAR_T','DE_VAR_T_RESE',output_folder+'/'+str(year)+'/to_balmorel/CapDev')




    #-------------------------------------------------------------
    # OTHER
    #-------------------------------------------------------------

    # create DA
    df = convert_to_list_df_new(df_cut,'DE_VAR_T','OTHER')
    create_list_inc(df,'DE_VAR_T','DE_VAR_T_OTHER',output_folder+'/'+str(year)+'/to_balmorel/DA/raw')
    df = convert_to_list_df_new(df_scaled,'DE_VAR_T','OTHER')
    create_list_inc(df,'DE_VAR_T','DE_VAR_T_OTHER',output_folder+'/'+str(year)+'/to_balmorel/DA/scaled')

    # create CapDev
    CapDev_timesteps=get_CapDev_timesteps(config)
    df_t_cut=time_df[time_df.CapDev_time.isin(CapDev_timesteps)]
    filtered_df1 = df_scaled[df_scaled.index.isin(df_t_cut.DA_time)]
    df_scaled_capdev=scale_data_to_same_mean_with_full_time_series(df_scaled,filtered_df1)
    df_scaled_capdev.index=df_t_cut.CapDev_time

    df = convert_to_list_df_new(df_scaled_capdev,'DE_VAR_T','OTHER')
    create_list_inc(df,'DE_VAR_T','DE_VAR_T_OTHER',output_folder+'/'+str(year)+'/to_balmorel/CapDev')















    #############################################################################################
    # HEAT : INDIVIDUAL USER
    #############################################################################################

    # read hindcast output
    df_full, df_cut, df_scaled = treat_timeseries(df_space_heat_profile,year,year,fix_monday=True)

    check_if_dir_exists(output_folder+'/'+str(year)+'/heat_profile_indiv_user')
    check_if_dir_exists(output_folder+'/'+str(year)+'/heat_profile_indiv_user/raw')
    check_if_dir_exists(output_folder+'/'+str(year)+'/heat_profile_indiv_user/scaled')

    df_cut.to_csv(output_folder+'/'+str(year)+'/heat_profile_indiv_user/raw/heat_profile_indiv_user.csv')
    df_scaled.to_csv(output_folder+'/'+str(year)+'/heat_profile_indiv_user/scaled/heat_profile_indiv_user.csv')



    #-------------------------------------------------------------
    # CREATE INC FILE
    #-------------------------------------------------------------

    time_df = create_time_column()
    df_cut.index = time_df['DA_time']
    df_scaled.index = time_df['DA_time']


    #-------------------------------------------------------------
    # RESIDENTIAL 
    #-------------------------------------------------------------

    # create DA raw
    df = convert_to_list_df_new(df_cut,'DH_VAR_T','RESIDENTIAL')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_RESIDENTIAL',output_folder+'/'+str(year)+'/to_balmorel/DA/raw')

    # create DA scaled
    df = convert_to_list_df_new(df_scaled,'DH_VAR_T','RESIDENTIAL')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_RESIDENTIAL',output_folder+'/'+str(year)+'/to_balmorel/DA/scaled')

    # create CapDev
    CapDev_timesteps=get_CapDev_timesteps(config)
    df_t_cut=time_df[time_df.CapDev_time.isin(CapDev_timesteps)]
    filtered_df1 = df_scaled[df_scaled.index.isin(df_t_cut.DA_time)]
    df_scaled_capdev=scale_data_to_same_mean_with_full_time_series(df_scaled,filtered_df1)
    df_scaled_capdev.index=df_t_cut.CapDev_time

    df = convert_to_list_df_new(df_scaled_capdev,'DH_VAR_T','RESIDENTIAL')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_RESIDENTIAL',output_folder+'/'+str(year)+'/to_balmorel/CapDev')


    #-------------------------------------------------------------
    # TERTIARY
    #-------------------------------------------------------------

    # create DA raw
    df = convert_to_list_df_new(df_cut,'DH_VAR_T','TERTIARY')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_TERTIARY',output_folder+'/'+str(year)+'/to_balmorel/DA/raw')

    # create DA scaled
    df = convert_to_list_df_new(df_scaled,'DH_VAR_T','TERTIARY')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_TERTIARY',output_folder+'/'+str(year)+'/to_balmorel/DA/scaled')

    # create CapDev
    CapDev_timesteps=get_CapDev_timesteps(config)
    df_t_cut=time_df[time_df.CapDev_time.isin(CapDev_timesteps)]
    filtered_df1 = df_scaled[df_scaled.index.isin(df_t_cut.DA_time)]
    df_scaled_capdev=scale_data_to_same_mean_with_full_time_series(df_scaled,filtered_df1)
    df_scaled_capdev.index=df_t_cut.CapDev_time

    df = convert_to_list_df_new(df_scaled_capdev,'DH_VAR_T','TERTIARY')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_TERTIARY',output_folder+'/'+str(year)+'/to_balmorel/CapDev')




    #############################################################################################
    # HEAT : RESH  
    #############################################################################################


    # read hindcast output
    df_full, df_cut, df_scaled = treat_timeseries(df_resh_heat_profile,year,year,fix_monday=True)

    check_if_dir_exists(output_folder+'/'+str(year)+'/heat_profile_resh')
    check_if_dir_exists(output_folder+'/'+str(year)+'/heat_profile_resh/raw')
    check_if_dir_exists(output_folder+'/'+str(year)+'/heat_profile_resh/scaled')


    #-------------------------------------------------------------
    # CREATE INC FILE
    #-------------------------------------------------------------

    time_df = create_time_column()
    df_cut.index = time_df['DA_time']
    df_scaled.index = time_df['DA_time']

    df_resh_hotWater_profile.index = time_df['DA_time']
    df_cut = df_cut*spaceHeat_to_hotWater_ratio + df_resh_hotWater_profile*(1-spaceHeat_to_hotWater_ratio)
    df_scaled = df_scaled*spaceHeat_to_hotWater_ratio + df_resh_hotWater_profile*(1-spaceHeat_to_hotWater_ratio)
    
    #-------------------------------------------------------------
    # RESH
    #-------------------------------------------------------------

    # create DA raw
    df = convert_to_list_df_new(df_cut,'DH_VAR_T','RESH')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_RESH',output_folder+'/'+str(year)+'/to_balmorel/DA/raw')

    # create DA scaled
    df = convert_to_list_df_new(df_scaled,'DH_VAR_T','RESH')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_RESH',output_folder+'/'+str(year)+'/to_balmorel/DA/scaled')

    # create CapDev
    CapDev_timesteps=get_CapDev_timesteps(config)
    df_t_cut=time_df[time_df.CapDev_time.isin(CapDev_timesteps)]
    filtered_df1 = df_scaled[df_scaled.index.isin(df_t_cut.DA_time)]
    df_scaled_capdev=scale_data_to_same_mean_with_full_time_series(df_scaled,filtered_df1)
    df_scaled_capdev.index=df_t_cut.CapDev_time

    df = convert_to_list_df_new(df_scaled_capdev,'DH_VAR_T','RESH')
    create_list_inc(df,'DH_VAR_T','DH_VAR_T_RESH',output_folder+'/'+str(year)+'/to_balmorel/CapDev')












    #############################################################################################
    # HEAT : DH correction factor : INDIVIDUAL USER
    #############################################################################################

    # PARAMETER DH(YYY,AAA,DHUSER)
    # DH(YYY,'DK1_Large','RESH') = DH(YYY,'DK1_Large','RESH')*1.2 , where 1.2 is the correction factor 

    df_heat_corr_factor_year = df_heat_corr_factors_indiv_user.loc[year]/df_heat_corr_factors_indiv_user.loc[ann_corr_fac_ref_year]
    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year,'DH','RESIDENTIAL')
    create_list_inc(df,'DH','DH_RESIDENTIAL',output_folder+'/'+str(year)+'/to_balmorel/')

    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year,'DH','TERTIARY')
    create_list_inc(df,'DH','DH_TERTIARY',output_folder+'/'+str(year)+'/to_balmorel/')





    #############################################################################################
    # HEAT : DH correction factor : RESH
    #############################################################################################

    # PARAMETER DH(YYY,AAA,DHUSER)
    # DH(YYY,'DK1_Large','RESH') = DH(YYY,'DK1_Large','RESH')*1.2 , where 1.2 is the correction factor 
    df_heat_corr_factor_year = df_heat_corr_factors_resh.loc[year]/df_heat_corr_factors_resh.loc[ann_corr_fac_ref_year]

    df = convert_to_list_df_annual_correction(df_heat_corr_factor_year,'DH','RESH')
    create_list_inc(df,'DH','DH_RESH',output_folder+'/'+str(year)+'/to_balmorel/')










































