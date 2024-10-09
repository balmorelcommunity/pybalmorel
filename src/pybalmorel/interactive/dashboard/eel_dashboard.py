import eel
import ast
import pkg_resources
from typing import Tuple
import os

# 1.0 Other functions
def get_wkdir():
  return os.path.abspath('.')

# 1.1 Create .inc Files
def create_incfile(unique_processing):
  """The general wrapper for creating and saving .inc files, 
  because the creating of the IncFile class and saving it is the same everytime.
  The unique processing of the .body content differs, however. 

  Args:
    unique_processing (func): The unique processing per case
    **incfile_kwargs: Keyword arguments to pass to IncFile
  """
  def wrapper(**kwargs):
    from ... import IncFile
    inc_file = IncFile(name=kwargs['name'], prefix=kwargs['prefix'],
                       suffix=kwargs['suffix'], path=kwargs['path'])
    unique_processing(inc_file, kwargs['geo_nodes'])
    inc_file.save()
  return wrapper

## 1.1.1 CCC, RRR or AAA
@create_incfile
def create_sets(inc_file, geo_nodes_layer2: dict):
  inc_file.body += '\n'.join(list(geo_nodes_layer2.keys())) 

## 1.1.2 CCCRRRAAA
@create_incfile
def create_CCCRRRAAA(inc_file, geo_nodes: dict):
  for key in geo_nodes.keys():
    inc_file.body += '\n* %s:\n' % key.capitalize()
    inc_file.body += '\n'.join(geo_nodes[key].keys())

## 1.1.3 CCCRRR or RRRAAA
@create_incfile
def create_setconnection(inc_file, geo_nodes_layer1: dict):
  for node in geo_nodes_layer1.keys():
    if len(geo_nodes_layer1[node]) != 0:
      inc_file.body += f'\n{node} . '
      inc_file.body += f'\n{node} . '.join(geo_nodes_layer1[node]) 


def create_incfiles(output: Tuple[str, dict], 
                    path: str,
                    set_prefix: str = ''):
    if type(output) == str:
      geo_nodes = ast.literal_eval(output) # Convert output to dict

    prefix = """SET CCC(CCCRRRAAA)  'All countries'
/\n"""
    create_sets(geo_nodes=geo_nodes['countries'], name=set_prefix+'CCC', prefix=prefix, suffix="\n/;", path=path)
    
    prefix = """SET RRR(CCCRRRAAA)  'All regions'
/\n"""
    create_sets(geo_nodes=geo_nodes['regions'], name=set_prefix+'RRR', prefix=prefix, suffix="\n/;", path=path)
    
    prefix = """SET AAA(CCCRRRAAA)  'All areas'
/\n"""
    create_sets(geo_nodes=geo_nodes['areas'], name=set_prefix+'AAA', prefix=prefix, suffix="\n/;", path=path)
    
    prefix = """* All sets that are related to Geographical resolution
SET CCCRRRAAA 'All geographical entities (CCC + RRR + AAA)'
/"""
    create_CCCRRRAAA(geo_nodes=geo_nodes, name=set_prefix+'CCCRRRAAA', prefix=prefix, suffix="\n/;", path=path)

    prefix="""SET CCCRRR(CCC,RRR) "Regions in countries"
/"""
    create_setconnection(geo_nodes=geo_nodes['countries'], name=set_prefix+'CCCRRR', prefix=prefix, suffix="\n/;", path=path)

    prefix="""SET RRRAAA(RRR,AAA) "Areas in regions"                                                                  
/"""
    create_setconnection(geo_nodes=geo_nodes['regions'], name=set_prefix+'RRRAAA', prefix=prefix, suffix="\n/;", path=path)

def interactive_geofilemaker():
    
    # Get working directory and package directory
    static_path = pkg_resources.resource_filename(__name__, 'static')
    index_path = pkg_resources.resource_filename(__name__, 'static/index.html')
    
    eel.init(static_path)
    eel.expose(get_wkdir)
    eel.expose(create_incfiles)
    eel.start(index_path)