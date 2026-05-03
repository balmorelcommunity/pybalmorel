"""
TITLE

Description


@author: Polyneikis Kanellas, Development Engineer DTU Wind
"""


from typing import Union
import pandas as pd
import os

#from pybalmorel.classes import IncFile


_INC_PREFIX_MAP: dict[str, str] = {
    "AAA_renewable":        "SET AAA(CCCRRRAAA)  'Areas with renewables'  \n ",
    "CCCRRRAAA_renewable":  "SET CCCRRRAAA  'Areas with renewables' \n",
    "GGG_renewable":        "SET GGG  'Renewable technologies' \n",
    "G_renewable":          "SET G(GGG)  'Renewable technologies' \n",
    "RRRAAA_renewable":     "SET RRRAAA(RRR,AAA)  'Areas in regions'  \n",
    "INVDATASET_renewables": "SET INVDATASET    \n",
    "INVDATA_renewable":    "",
    "ALLOWEDINV":           "SET ALLOWEDINV(AAA,GGG) ",
    "ANNUITYCG_renewables": "PARAMETER ANNUITYCG(CCC,GGG) ",
}

class IncFile_temp:
    """A useful class for creating .inc-files for GAMS models
    Args:
    prefix (str): The first part of the .inc file.
    body (str): The main part of the .inc file.
    suffix (str): The last part of the .inc file.
    name (str): The name of the .inc file.
    path (str): The path to save the file, defaults to 'Balmorel/base/data'.
    """
    def __init__(self, prefix: str = '', body: str = '', 
                 suffix: str = '', name: str = 'name', 
                 path: str = 'Balmorel/base/data/'):
        self.prefix = prefix
        self.body = body
        self.suffix = suffix
        self.name = name
        self.path = path

    def body_concat(self, df: pd.DataFrame) -> None:
        """Concatenate a body temporarily being a dataframe to another dataframe
        """
        self.body = pd.concat((self.body, df)) # perhaps make a IncFile.body.concat function.. 

    def body_prepare(self, index: list, columns: list,
                    values: str = 'Value',
                    aggfunc: str ='sum',
                    fill_value: Union[str, int] = '') -> None:
    
        # Pivot
        self.body = self.body.pivot_table(index=index, columns=columns, 
                            values=values, aggfunc=aggfunc,
                            fill_value=fill_value)
        
        # Check if there are multiple levels in index and 
        # concatenate with " . "
        if hasattr(self.body.index, 'levels'):
            new_ind = pd.Series(self.body.index.get_level_values(0))
            for level in range(1, len(self.body.index.levels)):
                new_ind += ' . ' + self.body.index.get_level_values(level) 

            self.body.index = new_ind
        
        # Check if there are multiple levels in columns and 
        # concatenate with " . "
        if hasattr(self.body.columns, 'levels'):
            new_ind = pd.Series(self.body.columns.get_level_values(0))
            for level in range(1, len(self.body.columns.levels)):
                new_ind += ' . ' + self.body.columns.get_level_values(level) 

            self.body.columns = new_ind
            
        # Delete names
        self.body.columns.name = ''
        self.body.index.name = ''


    def save(self) -> None:
        if self.name[-4:] != '.inc':
            self.name += '.inc'  
       
        with open(os.path.join(self.path, self.name), 'w') as f:
            f.write(self.prefix)
            if isinstance(self.body, str):
                f.write(self.body)
            elif isinstance(self.body, pd.DataFrame):
                f.write(self.body.to_string())
            else:
                print('Wrong format of %s.body!'%self.name)
                print('No body written')
            f.write(self.suffix)





def create_SSS_TTT_AAA_inc(df: pd.DataFrame, name: str, output_folder: str) -> None:

    if name=="WND_VAR_T":
        prefix = "TABLE   WND_VAR_T1(SSS,TTT,AAA)  'Variation of the wind generation'\n"
        suffix = "\n;\nWND_VAR_T(AAA,SSS,TTT) = WND_VAR_T1(SSS,TTT,AAA);  \nWND_VAR_T(IA,SSS,TTT)$((NOT SUM((S,T), WND_VAR_T(IA,S,T))) AND WNDFLH(IA)) = WND_VAR_T('DK2_NoDH',SSS,TTT) ; \nWND_VAR_T1(SSS,TTT,AAA)=0;"
    elif name=="SOLE_VAR_T":
        prefix = "TABLE SOLE_VAR_T1(SSS,TTT,AAA)  'Variation of the solar generation'\n"
        suffix = "\n;\nSOLE_VAR_T(IA,SSS,TTT)= SOLE_VAR_T1(SSS,TTT,IA); \n SOLE_VAR_T1(SSS,TTT,AAA)=0;     "
    
    
    ts=IncFile_temp(name= name,
        prefix=prefix,
        suffix=suffix,
        path=output_folder)
    
    ts.body = pd.DataFrame(index=list(df.index) , columns=list(df.columns),
                       data=df.values)
    ts.save()

    
    #df.to_csv(output_folder + "/" + name + ".csv") #might be removed in the future since it is not necessary


def create_AAA_inc(df: pd.DataFrame, name: str, output_folder: str) -> None:

    if name=="WNDFLH":
        prefix = "PARAMETER WNDFLH(AAA)  'Full load hours for wind power (hours)'  \n / \n "
        suffix = "\n/;\n"
    elif name=="SOLEFLH":
        prefix = "PARAMETER SOLEFLH(AAA)  'Full load hours for solar power' \n / \n "
        suffix = "\n/;\n     "
    
    
    ts=IncFile_temp(name= name,
        prefix=prefix,
        suffix=suffix,
        path=output_folder)
    
    ts.body = pd.DataFrame(index=list(df.index),columns=[""],data=df.values)

    ts.save()





def create_GGG_GDATASET_inc(df: pd.DataFrame, name: str, output_folder: str) -> None:

    if name=="GDATA_renewable":
        prefix = "$onMulti \n TABLE GDATA(GGG,GDATASET)  'Technologies characteristics'  \n"
        suffix = "\n;\n"

    
    
    ts=IncFile_temp(name= name,
        prefix=prefix,
        suffix=suffix,
        path=output_folder)
    
    #ts.body = pd.DataFrame(index=list(df.index),columns=[""],data=df.values)
    ts.body=df

    ts.save()






def append_split_wind_solar_sets(the_file, df: pd.DataFrame, name: str) -> None:
    if name=="AAA_renewable":
        prefix_wind = "SET IA_wind(AAA)  'Areas with renewables'  \n "
        prefix_solar = "SET IA_solar(AAA)  'Areas with renewables'  \n "
    elif name=="G_renewable":
        prefix_wind = "SET IG_wind(GGG)  'Renewable technologies'  \n "
        prefix_solar = "SET IG_solar(GGG)  'Renewable technologies'  \n "
    
    df_wind=df[df.iloc[:, 0].str.contains("_OFF", na=False) | df.iloc[:, 0].str.contains("_ONS", na=False) ]
    df_solar= df[df.iloc[:,0].str.contains("PV", na=False)]

    the_file.write("\n \n \n \n \n \n \n")
    the_file.write(prefix_wind )
    the_file.write("\n")
    the_file.write("/ ")
    the_file.write("\n")
    for item in df_wind[name]:
        the_file.write(item +"\n" )
    the_file.write("/ ;")
    
    the_file.write("\n \n \n \n \n \n \n")
    the_file.write(prefix_solar )
    the_file.write("\n")
    the_file.write("/ ")
    the_file.write("\n")
    for item in df_solar[name]:
        the_file.write(item +"\n" )
    the_file.write("/ ;")




def build_inc_file_list_type(
    df: pd.DataFrame,
    name: str,
    output_folder: str,
    equations: bool = False,
    filename: str | None = None,
) -> None:
    """Write Balmorel set/parameter assignment lines to a .inc file.

    Args:
        df: DataFrame whose column ``name`` contains the assignment lines to write.
        name: Column key used to look up lines in ``df`` and to resolve the GAMS
            prefix/suffix for known renewable-set names.
        output_folder: Directory where the ``.inc`` file is written.
        equations: When *True*, skip the ``$onMulti`` / ``/ … /;`` envelope and
            write raw assignment lines only (used for INVDATA and ANNUITYCG blocks).
        filename: Output file stem (without ``.inc``). Defaults to ``name`` when
            not provided, allowing callers to write a different file name while
            still keying into ``df`` by ``name``.
    """
    output_filename = filename if filename is not None else name
    prefix = _INC_PREFIX_MAP.get(name)
    write_envelope = (prefix is not None) and (not equations)

    with open(os.path.join(output_folder, f"{output_filename}.inc"), "w") as the_file:
        the_file.write("*File created from weatheryear module\n")
        if write_envelope:
            the_file.write("$onMulti\n")
            the_file.write(prefix)
            the_file.write("\n/ \n")
        for item in df[name]:
            the_file.write(item + "\n")
        if write_envelope:
            the_file.write("/ ;")
        if name in ("AAA_renewable", "G_renewable"):
            append_split_wind_solar_sets(the_file, df, name)
            #elif name=="ALLOWEDINV":
            #    append_ALLOWEDINV_eqs(the_file,df)




def create_GKFX_inc(GKFX: pd.DataFrame, name: str, output_folder: str) -> None:
    if name=="GKFX_renewable":
            prefix = "$onMulti \n TABLE GKFX1(AAA,GGG,YYY)  'Technologies characteristics'  \n"
            suffix = "\n;\n"
    
    ts=IncFile_temp(name= name,
            prefix=prefix,
            suffix=suffix,
            path=output_folder)
    
    ts.body=GKFX
    
    ts.save()
    
def create_Table_inc(df: pd.DataFrame, name: str, output_folder: str) -> None:
    if name=="SUBTECHGROUPKPOT":
        prefix = "$onMulti \nTABLE SUBTECHGROUPKPOT(CCCRRRAAA,TECH_GROUP,SUBTECH_GROUP) 'SubTechnology group capacity restriction by geography (MW)' \n"
        suffix = "\n;\n"
    elif name=="DISCOST_H_renewable":
        prefix = "$onMulti \n PARAMETER DISCOST_H(AAA)  'Cost of heat distribution (Money/MWh)'   \n/\n"
        suffix = "\n/;"

    ts=IncFile_temp(name= name,
            prefix=prefix,
            suffix=suffix,
            path=output_folder)
    
    ts.body=df
    
    ts.save()
    